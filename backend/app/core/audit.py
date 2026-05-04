from __future__ import annotations

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


async def log_action(
    db: AsyncSession,
    action: str,
    resource: str,
    user_id: int | None = None,
    details: dict | None = None,
    request: Request | None = None,
) -> None:
    ip_address = None
    if request:
        ip_address = request.client.host if request.client else None

    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource=resource,
        details_json=details,
        ip_address=ip_address,
    )
    db.add(entry)
    await db.flush()
