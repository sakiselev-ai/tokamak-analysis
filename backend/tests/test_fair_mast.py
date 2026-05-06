from __future__ import annotations

import pytest
import numpy as np
from unittest.mock import MagicMock, patch, PropertyMock
import xarray as xr


@pytest.fixture
def mock_s3():
    """Mock s3fs.S3FileSystem."""
    with patch("app.services.fair_mast.s3fs.S3FileSystem") as MockS3:
        s3 = MockS3.return_value
        yield s3


@pytest.fixture
def mock_s3map():
    """Mock s3fs.S3Map."""
    with patch("app.services.fair_mast.s3fs.S3Map") as MockMap:
        yield MockMap


def _make_dataset(var_name: str = "data", time_dim: str = "time", n_points: int = 5):
    """Create a simple xarray Dataset mimicking a FAIR-MAST signal."""
    times = np.linspace(0, 1, n_points)
    values = np.random.randn(n_points)
    ds = xr.Dataset(
        {var_name: (time_dim, values, {"units": "eV", "long_name": "Test Signal"})},
        coords={time_dim: times},
    )
    return ds


@pytest.mark.asyncio
async def test_load_shot_success(mock_s3, mock_s3map):
    """load_shot should return signal data when S3 has valid zarr data."""
    mock_s3.ls.return_value = ["mast/level1/shots/30420.zarr/signal_a"]

    ds = _make_dataset("data", "time", 5)
    with patch("app.services.fair_mast.xr.open_zarr", return_value=ds):
        from app.services.fair_mast import FairMastClient
        client = FairMastClient.__new__(FairMastClient)
        client.s3 = mock_s3
        client.bucket = "mast"

        signals = await client.load_shot(30420)

    assert len(signals) == 1
    key = list(signals.keys())[0]
    assert "timestamps" in signals[key]
    assert "values" in signals[key]
    assert "units" in signals[key]
    assert len(signals[key]["timestamps"]) == 5


@pytest.mark.asyncio
async def test_load_shot_not_found(mock_s3):
    """load_shot should raise ValueError when shot doesn't exist."""
    mock_s3.ls.side_effect = FileNotFoundError("Not found")

    from app.services.fair_mast import FairMastClient
    client = FairMastClient.__new__(FairMastClient)
    client.s3 = mock_s3
    client.bucket = "mast"

    with pytest.raises(ValueError, match="not found"):
        await client.load_shot(99999)


@pytest.mark.asyncio
async def test_load_shot_no_valid_signals(mock_s3, mock_s3map):
    """load_shot should raise ValueError when no valid signals are found."""
    mock_s3.ls.return_value = ["mast/level1/shots/30420.zarr/bad_signal"]

    # Make open_zarr raise an exception for the signal
    with patch("app.services.fair_mast.xr.open_zarr", side_effect=Exception("corrupt")):
        from app.services.fair_mast import FairMastClient
        client = FairMastClient.__new__(FairMastClient)
        client.s3 = mock_s3
        client.bucket = "mast"

        with pytest.raises(ValueError, match="No valid signals"):
            await client.load_shot(30420)


@pytest.mark.asyncio
async def test_load_shot_nan_replacement(mock_s3, mock_s3map):
    """load_shot should replace NaN/inf values with 0.0."""
    mock_s3.ls.return_value = ["mast/level1/shots/30420.zarr/signal_a"]

    # Create dataset with NaN values
    ds = xr.Dataset(
        {"data": ("time", [1.0, float("nan"), float("inf")], {"units": "eV", "long_name": "Test"})},
        coords={"time": [0.0, float("nan"), 0.2]},
    )

    with patch("app.services.fair_mast.xr.open_zarr", return_value=ds):
        from app.services.fair_mast import FairMastClient
        client = FairMastClient.__new__(FairMastClient)
        client.s3 = mock_s3
        client.bucket = "mast"

        signals = await client.load_shot(30420)

    key = list(signals.keys())[0]
    # NaN/inf should be replaced with 0.0
    assert 0.0 in signals[key]["timestamps"]
    assert 0.0 in signals[key]["values"]


@pytest.mark.asyncio
async def test_load_shot_multiple_signals(mock_s3, mock_s3map):
    """load_shot should handle multiple signals from the same shot."""
    mock_s3.ls.return_value = [
        "mast/level1/shots/30420.zarr/signal_a",
        "mast/level1/shots/30420.zarr/signal_b",
    ]

    ds = _make_dataset("data", "time", 3)
    with patch("app.services.fair_mast.xr.open_zarr", return_value=ds):
        from app.services.fair_mast import FairMastClient
        client = FairMastClient.__new__(FairMastClient)
        client.s3 = mock_s3
        client.bucket = "mast"

        signals = await client.load_shot(30420)

    assert len(signals) == 2


@pytest.mark.asyncio
async def test_list_shots_success(mock_s3):
    """list_shots should return sorted shot IDs."""
    mock_s3.ls.return_value = [
        "mast/level1/shots/30420.zarr",
        "mast/level1/shots/11700.zarr",
        "mast/level1/shots/12000.zarr",
    ]

    from app.services.fair_mast import FairMastClient
    client = FairMastClient.__new__(FairMastClient)
    client.s3 = mock_s3
    client.bucket = "mast"

    shots = await client.list_shots(limit=10)
    assert shots == [11700, 12000, 30420]


@pytest.mark.asyncio
async def test_list_shots_with_limit(mock_s3):
    """list_shots should respect the limit parameter."""
    mock_s3.ls.return_value = [
        "mast/level1/shots/30420.zarr",
        "mast/level1/shots/11700.zarr",
        "mast/level1/shots/12000.zarr",
    ]

    from app.services.fair_mast import FairMastClient
    client = FairMastClient.__new__(FairMastClient)
    client.s3 = mock_s3
    client.bucket = "mast"

    shots = await client.list_shots(limit=2)
    assert len(shots) == 2


@pytest.mark.asyncio
async def test_list_shots_with_invalid_entries(mock_s3):
    """list_shots should skip non-numeric entries."""
    mock_s3.ls.return_value = [
        "mast/level1/shots/30420.zarr",
        "mast/level1/shots/readme.txt",
    ]

    from app.services.fair_mast import FairMastClient
    client = FairMastClient.__new__(FairMastClient)
    client.s3 = mock_s3
    client.bucket = "mast"

    shots = await client.list_shots()
    assert shots == [30420]


@pytest.mark.asyncio
async def test_list_shots_error(mock_s3):
    """list_shots should return empty list on error."""
    mock_s3.ls.side_effect = Exception("Connection failed")

    from app.services.fair_mast import FairMastClient
    client = FairMastClient.__new__(FairMastClient)
    client.s3 = mock_s3
    client.bucket = "mast"

    shots = await client.list_shots()
    assert shots == []
