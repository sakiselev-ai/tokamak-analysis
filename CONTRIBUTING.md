# Contributing / Руководство для разработчиков

## Настройка среды разработки

### Требования

- Docker + Docker Compose >= 2.0
- Python 3.11 (для локального запуска backend/ML)
- Node.js 20 (для локального запуска frontend)
- Git

### Запуск через Docker (рекомендуется)

```bash
# Клонировать репозиторий
git clone <repo-url>
cd tokamak-analysis

# Скопировать переменные окружения
cp .env.example .env

# Запуск в dev-режиме (hot-reload)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

### Локальный запуск (без Docker)

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# ML Service
cd ml_service
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn service.server:app --reload --port 8001

# Frontend
cd frontend
npm install
npm run dev
```

При локальном запуске необходимы PostgreSQL и Redis. Настройте `DATABASE_URL`
и `REDIS_URL` в `.env`.

## Code Style

### Python (backend + ML service)

- Linter: **ruff** (запускается в CI)
- Все файлы начинаются с `from __future__ import annotations`
- Type hints обязательны для всех функций и параметров
- SQLAlchemy: `Mapped[]` + `mapped_column()` (declarative style)
- Для nullable полей ORM: `Mapped[Optional[X]]`
- Pydantic v2: `model_config = {"from_attributes": True}`
- Логирование: `structlog` (structured JSON logs)

```bash
# Проверка стиля
ruff check backend/
ruff check ml_service/

# Автоисправление
ruff check --fix backend/
```

### TypeScript (frontend)

- Strict mode включен (`tsconfig.json`)
- React functional components + hooks
- State management: Zustand
- HTTP client: Axios с JWT interceptor

```bash
# Type check + build
cd frontend && npm run build
```

## Структура веток

- `main` — стабильная версия, защищенная ветка
- `develop` — текущая разработка
- Feature branches: `feature/<name>`
- Bug fixes: `fix/<name>`

## Pull Request Process

1. Создайте feature branch от `develop`:
   ```bash
   git checkout develop
   git pull
   git checkout -b feature/my-feature
   ```

2. Внесите изменения, напишите/обновите тесты

3. Убедитесь, что все проверки проходят:
   ```bash
   # Lint
   ruff check backend/ ml_service/

   # Tests
   cd backend && pytest tests/ -v
   cd ml_service && pytest tests/ -v

   # Frontend build
   cd frontend && npm run build
   ```

4. Создайте pull request в `develop`

5. CI pipeline автоматически запустит:
   - `ruff check` (backend + ML service)
   - `pytest` с coverage (backend + ML service)
   - `npm run build` (frontend)
   - Docker build всех образов

## Требования к тестам

- **Целевое покрытие**: >= 80%
- Backend: `pytest-asyncio` + `httpx.AsyncClient` + SQLite (in-memory)
- ML Service: `pytest` с синтетическими данными
- Используйте готовые fixtures из `conftest.py`:
  - `client` — неаутентифицированный HTTP клиент
  - `auth_client` — клиент с JWT токеном
- Каждый новый endpoint должен иметь тесты на:
  - Успешный сценарий (200/201/202)
  - Ошибки авторизации (401/403)
  - Невалидные данные (422)
  - Not found (404)

```bash
# Запуск тестов с coverage
cd backend && pytest tests/ -v --cov=app --cov-report=term-missing
cd ml_service && pytest tests/ -v --cov=service --cov-report=term-missing
```

## Добавление нового API endpoint

1. Создайте/обновите Pydantic-схему в `backend/app/schemas/`
2. Добавьте endpoint в соответствующий router (`backend/app/api/`)
3. При необходимости добавьте ORM модель в `backend/app/models/`
4. Добавьте миграцию: `cd backend && alembic revision --autogenerate -m "description"`
5. Напишите тесты в `backend/tests/`

## Добавление новой ML модели

1. Реализуйте `ModelInterface` (fit, predict, predict_proba, save, load, metadata)
2. Зарегистрируйте в `ml_service/service/training/trainer.py` (model factory)
3. Добавьте конфиг с гиперпараметрами в `configs/<model_name>.yml`
4. Напишите тесты в `ml_service/tests/`
