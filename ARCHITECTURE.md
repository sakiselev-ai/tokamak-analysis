# Архитектура / Architecture

## System Context (C4 Level 1)

```
┌──────────────┐       HTTPS        ┌──────────────────────────────────────┐
│  Researcher  │ ──────────────────> │       Tokamak Analysis Platform      │
│  / Engineer  │ <────────────────── │  (анализ данных плазменных           │
│  / Admin     │    JWT auth         │   экспериментов)                     │
└──────────────┘                     └────────────┬───────────────────────┬─┘
                                                  │                       │
                                                  │ S3 (anonymous)        │ S3 (MinIO)
                                                  ▼                       ▼
                                     ┌────────────────────┐   ┌──────────────────┐
                                     │    FAIR-MAST        │   │   MinIO           │
                                     │ (s3.echo.stfc.ac.uk)│   │ (model artifacts) │
                                     │  11 573 выстрела    │   │                   │
                                     └────────────────────┘   └──────────────────┘
```

Пользователи (3 роли: researcher, engineer, admin) работают через web-интерфейс.
Платформа загружает экспериментальные данные из архива FAIR-MAST и хранит
обученные модели в MinIO.

## Container Diagram (C4 Level 2)

```
                          ┌─── frontend network (public) ───────────────────┐
                          │                                                  │
  Browser ───── :80 ─────>│  ┌─────────┐     ┌───────────┐    ┌──────────┐  │
                          │  │  Nginx   │────>│  Frontend  │    │ Backend  │  │
                          │  │ (reverse │────>│  React 18  │    │ FastAPI  │  │
                          │  │  proxy)  │     │  Vite      │    │ :8000    │  │
                          │  └─────────┘     └───────────┘    └────┬─────┘  │
                          │                                        │        │
                          └────────────────────────────────────────┼────────┘
                                                                   │
                     ┌─── backend network (internal) ──────────────┼────────┐
                     │                                             │        │
                     │  ┌──────────────┐   ┌────────────┐   ┌─────┴─────┐  │
                     │  │  ML Service   │   │   Redis 7   │   │  Backend  │  │
                     │  │  FastAPI      │   │  (broker +   │   │          │  │
                     │  │  :8001        │   │   cache)     │   │          │  │
                     │  └──────────────┘   └────────────┘   └─────┬─────┘  │
                     │                                            │        │
                     │  ┌──────────────┐   ┌────────────────┐     │        │
                     │  │  MinIO        │   │ Celery Worker  │─────┘        │
                     │  │  (S3 storage) │   │ (async train)  │             │
                     │  │  :9000/:9001  │   └────────────────┘             │
                     │  └──────────────┘                                   │
                     └─────────────────────────────────────────────────────┘
                                                                   │
                     ┌─── db network (isolated) ───────────────────┼────────┐
                     │                                             │        │
                     │  ┌────────────────┐                   ┌─────┴─────┐  │
                     │  │ PostgreSQL 16   │<──────────────────│  Backend  │  │
                     │  │ (tokamak_db)   │                   │ + Celery  │  │
                     │  └────────────────┘                   └───────────┘  │
                     └─────────────────────────────────────────────────────┘

                     ┌─── monitoring network ──────────────────────────────┐
                     │                                                      │
                     │  ┌──────────────┐   ┌────────────┐                   │
                     │  │  Prometheus   │──>│  Grafana    │                  │
                     │  │  :9090        │   │  :3001      │                  │
                     │  └──────┬───────┘   └────────────┘                   │
                     │         │ scrape /metrics                            │
                     │         ├── Backend                                   │
                     │         └── ML Service                               │
                     └──────────────────────────────────────────────────────┘
```

## Сервисы (Docker Compose)

| Сервис          | Image / Build       | Порт(ы)     | Сеть(и)                          | Ресурсы        |
|-----------------|---------------------|-------------|----------------------------------|----------------|
| nginx           | nginx:1.25-alpine   | 80:80       | frontend                         | 0.5 CPU, 256M  |
| frontend        | ./frontend          | (internal)  | frontend                         | 0.5 CPU, 256M  |
| backend         | ./backend           | (internal)  | frontend, backend, db, monitoring| 2 CPU, 2G      |
| ml-service      | ./ml_service        | (internal)  | backend, monitoring              | 4 CPU, 8G      |
| celery-worker   | ./backend           | --          | backend, db                      | 2 CPU, 4G      |
| postgres         | postgres:16-alpine  | (internal)  | db                               | 2 CPU, 4G      |
| redis           | redis:7-alpine      | (internal)  | backend                          | 1 CPU, 1G      |
| minio           | minio/minio         | 9001:9001   | backend                          | 1 CPU, 1G      |
| minio-init      | minio/mc            | --          | backend                          | one-shot       |
| prometheus      | prom/prometheus      | 9090:9090   | monitoring, backend              | 0.5 CPU, 512M  |
| grafana         | grafana/grafana      | 3001:3000   | monitoring                       | 0.5 CPU, 512M  |

