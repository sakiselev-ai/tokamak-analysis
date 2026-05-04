# CLAUDE.md

## Project Overview

Tokamak plasma analysis platform — ML system for analyzing experimental data from fusion reactors.
Built for НИЯУ МИФИ (National Research Nuclear University MEPhI).

The platform loads shot data from FAIR-MAST (UK tokamak archive, 11,573 shots),
preprocesses time series, and runs ML models for plasma stability classification
and disruption prediction.

## Tech Stack

- **Backend**: FastAPI + SQLAlchemy async (Mapped[] ORM) + PostgreSQL 16 + Redis 7 + Celery
- **ML Service**: PyTorch (LSTM, Transformer) + scikit-learn (Random Forest) — separate FastAPI app on port 8001
- **Frontend**: React 18 + TypeScript + Vite + Plotly.js + Zustand (auth state)
- **Infra**: Docker Compose (11 services, 4 networks), Nginx reverse proxy, MinIO (S3-compatible model storage)
- **Monitoring**: Prometheus + Grafana (pre-provisioned dashboards)
- **CI**: GitHub Actions — ruff lint, pytest, docker build

## Key Commands

```bash
# Start all services
docker compose up -d

# Dev mode with hot-reload
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Backend tests (pytest-asyncio + httpx + SQLite)
cd backend && pytest tests/ -v --cov=app

# ML service tests (pytest + synthetic data)
cd ml_service && pytest tests/ -v --cov=service

# Frontend dev server
cd frontend && npm run dev

# Lint
ruff check backend/
ruff check ml_service/

# Run DB migrations
cd backend && alembic upgrade head
```

## Architecture

- Modular monolith backend + separate ML service (ADR-001)
- REST API between frontend-backend (port 80 via nginx) and backend-ML service (port 8001, internal network)
- Celery worker for async model training (Redis as broker)
- 4 Docker networks:
  - `frontend` — nginx, frontend, backend (public-facing)
  - `backend` — backend, ml-service, celery-worker, redis, minio (internal, no external access)
  - `db` — backend, celery-worker, postgres (isolated)
  - `monitoring` — prometheus, grafana, backend, ml-service

## Code Layout

```
backend/app/
├── api/           # FastAPI routers: auth, experiments, predictions, models, admin
├── core/          # security.py (JWT, bcrypt, RBAC), headers.py, audit.py, metrics.py, logging_config.py
├── models/        # SQLAlchemy ORM: User, Experiment, TimeSeriesData, Prediction, MLModel, ModelRun, AuditLog
├── schemas/       # Pydantic: auth.py, experiment.py, prediction.py
├── services/      # fair_mast.py (S3 loader), ml_client.py (httpx to ML service), preprocessing.py
├── tasks/         # training.py (Celery task)
├── config.py      # Pydantic Settings (all env vars)
├── database.py    # async engine, get_db dependency
└── main.py        # app factory, middleware stack, router registration

ml_service/service/
├── data/          # dataset.py, fair_mast_loader.py, preprocessing.py, metrics.py
├── training/      # trainer.py — model factory, ModelInterface protocol
├── server.py      # FastAPI app with /predict/classify, /predict/disruption, /train
└── metrics.py     # Prometheus counters for ML inference/training

frontend/src/
├── api/client.ts       # Axios instance with JWT interceptor
├── components/         # Layout, ShotLoader, TimeSeriesChart, PredictionPanel, Toast
├── pages/              # LoginPage, DashboardPage, ExperimentPage, TrainingPage
├── store/authStore.ts  # Zustand store (login, logout, token refresh)
└── types/index.ts      # TypeScript interfaces
```

## Code Conventions

- All Python files start with `from __future__ import annotations`
- Use `Optional[X]` in SQLAlchemy `Mapped[]` fields (Python 3.9 compat)
- Pydantic schemas in `backend/app/schemas/`, models in `backend/app/models/`
- API routers in `backend/app/api/`, all prefixed with `/api/v1/`
- ML models implement `ModelInterface` protocol: fit, predict, predict_proba, save, load, metadata
- Config via `pydantic_settings.BaseSettings` — all from env vars, `.env` file
- Structured logging with `structlog`
- Type hints everywhere; ruff for linting

## Testing

- **Backend**: pytest-asyncio + httpx `AsyncClient` + SQLite in-memory for tests
- **ML Service**: pytest with synthetic data generation (`get_sample_dataset`)
- **Fixtures**: `conftest.py` provides `client` (unauthenticated) and `auth_client` (JWT-authenticated) fixtures
- Tests cover: auth flow, experiments CRUD, predictions, model training API, admin endpoints, security headers, preprocessing

## API Routes Summary

- `POST /api/v1/auth/register` — create user
- `POST /api/v1/auth/login` — get JWT tokens
- `POST /api/v1/auth/refresh` — refresh access token
- `GET  /api/v1/auth/me` — current user profile
- `POST /api/v1/experiments/load` — load shot from FAIR-MAST
- `GET  /api/v1/experiments/` — list user experiments
- `GET  /api/v1/experiments/{id}` — experiment details
- `GET  /api/v1/experiments/{id}/timeseries` — time series data
- `GET  /api/v1/experiments/{id}/export` — export CSV/JSON
- `POST /api/v1/predictions/classify` — plasma stability classification
- `POST /api/v1/predictions/disruption` — disruption prediction
- `POST /api/v1/models/train` — start training (async Celery)
- `GET  /api/v1/models/` — list models
- `GET  /api/v1/models/{id}/versions` — model versions
- `PUT  /api/v1/models/{id}/activate` — activate model version
- `GET  /api/v1/models/runs` — list training runs
- `GET  /api/v1/models/runs/{id}` — run details
- `GET  /api/v1/models/runs/{id}/status` — training progress (Celery poll)
- `GET  /api/v1/admin/users` — list users (admin only)
- `PUT  /api/v1/admin/users/{id}/role` — change user role (admin only)
- `PUT  /api/v1/admin/users/{id}/deactivate` — deactivate user (admin only)
- `GET  /health` — simple healthcheck
- `GET  /api/v1/health` — extended healthcheck (ML service status)

## Important Notes

- FAIR-MAST data: S3 at `https://s3.echo.stfc.ac.uk`, bucket `mast`, anonymous access (no credentials needed)
- ML models implement unified `ModelInterface` (fit/predict/predict_proba/save/load/metadata)
- Config files in `/configs/{rf,lstm,transformer}.yml` — hyperparameters + grid search spaces
- Model artifacts stored in MinIO (buckets: `models`, `data`)
- bcrypt cost = 12, JWT algorithm = HS256
- User roles: `researcher`, `engineer`, `admin` (enum in `UserRole`)
- Rate limiting: 100 req/min per IP via slowapi
- Security headers middleware adds HSTS, X-Content-Type-Options, X-Frame-Options, CSP
- Audit log captures user actions with IP address
- `consent_given_at` and `deleted_at` fields on User model for 152-FZ compliance
