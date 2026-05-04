import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register(client: AsyncClient):
    res = await client.post("/api/v1/auth/register", json={
        "email": "user@mephi.ru",
        "password": "password123",
        "full_name": "Test Researcher",
        "consent_given": True,
    })
    assert res.status_code == 201
    data = res.json()
    assert data["email"] == "user@mephi.ru"
    assert data["role"] == "researcher"


@pytest.mark.asyncio
async def test_register_without_consent(client: AsyncClient):
    res = await client.post("/api/v1/auth/register", json={
        "email": "noconsent@mephi.ru",
        "password": "password123",
        "full_name": "No Consent User",
        "consent_given": False,
    })
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_register_duplicate(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={
        "email": "dup@mephi.ru",
        "password": "password123",
        "full_name": "User One",
        "consent_given": True,
    })
    res = await client.post("/api/v1/auth/register", json={
        "email": "dup@mephi.ru",
        "password": "password456",
        "full_name": "User Two",
        "consent_given": True,
    })
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_login(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={
        "email": "login@mephi.ru",
        "password": "password123",
        "full_name": "Login User",
        "consent_given": True,
    })
    res = await client.post("/api/v1/auth/login", json={
        "email": "login@mephi.ru",
        "password": "password123",
    })
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={
        "email": "wrong@mephi.ru",
        "password": "password123",
        "full_name": "Wrong User",
        "consent_given": True,
    })
    res = await client.post("/api/v1/auth/login", json={
        "email": "wrong@mephi.ru",
        "password": "wrongpassword",
    })
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_me(auth_client: AsyncClient):
    res = await auth_client.get("/api/v1/auth/me")
    assert res.status_code == 200
    data = res.json()
    assert data["email"] == "test@mephi.ru"
    assert data["full_name"] == "Test User"


@pytest.mark.asyncio
async def test_me_unauthorized(client: AsyncClient):
    res = await client.get("/api/v1/auth/me")
    assert res.status_code in (401, 403)  # No bearer token


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={
        "email": "refresh@mephi.ru",
        "password": "password123",
        "full_name": "Refresh User",
        "consent_given": True,
    })
    login_res = await client.post("/api/v1/auth/login", json={
        "email": "refresh@mephi.ru",
        "password": "password123",
    })
    refresh_token = login_res.json()["refresh_token"]

    res = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert res.status_code == 200
    assert "access_token" in res.json()


@pytest.mark.asyncio
async def test_password_too_short(client: AsyncClient):
    res = await client.post("/api/v1/auth/register", json={
        "email": "short@mephi.ru",
        "password": "123",
        "full_name": "Short Pass",
        "consent_given": True,
    })
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_export_data(auth_client: AsyncClient):
    res = await auth_client.get("/api/v1/auth/export-data")
    assert res.status_code == 200
    data = res.json()
    assert "profile" in data
    assert "experiments" in data
    assert "predictions" in data
    assert "model_runs" in data
    assert data["profile"]["email"] == "test@mephi.ru"


@pytest.mark.asyncio
async def test_delete_account(client: AsyncClient):
    # Register and login a user to delete
    await client.post("/api/v1/auth/register", json={
        "email": "delete@mephi.ru",
        "password": "password123",
        "full_name": "Delete User",
        "consent_given": True,
    })
    login_res = await client.post("/api/v1/auth/login", json={
        "email": "delete@mephi.ru",
        "password": "password123",
    })
    token = login_res.json()["access_token"]

    res = await client.delete(
        "/api/v1/auth/account",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200

    # Verify login fails after deletion
    login_res = await client.post("/api/v1/auth/login", json={
        "email": "delete@mephi.ru",
        "password": "password123",
    })
    assert login_res.status_code == 403  # Account disabled


@pytest.mark.asyncio
async def test_privacy_policy(client: AsyncClient):
    res = await client.get("/api/v1/legal/privacy-policy")
    assert res.status_code == 200
    data = res.json()
    assert data["title"] == "Политика конфиденциальности"
    assert "content" in data
    assert "rights" in data["content"]


@pytest.mark.asyncio
async def test_terms_of_service(client: AsyncClient):
    res = await client.get("/api/v1/legal/terms")
    assert res.status_code == 200
    data = res.json()
    assert data["title"] == "Условия использования"
