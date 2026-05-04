from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api import admin, auth, experiments, models, predictions
from app.config import settings
from app.services.ml_client import MLServiceClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
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


@app.get("/api/v1/health")
async def health():
    ml_client = MLServiceClient()
    ml_status = await ml_client.health()
    return {
        "status": "healthy",
        "version": "1.0.0",
        "ml_service": "connected" if ml_status else "unavailable",
    }


@app.get("/health")
async def health_simple():
    return {"status": "ok"}
