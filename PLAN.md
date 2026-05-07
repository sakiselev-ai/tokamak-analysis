# План проекта «Токамак-Анализ» — дорожная карта до 25 июля 2026

## Текущий статус (07 мая 2026, W2)

### Инженерный трек
- **Sprint 0-5**: ✅ Все завершены
- **VPS**: 12 Docker-сервисов, все healthy, https://tokamak-ai.ru
- **Код**: 31 коммит, ~23,000 LOC, 213 файлов, 205 тестов (81% coverage)
- **FR-001–FR-017**: Все 17 функциональных требований реализованы
- **Данные**: 500 shots FAIR-MAST, 567 в кеше, модели обучены
- **SSL**: Let's Encrypt, TLS 1.2/1.3, expires 2026-08-05

### Конкурсный трек «Код МИФИста»

| # | Артефакт | Статус | Следующий шаг |
|---|----------|--------|---------------|
| 1 | **GitHub** | ✅ Готов | https://github.com/sakiselev-ai/tokamak-analysis, 31 коммит, public, MIT |
| 2 | **Роспатент** | ⚠️ Документы готовы | 🔴 **ПОДАТЬ ASAP** — рассмотрение 2-3 мес |
| 3 | **TokaMark** | ⚠️ Модели готовы | LSTM NRMSE=0.143, Transformer=0.196. Ждём лидерборд |
| 4 | **arXiv** | ⚠️ PDF готов | Найти endorser (через ЛаПлаз), загрузить |
| 5 | **Письмо ЛаПлаз** | ❌ Шаблон готов | 🔴 **ОТПРАВИТЬ ASAP** |

### ML результаты

**Классификация (FAIR-MAST, 500 shots):**

| Модель | CV AUC | Temporal AUC |
|--------|--------|-------------|
| RF | 0.983 | 0.969 |
| Transformer | 0.938 | 0.892 |
| LSTM | 0.867 | 0.671 |

**Forecasting / TokaMark (FAIR-MAST, 100 shots, normalized):**

| Модель | NRMSE | vs TokaMark Group 1 baseline (0.163) |
|--------|-------|--------------------------------------|
| LSTM Forecaster | **0.143** | Лучше baseline |
| Transformer Forecaster | **0.196** | Сравнимо |

### Готовые артефакты

| Артефакт | Путь | Статус |
|----------|------|--------|
| GitHub repo | https://github.com/sakiselev-ai/tokamak-analysis | ✅ public, MIT, CI |
| GitHub Release | https://github.com/sakiselev-ai/tokamak-analysis/releases/tag/v1.0.0 | ✅ v1.0.0 (обновить метрики в W12) |
| HTTPS сайт | https://tokamak-ai.ru | ✅ SSL Let's Encrypt |
| Препринт PDF | `paper/preprint.pdf` | ✅ 10 стр, LSTM AUC 0.9938 |
| Kaggle notebook | `notebooks/kaggle_disruption_prediction.ipynb` | ✅ Создан, ⚠️ не опубликован на kaggle.com |
| Презентация | `presentation/index.html` | ✅ 13 слайдов |
| Роспатент листинг | `rospatent/deposited_listing.txt` | ✅ 1666 строк |
| Инструкция ФИПС | `rospatent/README_FINAL.md` | ✅ |
| User guide | `docs/user-guide.md` | ✅ На русском |
| Deploy guide | `docs/deployment-guide.md` | ✅ На русском |
| API reference | `docs/api-reference.md` | ✅ 30 endpoints |
| Grafana dashboards | `monitoring/grafana/dashboards/` | ✅ 2 дашборда |
| Бэкап cron | VPS crontab | ✅ Daily 3:00 |

### NFR покрытие

| NFR | Требование | Статус |
|-----|-----------|--------|
| NFR-003 | Inference ≤50ms | ✅ 19ms |
| NFR-007 | TLS 1.3 | ✅ tokamak-ai.ru |
| NFR-008 | bcrypt ≥12 | ✅ |
| NFR-011 | Coverage ≥80% | ✅ 81% |
| NFR-013 | Бэкапы AES-256 | ✅ |
| NFR-014 | Сетевая изоляция | ✅ |
| NFR-017 | RPO 24ч | ✅ |

---

## ❗ КРИТИЧЕСКИЙ ПУТЬ — от пользователя

| # | Задача | Дедлайн | Примечание |
|---|--------|---------|------------|
| **1** | **Подать Роспатент** | 10-12 мая | Госпошлина 3000р, docs готовы в `rospatent/` |
| **2** | **Отправить письмо ЛаПлаз** | 07-10 мая | Шаблон в `Комплект_документов_Код_МИФИста.docx`, Часть 3 |
| **3** | **Опубликовать Kaggle notebook** | W3 | kaggle.com → New Notebook → Upload `notebooks/kaggle_disruption_prediction.ipynb` → Save & Run All → Make Public |

---

## W2 (06-12 мая) — ВЫПОЛНЕНО

