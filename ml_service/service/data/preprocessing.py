from __future__ import annotations

import numpy as np
from scipy import interpolate


def prepare_features(signals: dict[str, dict], sequence_length: int = 200) -> np.ndarray:
    """Convert raw signal data into feature matrix for ML models.

    Args:
        signals: dict mapping signal_name -> {timestamps, values}
        sequence_length: target number of time steps

    Returns:
        np.ndarray of shape (1, sequence_length, num_signals) for single shot,
        or (num_shots, sequence_length, num_signals) for batch.
    """
    signal_names = sorted(signals.keys())
    num_signals = len(signal_names)

    features = np.zeros((sequence_length, num_signals))

    for i, name in enumerate(signal_names):
        signal = signals[name]
        ts = np.array(signal["timestamps"], dtype=float)
        vals = np.array(signal["values"], dtype=float)

        # Remove invalid values
        valid = np.isfinite(ts) & np.isfinite(vals)
        if valid.sum() < 2:
            continue

        ts_clean = ts[valid]
        vals_clean = vals[valid]

        # Sort and remove duplicates
        sort_idx = np.argsort(ts_clean)
        ts_clean = ts_clean[sort_idx]
        vals_clean = vals_clean[sort_idx]

        # Resample to target length
        ts_target = np.linspace(ts_clean[0], ts_clean[-1], sequence_length)
        f = interpolate.interp1d(ts_clean, vals_clean, kind="linear", fill_value="extrapolate")
        features[:, i] = f(ts_target)

    # Normalize each signal to zero mean, unit variance
    mean = features.mean(axis=0, keepdims=True)
    std = features.std(axis=0, keepdims=True)
    std[std < 1e-10] = 1.0
    features = (features - mean) / std

    return features[np.newaxis, :, :]  # Add batch dimension


def prepare_batch(shots_data: list[dict], sequence_length: int = 200) -> np.ndarray:
    """Prepare batch of shots for training."""
    batch = []
    for shot in shots_data:
        features = prepare_features(shot["signals"], sequence_length)
        batch.append(features[0])  # Remove batch dim
    return np.stack(batch)
