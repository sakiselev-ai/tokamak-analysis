# Tokamak Analysis — ИИ-система для анализа экспериментальных данных токамаков

НИЯУ МИФИ | Версия 1.0 | 2026

## Описание

ML-платформа для анализа и оптимизации данных плазменных экспериментов.
Загрузка данных из FAIR-MAST (11 573 выстрела), визуализация временных рядов,
классификация стабильности плазмы и предсказание срывов.

Ключевые возможности:
- Загрузка экспериментальных данных из FAIR-MAST S3 (анонимный доступ)
- Препроцессинг и визуализация временных рядов (Plotly.js)
- Классификация стабильности плазмы (stable / unstable)
- Предсказание срывов (disruption prediction) с вероятностным окном предупреждения
- Обучение моделей через web-интерфейс с отслеживанием прогресса (Celery)
- JWT-аутентификация, RBAC (3 роли), аудит-лог всех действий

## Архитектура

- **Backend**: Python 3.11, FastAPI, SQLAlchemy async, Celery
- **ML Service**: PyTorch, scikit-learn (3 модели: RF, bi-LSTM+attention, Transformer)
- **Frontend**: React 18, TypeScript, Vite, Plotly.js
- **Инфраструктура**: PostgreSQL 16, Redis 7, MinIO, Docker Compose
- **Мониторинг**: Prometheus + Grafana (предварительно настроенные дашборды)
- **CI/CD**: GitHub Actions (lint, test, docker build)

Подробнее — [ARCHITECTURE.md](ARCHITECTURE.md).

## Быстрый старт

### Требования

- Docker + Docker Compose >= 2.0
- (для разработки) Python 3.11, Node.js 20

### Запуск

```bash
cp .env.example .env
docker compose up -d
```

| Сервис          | URL                          |
|-----------------|------------------------------|
| Frontend        | http://localhost              |
| API docs        | http://localhost/docs         |
| Grafana         | http://localhost:3001         |
| MinIO Console   | http://localhost:9001         |
| Prometheus      | http://localhost:9090         |

### Разработка (hot-reload)

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
# Frontend dev server также доступен на http://localhost:3000
```

## Структура проекта

```
tokamak-analysis/
├── backend/                   # FastAPI backend
│   ├── app/
│   │   ├── api/               # REST endpoints (auth, experiments, predictions, models, admin)
│   │   ├── core/              # Security, headers, audit, metrics, logging
│   │   ├── models/            # SQLAlchemy ORM models (user, experiment, prediction, ml_model, audit_log)
│   │   ├── schemas/           # Pydantic request/response schemas
│   │   ├── services/          # Business logic (fair_mast, ml_client, preprocessing)
│   │   ├── tasks/             # Celery tasks (training)
│   │   ├── config.py          # Pydantic Settings (env vars)
│   │   ├── database.py        # async engine + session
│   │   └── main.py            # FastAPI app, middleware, lifespan
│   ├── alembic/               # Database migrations
│   ├── tests/                 # pytest-asyncio tests
│   ├── Dockerfile
│   └── requirements.txt
├── ml_service/                # Отдельный ML-сервис
│   ├── service/
│   │   ├── data/              # Dataset, FAIR-MAST loader, preprocessing, metrics
│   │   ├── training/          # Trainer, model factory (RF, LSTM, Transformer)
│   │   ├── server.py          # FastAPI ML endpoints
│   │   └── metrics.py         # Prometheus ML metrics
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                  # React SPA
│   ├── src/
│   │   ├── api/               # HTTP client (axios)
│   │   ├── components/        # Layout, ShotLoader, TimeSeriesChart, PredictionPanel, Toast
│   │   ├── pages/             # LoginPage, DashboardPage, ExperimentPage, TrainingPage
│   │   ├── store/             # Zustand auth store
│   │   └── types/             # TypeScript interfaces
│   ├── Dockerfile
│   ├── nginx.conf             # Production static serving
│   └── vite.config.ts
├── configs/                   # ML model configs (YAML)
│   ├── rf.yml                 # Random Forest hyperparameters
│   ├── lstm.yml               # bi-LSTM+Attention hyperparameters
│   └── transformer.yml        # Transformer hyperparameters
├── monitoring/
│   ├── prometheus/            # prometheus.yml
│   └── grafana/               # Provisioned datasources + dashboards
├── nginx/                     # Reverse proxy config
│   └── nginx.conf
├── .github/workflows/ci.yml   # GitHub Actions CI pipeline
├── docker-compose.yml         # Production compose (11 сервисов)
├── docker-compose.dev.yml     # Dev overrides (hot-reload)
├── .env.example               # Шаблон переменных окружения
└── .gitignore
```

## API Endpoints

### Auth (`/api/v1/auth`)

| Метод  | Путь              | Описание                         | Auth |
|--------|--------------------|----------------------------------|------|
| POST   | `/register`        | Регистрация пользователя          | --   |
| POST   | `/login`           | Аутентификация, выдача JWT токенов| --   |
| POST   | `/refresh`         | Обновление access token           | --   |
| GET    | `/me`              | Текущий пользователь              | JWT  |

### Experiments (`/api/v1/experiments`)

| Метод  | Путь                             | Описание                              | Auth |
|--------|----------------------------------|---------------------------------------|------|
| POST   | `/load`                          | Загрузка выстрела из FAIR-MAST        | JWT  |
| GET    | `/`                              | Список экспериментов (pagination)     | JWT  |
| GET    | `/{experiment_id}`               | Детали эксперимента                   | JWT  |
| GET    | `/{experiment_id}/timeseries`    | Временные ряды эксперимента           | JWT  |
| GET    | `/{experiment_id}/export`        | Экспорт в CSV / JSON                  | JWT  |

### Predictions (`/api/v1/predictions`)

| Метод  | Путь           | Описание                                  | Auth |
|--------|----------------|-------------------------------------------|------|
| POST   | `/classify`    | Классификация стабильности плазмы          | JWT  |
| POST   | `/disruption`  | Предсказание срыва (временной ряд вероятностей) | JWT  |

### Models (`/api/v1/models`)

| Метод  | Путь                      | Описание                              | Auth |
|--------|---------------------------|---------------------------------------|------|
| POST   | `/train`                  | Запуск обучения модели (async, Celery) | JWT  |
| GET    | `/`                       | Список всех моделей                   | JWT  |
| GET    | `/{model_id}/versions`    | Версии конкретной модели              | JWT  |
| PUT    | `/{model_id}/activate`    | Активация версии модели (rollback)     | JWT  |
| GET    | `/runs`                   | Список запусков обучения               | JWT  |
| GET    | `/runs/{run_id}`          | Детали запуска                         | JWT  |
| GET    | `/runs/{run_id}/status`   | Статус обучения (polling Celery)       | JWT  |

### Admin (`/api/v1/admin`)

| Метод  | Путь                          | Описание                   | Auth  |
|--------|-------------------------------|----------------------------|-------|
| GET    | `/users`                      | Список пользователей       | ADMIN |
| PUT    | `/users/{user_id}/role`       | Изменение роли             | ADMIN |
| PUT    | `/users/{user_id}/deactivate` | Деактивация пользователя   | ADMIN |

### Health & Metrics

| Метод  | Путь               | Описание                        |
|--------|--------------------|---------------------------------|
| GET    | `/health`          | Простая проверка (ok)            |
| GET    | `/api/v1/health`   | Расширенная проверка (ML status) |
| GET    | `/metrics`         | Prometheus metrics (backend)     |

### ML Service (внутренний, порт 8001)

| Метод  | Путь                          | Описание                        |
|--------|-------------------------------|---------------------------------|
| GET    | `/health`                     | Healthcheck ML-сервиса           |
| GET    | `/metrics`                    | Prometheus metrics (ML)          |
| POST   | `/api/v1/predict/classify`    | Инференс классификации           |
| POST   | `/api/v1/predict/disruption`  | Инференс предсказания срыва      |
| POST   | `/api/v1/train`               | Запуск обучения модели            |

## ML Модели (ADR-004)

| Модель              | Тип           | Config               | Назначение                     | Латентность     |
|---------------------|---------------|-----------------------|--------------------------------|-----------------|
| Random Forest       | Baseline      | `configs/rf.yml`      | Классификация стабильности     | ≤5ms CPU        |
| bi-LSTM+Attention   | Основная      | `configs/lstm.yml`    | Классификация + предсказание срывов | ≤30ms GPU  |
| Transformer         | Экспериментальная | `configs/transformer.yml` | SOTA предсказание срывов  | ≤50ms GPU       |

Все модели реализуют единый `ModelInterface`:
- `fit(X_train, y_train, X_val, y_val)` — обучение
- `predict(X)` / `predict_proba(X)` — инференс
- `save(path)` / `load(path)` — сериализация
- `metadata()` — метаданные модели

## Тестирование

```bash
# Backend (pytest-asyncio + httpx + SQLite)
cd backend && pytest tests/ -v --cov=app