| # | Задача | Статус |
|---|--------|--------|
| ✅ | GitHub repo создан + push | 31 коммит |
| ✅ | Домен tokamak-ai.ru | DNS настроен |
| ✅ | SSL Let's Encrypt | HTTPS работает |
| ✅ | Test coverage ≥80% | 81%, 205 тестов |
| ✅ | TokaMark forecasting модели | NRMSE 0.143 / 0.196 |
| ✅ | Полное обучение classification (50 эпох) | LSTM AUC 0.9938, RF 0.9677, Transformer 0.9415 |
| ✅ | Препринт обновлён финальными метриками | PDF 331 KB |
| ✅ | Release v1.0.0 обновлён | Финальные метрики |
| ✅ | Kaggle notebook создан | `notebooks/kaggle_disruption_prediction.ipynb` |
| ⚠️ | Kaggle notebook опубликован | **Пользователь**: upload на kaggle.com, Make Public |
| ⚠️ | Письмо ЛаПлаз | Не отправлено |
| ⚠️ | Роспатент | Не подано |

---

## W3 (13-19 мая)

| # | Задача | Кто | Время |
|---|--------|-----|-------|
| 1 | ~~Kaggle notebook~~ | ✅ Создан |
| 1a | **Опубликовать Kaggle notebook** | **Пользователь**: kaggle.com → Upload → Make Public |
| 2 | Скриншоты UI для Роспатент (5-10 шт) | Claude | 30 мин |
| 3 | ~~Обучение forecasting~~ | ✅ NRMSE 0.143 |
| 4 | Обновить презентацию TokaMark результатами | Claude | 30 мин |

---

## W4-W6 (20 мая — 09 июня)

| # | Задача | Кто |
|---|--------|-----|
| 5 | Полное обучение классификации LSTM (50 эпох, реальные данные) | Claude |
| 6 | TokaMark submission (когда лидерборд откроется, KDD Aug 2026) | Claude |
| 7 | DisruptionBench research + submission | Claude |
| 8 | Обновить препринт финальными метриками | Claude |

**Контрольная точка W6 (09 июня):** Целевые метрики достигнуты.

---

## W7-W10 (10 июня — 07 июля)

| # | Задача | Кто |
|---|--------|-----|
| 9 | Найти arXiv endorser (cs.LG / physics.plasm-ph) | **Пользователь** (через ЛаПлаз) |
| 10 | Загрузить препринт на arXiv | Claude/Пользователь |
| 11 | Demo video 90 сек | **Пользователь** |
| 12 | Запросить письмо-поддержку ЛаПлаз | **Пользователь** |
| 13 | Kaggle notebook опубликован | Claude |

**Контрольная точка W10 (07 июля):** arXiv загружен, endorser найден.

---

## W11-W12 (08-21 июля)

| # | Задача | Кто |
|---|--------|-----|
| 14 | ~~GitHub Release v1.0 + git tag~~ | ✅ Сделано (v1.0.0, 07 мая) |
| 14a | **Обновить GitHub Release v1.0.0** финальными метриками | Claude |
| 15 | Обновить README: badges, demo GIF, финальные метрики | Claude |
| 16 | Финальная компиляция препринта | Claude |
| 17 | Проверить статус Роспатент | **Пользователь** |
| 18 | Получить письмо-поддержку ЛаПлаз | **Пользователь** |

**Контрольная точка W12 (21 июля):** Release v1.0, все артефакты готовы.

---

## W13 (22-25 июля) — Подготовка к собеседованию

| # | Задача | Кто |
|---|--------|-----|
| 19 | Питчи 30с/2мин/5мин — 10+ раз вслух | **Пользователь** |
| 20 | Демо на ноутбуке 90 сек | **Пользователь** |
| 21 | FAQ (Часть 4.5 комплекта) | **Пользователь** |
| 22 | Подать заявление «Код МИФИста» | **Пользователь** |

**Технические работы в W13 не ведутся.**

---

## Риски

| Риск | Вероятность | Митигация |
|------|------------|-----------|
| Роспатент не успеет к 25.07 | Средняя | Подать ASAP, показать рег. номер заявки |
| Нет endorser для arXiv | Средняя | Zenodo как альтернатива (даёт DOI) |
| Нет ответа от ЛаПлаз | Низкая | Дублировать через приёмную МИФИ |
| TokaMark лидерборд не откроется | Средняя | Показать NRMSE результаты в препринте |

---

## Метрики проекта

| Метрика | Значение |
|---------|----------|
| Коммитов | 31 |
| Файлов | 213 |
| LOC | ~23,000 |
| Python LOC | 12,107 |
| API endpoints | 30 |
| ML модели | 5 (3 classification + 2 forecasting) |
| Тестов | 205 (139 backend + 45 ML + 21 E2E) |
| Coverage | 81% |
| Docker-сервисов | 12 |
| FR покрытие | 17/17 (100%) |
| GitHub | https://github.com/sakiselev-ai/tokamak-analysis |
| HTTPS | https://tokamak-ai.ru |
