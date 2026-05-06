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
- **Infra**: Docker Compose (12 services, 4 networks), Nginx reverse proxy, MinIO (S3-compatible model storage)
- **Monitoring**: Prometheus + Grafana (2 dashboards) + Alertmanager (10 alerts) + Telegram bot
- **CI**: GitHub Actions — ruff lint, pytest, docker build, Playwright E2E
- **Docs**: User guide, deployment guide, API reference, ARCHITECTURE.md

## VPS Production Server

- **SSH**: `ssh root@186.246.31.81`
- **Project path**: `/opt/tokamak-analysis`
- **OS**: Ubuntu 24.04, x86_64, 48GB disk (24GB free)
- **Services**: 12 Docker containers running (all healthy)
- **Frontend**: http://186.246.31.81/
- **API docs**: http://186.246.31.81/docs
- **Grafana**: http://186.246.31.81:3001/
- **DB**: 5 users, 5 models, 3 experiments (shots 11700, 11750, 30420), 4+ predictions, 5 training runs (1 completed RF, 4 failed LSTM/Transformer)
- **Trained models on disk**: `rf_baseline.joblib`, `lstm_attention.pt`, `transformer.pt` + 7 checkpoints
- **Backups**: cron daily at 3:00 → pg_dump + encrypt + MinIO
- **Not a git repo on VPS** — sync via `rsync` or `scp`, then `docker compose build`
- **Admin login**: `admin@mephi.ru` / `admin123`

### Sync & deploy commands
```bash
# Sync local → VPS (excludes .git, node_modules, .env, data, models)
rsync -avz --exclude='.git' --exclude='node_modules' --exclude='__pycache__' \
    --exclude='.env' --exclude='test.db' --exclude='.claude' --exclude='data/' --exclude='models/' \
    . root@186.246.31.81:/opt/tokamak-analysis/

# Rebuild and restart specific services
ssh root@186.246.31.81 "cd /opt/tokamak-analysis && docker compose stop ml-service && docker compose build ml-service && docker compose up -d ml-service"

# Full deploy
./deploy/deploy.sh 186.246.31.81
```

## Key Commands

```bash
# Start all services
docker compose up -d

# Dev mode with hot-reload
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Production mode (log rotation, port restriction, restart: always)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Backend tests (pytest-asyncio + httpx + SQLite)
cd backend && pytest tests/ -v --cov=app

# ML service tests (pytest + synthetic data)
cd ml_service && pytest tests/ -v --cov=service

# E2E tests (Playwright, requires running docker compose)
cd e2e && npx playwright test

# Frontend dev server
cd frontend && npm run dev

# Lint
ruff check backend/
ruff check ml_service/

# Run DB migrations
cd backend && alembic upgrade head

# Run ML experiments on VPS (inside ml-service container)
docker exec tokamak-analysis-ml-service-1 python3 scripts/full_experiment.py --data data/fair_mast_500.npz --quick
docker exec tokamak-analysis-ml-service-1 python3 scripts/temporal_validation.py --data data/fair_mast_500.npz --quick
docker exec tokamak-analysis-ml-service-1 python3 scripts/generate_paper_tables.py --demo --both-langs
```

## Architecture

- Modular monolith backend + separate ML service (ADR-001)
- REST API between frontend-backend (port 80 via nginx) and backend-ML service (port 8001, internal network)
- Celery worker for async model training (Redis as broker)
- 4 Docker networks:
  - `frontend` — nginx, frontend, backend (public-facing)
  - `backend` — backend, ml-service, celery-worker, redis, minio (internal, no external access)
  - `db` — backend, celery-worker, postgres (isolated)
  - `monitoring` — prometheus, grafana, alertmanager, telegram-bot, backend, ml-service

## Code Layout

