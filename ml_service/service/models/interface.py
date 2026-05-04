from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np


class ModelInterface(ABC):
    """Unified interface for all ML models (ADR-004).

    All three models (Random Forest, bi-LSTM+attention, Transformer)
    implement this interface for interchangeability in the training
    and inference pipeline.
    """

    @abstractmethod
    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray | None = None,
        y_val: np.ndarray | None = None,
        hyperparams: dict | None = None,
        progress_callback: Any = None,
    ) -> dict:
        """Train the model.

        Returns dict with training metrics (loss, accuracy, auc, etc.).
        """
        ...

    @abstractmethod
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Return class labels (classification) or disruption probabilities over time."""
        ...

    @abstractmethod
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Return probability estimates for AUC-ROC and calibration curves."""
        ...

    @abstractmethod
    def save(self, path: str) -> None:
        """Serialize model to file (joblib for RF, TorchScript for PyTorch models)."""
        ...

    @abstractmethod
    def load(self, path: str) -> "ModelInterface":
        """Load model from file."""
        ...

    @abstractmethod
    def metadata(self) -> dict:
        """Return model metadata: architecture, hyperparameters, training date,
        validation metrics, dataset hash."""
        ...
