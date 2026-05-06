from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient


@pytest_asyncio.fixture
async def admin_client(client: AsyncClient) -> AsyncClient:
    """Register and login as admin user."""
    await client.post("/api/v1/auth/register", json={
        "email": "admin_test@mephi.ru",
        "password": "adminpassword123",
        "full_name": "Admin User",
        "role": "admin",
        "consent_given": True,
    })
    res = await client.post("/api/v1/auth/login", json={
        "email": "admin_test@mephi.ru",
        "password": "adminpassword123",
    })
    token = res.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client


@pytest.mark.asyncio
async def test_admin_unauthorized(auth_client: AsyncClient):
    """Researcher should not access admin endpoints (TC-011)."""
    res = await auth_client.get("/api/v1/admin/users")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_list_users(admin_client: AsyncClient):
    """Admin should be able to list users."""
    res = await admin_client.get("/api/v1/admin/users")
    assert res.status_code == 200
    users = res.json()
    assert isinstance(users, list)
    assert len(users) >= 1  # at least the admin user
    emails = [u["email"] for u in users]
    assert "admin_test@mephi.ru" in emails


@pytest.mark.asyncio
async def test_list_users_pagination(admin_client: AsyncClient):
    """Admin list users should support skip/limit."""
    res = await admin_client.get("/api/v1/admin/users?skip=0&limit=1")
    assert res.status_code == 200
    assert len(res.json()) <= 1


@pytest.mark.asyncio
async def test_update_user_role(admin_client: AsyncClient, client: AsyncClient):
    """Admin should be able to change a user's role."""
    # Create a regular user
    await client.post("/api/v1/auth/register", json={
        "email": "role_change@mephi.ru",
        "password": "password123",
        "full_name": "Role User",
        "consent_given": True,
    })
    # Find the user in the list
    res = await admin_client.get("/api/v1/admin/users")
    users = res.json()
    target_user = [u for u in users if u["email"] == "role_change@mephi.ru"][0]

    # Change role to engineer
    res = await admin_client.put(
        f"/api/v1/admin/users/{target_user['id']}/role?role=engineer"
    )
    assert res.status_code == 200
    assert res.json()["new_role"] == "engineer"


@pytest.mark.asyncio
async def test_update_role_user_not_found(admin_client: AsyncClient):
    """Update role for non-existent user should return 404."""
    res = await admin_client.put("/api/v1/admin/users/99999/role?role=engineer")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_deactivate_user(admin_client: AsyncClient, client: AsyncClient):
    """Admin should be able to deactivate a user."""
    # Create a user to deactivate
    await client.post("/api/v1/auth/register", json={
        "email": "deactivate_me@mephi.ru",
        "password": "password123",
        "full_name": "Deactivate User",
        "consent_given": True,
    })
    res = await admin_client.get("/api/v1/admin/users")
    users = res.json()
    target_user = [u for u in users if u["email"] == "deactivate_me@mephi.ru"][0]

    res = await admin_client.put(f"/api/v1/admin/users/{target_user['id']}/deactivate")
    assert res.status_code == 200
    assert res.json()["message"] == "User deactivated"


@pytest.mark.asyncio
async def test_deactivate_self(admin_client: AsyncClient):
    """Admin should not be able to deactivate themselves."""
    # Get own user id
    me_res = await admin_client.get("/api/v1/auth/me")
    my_id = me_res.json()["id"]

    res = await admin_client.put(f"/api/v1/admin/users/{my_id}/deactivate")
    assert res.status_code == 400
    assert "yourself" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_deactivate_user_not_found(admin_client: AsyncClient):
    """Deactivate non-existent user should return 404."""
    res = await admin_client.put("/api/v1/admin/users/99999/deactivate")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_admin_unauthenticated(client: AsyncClient):
    """All admin endpoints should reject unauthenticated requests."""
    res = await client.get("/api/v1/admin/users")
    assert res.status_code in (401, 403)