```
backend/app/
├── api/           # FastAPI routers: auth, experiments, predictions, models, admin, legal
├── core/          # security.py (JWT, bcrypt, RBAC), headers.py, audit.py, metrics.py, logging_config.py
├── models/        # SQLAlchemy ORM: User, Experiment, TimeSeriesData, Prediction, MLModel, ModelRun, AuditLog, UserSettings
├── schemas/       # Pydantic: auth.py, experiment.py, prediction.py
├── services/      # fair_mast.py (S3 loader), ml_client.py (httpx to ML service), preprocessing.py, recommendations.py
├── tasks/         # training.py (Celery task), db_sync.py (sync session for Celery)
├── config.py      # Pydantic Settings (all env vars)
├── database.py    # async engine, get_db dependency
└── main.py        # app factory, middleware stack, router registration, /api/docs redirect

ml_service/service/
├── data/          # dataset.py, fair_mast_loader.py (load_shots, load_disruption_labels, make_disruption_labels), preprocessing.py (sliding_window_labels), metrics.py
├── models/        # interface.py (ModelInterface ABC), random_forest.py, lstm_attention.py, transformer.py
├── training/      # trainer.py — model factory (create_model, load_model)
├── server.py      # FastAPI app with /predict/classify, /predict/disruption, /train
└── metrics.py     # Prometheus counters for ML inference/training

ml_service/scripts/
├── download_fair_mast.py    # Download shots from FAIR-MAST S3 archive
├── temporal_validation.py   # Train-early/test-late vs random split comparison
├── full_experiment.py       # 3/5-fold CV + latency benchmark for all models
├── generate_paper_tables.py # LaTeX tables (RU/EN) for preprint
├── benchmark_models.py      # Model inference benchmarks
├── retrain_models.py        # Retrain all 3 models with n_features=10, save to models/
├── warmup_models.py         # Verify model loading (container startup check)
└── train_*.py               # Individual model training scripts

frontend/src/
├── api/client.ts              # Axios instance with JWT interceptor
├── components/                # Layout, ShotLoader, TimeSeriesChart, PredictionPanel, DisruptionChart, ExportButton, Toast, HyperparamForm, RecommendationPanel
├── pages/                     # LoginPage, DashboardPage (model comparison), ExperimentPage, TrainingPage, BatchPage, SettingsPage
├── store/authStore.ts         # Zustand store (login, logout, token refresh)
└── types/index.ts             # TypeScript interfaces (Experiment, TimeSeries, ModelRun, MLModel, DisruptionResult, etc.)

docs/
├── user-guide.md              # Full user guide (Russian)
├── deployment-guide.md        # VPS setup, SSL, backups (Russian)
└── api-reference.md           # All 30 endpoints with examples

monitoring/
├── prometheus/alerts.yml      # 10 alerts: APIDown, MLServiceDown, HighLatency, HighErrorRate, DiskSpace, PostgresDown, LongTraining, AccuracyDrift, HighMemory, CeleryBacklog
├── grafana/dashboards/        # tokamak.json (request metrics), ml-metrics.json (inference/training/accuracy)
├── grafana/provisioning/      # Prometheus datasource + dashboard provider
├── alertmanager/              # Alertmanager config → telegram-bot webhook
└── telegram-bot/bot.py        # Alertmanager webhook → Telegram (Russian alerts)

deploy/
├── deploy.sh                  # Full deploy: rsync + SSL + docker compose
├── setup_ssl.sh               # Let's Encrypt SSL setup
├── setup_backups.sh           # Cron setup for daily backups
└── backup.sh                  # pg_dump + encrypt + MinIO upload + retention (7 daily, 4 weekly)

e2e/tests/                     # 6 Playwright specs: auth, experiments, export, predictions, training + helpers
paper/                         # preprint.tex + references.bib (25 citations) + preprint.pdf (10 pages)
rospatent/                     # referat.md, application_form.md, deposited_code.py, deposited_listing.txt, README_FINAL.md
presentation/                  # slides.md, demo_script.md, index.html (13-slide standalone HTML)
configs/                       # rf.yml, lstm.yml, transformer.yml (hyperparams + grid search)
```

## FAIR-MAST Data

- **S3 endpoint**: `https://s3.echo.stfc.ac.uk`, bucket `mast`, anonymous access
- **Structure**: `mast/level1/shots/{shot_id}.zarr` (NOT `mast/shots/` or `mast/{id}`)
- **Also available**: `mast/level2/`, `mast/dev/`, `mast/test/`, `mast/tokamark/`
- **Shot IDs in cache**: 11695–12445 range (early MAST campaigns)
- **VPS cache**: `/opt/tokamak-analysis/ml_service/data/shot_cache/` — 567 shots as `.pkl` tuples `(features_ndarray, label_int)`
- **Dataset**: `data/fair_mast_500.npz` — 500 shots × 200 timesteps × 20 features, 86.8% disruptions
- **Labels**: Heuristic-based via plasma current drop (not `cpf/disruption_time` — most early MAST shots lack this field)
- `load_shots()` returns `(data_list, loaded_ids)` tuple — important for correct label alignment

## Experiment Results (real data, VPS, 2026-05-06)

### Cross-validation (3-fold, --quick mode)

