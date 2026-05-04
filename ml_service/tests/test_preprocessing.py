import numpy as np
import pytest

from service.data.preprocessing import prepare_features, prepare_batch


def test_prepare_features_basic():
    signals = {
        "signal_a": {"timestamps": [0.0, 0.1, 0.2, 0.3], "values": [1.0, 2.0, 3.0, 4.0]},
        "signal_b": {"timestamps": [0.0, 0.1, 0.2, 0.3], "values": [10.0, 20.0, 30.0, 40.0]},
    }
    result = prepare_features(signals, sequence_length=10)
    assert result.shape == (1, 10, 2)
    assert np.isfinite(result).all()


def test_prepare_features_with_nans():
    signals = {
        "signal": {
            "timestamps": [0.0, 0.1, float("nan"), 0.3],
            "values": [1.0, float("nan"), 3.0, 4.0],
        },
    }
    result = prepare_features(signals, sequence_length=5)
    assert result.shape == (1, 5, 1)
    assert np.isfinite(result).all()


def test_prepare_features_empty():
    signals = {
        "signal": {"timestamps": [], "values": []},
    }
    result = prepare_features(signals, sequence_length=5)
    assert result.shape == (1, 5, 1)


def test_prepare_batch():
    shots = [
        {"signals": {"a": {"timestamps": [0.0, 0.1, 0.2], "values": [1.0, 2.0, 3.0]}}},
        {"signals": {"a": {"timestamps": [0.0, 0.1, 0.2], "values": [4.0, 5.0, 6.0]}}},
    ]
    result = prepare_batch(shots, sequence_length=5)
    assert result.shape == (2, 5, 1)
