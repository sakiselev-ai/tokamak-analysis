from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from jose import jwt
from sqlalchemy import select

from app.config import settings
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token
from app.models.audit_log import AuditLog


@pytest.mark.asyncio
async def test_expired_access_token(client: AsyncClient):
    """An expired JWT access token should be rejected with 401."""
    expired_payload = {
        "sub": "1",
        "role": "researcher",
        "type": "access",
        "exp": datetime.now(timezone.utc) - timedelta(minutes=5),
    }
    token = jwt.encode(expired_payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    client.headers["Authorization"] = f"Bearer {token}"
    res = await client.get("/api/v1/auth/me")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_invalid_token_signature(client: AsyncClient):
    """A token signed with the wrong key should be rejected."""
    payload = {
        "sub": "1",
        "role": "researcher",
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
    }
    token = jwt.encode(payload, "wrong_secret_key", algorithm=settings.jwt_algorithm)
    client.headers["Authorization"] = f"Bearer {token}"
    res = await client.get("/api/v1/auth/me")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_malformed_token(client: AsyncClient):
    """A completely malformed token should be rejected."""
    client.headers["Authorization"] = "Bearer not.a.valid.jwt.token"
    res = await client.get("/api/v1/auth/me")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_cannot_access_protected_endpoints(client: AsyncClient):
    """Using a refresh token (wrong type) for auth should be rejected."""
    # Register a user first
    await client.post("/api/v1/auth/register", json={
        "email": "refreshonly@mephi.ru",
        "password": "password123",
        "full_name": "Refresh Only",
    })
    login_res = await client.post("/api/v1/auth/login", json={
        "email": "refreshonly@mephi.ru",
        "password": "password123",
    })
    refresh_token = login_res.json()["refresh_token"]

    # Try to use refresh token as access token
    client.headers["Authorization"] = f"Bearer {refresh_token}"
    res = await client.get("/api/v1/auth/me")
    assert res.status_code == 401
    assert "token type" in res.json()["detail"].lower() or "invalid" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_access_token_cannot_refresh(client: AsyncClient):
    """Using an access token for the refresh endpoint should be rejected."""
    await client.post("/api/v1/auth/register", json={
        "email": "accessonly@mephi.ru",
        "password": "password123",
        "full_name": "Access Only",
    })
    login_res = await client.post("/api/v1/auth/login", json={
        "email": "accessonly@mephi.ru",
        "password": "password123",
    })
    access_token = login_res.json()["access_token"]

    res = await client.post("/api/v1/auth/refresh", json={"refresh_token": access_token})
    assert res.status_code == 401


def test_password_hashing():
    """Hashed password should verify correctly against the original."""
    password = "secure_password_123"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed) is True


def test_password_verification_fails_for_wrong_password():
    """Wrong password should not verify."""
    hashed = hash_password("correct_password")
    assert verify_password("wrong_password", hashed) is False


def test_different_hashes_for_same_password():
    """Bcrypt should produce different hashes for the same input (salt)."""
    password = "same_password"
    hash1 = hash_password(password)
    hash2 = hash_password(password)
    assert hash1 != hash2
    assert verify_password(password, hash1) is True
    assert verify_password(password, hash2) is True


def test_create_access_token_structure():
    """Access token should contain correct claims."""
    token = create_access_token(user_id=42, role="researcher")
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    assert payload["sub"] == "42"
    assert payload["role"] == "researcher"
    assert payload["type"] == "access"
    assert "exp" in payload


def test_create_refresh_token_structure():
    """Refresh token should contain correct claims."""
    token = create_refresh_token(user_id=42)
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    assert payload["sub"] == "42"
    assert payload["type"] == "refresh"
    assert "exp" in payload


@pytest.mark.asyncio
async def test_audit_log_on_login(client: AsyncClient):
    """A successful login should create an audit log entry."""
    from app.database import get_db
    from app.main import app as fastapi_app

    await client.post("/api/v1/auth/register", json={
        "email": "audit@mephi.ru",
        "password": "password123",
        "full_name": "Audit User",
    })
    await client.post("/api/v1/auth/login", json={
        "email": "audit@mephi.ru",
        "password": "password123",
    })

    # Query the database directly for audit logs
    async for db in fastapi_app.dependency_overrides[get_db]():
        result = await db.execute(
            select(AuditLog).where(AuditLog.action == "login")
        )
        logs = result.scalars().all()
        assert len(logs) >= 1
        login_log = logs[-1]
        assert login_log.action == "login"
        assert login_log.resource == "auth"
        assert login_log.user_id is not None


@pytest.mark.asyncio
async def test_audit_log_on_failed_login(client: AsyncClient):
    """A failed login attempt should create an audit log entry."""
    from app.database import get_db
    from app.main import app as fastapi_app

    await client.post("/api/v1/auth/register", json={
        "email": "failaudit@mephi.ru",
        "password": "password123",
        "full_name": "Fail Audit",
    })
    await client.post("/api/v1/auth/login", json={
        "email": "failaudit@mephi.ru",
        "password": "wrongpassword",
    })

    async for db in fastapi_app.dependency_overrides[get_db]():
        result = await db.execute(
            select(AuditLog).where(AuditLog.action == "login_failed")
        )
        logs = result.scalars().all()
        assert len(logs) >= 1
        fail_log = logs[-1]
        assert fail_log.action == "login_failed"
        assert fail_log.resource == "auth"
        assert fail_log.details_json is not None
        assert fail_log.details_json["email"] == "failaudit@mephi.ru"
