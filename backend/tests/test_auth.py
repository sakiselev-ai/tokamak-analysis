import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register(client: AsyncClient):
    res = await client.post("/api/v1/auth/register", json={
        "email": "user@mephi.ru",
        "password": "password123",
        "full_name": "Test Researcher",
    })
    assert res.status_code == 201
    data = res.json()
    assert data["email"] == "user@mephi.ru"
    assert data["role"] == "researcher"


@pytest.mark.asyncio
async def test_register_duplicate(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={
        "email": "dup@mephi.ru",
        "password": "password123",
        "full_name": "User One",
    })
    res = await client.post("/api/v1/auth/register", json={
        "email": "dup@mephi.ru",
        "password": "password456",
        "full_name": "User Two",
    })
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_login(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={
        "email": "login@mephi.ru",
        "password": "password123",
        "full_name": "Login User",
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
    })
    assert res.status_code == 422