# ML Service (pytest + synthetic data)
cd ml_service && pytest tests/ -v --cov=service

# Frontend build check
cd frontend && npm run build
```

CI pipeline (GitHub Actions) автоматически запускает lint (ruff), тесты и docker build
при push в `main`/`develop` и при pull requests.

## Безопасность

- **Аутентификация**: JWT (access 15 мин + refresh 7 дней с ротацией)
- **Хеширование**: bcrypt (cost 12)
- **Авторизация**: RBAC — 3 роли: `researcher`, `engineer`, `admin`
- **Security headers**: HSTS, X-Content-Type-Options, X-Frame-Options, CSP
- **Rate limiting**: 100 запросов/мин на IP (slowapi)
- **Аудит**: все действия логируются в `audit_logs` (пользователь, IP, действие)
- **152-ФЗ compliance**: поля `consent_given_at`, `deleted_at` в модели User

## Переменные окружения

Скопируйте `.env.example` в `.env` и измените значения для production:

| Переменная              | Описание                          | Default                        |
|-------------------------|-----------------------------------|--------------------------------|
| `DATABASE_URL`          | PostgreSQL connection string      | `postgresql+asyncpg://...`     |
| `REDIS_URL`             | Redis URL                         | `redis://redis:6379/0`         |
| `JWT_SECRET_KEY`        | Секрет для подписи JWT            | changeme                       |
| `ML_SERVICE_URL`        | URL ML-сервиса                    | `http://ml-service:8001`       |
| `MINIO_ROOT_USER/PASSWORD` | Credentials для MinIO          | minioadmin / minioadmin123     |
| `FAIR_MAST_S3_ENDPOINT` | S3 endpoint для FAIR-MAST        | `https://s3.echo.stfc.ac.uk`  |

## Метрики успеха

| Метрика                  | Целевое значение |
|--------------------------|-----------------|
| Accuracy классификации   | ≥ 85%           |
| AUC-ROC срывов           | ≥ 0.90          |
| Инференс срывов          | ≤ 50 мс         |
| Покрытие тестами         | ≥ 80%           |

## Лицензия

MIT

## Авторы

НИЯУ МИФИ, 2026