| Model | CV Accuracy | CV AUC-ROC | Test Acc | Test AUC | P99 Latency |
|-------|-------------|------------|----------|----------|-------------|
| Random Forest | 98.4% ± 0.8% | 0.983 ± 0.012 | 100% | 1.000 | 73 ms |
| bi-LSTM+Attention | 78.4% ± 0.9% | 0.867 ± 0.013 | 80% | 0.944 | 39 ms |
| Transformer | 87.8% ± 1.0% | 0.938 ± 0.034 | 100% | 1.000 | 131 ms |

### Temporal validation (train shots < 12035, test shots >= 12035)

| Model | Random AUC | Temporal AUC | Delta |
|-------|-----------|-------------|-------|
| Random Forest | 1.000 | 0.969 | -3.1% |
| bi-LSTM+Attention | 0.941 | 0.671 | -27.0% |
| Transformer | 1.000 | 0.892 | -10.8% |

**Key findings:**
- Random split gives inflated metrics (1.0 for RF/Transformer) — temporal validation is essential
- RF most robust to temporal shift (AUC 0.969 temporal)
- LSTM underperforms in quick mode (5 epochs) — needs full training (50 epochs)
- Strong class imbalance (86.8% disruptions) may inflate RF metrics
- Results saved: `results/full_experiment.json`, `results/temporal_validation.json` on VPS

## Project Metrics

- **25 commits** on main branch, pushed to GitHub
- **195+ files**, **~22,500 LOC total**
- **90+ Python files** (~10,500 LOC), **29 TypeScript files** (~3,100 LOC)
- **Infrastructure**: ~1,100 LOC (YAML/JSON/conf)
- **Documentation**: ~7,400 LOC (MD/TeX/bib/HTML)
- **30 API endpoints**, **10 ORM models**, **3 ML models**
- **170 tests** (139 backend + 31 ML + 21 E2E), **backend coverage 81%** (NFR-011 ✅)
- **12 Docker services**, **4 networks**, **3 Alembic migrations**
- **10 Prometheus alerts**, **2 Grafana dashboards**
- **All 17 functional requirements (FR-001–FR-017) covered**
- **End-to-end predict flow verified**: load shot → classify → disruption prediction

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

- **Backend**: pytest-asyncio + httpx `AsyncClient` + SQLite in-memory (**139 tests, 81% coverage**)
  - `test_auth.py` (13), `test_experiments.py` (15), `test_predictions.py` (21), `test_models_api.py` (17)
  - `test_admin.py` (9), `test_security.py` (12), `test_health.py` (2), `test_preprocessing.py` (4)
  - `test_fair_mast.py` (9), `test_minio_client.py` (7), `test_ml_client.py` (5)
  - `test_recommendations.py` (10), `test_training.py` (8)
- **ML Service**: pytest with synthetic data generation + mocked S3 (31 tests)
- **E2E**: Playwright — auth, experiments, export, predictions, training (21 tests)
- **CI**: GitHub Actions — lint + test + build + E2E (with docker compose)
- **Fixtures**: `conftest.py` provides `client`, `auth_client`, `admin_client` fixtures

## TokaMark Benchmark

- **Paper**: arXiv:2602.10132 (Feb 2026), KDD 2026
- **14 tasks** in 4 groups: equilibrium, magnetics, profiles, MHD/disruptions
- **Metric**: NRMSE (regression), not AUC (classification)
- **Data**: HuggingFace `UKAEA-IBM-STFC/tokamark-dataset` (~388 GB)
- **Code**: `github.com/UKAEA-IBM-STFC-Fusion-FMs/tokamark`
- **Relevant tasks**: Group 4 (4-1 to 4-5) — thermal quench, vertical displacement, current quench, locked modes
- **No formal leaderboard yet** — self-evaluation against published baselines
- **Strategy**: Adapt our models to TokaMark task format (time-series forecasting, not binary classification)

## API Routes Summary

### Auth (`/api/v1/auth`)
- `POST /register` — create user (requires 152-ФЗ consent)
- `POST /login` — get JWT tokens
- `POST /refresh` — refresh access token
- `GET  /me` — current user profile
- `DELETE /account` — full data deletion (152-ФЗ)

### Experiments (`/api/v1/experiments`)
- `POST /load` — load shot from FAIR-MAST
- `POST /batch` — batch load multiple shots
- `GET  /` — list user experiments
- `GET  /{id}` — experiment details
- `GET  /{id}/timeseries` — time series data
- `GET  /{id}/export` — export CSV/JSON

### Predictions (`/api/v1/predictions`)
- `POST /classify` — plasma stability classification
- `POST /disruption` — disruption prediction
- `POST /batch-classify` — batch classification
- `POST /batch-disruption` — batch disruption prediction
- `GET  /threshold` — get user threshold
- `PUT  /threshold` — update user threshold

