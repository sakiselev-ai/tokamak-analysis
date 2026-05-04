from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings

# Convert async URL to sync for Celery workers
# Lazy init to avoid import-time errors when psycopg2 is not available (e.g. in tests)
_sync_engine = None
_SyncSessionFactory = None


def _get_sync_engine():
    global _sync_engine
    if _sync_engine is None:
        sync_url = settings.database_url.replace("+asyncpg", "").replace("+aiosqlite", "")
        _sync_engine = create_engine(sync_url)
    return _sync_engine


def SyncSession():
    global _SyncSessionFactory
    if _SyncSessionFactory is None:
        _SyncSessionFactory = sessionmaker(_get_sync_engine())
    return _SyncSessionFactory()