## Data Flow

### 1. Загрузка эксперимента

```
Browser                     Nginx       Backend                FAIR-MAST S3        PostgreSQL
  │                           │            │                        │                  │
  │  POST /api/v1/experiments/load         │                        │                  │
  │──────────────────────────>│───────────>│                        │                  │
  │                           │            │  GET shot signals      │                  │
  │                           │            │───────────────────────>│                  │
  │                           │            │<──────────────────────│                  │
  │                           │            │  preprocess_timeseries │                  │
  │                           │            │  (normalize, resample) │                  │
  │                           │            │                        │                  │
  │                           │            │  INSERT experiment +   │                  │
  │                           │            │  timeseries + audit_log│                  │
  │                           │            │───────────────────────────────────────────>│
  │                           │            │<─────────────────────────────────────────│
  │  201 ExperimentResponse   │            │                        │                  │
  │<──────────────────────────│<───────────│                        │                  │
```

### 2. Классификация стабильности плазмы

```
Browser          Nginx       Backend                ML Service         PostgreSQL
  │                │            │                        │                  │
  │  POST /api/v1/predictions/classify                   │                  │
  │───────────────>│───────────>│                        │                  │
  │                │            │  SELECT experiment +   │                  │
  │                │            │  timeseries            │                  │
  │                │            │───────────────────────────────────────────>│
  │                │            │<─────────────────────────────────────────│
  │                │            │                        │                  │
  │                │            │  POST /predict/classify│                  │
  │                │            │───────────────────────>│                  │
  │                │            │  {label, confidence}   │                  │
  │                │            │<──────────────────────│                  │
  │                │            │                        │                  │
  │                │            │  INSERT prediction     │                  │
  │                │            │───────────────────────────────────────────>│
  │  ClassifyResponse           │                        │                  │
  │<───────────────│<───────────│                        │                  │
```

### 3. Обучение модели (async)

```
Browser      Nginx     Backend       Celery Worker     ML Service     Redis    MinIO
  │            │          │               │                │            │        │
  │  POST /models/train   │               │                │            │        │
  │───────────>│─────────>│               │                │            │        │
  │            │          │  Enqueue task │                │            │        │
  │            │          │──────────────────────────────────────────-->│        │
  │  202 {run_id, task_id}│               │                │            │        │
  │<───────────│<─────────│               │                │            │        │
  │            │          │               │  Dequeue task  │            │        │
  │            │          │               │<───────────────────────────│        │
  │            │          │               │                │            │        │
  │            │          │               │  POST /train   │            │        │
  │            │          │               │───────────────>│            │        │
  │            │          │               │  {metrics}     │            │        │
  │            │          │               │<──────────────│            │        │
  │            │          │               │                │            │        │
  │            │          │               │  Upload model artifact     │        │
  │            │          │               │────────────────────────────────────>│
  │            │          │               │                │            │        │
  │  GET /runs/{id}/status│               │                │            │        │
  │───────────>│─────────>│  Poll Celery  │                │            │        │
  │            │          │──────────────────────────────────────────-->│        │
  │  {progress, metrics}  │               │                │            │        │
  │<───────────│<─────────│               │                │            │        │
```

## Сетевая топология (Docker Networks)

