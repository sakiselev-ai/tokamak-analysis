from __future__ import annotations

from dataclasses import dataclass

import numpy as np


# ---------------------------------------------------------------------------
# Forecasting dataset container
# ---------------------------------------------------------------------------


@dataclass
class ForecastingDataset:
    """Train / val / test container for time-series forecasting.

    Each split stores matched ``(past, future)`` pairs:

    - ``X_past``:  ``(n, past_len, n_features)``
    - ``X_future``: ``(n, future_len, n_features)``
    """

    X_train_past: np.ndarray
    X_train_future: np.ndarray
    X_val_past: np.ndarray
    X_val_future: np.ndarray
    X_test_past: np.ndarray
    X_test_future: np.ndarray

    @property
    def n_features(self) -> int:
        return self.X_train_past.shape[-1]

    @property
    def past_len(self) -> int:
        return self.X_train_past.shape[1]

    @property
    def future_len(self) -> int:
        return self.X_train_future.shape[1]


# ---------------------------------------------------------------------------
# Sliding-window dataset builder
# ---------------------------------------------------------------------------


def prepare_forecasting_dataset(
    X: np.ndarray,
    past_len: int = 20,
    future_len: int = 10,
    ratios: tuple[float, float, float] = (0.8, 0.1, 0.1),
    seed: int = 42,
) -> ForecastingDataset:
    """Create past/future sliding-window pairs from shot data.

    Args:
        X: ``(n_shots, seq_len, n_features)`` array of time-series data.
        past_len: Number of timesteps in the past (input) window.
        future_len: Number of timesteps in the future (target) window.
        ratios: Train / val / test split ratios.
        seed: Random seed for reproducibility.

    Returns:
        A :class:`ForecastingDataset` with matched past/future pairs
        split into train, val, and test sets.

    Raises:
        ValueError: If ``seq_len < past_len + future_len``.
    """
    if X.ndim != 3:
        raise ValueError(f"Expected 3-D input (n_shots, seq_len, n_features), got shape {X.shape}")

    n_shots, seq_len, n_features = X.shape
    window_total = past_len + future_len

    if seq_len < window_total:
        raise ValueError(
            f"seq_len ({seq_len}) must be >= past_len + future_len ({window_total})"
        )

    # Extract sliding windows from each shot
    all_past = []
    all_future = []
    for i in range(n_shots):
        for t in range(seq_len - window_total + 1):
            all_past.append(X[i, t : t + past_len])
            all_future.append(X[i, t + past_len : t + window_total])

    X_past = np.array(all_past, dtype=np.float32)
    X_future = np.array(all_future, dtype=np.float32)

    # Shuffle and split
    rng = np.random.RandomState(seed)
    n = len(X_past)
    perm = rng.permutation(n)
    X_past = X_past[perm]
    X_future = X_future[perm]

    n_train = int(n * ratios[0])
    n_val = int(n * ratios[1])

    return ForecastingDataset(
        X_train_past=X_past[:n_train],
        X_train_future=X_future[:n_train],
        X_val_past=X_past[n_train : n_train + n_val],
        X_val_future=X_future[n_train : n_train + n_val],
        X_test_past=X_past[n_train + n_val :],
        X_test_future=X_future[n_train + n_val :],
    )


# ---------------------------------------------------------------------------
# NRMSE metric
# ---------------------------------------------------------------------------


def compute_nrmse(
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> dict:
    """Compute Normalized Root Mean Square Error (TokaMark metric).

    NRMSE = RMSE / std(y_true) per signal, then averaged across signals.
    An NRMSE < 1.0 means the model is better than predicting the mean.

    Args:
        y_true: ``(n_samples, future_len, n_signals)`` ground truth.
        y_pred: ``(n_samples, future_len, n_signals)`` predictions.

    Returns:
        Dict with ``"nrmse_per_signal"`` (list), ``"nrmse_mean"`` (float),
        ``"rmse_per_signal"`` (list), and ``"std_per_signal"`` (list).
    """
    y_true = np.asarray(y_true, dtype=np.float64)
    y_pred = np.asarray(y_pred, dtype=np.float64)

    if y_true.shape != y_pred.shape:
        raise ValueError(
            f"Shape mismatch: y_true {y_true.shape} vs y_pred {y_pred.shape}"
        )

    # Flatten samples and time: (n_samples * future_len, n_signals)
    n_signals = y_true.shape[-1]
    y_true_flat = y_true.reshape(-1, n_signals)
    y_pred_flat = y_pred.reshape(-1, n_signals)

    # Per-signal RMSE and std
    mse_per_signal = np.mean((y_true_flat - y_pred_flat) ** 2, axis=0)
    rmse_per_signal = np.sqrt(mse_per_signal)
    std_per_signal = np.std(y_true_flat, axis=0)

    # Avoid division by zero for constant signals
    std_safe = std_per_signal.copy()
    std_safe[std_safe < 1e-10] = 1.0

    nrmse_per_signal = rmse_per_signal / std_safe

    return {
        "nrmse_per_signal": nrmse_per_signal.tolist(),
        "nrmse_mean": float(np.mean(nrmse_per_signal)),
        "rmse_per_signal": rmse_per_signal.tolist(),
        "std_per_signal": std_per_signal.tolist(),
    }
