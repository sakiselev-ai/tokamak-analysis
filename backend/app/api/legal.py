from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/legal", tags=["legal"])


@router.get("/privacy-policy")
async def privacy_policy():
    """Return privacy policy text (FR-015)."""
    return {
        "title": "Политика конфиденциальности",
        "version": "1.0",
        "effective_date": "2026-05-01",
        "content": {
            "data_controller": {
                "name": "НИЯУ МИФИ",
                "address": "г. Москва, Каширское шоссе, 31",
                "email": "dpo@mephi.ru",
            },
            "data_collected": [
                "Email (для аутентификации)",
                "Полное имя (для идентификации)",
                "IP-адрес (для аудита безопасности)",
                "Данные экспериментов (научные данные)",
            ],
            "purposes": [
                "Аутентификация и авторизация",
                "Анализ экспериментальных данных токамаков",
                "Журналирование действий для безопасности",
            ],
            "legal_basis": "Согласие субъекта (ст. 9 152-ФЗ)",
            "retention": "Данные хранятся до удаления аккаунта пользователем",
            "rights": [
                "Право на доступ к персональным данным (ст. 14 152-ФЗ)",
                "Право на исправление неточных данных (ст. 21 152-ФЗ)",
                "Право на удаление данных (ст. 21 152-ФЗ)",
                "Право на отзыв согласия (ст. 9 п. 2 152-ФЗ)",
            ],
            "data_protection": [
                "Шифрование данных при передаче (TLS 1.3)",
                "Шифрование данных при хранении (AES-256)",
                "Хэширование паролей (bcrypt, cost ≥ 12)",
                "Журнал аудита всех действий",
            ],
            "third_parties": "Данные не передаются третьим лицам",
            "contact": "По вопросам обработки ПДн: dpo@mephi.ru",
        },
    }


@router.get("/terms")
async def terms_of_service():
    """Return terms of service text."""
    return {
        "title": "Условия использования",
        "version": "1.0",
        "content": "Платформа предоставляется для научно-исследовательских целей...",
    }
