from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import structlog

logger = structlog.get_logger()


@dataclass
class TokamakDataset:
    """Train / val / test container with sliding-window support.

    Attributes:
        X_train, y_train: Training data and labels.
        X_val, y_val: Validation data and labels.
        X_test, y_test: Test data and labels.
        feature_mean: Per-feature mean used for normalization.
        feature_std: Per-feature std used for normalization.
    """

    X_train: np.ndarray
    y_train: np.ndarray
    X_val: np.ndarray
    y_val: np.ndarray
    X_test: np.ndarray
    y_test: np.ndarray
    feature_mean: np.ndarray
    feature_std: np.ndarray

    # ---- helpers ----

    @property
    def n_features(self) -> int:
        return self.X_train.shape[-1]

    @property
    def seq_len(self) -> int:
        return self.X_train.shape[1] if self.X_train.ndim == 3 else 0

    def flat_train(self) -> tuple[np.ndarray, np.ndarray]:
        """Return X_train flattened to 2-D (for tree models)."""
        X = self.X_train.reshape(self.X_train.shape[0], -1)
        return X, self.y_train

    def flat_val(self) -> tuple[np.ndarray, np.ndarray]:
        X = self.X_val.reshape(self.X_val.shape[0], -1)
        return X, self.y_val

    def flat_test(self) -> tuple[np.ndarray, np.ndarray]:
        X = self.X_test.reshape(self.X_test.shape[0], -1)
        return X, self.y_test


# ---------------------------------------------------------------------------
# Sliding window extraction
# ---------------------------------------------------------------------------

def extract_windows(
    data: np.ndarray,
    window_size: int,
    stride: int = 1,
) -> np.ndarray:
    """Extract sliding windows from a 2-D array ``(time_steps, features)``.

    Returns:
        np.ndarray of shape ``(n_windows, window_size, features)``.
    """
    if data.ndim != 2:
        raise ValueError(f"Expected 2-D input, got shape {data.shape}")
    n_steps, n_feat = data.shape
    if n_steps < window_size:
        raise ValueError(
            f"Data length {n_steps} < window_size {window_size}"
        )
    indices = np.arange(0, n_steps - window_size + 1, stride)
    windows = np.stack([data[i : i + window_size] for i in indices])
    return windows


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def normalize_features(
    X: np.ndarray,
    mean: np.ndarray | None = None,
    std: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Zero-mean, unit-std normalization along the sample axis.

    If *mean* / *std* are ``None`` they are computed from *X*.

    Returns:
        ``(X_normalized, mean, std)``
    """
    original_shape = X.shape
    # Flatten to 2-D for stats: (total_timesteps, features)
    X_flat = X.reshape(-1, X.shape[-1])

    if mean is None:
        mean = X_flat.mean(axis=0)
    if std is None:
        std = X_flat.std(axis=0)

    std_safe = std.copy()
    std_safe[std_safe < 1e-10] = 1.0

    X_normed = (X_flat - mean) / std_safe
    return X_normed.reshape(original_shape), mean, std


# ---------------------------------------------------------------------------
# Dataset builders
# ---------------------------------------------------------------------------

def _split_indices(
    n: int,
    ratios: tuple[float, float, float] = (0.8, 0.1, 0.1),
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Randomly split indices into train / val / test."""
    rng = np.random.RandomState(seed)
    perm = rng.permutation(n)
    n_train = int(n * ratios[0])
    n_val = int(n * ratios[1])
    return perm[:n_train], perm[n_train : n_train + n_val], perm[n_train + n_val :]


def build_dataset(
    X: np.ndarray,
    y: np.ndarray,
    ratios: tuple[float, float, float] = (0.8, 0.1, 0.1),
    seed: int = 42,
) -> TokamakDataset:
    """Split pre-built arrays into a :class:`TokamakDataset` with normalization."""
    train_idx, val_idx, test_idx = _split_indices(len(X), ratios, seed)

    X_train_raw = X[train_idx]
    X_val_raw = X[val_idx]
    X_test_raw = X[test_idx]

    # Fit normalization on train only
    X_train, mean, std = normalize_features(X_train_raw)
    X_val, _, _ = normalize_features(X_val_raw, mean, std)
    X_test, _, _ = normalize_features(X_test_raw, mean, std)

    return TokamakDataset(
        X_train=X_train.astype(np.float32),
        y_train=y[train_idx].astype(np.float32),
        X_val=X_val.astype(np.float32),
        y_val=y[val_idx].astype(np.float32),
        X_test=X_test.astype(np.float32),
        y_test=y[test_idx].astype(np.float32),
        feature_mean=mean,
        feature_std=std,
    )


def get_sample_dataset(
    n_samples: int = 200,
    seq_len: int = 200,
    n_features: int = 39,
    task: Literal["classification", "disruption_prediction"] = "classification",
    seed: int = 42,
) -> TokamakDataset:
    """Generate a synthetic dataset for testing and development.

    For *classification* the label is based on a threshold on the mean
    signal energy.  For *disruption_prediction* a ramp-up pattern is
    injected into positive samples.

    Returns:
        A ready-to-use :class:`TokamakDataset`.
    """
    rng = np.random.RandomState(seed)
    X = rng.randn(n_samples, seq_len, n_features).astype(np.float32)

    if task == "disruption_prediction":
        # Positive class: inject a ramp that simulates growing instability
        n_pos = n_samples // 2
        ramp = np.linspace(0, 3, seq_len).reshape(1, seq_len, 1)
        X[:n_pos] += ramp
        y = np.zeros(n_samples, dtype=np.float32)
        y[:n_pos] = 1.0
    else:
        # Classification based on signal energy
        energy = np.mean(X ** 2, axis=(1, 2))
        y = (energy > np.median(energy)).astype(np.float32)

    # Shuffle
    perm = rng.permutation(n_samples)
    X = X[perm]
    y = y[perm]

    return build_dataset(X, y, seed=seed)
