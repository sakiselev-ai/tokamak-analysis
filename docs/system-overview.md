# Tokamak Analysis Platform -- Обзор системы

**Автор:** Киселев Ф.С., НИЯУ МИФИ  
**Сайт:** [tokamak-ai.ru](https://tokamak-ai.ru)  
**GitHub:** [sakiselev-ai/tokamak-analysis](https://github.com/sakiselev-ai/tokamak-analysis)  
**Лицензия:** MIT  
**Версия:** 1.0.0

---

## 1. Введение

Tokamak Analysis Platform -- интеллектуальная платформа для анализа экспериментальных данных токамаков с применением методов машинного обучения. Система разработана в НИЯУ МИФИ (Национальный исследовательский ядерный университет «МИФИ») и предназначена для исследователей, инженеров и операторов термоядерных установок.

Платформа решает три ключевые задачи: классификацию стабильности плазмы (stable/unstable), предсказание срывов плазмы с упреждающим окном предупреждения 30 мс и прогнозирование временных рядов плазменных параметров. Источником данных служит архив FAIR-MAST (Mega Ampere Spherical Tokamak, Великобритания), содержащий 11 573 выстрела с набором диагностических сигналов.

Система развёрнута в production-окружении на домене tokamak-ai.ru с TLS-шифрованием и полным набором средств мониторинга, резервного копирования и аудита.

---

## 2. Функциональные возможности

Платформа реализует 17 функциональных требований (FR-001--FR-017), покрывающих полный цикл работы с данными плазменных экспериментов.

**Работа с данными:**
- Загрузка экспериментальных данных из архива FAIR-MAST (анонимный S3-доступ, 11 573 выстрела)
- Препроцессинг временных рядов: нормализация, ресемплинг, sliding window для меток срывов
- Интерактивная визуализация на основе Plotly.js с масштабированием, панорамированием и экспортом графиков
- Экспорт данных в форматах CSV и JSON
- Пакетная загрузка и обработка до 50 выстрелов одновременно

**Машинное обучение:**
- Классификация стабильности плазмы тремя моделями: Random Forest, bi-LSTM+Attention, Transformer
- Предсказание срывов с упреждающим окном 30 мс и настраиваемым порогом срабатывания
- Прогнозирование временных рядов (forecasting) с NRMSE 0.143, превосходящим baseline TokaMark (0.163)
- Обучение моделей через веб-интерфейс с асинхронным исполнением через Celery и отслеживанием прогресса в реальном времени
- Управление версиями моделей с возможностью rollback

**Безопасность и администрирование:**
- Аутентификация по JWT-токенам (access 15 мин, refresh 7 дней)
- Ролевая модель доступа (RBAC): researcher, engineer, admin
- Аудит действий пользователей с фиксацией IP-адреса (соответствие 152-ФЗ)
- Согласие на обработку персональных данных, экспорт и удаление аккаунта (ст. 9, 14, 21 152-ФЗ)

**Мониторинг:**
- Сбор метрик Prometheus (HTTP-запросы, latency, инференс, обучение)
- Визуализация в Grafana (2 дашборда: request metrics и ML metrics)
- 10 алертов Alertmanager с уведомлениями в Telegram на русском языке

---

## 3. Архитектура

Система построена по принципу модульного монолита с выделенным ML-сервисом (ADR-001). Взаимодействие компонентов осуществляется через REST API.

### Контекстная диаграмма (C4 Level 1)

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

### Контейнерная диаграмма (C4 Level 2)

Платформа состоит из 12 Docker-сервисов, распределённых по 4 изолированным сетям:

```
                          ┌─── frontend network (public) ───────────────────┐
                          │                                                  │
  Browser ───── :80 ─────>│  ┌─────────┐     ┌───────────┐    ┌──────────┐  │
                          │  │  Nginx   │────>│  Frontend  │    │ Backend  │  │
                          │  │ (reverse │────>│  React 18  │    │ FastAPI  │  │
                          │  │  proxy)  │     │  Vite      │    │ :8000    │  │
                          │  └─────────┘     └───────────┘    └────┬─────┘  │
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

### Docker-сервисы

| Сервис | Образ | Порт(ы) | Сети | Ресурсы |
|--------|-------|---------|------|---------|
| nginx | nginx:1.25-alpine | 80:80 | frontend | 0.5 CPU, 256M |
| frontend | ./frontend | internal | frontend | 0.5 CPU, 256M |
| backend | ./backend | internal | frontend, backend, db, monitoring | 2 CPU, 2G |
| ml-service | ./ml_service | internal | backend, monitoring | 4 CPU, 8G |
| celery-worker | ./backend | -- | backend, db | 2 CPU, 4G |
| postgres | postgres:16-alpine | internal | db | 2 CPU, 4G |
| redis | redis:7-alpine | internal | backend | 1 CPU, 1G |
| minio | minio/minio | 9001 | backend | 1 CPU, 1G |
| minio-init | minio/mc | -- | backend | one-shot |
| prometheus | prom/prometheus | 9090 | monitoring, backend | 0.5 CPU, 512M |
| grafana | grafana/grafana | 3001 | monitoring | 0.5 CPU, 512M |

### Потоки данных

**Загрузка эксперимента:** Browser -> Nginx -> Backend -> FAIR-MAST S3 (загрузка сигналов) -> препроцессинг (нормализация, ресемплинг) -> PostgreSQL (experiment + timeseries + audit_log).

**Классификация:** Browser -> Nginx -> Backend -> PostgreSQL (SELECT experiment) -> ML Service (POST /predict/classify) -> Backend (INSERT prediction) -> Browser ({label, confidence}).

**Обучение модели (асинхронное):** Browser -> Backend -> Redis (enqueue) -> 202 Accepted. Celery Worker -> ML Service (POST /train) -> MinIO (upload artifact) -> PostgreSQL (metrics). Browser -> Backend (GET /runs/{id}/status) -> Redis (poll Celery) -> {progress, metrics}.

### Сетевая изоляция

- `frontend` -- публичная сеть, единственная точка входа через Nginx (порт 80)
- `backend` -- `internal: true`, недоступна извне Docker; содержит ML Service, Redis, MinIO, Celery Worker
- `db` -- `internal: true`, изолированная сеть для PostgreSQL; доступна только Backend и Celery Worker
- `monitoring` -- сеть мониторинга для Prometheus, Grafana, Alertmanager, Telegram-бота

---

## 4. Технологический стек

| Компонент | Технологии |
|-----------|-----------|
| Backend API | Python 3.11, FastAPI, SQLAlchemy async (Mapped[] ORM), Pydantic, Alembic |
| ML-сервис | PyTorch (LSTM, Transformer), scikit-learn (Random Forest), FastAPI :8001 |
| Frontend | React 18, TypeScript, Vite, Plotly.js, Zustand (state management) |
| База данных | PostgreSQL 16, 3 миграции Alembic, 10 ORM-моделей |
| Брокер задач | Redis 7 (Celery broker + cache) |
| Хранилище моделей | MinIO (S3-compatible), бакеты: `models`, `data` |
| Reverse proxy | Nginx 1.25-alpine |
| Контейнеризация | Docker Compose (12 сервисов, 4 сети), resource limits |
| Мониторинг | Prometheus + Grafana (2 дашборда) + Alertmanager (10 алертов) + Telegram-бот |
| CI/CD | GitHub Actions: ruff lint, pytest, docker build, Playwright E2E |
| Логирование | structlog (structured JSON logs) |

---

## 5. Модели машинного обучения

Все модели реализуют единый интерфейс `ModelInterface` (протокол): `fit`, `predict`, `predict_proba`, `save`, `load`, `metadata`. Конфигурации гиперпараметров хранятся в `configs/{rf,lstm,transformer}.yml`.

### Классификация стабильности плазмы

Модели обучены на 500 выстрелах FAIR-MAST (200 временных шагов, 20 признаков, 86.8% disruptions). Полное обучение -- 50 эпох с нормализацией.

| Модель | Тип | AUC-ROC (full) | CV AUC | Temporal AUC | P99 Latency |
|--------|-----|---------------|--------|-------------|-------------|
| Random Forest | Baseline (scikit-learn) | 0.9677 | 0.983 | 0.969 | 73 ms |
| bi-LSTM+Attention | Основная (PyTorch) | **0.9938** | 0.867* | 0.671* | 39 ms |
| Transformer | Экспериментальная (PyTorch) | 0.9415 | 0.938 | 0.892 | 131 ms |

*\* Значения CV/Temporal для LSTM указаны в quick-режиме (3 эпохи); при полном обучении (50 эпох) модель достигает AUC 0.9938.*

### Временная валидация

Темпоральная валидация (train: shots < 12035, test: shots >= 12035) показывает устойчивость моделей к временному сдвигу -- критически важное свойство для реальных экспериментов.

| Модель | Random AUC | Temporal AUC | Деградация |
|--------|-----------|-------------|------------|
| Random Forest | 1.000 | 0.969 | -3.1% |
| bi-LSTM+Attention | 0.941 | 0.671 | -27.0% |
| Transformer | 1.000 | 0.892 | -10.8% |

Случайное разбиение даёт завышенные метрики (AUC 1.0 для RF и Transformer), что подтверждает необходимость темпоральной валидации.

### Прогнозирование временных рядов (Forecasting)

| Модель | NRMSE | Сравнение с TokaMark Group 1 baseline (0.163) |
|--------|-------|----------------------------------------------|
| LSTM Forecaster | **0.143** | Лучше baseline на 12.3% |
| Transformer Forecaster | 0.196 | Сравнимо с baseline |

Результаты получены на 100 выстрелах FAIR-MAST с нормализацией.

---

## 6. API

Платформа предоставляет 30 REST API endpoints, сгруппированных в 6 модулей. Swagger UI доступен по адресу `https://tokamak-ai.ru/docs`.

| Модуль | Endpoints | Описание |
|--------|-----------|----------|
| Auth (`/api/v1/auth`) | 5 | Регистрация, вход, refresh, профиль, удаление аккаунта |
| Experiments (`/api/v1/experiments`) | 6 | Загрузка shot, batch-load, список, детали, timeseries, экспорт |
| Predictions (`/api/v1/predictions`) | 6 | Классификация, disruption, batch-classify, batch-disruption, threshold |
| Models (`/api/v1/models`) | 7 | Обучение, список моделей, версии, активация, запуски, статус |
| Admin (`/api/v1/admin`) | 3 | Список пользователей, изменение роли, деактивация |
| Other | 3 | Health, legal (privacy policy, terms) |

### Поток аутентификации

```
POST /api/v1/auth/register  ->  Регистрация (consent 152-ФЗ обязателен)
POST /api/v1/auth/login     ->  JWT-токены (access + refresh)
Authorization: Bearer <access_token>  ->  Все защищённые endpoints
POST /api/v1/auth/refresh   ->  Обновление access token
```

Rate limiting: 100 запросов в минуту на IP-адрес (slowapi).

---

## 7. Безопасность

### Аутентификация и авторизация

- **JWT** (HS256): access token 15 мин, refresh token 7 дней
- **bcrypt** (cost factor 12) для хэширования паролей
- **RBAC**: три роли -- `researcher`, `engineer`, `admin`

### Транспортная безопасность

- **HTTPS**: Let's Encrypt, TLS 1.2/1.3 (tokamak-ai.ru)
- **Security Headers**: HSTS, X-Content-Type-Options, X-Frame-Options, Content-Security-Policy
- **CORS**: ограничение origins через переменные окружения

### Сетевая изоляция

- Сети `backend` и `db` помечены как `internal: true` -- недоступны извне Docker
- PostgreSQL изолирован в отдельной сети, доступен только Backend и Celery Worker
- ML Service недоступен из frontend-сети

### Соответствие 152-ФЗ

- Обязательное согласие на обработку персональных данных при регистрации (`consent_given_at`)
- Экспорт персональных данных (ст. 14): `GET /api/v1/auth/export-data`
- Полное удаление аккаунта и связанных данных (ст. 21): `DELETE /api/v1/auth/account`
- Soft delete (`deleted_at`) с каскадным удалением предсказаний, экспериментов, запусков
- Аудит действий: каждое действие пользователя логируется с IP-адресом и временной меткой

### Дополнительные меры

- Rate limiting: 100 req/min per IP (slowapi)
- Structured logging (structlog) для forensic-анализа
- Middleware stack: CORS -> Security Headers -> Request Logging -> Rate Limiting -> Prometheus -> Router

---

## 8. Результаты экспериментов

### Классификация (полное обучение, 50 эпох, 500 выстрелов FAIR-MAST)

| Модель | AUC-ROC | Accuracy | F1 |
|--------|---------|----------|----|
| bi-LSTM+Attention | **0.9938** | 99.4% | 0.99 |
| Random Forest | 0.9677 | 96.8% | 0.97 |
| Transformer | 0.9415 | 94.2% | 0.94 |

### Кросс-валидация (3-fold, quick mode)

| Модель | CV Accuracy | CV AUC-ROC | Test Accuracy | Test AUC | P99 Latency |
|--------|-------------|------------|---------------|----------|-------------|
| Random Forest | 98.4% +/- 0.8% | 0.983 +/- 0.012 | 100% | 1.000 | 73 ms |
| bi-LSTM+Attention | 78.4% +/- 0.9% | 0.867 +/- 0.013 | 80% | 0.944 | 39 ms |
| Transformer | 87.8% +/- 1.0% | 0.938 +/- 0.034 | 100% | 1.000 | 131 ms |

### Forecasting (FAIR-MAST, 100 выстрелов)

| Модель | NRMSE | vs FRNN baseline | vs HDL baseline |
|--------|-------|------------------|-----------------|
| LSTM Forecaster | **0.143** | Лучше (0.163) | Сравнимо |
| Transformer Forecaster | 0.196 | Сравнимо | Сравнимо |

### Сравнение с бенчмарком TokaMark

TokaMark (arXiv:2602.10132, KDD 2026) -- бенчмарк с 14 задачами для моделей термоядерного синтеза. Наша модель LSTM Forecaster достигает NRMSE 0.143 на задачах Group 1, что на 12.3% лучше опубликованного baseline (0.163).

---

## 9. Инфраструктура

### Контейнеризация

- 12 Docker-сервисов в Docker Compose с resource limits
- 4 изолированных сети (frontend, backend, db, monitoring)
- Persistent volumes для PostgreSQL, Redis, MinIO, Prometheus, Grafana
- Production-конфигурация: log rotation, restart: always, port restriction

### SSL и домен

- Домен: tokamak-ai.ru
- SSL: Let's Encrypt (автоматическое продление), TLS 1.2/1.3
- Сертификат действителен до 2026-08-05

### Резервное копирование

- Ежедневное автоматическое резервное копирование (cron, 3:00 AM)
- pg_dump -> AES-256 шифрование -> загрузка в MinIO
- Политика ротации: 7 ежедневных + 4 еженедельных копии
- RPO (Recovery Point Objective): 24 часа

### Мониторинг

- **Prometheus**: сбор метрик HTTP, ML-инференс, обучение, системные
- **Grafana**: 2 дашборда (request metrics, ML metrics), pre-provisioned
- **Alertmanager**: 10 алертов (APIDown, MLServiceDown, HighLatency, HighErrorRate, DiskSpace, PostgresDown, LongTraining, AccuracyDrift, HighMemory, CeleryBacklog)
- **Telegram-бот**: webhook-интеграция с Alertmanager, уведомления на русском языке

### Деплой

```bash
# Синхронизация и деплой на VPS
./deploy/deploy.sh <server-ip>

# SSL-настройка
./deploy/setup_ssl.sh

# Настройка резервного копирования
./deploy/setup_backups.sh
```

---

## 10. Тестирование

### Состав тестов

| Категория | Количество | Инструменты |
|-----------|-----------|-------------|
| Backend unit/integration | 139 | pytest-asyncio, httpx AsyncClient, SQLite in-memory |
| ML Service | 45 | pytest, synthetic data, mocked S3 |
| E2E | 21 | Playwright (auth, experiments, export, predictions, training) |
| **Всего** | **205** | |

### Покрытие кода

- Backend coverage: **81%** (NFR-011, требование >= 80%)
- Фикстуры: `client`, `auth_client`, `admin_client` для различных ролей

### CI/CD

GitHub Actions pipeline:
1. **Lint**: ruff check (backend + ml_service)
2. **Test**: pytest с покрытием
3. **Build**: docker compose build
4. **E2E**: Playwright с docker compose up

---

## 11. Метрики проекта

| Метрика | Значение |
|---------|----------|
| Коммитов в основной ветке | 56 |
| Файлов в репозитории | 228 |
| Общий объём кода | ~25 000 LOC |
| Python-код | ~12 100 LOC (90+ файлов) |
| TypeScript-код | ~3 100 LOC (29 файлов) |
| Инфраструктура (YAML/JSON/conf) | ~1 100 LOC |
| Документация (MD/TeX/HTML) | ~7 700 LOC |
| API endpoints | 30 |
| ORM-моделей | 10 |
| ML-моделей | 5 (3 classification + 2 forecasting) |
| Тестов | 205 (139 backend + 45 ML + 21 E2E) |
| Покрытие тестами | 81% |
| Docker-сервисов | 12 |
| Docker-сетей | 4 |
| Prometheus-алертов | 10 |
| Grafana-дашбордов | 2 |
| Функциональных требований | 17/17 (100%) |
| Миграций Alembic | 3 |

### Готовые артефакты

| Артефакт | Статус |
|----------|--------|
| GitHub (public, MIT, CI) | github.com/sakiselev-ai/tokamak-analysis |
| Production-сайт (HTTPS) | tokamak-ai.ru |
| Препринт (10 стр, 25 цитирований) | paper/preprint.pdf |
| Презентация (13 слайдов, HTML) | presentation/index.html |
| Kaggle notebook (самодостаточный) | notebooks/kaggle_disruption_prediction.ipynb |
| Роспатент (листинг 1666 строк) | rospatent/deposited_listing.txt |
| Руководство пользователя (рус.) | docs/user-guide.md |
| Руководство по деплою (рус.) | docs/deployment-guide.md |
| Справочник API (30 endpoints) | docs/api-reference.md |
| Grafana-дашборды | monitoring/grafana/dashboards/ |

---

*Документ подготовлен для Tokamak Analysis Platform v1.0.0. Вопросы и предложения -- [GitHub Issues](https://github.com/sakiselev-ai/tokamak-analysis/issues).*