### Models (`/api/v1/models`)
- `POST /train` — start training (async Celery)
- `GET  /` — list models
- `GET  /{id}/versions` — model versions
- `PUT  /{id}/activate` — activate model version
- `GET  /runs` — list training runs
- `GET  /runs/{id}` — run details
- `GET  /runs/{id}/status` — training progress (Celery poll)

### Admin (`/api/v1/admin`)
- `GET  /users` — list users (admin only)
- `PUT  /users/{id}/role` — change user role
- `PUT  /users/{id}/deactivate` — deactivate user

### Other
- `GET  /health` — simple healthcheck
- `GET  /api/v1/health` — extended healthcheck (ML service status)
- `GET  /api/v1/legal/privacy-policy` — 152-ФЗ privacy policy
- `GET  /api/v1/legal/terms` — terms of service
- `GET  /api/docs` — redirect to Swagger UI

## Important Notes

- FAIR-MAST S3 path: `mast/level1/shots/{shot_id}.zarr` (NOT `mast/shots/` or `mast/{id}`)
- `load_shots()` returns `(data_list, loaded_ids)` — tracks which shots loaded successfully
- ML models implement unified `ModelInterface` (fit/predict/predict_proba/save/load/metadata)
- Config files in `/configs/{rf,lstm,transformer}.yml` — hyperparameters + grid search spaces
- Model artifacts stored in MinIO (buckets: `models`, `data`)
- bcrypt cost = 12, JWT algorithm = HS256
- User roles: `researcher`, `engineer`, `admin` (enum in `UserRole`)
- Rate limiting: 100 req/min per IP via slowapi
- Security headers middleware adds HSTS, X-Content-Type-Options, X-Frame-Options, CSP
- Audit log captures user actions with IP address
- `consent_given_at` and `deleted_at` fields on User model for 152-FZ compliance
- `sliding_window_labels()` implements 30ms warning window (FR-005)
- Temporal validation script auto-computes median split point when `--split-point=0`
- `PredictRequest.model_path` is optional — ML service falls back to default models or trains on-the-fly
- `prepare_features` defaults to `max_features=10` to match trained models on VPS
- Trained models on VPS expect 10 features; dataset has 20 features (padded from varied shapes)
- Predict endpoints flatten features to 2D for RF (`features.reshape(n, -1)`) — RF needs flat input, neural models need 3D
- Train endpoint defaults `input_size=10` and injects it into LSTM/Transformer hyperparams before model creation
- `retrain_models.py` retrains all 3 models with consistent n_features=10, saves to `models/`
- After `docker compose build`, run `retrain_models.py` inside container (COPY bakes in old host models)
- **Actual ML inference: ~19ms** — the 6s total latency is `prepare_features` interpolating 229 raw signals, not the model
- Experiment list endpoint uses `noload(Experiment.timeseries)` — timeseries loaded separately via `/{id}/timeseries`
- **23 commits**, **~21,000 LOC**, dashboard fully functional with 7 experiments
- **GitHub**: https://github.com/sakiselev-ai/tokamak-analysis (public, MIT)
- **Always push after commit** — every git commit must be followed by git push

## Known Limitations

- **Data preprocessing ~6s per shot**: `prepare_features` interpolates up to 229 signals from FAIR-MAST. Optimization: pre-cache features or limit signal count in backend
- **LSTM quick-mode AUC 0.867**: Needs full training (50 epochs) for production-quality results
- **RF/Transformer P99 > 50ms target**: Need model optimization or reduced n_estimators/sequence_length
- **Class imbalance 86.8%**: Heuristic labels skew disruption-heavy; real `cpf/disruption_time` labels preferred
- **SSL not configured**: Needs domain name for Let's Encrypt

## Completed Artifacts

| Artifact | Path | Status |
|----------|------|--------|
| Preprint PDF | `paper/preprint.pdf` | 10 pages, real metrics, 25 citations |
| Presentation | `presentation/index.html` | 13 slides, standalone HTML, printable |
| Rospatent listing | `rospatent/deposited_listing.txt` | 1666 lines, 10 source files |
| Rospatent instructions | `rospatent/README_FINAL.md` | FIPS submission checklist |
| User guide | `docs/user-guide.md` | Full guide in Russian |
| Deployment guide | `docs/deployment-guide.md` | VPS setup, SSL, backups |
| API reference | `docs/api-reference.md` | 30 endpoints with examples |
| Grafana dashboards | `monitoring/grafana/dashboards/` | 2 dashboards pre-provisioned |
| Backup cron | VPS crontab | Daily 3:00 AM, 7 daily + 4 weekly |
