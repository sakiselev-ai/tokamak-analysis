from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient

MOCK_SIGNALS = {
    "signal_a": {"timestamps": [0.0, 0.1, 0.2], "values": [1.0, 2.0, 3.0], "units": "eV", "description": "Test"},
    "signal_b": {"timestamps": [0.0, 0.1, 0.2], "values": [4.0, 5.0, 6.0], "units": "m", "description": "Test2"},
}


@pytest.mark.asyncio
async def test_load_experiment(auth_client: AsyncClient):
    with patch("app.api.experiments.FairMastClient") as MockClient:
        instance = MockClient.return_value
        instance.load_shot = AsyncMock(return_value=MOCK_SIGNALS)
        res = await auth_client.post("/api/v1/experiments/load", json={"shot_id": 30420, "source": "mast"})
        assert res.status_code == 201
        data = res.json()
        assert data["shot_id"] == 30420
        assert data["status"] == "preprocessed"
        assert len(data["timeseries"]) == 2


@pytest.mark.asyncio
async def test_list_experiments(auth_client: AsyncClient):
    """List experiments returns empty list initially."""
    res = await auth_client.get("/api/v1/experiments/")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 0
    assert data["experiments"] == []


@pytest.mark.asyncio
async def test_list_experiments_after_load(auth_client: AsyncClient):
    """After loading an experiment, listing should include it."""
    with patch("app.api.experiments.FairMastClient") as MockClient:
        instance = MockClient.return_value
        instance.load_shot = AsyncMock(return_value=MOCK_SIGNALS)
        await auth_client.post("/api/v1/experiments/load", json={"shot_id": 30420, "source": "mast"})

    res = await auth_client.get("/api/v1/experiments/")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["experiments"][0]["shot_id"] == 30420


@pytest.mark.asyncio
async def test_get_experiment(auth_client: AsyncClient):
    """Retrieve a single experiment by ID."""
    with patch("app.api.experiments.FairMastClient") as MockClient:
        instance = MockClient.return_value
        instance.load_shot = AsyncMock(return_value=MOCK_SIGNALS)
        load_res = await auth_client.post("/api/v1/experiments/load", json={"shot_id": 30420, "source": "mast"})
        experiment_id = load_res.json()["id"]

    res = await auth_client.get(f"/api/v1/experiments/{experiment_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["shot_id"] == 30420
    assert data["id"] == experiment_id
    assert len(data["timeseries"]) == 2


@pytest.mark.asyncio
async def test_get_experiment_not_found(auth_client: AsyncClient):
    """Requesting a non-existent experiment returns 404."""
    res = await auth_client.get("/api/v1/experiments/99999")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_get_timeseries(auth_client: AsyncClient):
    """Retrieve timeseries data for a loaded experiment."""
    with patch("app.api.experiments.FairMastClient") as MockClient:
        instance = MockClient.return_value
        instance.load_shot = AsyncMock(return_value=MOCK_SIGNALS)
        load_res = await auth_client.post("/api/v1/experiments/load", json={"shot_id": 30420, "source": "mast"})
        experiment_id = load_res.json()["id"]

    res = await auth_client.get(f"/api/v1/experiments/{experiment_id}/timeseries")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 2
    param_names = {ts["parameter_name"] for ts in data}
    assert param_names == {"signal_a", "signal_b"}
    for ts in data:
        assert "timestamps" in ts
        assert "values" in ts


@pytest.mark.asyncio
async def test_export_csv(auth_client: AsyncClient):
    """Export experiment data as CSV."""
    with patch("app.api.experiments.FairMastClient") as MockClient:
        instance = MockClient.return_value
        instance.load_shot = AsyncMock(return_value=MOCK_SIGNALS)
        load_res = await auth_client.post("/api/v1/experiments/load", json={"shot_id": 30420, "source": "mast"})
        experiment_id = load_res.json()["id"]

    res = await auth_client.get(f"/api/v1/experiments/{experiment_id}/export?format=csv")
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    content = res.text
    assert "parameter" in content
    assert "timestamp" in content
    assert "value" in content


@pytest.mark.asyncio
async def test_export_json(auth_client: AsyncClient):
    """Export experiment data as JSON."""
    with patch("app.api.experiments.FairMastClient") as MockClient:
        instance = MockClient.return_value
        instance.load_shot = AsyncMock(return_value=MOCK_SIGNALS)
        load_res = await auth_client.post("/api/v1/experiments/load", json={"shot_id": 30420, "source": "mast"})
        experiment_id = load_res.json()["id"]

    res = await auth_client.get(f"/api/v1/experiments/{experiment_id}/export?format=json")
    assert res.status_code == 200
    assert "application/json" in res.headers["content-type"]
    data = res.json()
    assert data["shot_id"] == 30420
    assert "signals" in data
    assert "signal_a" in data["signals"]
    assert "signal_b" in data["signals"]


@pytest.mark.asyncio
async def test_unauthenticated(client: AsyncClient):
    """All experiment endpoints should reject unauthenticated requests."""
    endpoints = [
        ("GET", "/api/v1/experiments/"),
        ("POST", "/api/v1/experiments/load"),
        ("GET", "/api/v1/experiments/1"),
        ("GET", "/api/v1/experiments/1/timeseries"),
        ("GET", "/api/v1/experiments/1/export"),
    ]
    for method, url in endpoints:
        if method == "GET":
            res = await client.get(url)
        else:
            res = await client.post(url, json={"shot_id": 30420, "source": "mast"})
        assert res.status_code in (401, 403), f"Expected 403 for {method} {url}, got {res.status_code}"