```
                    INTERNET
                       │
                       ▼
               ┌───────────────┐
               │   Port 80     │
               │   (Nginx)     │
               └───────┬───────┘
                       │
          ┌────────────┼────────────────────────────────┐
          │  frontend  │ (bridge, public)                │
          │            │                                 │
          │   ┌────────┴───────┐    ┌──────────────┐     │
          │   │   Frontend     │    │   Backend     │     │
          │   │   :3000        │    │   :8000       │     │
          │   └────────────────┘    └───────┬───────┘     │
          └─────────────────────────────────┼─────────────┘
                                            │
          ┌─────────────────────────────────┼─────────────┐
          │  backend (bridge, internal)     │              │
          │                                 │              │
          │  ┌──────────┐  ┌─────────┐  ┌──┴────────┐    │
          │  │ML Service│  │  Redis  │  │  Backend  │    │
          │  │  :8001   │  │  :6379  │  │           │    │
          │  └──────────┘  └─────────┘  └──┬────────┘    │
          │  ┌──────────┐  ┌──────────────┐│             │
          │  │  MinIO   │  │Celery Worker ││             │
          │  │:9000/9001│  │              │┘             │
          │  └──────────┘  └──────┬───────┘              │
          └───────────────────────┼───────────────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          │  db (bridge, isolated)│                        │
          │                      │                        │
          │  ┌──────────────┐  ┌─┴──────────┐             │
          │  │ PostgreSQL 16│  │  Backend    │             │
          │  │  :5432       │  │ + Celery    │             │
          │  └──────────────┘  └────────────┘             │
          └───────────────────────────────────────────────┘
```

**Ключевые решения по сетевой изоляции:**
- `backend` и `db` — `internal: true` (недоступны извне Docker)
- Frontend общается с backend только через nginx reverse proxy
- ML Service недоступен напрямую из frontend-сети
- PostgreSQL изолирован в отдельной сети, доступен только backend и celery-worker

## Middleware Stack (Backend)

Порядок обработки запроса (снаружи внутрь):

1. **CORS** — `CORSMiddleware` (origins из env)
2. **Security Headers** — HSTS, X-Content-Type-Options, X-Frame-Options, CSP
3. **Request Logging** — structlog (method, path, status, duration_ms)
4. **Rate Limiting** — slowapi (100 req/min per IP)
5. **Prometheus** — prometheus-fastapi-instrumentator
6. **Router** — FastAPI endpoint handler

## Модель данных (Entity Relationship)

```
┌──────────────┐     ┌──────────────────┐     ┌─────────────────┐
│    User      │     │   Experiment     │     │ TimeSeriesData   │
├──────────────┤     ├──────────────────┤     ├─────────────────┤
│ id           │──1:N│ id               │──1:N│ id               │
│ email        │     │ shot_id          │     │ experiment_id    │
│ password_hash│     │ source           │     │ parameter_name   │
│ full_name    │     │ status           │     │ timestamps[]     │
│ role         │     │ metadata_json    │     │ values[]         │
│ is_active    │     │ user_id (FK)     │     │ units            │
│ consent_at   │     │ loaded_at        │     │ description      │
│ deleted_at   │     └──────┬───────────┘     └─────────────────┘
└──────┬───────┘            │
       │                    │ 1:N
       │              ┌─────┴──────────┐     ┌──────────────────┐
       │              │  Prediction    │     │    MLModel       │
       │              ├────────────────┤     ├──────────────────┤
       │              │ id             │  N:1│ id               │
       │              │ experiment_id  │─────│ name             │
       │              │ model_id (FK)  │     │ model_type       │
       │              │ result_json    │     │ task             │
       │              │ probability    │     │ version          │
       │              │ created_at     │     │ s3_path          │
       │              └────────────────┘     │ metrics_json     │
       │                                     │ is_active        │
       │ 1:N                                 └────────┬─────────┘
       │          ┌──────────────────┐                │ 1:N
       │          │   AuditLog       │         ┌──────┴──────────┐
       │          ├──────────────────┤         │   ModelRun      │
       └──────────│ id               │         ├─────────────────┤
                  │ user_id (FK)     │         │ id              │
                  │ action           │         │ model_id (FK)   │
                  │ resource_type    │         │ user_id (FK)    │
                  │ details_json     │         │ status          │
                  │ ip_address       │         │ celery_task_id  │
                  │ created_at       │         │ hyperparams_json│
                  └──────────────────┘         │ metrics_json    │
                                               │ progress        │
                                               └─────────────────┘
```

## Варианты деплоя

### 1. Локальная разработка (Docker Compose)

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```
- Hot-reload для backend, ML service и frontend
- Frontend dev server на :3000
- SQLite для тестов (pytest)

### 2. Production (Docker Compose)

```bash
cp .env.example .env   # настроить production credentials
docker compose up -d
```
- Все сервисы за nginx reverse proxy
- Resource limits настроены в compose
- Persistent volumes для postgres, redis, minio, prometheus, grafana

### 3. Kubernetes (перспектива)

Архитектура готова к миграции на Kubernetes:
- Каждый сервис = отдельный Deployment
- NetworkPolicy повторяют текущую сетевую изоляцию
- HPA для backend и ML Service
- PVC для stateful сервисов (postgres, minio)
- Ingress вместо nginx container
