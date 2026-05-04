import numpy as np
import pytest

from app.services.preprocessing import preprocess_timeseries


def test_preprocess_basic():
    ts = [0.0, 0.1, 0.2, 0.3, 0.4]
    vals = [0.0, 1.0, 2.0, 3.0, 4.0]
    result_ts, result_vals = preprocess_timeseries(ts, vals)
    assert len(result_ts) == 5
    assert len(result_vals) == 5
    # Should be normalized to [0, 1]
    assert min(result_vals) >= -0.01
    assert max(result_vals) <= 1.01


def test_preprocess_with_nans():
    ts = [0.0, 0.1, float("nan"), 0.3, 0.4]
    vals = [0.0, 1.0, 2.0, float("nan"), 4.0]
    result_ts, result_vals = preprocess_timeseries(ts, vals)
    assert all(np.isfinite(v) for v in result_vals)


def test_preprocess_resample():
    ts = [0.0, 0.5, 1.0]
    vals = [0.0, 5.0, 10.0]
    result_ts, result_vals = preprocess_timeseries(ts, vals, target_length=10)
    assert len(result_ts) == 10
    assert len(result_vals) == 10


def test_preprocess_constant():
    ts = [0.0, 0.1, 0.2]
    vals = [5.0, 5.0, 5.0]
    result_ts, result_vals = preprocess_timeseries(ts, vals)
    # Constant signal: normalization should handle gracefully
    assert len(result_vals) == 3
