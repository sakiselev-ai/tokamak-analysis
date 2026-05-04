from __future__ import annotations

import numpy as np
from scipy import interpolate


def preprocess_timeseries(
    timestamps: list[float],
    values: list[float],
    target_length: int | None = None,
    fill_method: str = "interpolate",
) -> tuple[list[float], list[float]]:
    """Normalize and interpolate time series data.

    - Removes NaN/inf values
    - Interpolates gaps
    - Normalizes to [0, 1] range
    - Optionally resamples to target_length
    """
    ts = np.array(timestamps, dtype=float)
    vals = np.array(values, dtype=float)

    # Remove NaN and inf
    valid_mask = np.isfinite(ts) & np.isfinite(vals)
    if valid_mask.sum() < 2:
        return timestamps, values

    ts_clean = ts[valid_mask]
    vals_clean = vals[valid_mask]

    # Sort by time
    sort_idx = np.argsort(ts_clean)
    ts_clean = ts_clean[sort_idx]
    vals_clean = vals_clean[sort_idx]

    # Interpolate missing values if needed
    if len(ts_clean) < len(ts):
        f = interpolate.interp1d(ts_clean, vals_clean, kind="linear", fill_value="extrapolate")
        ts_full = ts[np.isfinite(ts)]
        ts_full.sort()
        vals_interp = f(ts_full)
        ts_clean = ts_full
        vals_clean = vals_interp

    # Resample to target length
    if target_length and len(ts_clean) != target_length:
        ts_new = np.linspace(ts_clean[0], ts_clean[-1], target_length)
        f = interpolate.interp1d(ts_clean, vals_clean, kind="linear", fill_value="extrapolate")
        vals_clean = f(ts_new)
        ts_clean = ts_new

    # Normalize to [0, 1]
    val_min = vals_clean.min()
    val_max = vals_clean.max()
    if val_max - val_min > 1e-10:
        vals_clean = (vals_clean - val_min) / (val_max - val_min)

    return ts_clean.tolist(), vals_clean.tolist()
