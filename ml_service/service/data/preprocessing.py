from __future__ import annotations

import numpy as np


def prepare_features(signals: dict[str, dict], sequence_length: int = 200, max_features: int = 10) -> np.ndarray:
    """Convert raw signal data into feature matrix for ML models.

    Args:
        signals: dict mapping signal_name -> {timestamps, values}
        sequence_length: target number of time steps
        max_features: maximum number of signal features (pad/truncate)

    Returns:
        np.ndarray of shape (1, sequence_length, max_features).
    """
    # Pre-filter: only take the first max_features sorted signals that have
    # enough valid data points, avoiding work on unusable signals.
    signal_names: list[str] = []
    for name in sorted(signals.keys()):
        if len(signal_names) >= max_features:
            break
        sig = signals[name]
        ts_raw = sig.get("timestamps")
        vals_raw = sig.get("values")
        if ts_raw is None or vals_raw is None:
            continue
        # Quick length check before allocating arrays
        if len(ts_raw) < 2 or len(vals_raw) < 2:
            continue
        signal_names.append(name)

    features = np.zeros((sequence_length, max_features))

    for i, name in enumerate(signal_names):
        signal = signals[name]
        ts = np.asarray(signal["timestamps"], dtype=np.float64)
        vals = np.asarray(signal["values"], dtype=np.float64)

        # Remove invalid values
        valid = np.isfinite(ts) & np.isfinite(vals)
        if valid.sum() < 2:
            continue

        ts_clean = ts[valid]
        vals_clean = vals[valid]

        # Sort by timestamp
        sort_idx = np.argsort(ts_clean)
        ts_clean = ts_clean[sort_idx]
        vals_clean = vals_clean[sort_idx]

        # Resample to target length using numpy (much faster than scipy interp1d)
        ts_target = np.linspace(ts_clean[0], ts_clean[-1], sequence_length)
        features[:, i] = np.interp(ts_target, ts_clean, vals_clean)

    # Normalize each signal to zero mean, unit variance (vectorized)
    mean = features.mean(axis=0, keepdims=True)
    std = features.std(axis=0, keepdims=True)
    std[std < 1e-10] = 1.0
    features = (features - mean) / std

    return features[np.newaxis, :, :]  # Add batch dimension


def sliding_window_labels(
    probabilities: np.ndarray,
    timestamps: np.ndarray,
    threshold: float,
    warning_ms: float = 30.0,
) -> np.ndarray:
    """Generate sliding-window disruption labels for a time series.

    Implements the 30ms warning window requirement (FR-005): a time step
    is labelled positive (1) if a disruption occurs within ``warning_ms``
    milliseconds *after* that time step.

    Args:
        probabilities: 1-D array of disruption probabilities (unused for
            label generation but kept for API symmetry; the caller may
            pass raw signal data or probabilities).
        timestamps: 1-D array of timestamps in **seconds**.
        threshold: Not used for label generation (reserved for downstream
            thresholding of predictions).
        warning_ms: Warning window in milliseconds. Time steps within this
            window before a disruption are labelled 1. Default 30ms per
            FR-005.

    Returns:
        1-D float32 array of binary labels (same length as *timestamps*).
        1.0 if the time step falls within the warning window before
        the end of the shot (assumed disruption time = last timestamp),
        0.0 otherwise.
    """
    timestamps = np.asarray(timestamps, dtype=np.float64)
    n = len(timestamps)
    labels = np.zeros(n, dtype=np.float32)

    if n == 0:
        return labels

    warning_s = warning_ms / 1000.0
    disruption_time = timestamps[-1]

    # Label time steps within the warning window before disruption
    window_start = disruption_time - warning_s
    labels[timestamps >= window_start] = 1.0

    return labels


def prepare_batch(shots_data: list[dict], sequence_length: int = 200) -> np.ndarray:
    """Prepare batch of shots for training."""
    batch = []
    for shot in shots_data:
        features = prepare_features(shot["signals"], sequence_length)
        batch.append(features[0])  # Remove batch dim
    return np.stack(batch)
