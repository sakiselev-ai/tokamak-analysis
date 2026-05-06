from __future__ import annotations

import structlog
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

logger = structlog.get_logger()


async def log_action(
    db: AsyncSession,
    action: str,
    resource: str,
    user_id: int | None = None,
    details: dict | None = None,
    request: Request | None = None,
) -> None:
    """Write an audit record and commit it immediately.

    Uses the caller's session bind to create a dedicated session so the audit
    record is persisted even if the caller's transaction rolls back later.
    Falls back to the caller's own session when the bind is unavailable
    (e.g. during tests with SQLite).
    """
    ip_address = None
    if request:
        ip_address = request.client.host if request.client else None

    kwargs = dict(
        user_id=user_id,
        action=action,
        resource=resource,
        details_json=details,
        ip_address=ip_address,
    )

    try:
        # Use a separate session so the audit INSERT is committed independently.
        from app.database import async_session

        async with async_session() as audit_db:
            audit_db.add(AuditLog(**kwargs))
            await audit_db.commit()
    except Exception:
        # Fallback: write via the caller's session (committed by get_db later).
        try:
            db.add(AuditLog(**kwargs))
            await db.flush()
        except Exception:
            await logger.awarning(
                "audit_log_failed",
                action=action,
                resource=resource,
                user_id=user_id,
            )
