from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient

MOCK_SIGNALS = {
    "signal_a": {"timestamps": [0.0, 0.1, 0.2], "values": [1.0, 2.0, 3.0], "units": "eV", "description": "Test"},
    "signal_b": {"timestamps": [0.0, 0.1, 0.2], "values": [4.0, 5.0, 6.0], "units": "m", "description": "Test2"},
}


async def _load_experiment(auth_client: AsyncClient, shot_id: int = 30420) -> dict:
    """Load a test experiment and return the full JSON response."""
    with patch("app.api.experiments.FairMastClient") as MockClient:
        instance = MockClient.return_value
        instance.load_shot = AsyncMock(return_value=MOCK_SIGNALS)
        res = await auth_client.post("/api/v1/experiments/load", json={"shot_id": shot_id, "source": "mast"})
        return res.json()


# ────────────────────────────────────────────────────────────────
# Load experiment
# ────────────────────────────────────────────────────────────────


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
async def test_load_experiment_failure(auth_client: AsyncClient):
    """When FairMastClient.load_shot raises, should return 502."""
    with patch("app.api.experiments.FairMastClient") as MockClient:
        instance = MockClient.return_value
        instance.load_shot = AsyncMock(side_effect=ValueError("Shot not found"))
        res = await auth_client.post("/api/v1/experiments/load", json={"shot_id": 99999, "source": "mast"})
        assert res.status_code == 502
        assert "Failed to load shot" in res.json()["detail"]


# ────────────────────────────────────────────────────────────────
# List experiments (including pagination)
# ────────────────────────────────────────────────────────────────


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
    await _load_experiment(auth_client)

    res = await auth_client.get("/api/v1/experiments/")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["experiments"][0]["shot_id"] == 30420


@pytest.mark.asyncio
async def test_list_experiments_pagination(auth_client: AsyncClient):
    """Pagination: skip and limit should work correctly."""
    # Load 3 experiments
    await _load_experiment(auth_client, shot_id=10001)
    await _load_experiment(auth_client, shot_id=10002)
    await _load_experiment(auth_client, shot_id=10003)

    # Get all
    res = await auth_client.get("/api/v1/experiments/?skip=0&limit=10")
    assert res.status_code == 200
    assert res.json()["total"] == 3
    assert len(res.json()["experiments"]) == 3

    # Get first only
    res = await auth_client.get("/api/v1/experiments/?skip=0&limit=1")
    assert res.status_code == 200
    assert len(res.json()["experiments"]) == 1
    assert res.json()["total"] == 3

    # Skip first two
    res = await auth_client.get("/api/v1/experiments/?skip=2&limit=10")
    assert res.status_code == 200
    assert len(res.json()["experiments"]) == 1


# ────────────────────────────────────────────────────────────────
# Get experiment
# ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_experiment(auth_client: AsyncClient):
    """Retrieve a single experiment by ID."""
    loaded = await _load_experiment(auth_client)
    experiment_id = loaded["id"]

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


# ────────────────────────────────────────────────────────────────
# Timeseries
# ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_timeseries(auth_client: AsyncClient):
    """Retrieve timeseries data for a loaded experiment."""
    loaded = await _load_experiment(auth_client)
    experiment_id = loaded["id"]

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
async def test_get_timeseries_not_found(auth_client: AsyncClient):
    """Timeseries for non-existent experiment should return 404."""
    res = await auth_client.get("/api/v1/experiments/99999/timeseries")
    assert res.status_code == 404


# ────────────────────────────────────────────────────────────────
# Export CSV / JSON
# ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_export_csv(auth_client: AsyncClient):
    """Export experiment data as CSV."""
    loaded = await _load_experiment(auth_client)
    experiment_id = loaded["id"]

    res = await auth_client.get(f"/api/v1/experiments/{experiment_id}/export?format=csv")
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    content = res.text
    assert "parameter" in content
    assert "timestamp" in content
    assert "value" in content
    # Check that we have data rows
    lines = content.strip().split("\n")
    assert len(lines) > 1  # header + data


@pytest.mark.asyncio
async def test_export_json(auth_client: AsyncClient):
    """Export experiment data as JSON."""
    loaded = await _load_experiment(auth_client)
    experiment_id = loaded["id"]

    res = await auth_client.get(f"/api/v1/experiments/{experiment_id}/export?format=json")
    assert res.status_code == 200
    assert "application/json" in res.headers["content-type"]
    data = res.json()
    assert data["shot_id"] == 30420
    assert "signals" in data
    assert "signal_a" in data["signals"]
    assert "signal_b" in data["signals"]


@pytest.mark.asyncio
async def test_export_not_found(auth_client: AsyncClient):
    """Export for non-existent experiment should return 404."""
    res = await auth_client.get("/api/v1/experiments/99999/export?format=csv")
    assert res.status_code == 404


# ────────────────────────────────────────────────────────────────
# Batch load
# ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_batch_load_success(auth_client: AsyncClient):
    """Batch load should load at least one experiment successfully."""
    with patch("app.api.experiments.FairMastClient") as MockClient:
        instance = MockClient.return_value
        instance.load_shot = AsyncMock(return_value=MOCK_SIGNALS)
        res = await auth_client.post("/api/v1/experiments/batch-load", json={
            "shot_ids": [10001],
            "source": "mast",
        })

    assert res.status_code == 201
    data = res.json()
    assert data["total_loaded"] == 1
    assert len(data["experiments"]) == 1
    assert data["failed"] == []


@pytest.mark.asyncio
async def test_batch_load_partial_failure(auth_client: AsyncClient):
    """Batch load with some failures should report them."""
    call_count = 0

    async def _side_effect(shot_id):
        nonlocal call_count
        call_count += 1
        if shot_id == 99999:
            raise ValueError("Shot not found")
        return MOCK_SIGNALS

    with patch("app.api.experiments.FairMastClient") as MockClient:
        instance = MockClient.return_value
        instance.load_shot = AsyncMock(side_effect=_side_effect)
        res = await auth_client.post("/api/v1/experiments/batch-load", json={
            "shot_ids": [10001, 99999],
            "source": "mast",
        })

    assert res.status_code == 201
    data = res.json()
    assert data["total_loaded"] == 1
    assert len(data["failed"]) == 1
    assert data["failed"][0]["shot_id"] == 99999


@pytest.mark.asyncio
async def test_batch_load_unauthenticated(client: AsyncClient):
    """Batch load should reject unauthenticated requests."""
    res = await client.post("/api/v1/experiments/batch-load", json={
        "shot_ids": [10001],
        "source": "mast",
    })
    assert res.status_code in (401, 403)


# ────────────────────────────────────────────────────────────────
# Unauthenticated
# ────────────────────────────────────────────────────────────────


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
