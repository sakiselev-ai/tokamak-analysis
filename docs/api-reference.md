# API Reference — Tokamak Analysis Platform

## Содержание

1. [Общая информация](#общая-информация)
2. [Аутентификация](#аутентификация)
3. [Auth API](#auth-api)
4. [Experiments API](#experiments-api)
5. [Predictions API](#predictions-api)
6. [Models API](#models-api)
7. [Admin API](#admin-api)
8. [Legal API](#legal-api)
9. [Health и Metrics](#health-и-metrics)
10. [Коды ошибок](#коды-ошибок)
11. [Rate Limiting](#rate-limiting)

---

## Общая информация

- **Base URL**: `http://localhost/api/v1`
- **Формат**: JSON
- **Swagger UI**: доступен по адресу [http://localhost/docs](http://localhost/docs) (а также `/api/docs` -- перенаправляет на `/docs`)
- **ReDoc**: доступен по адресу [http://localhost/redoc](http://localhost/redoc)

Все endpoint'ы (кроме auth, health и legal) требуют JWT-аутентификации.

---

## Аутентификация

Платформа использует JWT (JSON Web Tokens) с двумя типами токенов:
- **Access token** -- для доступа к API (время жизни: 15 минут)
- **Refresh token** -- для обновления access token (время жизни: 7 дней)

### Поток аутентификации

```
1. POST /api/v1/auth/register   -- Регистрация (получение аккаунта)
2. POST /api/v1/auth/login      -- Вход (получение токенов)
3. Используйте access_token в заголовке: Authorization: Bearer <token>
4. POST /api/v1/auth/refresh    -- Обновление access token (когда истек)
```

### Заголовок авторизации

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

---

## Auth API

### POST /api/v1/auth/register

Регистрация нового пользователя.

**Аутентификация**: не требуется

**Request Body:**
```json
{
  "email": "researcher@mephi.ru",
  "password": "securePassword123",
  "full_name": "Иванов Иван Иванович",
  "role": "researcher",
  "consent_given": true
}
```

| Поле | Тип | Обязательное | Описание |
|------|-----|-------------|----------|
| `email` | string (email) | да | Email пользователя |
| `password` | string | да | Пароль (8-128 символов) |
| `full_name` | string | да | ФИО (1-255 символов) |
| `role` | string | нет | Роль: `researcher` (по умолчанию), `engineer`, `admin` |
| `consent_given` | boolean | да | Согласие на обработку ПДн (152-ФЗ), должно быть `true` |

**Response 201:**
```json
{
  "id": 1,
  "email": "researcher@mephi.ru",
  "full_name": "Иванов Иван Иванович",
  "role": "researcher",
  "is_active": true
}
```

**Ошибки:**
- `400` -- согласие на обработку ПДн не дано
- `409` -- email уже зарегистрирован
- `422` -- невалидные данные (короткий пароль, некорректный email)

---

### POST /api/v1/auth/login

Аутентификация и получение JWT-токенов.

**Аутентификация**: не требуется

**Request Body:**
```json
{
  "email": "researcher@mephi.ru",
  "password": "securePassword123"
}
```

**Response 200:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

**Ошибки:**
- `401` -- неверные учетные данные
- `403` -- аккаунт деактивирован

---

### POST /api/v1/auth/refresh

Обновление access token с помощью refresh token.

**Аутентификация**: не требуется

**Request Body:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**Response 200:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

**Ошибки:**
- `401` -- невалидный или истекший refresh token

---

### GET /api/v1/auth/me

Получение профиля текущего пользователя.

**Аутентификация**: JWT

**Response 200:**
```json
{
  "id": 1,
  "email": "researcher@mephi.ru",
  "full_name": "Иванов Иван Иванович",
  "role": "researcher",
  "is_active": true
}
```

---

### DELETE /api/v1/auth/account

Удаление аккаунта и всех связанных данных (152-ФЗ, ст. 21).

**Аутентификация**: JWT

**Response 200:**
```json
{
  "detail": "Аккаунт и все связанные данные удалены"
}
```

Удаляются: предсказания, временные ряды, эксперименты, запуски обучения, аудит-логи. Аккаунт деактивируется (soft delete).

---

### GET /api/v1/auth/export-data

Экспорт всех персональных данных пользователя (152-ФЗ, ст. 14).

**Аутентификация**: JWT

**Response 200:**
```json
{
  "profile": {
    "id": 1,
    "email": "researcher@mephi.ru",
    "full_name": "Иванов Иван Иванович",
    "role": "researcher",
    "is_active": true,
    "created_at": "2026-01-15T10:30:00",
    "consent_given_at": "2026-01-15T10:30:00"
  },
  "experiments": [...],
  "predictions": [...],
  "model_runs": [...]
}
```

---

## Experiments API

### POST /api/v1/experiments/load

Загрузка экспериментальных данных из FAIR-MAST.

**Аутентификация**: JWT

**Request Body:**
```json
{
  "shot_id": 30420,
  "source": "mast"
}
```

| Поле | Тип | Обязательное | Описание |
|------|-----|-------------|----------|
| `shot_id` | integer | да | ID выстрела (> 0) |
| `source` | string | нет | Источник данных (по умолчанию `mast`) |

**Response 201:**
```json
{
  "id": 1,
  "shot_id": 30420,
  "source": "mast",
  "status": "preprocessed",
  "metadata_json": {
    "signal_count": 12,
    "shot_id": 30420
  },
  "loaded_at": "2026-05-01T12:00:00",
  "timeseries": [
    {
      "parameter_name": "ip",
      "timestamps": [0.0, 0.001, 0.002, ...],
      "values": [100.0, 102.5, 105.1, ...],
      "units": "kA",
      "description": "Plasma current"
    }
  ]
}
```

**Ошибки:**
- `502` -- не удалось загрузить данные из FAIR-MAST

---

### POST /api/v1/experiments/batch-load

Пакетная загрузка нескольких выстрелов.

**Аутентификация**: JWT

**Request Body:**
```json
{
  "shot_ids": [30420, 30421, 30422],
  "source": "mast"
}
```

| Поле | Тип | Обязательное | Описание |
|------|-----|-------------|----------|
| `shot_ids` | array[integer] | да | Список shot_id (1-50 штук) |
| `source` | string | нет | Источник данных (по умолчанию `mast`) |

**Response 201:**
```json
{
  "experiments": [...],
  "failed": [
    {"shot_id": 30422, "error": "Shot not found"}
  ],
  "total_loaded": 2
}
```

---

### GET /api/v1/experiments/

Список экспериментов текущего пользователя с пагинацией.

**Аутентификация**: JWT

**Query Parameters:**
| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| `skip` | integer | 0 | Смещение |
| `limit` | integer | 20 | Количество записей |

**Response 200:**
```json
{
  "experiments": [
    {
      "id": 1,
      "shot_id": 30420,
      "source": "mast",
      "status": "preprocessed",
      "metadata_json": {"signal_count": 12},
      "loaded_at": "2026-05-01T12:00:00",
      "timeseries": [...]
    }
  ],
  "total": 42
}
```

---

### GET /api/v1/experiments/{experiment_id}

Детали конкретного эксперимента.

**Аутентификация**: JWT

**Response 200:** аналогично объекту из списка

**Ошибки:**
- `404` -- эксперимент не найден или принадлежит другому пользователю

---

### GET /api/v1/experiments/{experiment_id}/timeseries

Временные ряды эксперимента.

**Аутентификация**: JWT

**Response 200:**
```json
[
  {
    "parameter_name": "ip",
    "timestamps": [0.0, 0.001, 0.002],
    "values": [100.0, 102.5, 105.1],
    "units": "kA",
    "description": "Plasma current"
  },
  {
    "parameter_name": "ne",
    "timestamps": [0.0, 0.001, 0.002],
    "values": [2.5e19, 2.6e19, 2.7e19],
    "units": "m^-3",
    "description": "Electron density"
  }
]
```

---

### GET /api/v1/experiments/{experiment_id}/export

Экспорт данных эксперимента в CSV или JSON.

**Аутентификация**: JWT

**Query Parameters:**
| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| `format` | string | `csv` | Формат: `csv` или `json` |

**Response 200 (CSV):**
```
Content-Type: text/csv
Content-Disposition: attachment; filename=shot_30420.csv

parameter,timestamp,value,units
ip,0.0,100.0,kA
ip,0.001,102.5,kA
ne,0.0,2.5e+19,m^-3
```

**Response 200 (JSON):**
```json
{
  "shot_id": 30420,
  "source": "mast",
  "signals": {
    "ip": {
      "timestamps": [0.0, 0.001],
      "values": [100.0, 102.5],
      "units": "kA"
    }
  }
}
```

---

## Predictions API

### POST /api/v1/predictions/classify

Классификация стабильности плазмы.

**Аутентификация**: JWT

**Request Body:**
```json
{
  "experiment_id": 1,
  "model_id": null
}
```

| Поле | Тип | Обязательное | Описание |
|------|-----|-------------|----------|
| `experiment_id` | integer | да | ID эксперимента |
| `model_id` | integer | нет | ID модели (если не указан -- используется последняя активная) |

**Response 200:**
```json
{
  "experiment_id": 1,
  "label": "stable",
  "confidence": 0.92,
  "inference_time_ms": 4.5,
  "model_id": 3
}
```

**Ошибки:**
- `404` -- эксперимент или модель не найдены

---

### POST /api/v1/predictions/disruption

Предсказание срыва плазмы.

**Аутентификация**: JWT

**Request Body:**
```json
{
  "experiment_id": 1,
  "model_id": null,
  "threshold": 0.7
}
```

| Поле | Тип | Обязательное | Описание |
|------|-----|-------------|----------|
| `experiment_id` | integer | да | ID эксперимента |
| `model_id` | integer | нет | ID модели |
| `threshold` | float | нет | Порог срабатывания (0.0-1.0, по умолчанию 0.7) |

**Response 200:**
```json
{
  "experiment_id": 1,
  "timestamps": [0.0, 0.001, 0.002, 0.003, 0.004],
  "probabilities": [0.1, 0.15, 0.45, 0.78, 0.92],
  "warning_issued": true,
  "warning_time_ms": 3.0,
  "inference_time_ms": 25.3,
  "model_id": 5,
  "recommendations": [
    {
      "level": "high",
      "message": "Высокая вероятность срыва. Рекомендуется снижение мощности нагрева.",
      "action": "reduce_heating_power"
    }
  ]
}
```

---

### POST /api/v1/predictions/batch-classify

Пакетная классификация нескольких экспериментов.

**Аутентификация**: JWT

**Request Body:**
```json
{
  "experiment_ids": [1, 2, 3],
  "model_id": null
}
```

| Поле | Тип | Обязательное | Описание |
|------|-----|-------------|----------|
| `experiment_ids` | array[integer] | да | Список ID экспериментов (1-50) |
| `model_id` | integer | нет | ID модели |

**Response 200:**
```json
{
  "results": [
    {"experiment_id": 1, "label": "stable", "confidence": 0.92, "inference_time_ms": 4.5, "model_id": 3},
    {"experiment_id": 2, "label": "unstable", "confidence": 0.87, "inference_time_ms": 4.8, "model_id": 3}
  ],
  "failed": [
    {"experiment_id": 3, "error": "Experiment not found"}
  ]
}
```

---

### POST /api/v1/predictions/batch-disruption

Пакетное предсказание срывов.

**Аутентификация**: JWT

**Request Body:**
```json
{
  "experiment_ids": [1, 2],
  "model_id": null,
  "threshold": 0.7
}
```

| Поле | Тип | Обязательное | Описание |
|------|-----|-------------|----------|
| `experiment_ids` | array[integer] | да | Список ID экспериментов (1-50) |
| `model_id` | integer | нет | ID модели |
| `threshold` | float | нет | Порог срабатывания (0.0-1.0, по умолчанию 0.7) |

**Response 200:**
```json
{
  "results": [...],
  "failed": [...]
}
```

---

### PUT /api/v1/predictions/threshold

Обновление порога срабатывания для текущего пользователя.

**Аутентификация**: JWT

**Request Body:**
```json
{
  "threshold": 0.8
}
```

**Response 200:**
```json
{
  "threshold": 0.8,
  "notification_enabled": true,
  "updated_at": "2026-05-01T12:00:00"
}
```

---

### GET /api/v1/predictions/threshold

Получение текущего порога срабатывания.

**Аутентификация**: JWT

**Response 200:**
```json
{
  "threshold": 0.7,
  "notification_enabled": true,
  "updated_at": null
}
```

---

## Models API

### POST /api/v1/models/train

Запуск обучения модели (асинхронно через Celery).

**Аутентификация**: JWT

**Request Body:**
```json
{
  "model_type": "lstm_attention",
  "task": "classification",
  "hyperparameters": {
    "hidden_size": 128,
    "num_layers": 2,
    "learning_rate": 0.001,
    "epochs": 50
  },
  "dataset_shot_ids": [30420, 30421, 30422]
}
```

| Поле | Тип | Обязательное | Описание |
|------|-----|-------------|----------|
| `model_type` | string | да | `random_forest`, `lstm_attention` или `transformer` |
| `task` | string | нет | `classification` (по умолчанию) или `disruption_prediction` |
| `hyperparameters` | object | нет | Гиперпараметры (если не указаны -- из конфигурации) |
| `dataset_shot_ids` | array[integer] | нет | Shot ID для обучения (если не указаны -- весь датасет) |

**Response 202:**
```json
{
  "run_id": 7,
  "model_id": 3,
  "status": "queued",
  "celery_task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

---

### GET /api/v1/models/

Список всех моделей.

**Аутентификация**: JWT

**Query Parameters:**
| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| `skip` | integer | 0 | Смещение |
| `limit` | integer | 50 | Количество записей |

**Response 200:**
```json
[
  {
    "id": 1,
    "name": "random_forest_classification",
    "model_type": "random_forest",
    "task": "classification",
    "version": "1.0",
    "s3_path": "models/rf_classification_v1.pkl",
    "metrics_json": {"accuracy": 0.87, "f1": 0.85},
    "is_active": true
  }
]
```

---

### GET /api/v1/models/{model_id}/versions

Список всех версий конкретной модели (все модели с тем же типом и задачей).

**Аутентификация**: JWT

**Response 200:**
```json
[
  {
    "id": 3,
    "name": "lstm_attention_classification",
    "version": "2.0",
    "s3_path": "models/lstm_v2.pt",
    "metrics_json": {"accuracy": 0.91, "auc_roc": 0.94},
    "is_active": true
  },
  {
    "id": 1,
    "name": "lstm_attention_classification",
    "version": "1.0",
    "s3_path": "models/lstm_v1.pt",
    "metrics_json": {"accuracy": 0.87, "auc_roc": 0.90},
    "is_active": false
  }
]
```

---

### PUT /api/v1/models/{model_id}/activate

Активация конкретной версии модели (для rollback). Все остальные версии с тем же типом и задачей деактивируются.

**Аутентификация**: JWT

**Response 200:**
```json
{
  "id": 1,
  "name": "lstm_attention_classification",
  "model_type": "lstm_attention",
  "task": "classification",
  "version": "1.0",
  "s3_path": "models/lstm_v1.pt",
  "metrics_json": {"accuracy": 0.87},
  "is_active": true
}
```

**Ошибки:**
- `404` -- модель не найдена

---

### GET /api/v1/models/runs

Список запусков обучения текущего пользователя.

**Аутентификация**: JWT

**Query Parameters:**
| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| `skip` | integer | 0 | Смещение |
| `limit` | integer | 20 | Количество записей |

**Response 200:**
```json
[
  {
    "id": 7,
    "model_id": 3,
    "status": "completed",
    "hyperparams_json": {"hidden_size": 128, "epochs": 50},
    "metrics_json": {"accuracy": 0.91, "auc_roc": 0.94, "f1": 0.89},
    "progress": 100.0,
    "started_at": "2026-05-01T12:00:00",
    "finished_at": "2026-05-01T12:15:30",
    "created_at": "2026-05-01T11:59:50"
  }
]
```

---

### GET /api/v1/models/runs/{run_id}

Детали конкретного запуска обучения.

**Аутентификация**: JWT

**Response 200:** аналогично объекту из списка

**Ошибки:**
- `404` -- запуск не найден

---

### GET /api/v1/models/runs/{run_id}/status

Статус обучения (polling Celery task state).

**Аутентификация**: JWT

**Response 200:**
```json
{
  "run_id": 7,
  "celery_task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "state": "PROGRESS",
  "progress": 65.0,
  "status": "running",
  "info": {
    "progress": 65.0,
    "current_epoch": 33,
    "total_epochs": 50,
    "current_loss": 0.234
  }
}
```

**Возможные состояния (`state`):**
- `PENDING` -- задача в очереди
- `PROGRESS` -- выполняется (содержит прогресс в `info`)
- `SUCCESS` -- завершено успешно
- `FAILURE` -- завершено с ошибкой (содержит ошибку в `info.error`)
- `UNKNOWN` -- состояние неизвестно

---

## Admin API

Все endpoint'ы администрирования требуют роль `admin`.

### GET /api/v1/admin/users

Список всех пользователей.

**Аутентификация**: JWT (роль `admin`)

**Query Parameters:**
| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| `skip` | integer | 0 | Смещение |
| `limit` | integer | 50 | Количество записей |

**Response 200:**
```json
[
  {
    "id": 1,
    "email": "admin@mephi.ru",
    "full_name": "Администратор",
    "role": "admin",
    "is_active": true
  },
  {
    "id": 2,
    "email": "researcher@mephi.ru",
    "full_name": "Иванов Иван Иванович",
    "role": "researcher",
    "is_active": true
  }
]
```

**Ошибки:**
- `403` -- недостаточно прав (не admin)

---

### PUT /api/v1/admin/users/{user_id}/role

Изменение роли пользователя.

**Аутентификация**: JWT (роль `admin`)

**Query Parameters:**
| Параметр | Тип | Описание |
|----------|-----|----------|
| `role` | string | Новая роль: `researcher`, `engineer`, `admin` |

**Response 200:**
```json
{
  "message": "Role updated",
  "user_id": 2,
  "new_role": "engineer"
}
```

**Ошибки:**
- `404` -- пользователь не найден

---

### PUT /api/v1/admin/users/{user_id}/deactivate

Деактивация пользователя.

**Аутентификация**: JWT (роль `admin`)

**Response 200:**
```json
{
  "message": "User deactivated",
  "user_id": 2
}
```

**Ошибки:**
- `400` -- нельзя деактивировать самого себя
- `404` -- пользователь не найден

---

## Legal API

### GET /api/v1/legal/privacy-policy

Политика конфиденциальности (152-ФЗ).

**Аутентификация**: не требуется

**Response 200:**
```json
{
  "title": "Политика конфиденциальности",
  "version": "1.0",
  "effective_date": "2026-05-01",
  "content": {
    "data_controller": {"name": "НИЯУ МИФИ", ...},
    "data_collected": [...],
    "purposes": [...],
    "legal_basis": "Согласие субъекта (ст. 9 152-ФЗ)",
    "rights": [...],
    ...
  }
}
```

---

### GET /api/v1/legal/terms

Условия использования.

**Аутентификация**: не требуется

**Response 200:**
```json
{
  "title": "Условия использования",
  "version": "1.0",
  "content": "..."
}
```

---

## Health и Metrics

### GET /health

Простая проверка работоспособности.

**Аутентификация**: не требуется

**Response 200:**
```json
{
  "status": "ok"
}
```

---

### GET /api/v1/health

Расширенная проверка (включая статус ML-сервиса).

**Аутентификация**: не требуется

**Response 200:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "ml_service": "connected"
}
```

Значения `ml_service`: `connected` или `unavailable`.

---

### GET /metrics

Prometheus-метрики в формате OpenMetrics.

**Аутентификация**: не требуется

**Response 200:**
```
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="GET",path="/api/v1/health",status="200"} 42
...
```

---

## Коды ошибок

| Код | Описание |
|-----|----------|
| `200` | Успешный запрос |
| `201` | Ресурс создан |
| `202` | Запрос принят (асинхронная обработка) |
| `400` | Некорректный запрос (например, не дано согласие на ПДн) |
| `401` | Не аутентифицирован (нет токена или токен истек) |
| `403` | Доступ запрещен (недостаточно прав или аккаунт деактивирован) |
| `404` | Ресурс не найден |
| `409` | Конфликт (например, email уже зарегистрирован) |
| `422` | Ошибка валидации (невалидные данные в запросе) |
| `429` | Превышен лимит запросов (rate limiting) |
| `502` | Ошибка внешнего сервиса (FAIR-MAST недоступен) |

### Формат ошибки

```json
{
  "detail": "Описание ошибки"
}
```

Для ошибок валидации (422):
```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "value is not a valid email address",
      "type": "value_error.email"
    }
  ]
}
```

---

## Rate Limiting

Платформа ограничивает количество запросов для защиты от злоупотреблений:

- **Лимит**: 100 запросов в минуту на IP-адрес
- **Библиотека**: slowapi
- **Заголовки в ответе**:
  - `X-RateLimit-Limit` -- максимальное количество запросов
  - `X-RateLimit-Remaining` -- оставшееся количество запросов
  - `X-RateLimit-Reset` -- время сброса счетчика

При превышении лимита возвращается ответ `429 Too Many Requests`.
