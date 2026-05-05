import numpy as np
import pytest

from service.data.preprocessing import prepare_features, prepare_batch, sliding_window_labels
from service.data.fair_mast_loader import make_disruption_labels


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


# --- sliding_window_labels tests ---


def test_sliding_window_labels_basic():
    """Labels within 30ms of end should be 1."""
    timestamps = np.linspace(0, 0.1, 100)  # 100 steps over 100ms
    probs = np.zeros(100)
    labels = sliding_window_labels(probs, timestamps, threshold=0.5, warning_ms=30.0)

    # Last 30ms = last ~30 steps should be labelled 1
    assert labels[-1] == 1.0
    assert labels[0] == 0.0
    # Steps at t >= 0.07s should be 1 (disruption at 0.1s, window = 30ms)
    assert labels[timestamps >= 0.07].sum() > 0
    assert (labels[timestamps < 0.07] == 0.0).all()


def test_sliding_window_labels_empty():
    labels = sliding_window_labels(np.array([]), np.array([]), threshold=0.5)
    assert len(labels) == 0


def test_sliding_window_labels_single_step():
    labels = sliding_window_labels(np.array([0.5]), np.array([0.0]), threshold=0.5)
    assert labels[0] == 1.0  # Only step is within window


def test_sliding_window_labels_custom_window():
    timestamps = np.linspace(0, 1.0, 1000)  # 1 second, 1ms steps
    probs = np.zeros(1000)
    labels = sliding_window_labels(probs, timestamps, threshold=0.5, warning_ms=50.0)
    # Last 50ms = last ~50 steps
    assert labels[-1] == 1.0
    assert (labels[timestamps >= 0.95] == 1.0).all()
    assert (labels[timestamps < 0.95] == 0.0).all()


# --- make_disruption_labels tests ---


def test_make_disruption_labels_mixed():
    shot_ids = [1, 2, 3, 4]
    disruption_times = {1: 0.5, 2: None, 3: 0.3, 4: None}
    labels = make_disruption_labels(shot_ids, disruption_times)
    np.testing.assert_array_equal(labels, [1.0, 0.0, 1.0, 0.0])
    assert labels.dtype == np.float32


def test_make_disruption_labels_all_stable():
    shot_ids = [10, 11, 12]
    disruption_times = {10: None, 11: None, 12: None}
    labels = make_disruption_labels(shot_ids, disruption_times)
    np.testing.assert_array_equal(labels, [0.0, 0.0, 0.0])


def test_make_disruption_labels_all_disrupted():
    shot_ids = [20, 21]
    disruption_times = {20: 0.1, 21: 0.2}
    labels = make_disruption_labels(shot_ids, disruption_times)
    np.testing.assert_array_equal(labels, [1.0, 1.0])


def test_make_disruption_labels_missing_key():
    """Missing shot_id in disruption_times should default to stable."""
    shot_ids = [30, 31]
    disruption_times = {30: 0.5}  # 31 is missing
    labels = make_disruption_labels(shot_ids, disruption_times)
    np.testing.assert_array_equal(labels, [1.0, 0.0])
