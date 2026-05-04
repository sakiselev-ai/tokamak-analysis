from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score

from service.models.interface import ModelInterface


class RandomForestModel(ModelInterface):
    """Random Forest baseline model (ADR-004 §3.2.1).

    Used as baseline for classification (FR-004).
    CPU inference ≤ 5ms. No GPU required.
    """

    RF_PARAMS = {
        "n_estimators", "max_depth", "min_samples_split", "min_samples_leaf",
        "class_weight", "max_features", "random_state", "n_jobs",
        "criterion", "min_weight_fraction_leaf", "max_leaf_nodes",
        "min_impurity_decrease", "bootstrap", "oob_score", "verbose",
        "warm_start", "ccp_alpha", "max_samples",
    }

    def __init__(self, hyperparams: dict | None = None):
        defaults = {
            "n_estimators": 200,
            "max_depth": 20,
            "min_samples_split": 5,
            "min_samples_leaf": 2,
            "class_weight": "balanced",
            "max_features": "sqrt",
            "random_state": 42,
            "n_jobs": -1,
        }
        if hyperparams:
            # Only keep params that RF actually accepts
            filtered = {k: v for k, v in hyperparams.items() if k in self.RF_PARAMS}
            defaults.update(filtered)
        self.hyperparams = defaults
        self.model = RandomForestClassifier(**self.hyperparams)
        self.metrics: dict = {}
        self.trained_at: str | None = None
        self.dataset_hash: str | None = None

    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray | None = None,
        y_val: np.ndarray | None = None,
        hyperparams: dict | None = None,
        progress_callback: Any = None,
    ) -> dict:
        if hyperparams:
            self.hyperparams.update(hyperparams)
            self.model = RandomForestClassifier(**self.hyperparams)

        self.dataset_hash = hashlib.sha256(
            X_train.tobytes() + y_train.tobytes()
        ).hexdigest()[:16]

        self.model.fit(X_train, y_train)
        self.trained_at = datetime.now(timezone.utc).isoformat()

        self.metrics = {"train_accuracy": accuracy_score(y_train, self.model.predict(X_train))}

        if X_val is not None and y_val is not None:
            y_pred = self.model.predict(X_val)
            y_proba = self.model.predict_proba(X_val)

            self.metrics.update({
                "val_accuracy": accuracy_score(y_val, y_pred),
                "val_f1": f1_score(y_val, y_pred, average="weighted"),
            })
            if y_proba.shape[1] == 2:
                self.metrics["val_auc_roc"] = roc_auc_score(y_val, y_proba[:, 1])

        return self.metrics

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.model.predict(X)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        return self.model.predict_proba(X)

    def save(self, path: str) -> None:
        artifact = {
            "model": self.model,
            "hyperparams": self.hyperparams,
            "metrics": self.metrics,
            "trained_at": self.trained_at,
            "dataset_hash": self.dataset_hash,
        }
        joblib.dump(artifact, path)

    def load(self, path: str) -> "RandomForestModel":
        artifact = joblib.load(path)
        self.model = artifact["model"]
        self.hyperparams = artifact["hyperparams"]
        self.metrics = artifact["metrics"]
        self.trained_at = artifact["trained_at"]
        self.dataset_hash = artifact["dataset_hash"]
        return self

    def metadata(self) -> dict:
        return {
            "architecture": "RandomForest",
            "hyperparameters": self.hyperparams,
            "trained_at": self.trained_at,
            "metrics": self.metrics,
            "dataset_hash": self.dataset_hash,
            "feature_importances": (
                self.model.feature_importances_.tolist()
                if hasattr(self.model, "feature_importances_")
                else None
            ),
        }
