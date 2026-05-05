from __future__ import annotations

import time
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.api import admin, auth, experiments, legal, models, predictions
from app.config import settings
from app.core.headers import SecurityHeadersMiddleware
from app.core.logging_config import setup_logging
from app.core.metrics import instrumentator
from app.services.ml_client import MLServiceClient

logger = structlog.get_logger()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log method, path, status code and duration for every request."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        await logger.ainfo(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
        )
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    from app.database import engine
    yield
    # Shutdown
    await engine.dispose()


limiter = Limiter(key_func=get_remote_address, default_limits=[f"{settings.rate_limit_per_minute}/minute"])

app = FastAPI(
    title="Tokamak Analysis API",
    description="ИИ-система для анализа экспериментальных данных токамаков",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )


# Middleware (order matters: outermost middleware is added last)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# CORS
origins = [o.strip() for o in settings.backend_cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(experiments.router)
app.include_router(predictions.router)
app.include_router(models.router)
app.include_router(admin.router)
app.include_router(legal.router)

# Prometheus metrics
instrumentator.instrument(app).expose(app)


@app.get("/api/v1/health")
async def health():
    ml_client = MLServiceClient()
    ml_status = await ml_client.health()
    return {
        "status": "healthy",
        "version": "1.0.0",
        "ml_service": "connected" if ml_status else "unavailable",
    }


@app.get("/api/docs")
async def api_docs_redirect():
    return RedirectResponse(url="/docs")


@app.get("/health")
async def health_simple():
    return {"status": "ok"}
