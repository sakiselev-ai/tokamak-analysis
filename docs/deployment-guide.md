# Руководство по развертыванию — Tokamak Analysis Platform

## Содержание

1. [Требования](#требования)
2. [Клонирование и настройка](#клонирование-и-настройка)
3. [Development окружение](#development-окружение)
4. [Production окружение](#production-окружение)
5. [SSL/TLS настройка](#ssltls-настройка)
6. [Бэкапы PostgreSQL](#бэкапы-postgresql)
7. [Мониторинг](#мониторинг)
8. [Обновление](#обновление)
9. [Troubleshooting](#troubleshooting)

---

## Требования

### Минимальные системные требования

| Параметр | Значение |
|----------|---------|
| Docker | 24.0+ |
| Docker Compose | v2.0+ |
| RAM | 4 GB (8 GB рекомендуется для обучения моделей) |
| Диск | 20 GB свободного места |
| CPU | 2 ядра (4+ рекомендуется) |
| ОС | Linux (Ubuntu 22.04+), macOS, Windows (WSL2) |

### Для локальной разработки (без Docker)

| Компонент | Версия |
|-----------|--------|
| Python | 3.11+ |
| Node.js | 20+ |
| PostgreSQL | 16+ |
| Redis | 7+ |
| Git | 2.30+ |

### Порты

Убедитесь, что следующие порты свободны:

| Порт | Сервис |
|------|--------|
| 80 | Nginx (reverse proxy) |
| 3000 | Frontend dev server (только development) |
| 3001 | Grafana |
| 9001 | MinIO Console |
| 9090 | Prometheus |

---

## Клонирование и настройка

### 1. Клонирование репозитория

```bash
git clone <repo-url>
cd tokamak-analysis
```

### 2. Настройка переменных окружения

```bash
cp .env.example .env
```

Откройте `.env` и измените значения для вашего окружения:

```bash
# ОБЯЗАТЕЛЬНО измените для production:
POSTGRES_PASSWORD=<надежный_пароль>
JWT_SECRET_KEY=<случайная_строка_минимум_32_символа>
MINIO_ROOT_PASSWORD=<надежный_пароль>

# Генерация случайного секрета:
openssl rand -hex 32
```

**Полный список переменных:**

| Переменная | Описание | По умолчанию |
|------------|----------|-------------|
| `POSTGRES_USER` | Пользователь PostgreSQL | `tokamak` |
| `POSTGRES_PASSWORD` | Пароль PostgreSQL | `changeme_in_production` |
| `POSTGRES_DB` | Имя базы данных | `tokamak_db` |
| `DATABASE_URL` | Connection string | `postgresql+asyncpg://...` |
| `REDIS_URL` | URL Redis | `redis://redis:6379/0` |
| `JWT_SECRET_KEY` | Секрет для подписи JWT | `changeme_jwt_secret_key_in_production` |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Время жизни access token | `15` |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | Время жизни refresh token | `7` |
| `ML_SERVICE_URL` | URL ML-сервиса | `http://ml-service:8001` |
| `MINIO_ROOT_USER` | Пользователь MinIO | `minioadmin` |
| `MINIO_ROOT_PASSWORD` | Пароль MinIO | `minioadmin123` |
| `FAIR_MAST_S3_ENDPOINT` | S3 endpoint FAIR-MAST | `https://s3.echo.stfc.ac.uk` |
| `BACKEND_CORS_ORIGINS` | Разрешенные CORS origins | `http://localhost:3000,...` |
| `APP_ENV` | Окружение | `development` |

---

## Development окружение

### Запуск с hot-reload

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

Это запустит все 11 сервисов с hot-reload для backend, ML-сервиса и frontend.

### Доступные сервисы

| Сервис | URL |
|--------|-----|
| Frontend (dev server) | http://localhost:3000 |
| Frontend (через nginx) | http://localhost |
| API (Swagger UI) | http://localhost/docs |
| Grafana | http://localhost:3001 |
| MinIO Console | http://localhost:9001 |
| Prometheus | http://localhost:9090 |

### Локальный запуск без Docker

Если вы хотите запустить отдельные сервисы локально:

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

> При локальном запуске необходимы работающие PostgreSQL и Redis.
> Настройте `DATABASE_URL` и `REDIS_URL` в `.env`.

### Миграции базы данных

```bash
cd backend
alembic upgrade head
```

### Запуск тестов

```bash
# Backend
cd backend && pytest tests/ -v --cov=app

# ML Service
cd ml_service && pytest tests/ -v --cov=service

# Frontend (проверка сборки)
cd frontend && npm run build
```

---

## Production окружение

### Запуск

```bash
# Настройте production-значения в .env
cp .env.example .env
# Отредактируйте .env (см. раздел "Клонирование и настройка")

# Запуск всех сервисов
docker compose up -d
```

### Проверка статуса

```bash
# Статус всех контейнеров
docker compose ps

# Логи конкретного сервиса
docker compose logs -f backend
docker compose logs -f ml-service

# Health check
curl http://localhost/health
curl http://localhost/api/v1/health
```

### Ресурсные лимиты

В production compose настроены лимиты ресурсов:

| Сервис | CPU | RAM |
|--------|-----|-----|
| Nginx | 0.5 | 256 MB |
| Frontend | 0.5 | 256 MB |
| Backend | 2.0 | 2 GB |
| ML Service | 4.0 | 8 GB |
| Celery Worker | 2.0 | 4 GB |
| PostgreSQL | 2.0 | 4 GB |
| Redis | 1.0 | 1 GB |
| MinIO | 1.0 | 1 GB |
| Prometheus | 0.5 | 512 MB |
| Grafana | 0.5 | 512 MB |

### Persistent Volumes

Данные сохраняются между перезапусками через Docker volumes:
- `postgres_data` -- база данных PostgreSQL
- `redis_data` -- кеш и очередь задач Redis
- `minio_data` -- артефакты моделей (MinIO)
- `prometheus_data` -- метрики Prometheus
- `grafana_data` -- дашборды и настройки Grafana

### Сетевая изоляция

Платформа использует 4 изолированных Docker-сети:
- **frontend** -- nginx, frontend, backend (доступна извне)
- **backend** -- backend, ml-service, celery-worker, redis, minio (`internal: true`)
- **db** -- backend, celery-worker, postgres (`internal: true`)
- **monitoring** -- prometheus, grafana, backend, ml-service

PostgreSQL и ML-сервис недоступны напрямую из интернета.

---

## SSL/TLS настройка

### Let's Encrypt с Certbot

#### 1. Установите Certbot

```bash
apt install certbot python3-certbot-nginx
```

#### 2. Получите сертификат

```bash
certbot certonly --standalone -d your-domain.com
```

#### 3. Обновите конфигурацию Nginx

Создайте файл `nginx/nginx-ssl.conf`:

```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers on;

    # HSTS (уже включен middleware, но дублируем на уровне nginx)
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    location / {
        proxy_pass http://frontend:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /docs {
        proxy_pass http://backend:8000/docs;
    }
}
```

#### 4. Примонтируйте сертификаты в docker-compose

Добавьте в `docker-compose.yml` для сервиса nginx:

```yaml
volumes:
  - /etc/letsencrypt:/etc/letsencrypt:ro
  - ./nginx/nginx-ssl.conf:/etc/nginx/conf.d/default.conf:ro
ports:
  - "80:80"
  - "443:443"
```

#### 5. Автообновление сертификатов

```bash
# Добавьте в crontab
0 0 1 * * certbot renew --quiet && docker compose restart nginx
```

---

## Бэкапы PostgreSQL

### Создание бэкапа

```bash
# Полный дамп базы данных
docker compose exec postgres pg_dump -U tokamak tokamak_db > backup_$(date +%Y%m%d_%H%M%S).sql

# Сжатый бэкап
docker compose exec postgres pg_dump -U tokamak -Fc tokamak_db > backup_$(date +%Y%m%d_%H%M%S).dump
```

### Восстановление из бэкапа

```bash
# Из SQL-дампа
docker compose exec -T postgres psql -U tokamak tokamak_db < backup_20260501_120000.sql

# Из сжатого дампа
docker compose exec -T postgres pg_restore -U tokamak -d tokamak_db backup_20260501_120000.dump
```

### Автоматические бэкапы

Добавьте в crontab:

```bash
# Ежедневный бэкап в 3:00
0 3 * * * cd /path/to/tokamak-analysis && docker compose exec -T postgres pg_dump -U tokamak -Fc tokamak_db > /backups/tokamak_$(date +\%Y\%m\%d).dump

# Удаление бэкапов старше 30 дней
0 4 * * * find /backups -name "tokamak_*.dump" -mtime +30 -delete
```

### Бэкап MinIO (артефакты моделей)

```bash
# Установите MinIO Client
mc alias set local http://localhost:9001 minioadmin minioadmin123

# Скопируйте все артефакты
mc mirror local/models /backups/minio/models
mc mirror local/data /backups/minio/data
```

---

## Мониторинг

### Prometheus

Prometheus доступен по адресу http://localhost:9090.

Собираемые метрики:
- **Backend** (`/metrics`): HTTP-запросы (latency, count, errors), активные соединения
- **ML Service** (`/metrics`): инференс (latency, count), обучение (duration, count)

Конфигурация: `monitoring/prometheus/prometheus.yml`

### Grafana

Grafana доступен по адресу http://localhost:3001.

**Учетные данные по умолчанию**: admin / admin (измените при первом входе).

Предварительно настроенные дашборды:
- **Backend Overview** -- HTTP-запросы, latency p50/p95/p99, ошибки
- **ML Service** -- инференс latency, количество предсказаний, обучение
- **Infrastructure** -- CPU, RAM, диск (при наличии node-exporter)

Конфигурация:
- Datasources: `monitoring/grafana/provisioning/datasources/`
- Dashboards: `monitoring/grafana/provisioning/dashboards/`

### Health Checks

```bash
# Простая проверка backend
curl http://localhost/health
# {"status": "ok"}

# Расширенная проверка (включая ML-сервис)
curl http://localhost/api/v1/health
# {"status": "healthy", "version": "1.0.0", "ml_service": "connected"}
```

### Алерты

Рекомендуемые алерты для настройки в Grafana:
- Backend latency p95 > 1s
- ML Service недоступен более 5 минут
- Disk usage > 80%
- Error rate > 5%
- Celery queue length > 100

---

## Обновление

### Стандартное обновление

```bash
# 1. Получите последние изменения
git pull origin main

# 2. Пересоберите и перезапустите
docker compose up -d --build

# 3. Примените миграции БД (если есть)
docker compose exec backend alembic upgrade head

# 4. Проверьте статус
docker compose ps
curl http://localhost/api/v1/health
```

### Обновление с минимальным простоем

```bash
# 1. Соберите новые образы
docker compose build

# 2. Примените миграции (пока старая версия работает)
docker compose exec backend alembic upgrade head

# 3. Перезапустите сервисы по одному
docker compose up -d --no-deps backend
docker compose up -d --no-deps ml-service
docker compose up -d --no-deps celery-worker
docker compose up -d --no-deps frontend
docker compose up -d --no-deps nginx
```

### Откат

```bash
# Откат к предыдущей версии
git checkout <previous-tag>
docker compose up -d --build

# Откат миграций (если необходимо)
docker compose exec backend alembic downgrade -1
```

---

## Troubleshooting

### Контейнер не запускается

```bash
# Проверьте логи конкретного сервиса
docker compose logs backend
docker compose logs ml-service
docker compose logs postgres

# Проверьте статус всех контейнеров
docker compose ps
```

### Backend не может подключиться к PostgreSQL

**Симптом**: `Connection refused` или `could not connect to server`

**Решение**:
1. Убедитесь, что контейнер postgres запущен: `docker compose ps postgres`
2. Проверьте `DATABASE_URL` в `.env`
3. Проверьте, что пароль совпадает в `POSTGRES_PASSWORD` и `DATABASE_URL`
4. Дождитесь полной инициализации PostgreSQL (может занять 10-30 секунд при первом запуске)

### ML-сервис недоступен

**Симптом**: `ml_service: unavailable` в health check

**Решение**:
1. Проверьте логи: `docker compose logs ml-service`
2. Убедитесь, что `ML_SERVICE_URL` корректен в `.env`
3. Проверьте, что ML-сервис и backend в одной Docker-сети (`backend`)
4. ML-сервис может долго стартовать при загрузке тяжелых моделей

### Ошибки при загрузке данных из FAIR-MAST

**Симптом**: `502 Bad Gateway` при загрузке shot

**Решение**:
1. Проверьте доступность FAIR-MAST: `curl https://s3.echo.stfc.ac.uk`
2. Убедитесь, что контейнер имеет доступ к интернету
3. Проверьте `FAIR_MAST_S3_ENDPOINT` в `.env`
4. Некоторые shot_id могут не существовать в архиве

### Celery Worker не обрабатывает задачи

**Симптом**: обучение остается в статусе `queued`

**Решение**:
1. Проверьте логи: `docker compose logs celery-worker`
2. Убедитесь, что Redis доступен: `docker compose exec redis redis-cli ping`
3. Проверьте `REDIS_URL` в `.env`
4. Перезапустите worker: `docker compose restart celery-worker`

### Нехватка памяти при обучении моделей

**Симптом**: контейнер ml-service или celery-worker перезапускается (OOM killed)

**Решение**:
1. Увеличьте лимиты памяти в `docker-compose.yml` для `ml-service` и `celery-worker`
2. Уменьшите размер батча в гиперпараметрах модели
3. Для Transformer-моделей рекомендуется минимум 8 GB RAM

### Порт 80 занят

**Симптом**: `bind: address already in use`

**Решение**:
```bash
# Найдите процесс, занимающий порт
sudo lsof -i :80

# Остановите его или измените порт nginx в docker-compose.yml
# ports: - "8080:80"
```

### Сброс базы данных

> Внимание: это удалит все данные!

```bash
docker compose down -v  # -v удалит volumes
docker compose up -d
docker compose exec backend alembic upgrade head
```
