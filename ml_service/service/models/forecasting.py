from __future__ import annotations

import hashlib
import math
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

import numpy as np
import torch
import torch.nn as nn

from service.models.lstm_attention import AttentionLayer
from service.models.transformer import RotaryPositionalEncoding


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------


class ForecastingInterface(ABC):
    """Unified interface for time-series forecasting models (TokaMark benchmark).

    Unlike :class:`ModelInterface` which does binary classification,
    forecasting models predict future signal values given a past window.

    Input:  ``(batch, past_len, n_signals)``
    Output: ``(batch, future_len, n_signals)``
    """

    @abstractmethod
    def fit(
        self,
        X_past: np.ndarray,
        X_future: np.ndarray,
        X_val_past: np.ndarray | None = None,
        X_val_future: np.ndarray | None = None,
        hyperparams: dict | None = None,
        progress_callback: Any = None,
    ) -> dict:
        """Train the model on past -> future pairs.

        Returns dict with training metrics (loss history, epochs, etc.).
        """
        ...

    @abstractmethod
    def predict(self, X_past: np.ndarray) -> np.ndarray:
        """Predict future signal values.

        Args:
            X_past: ``(batch, past_len, n_signals)``

        Returns:
            ``(batch, future_len, n_signals)``
        """
        ...

    @abstractmethod
    def save(self, path: str) -> None:
        """Serialize model to file."""
        ...

    @abstractmethod
    def load(self, path: str) -> "ForecastingInterface":
        """Load model from file."""
        ...

    @abstractmethod
    def metadata(self) -> dict:
        """Return model metadata: architecture, hyperparameters, training date,
        validation metrics, dataset hash."""
        ...


# ---------------------------------------------------------------------------
# LSTM Forecaster — bi-LSTM encoder + linear decoder
# ---------------------------------------------------------------------------


class BiLSTMEncoderNet(nn.Module):
    """Bi-LSTM encoder with attention, outputting a fixed-size context vector."""

    def __init__(
        self,
        input_size: int = 10,
        hidden_size: int = 128,
        num_layers: int = 2,
        num_heads: int = 4,
        dropout: float = 0.3,
        bidirectional: bool = True,
    ):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            bidirectional=bidirectional,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.lstm_output_size = hidden_size * (2 if bidirectional else 1)
        self.attention = AttentionLayer(self.lstm_output_size, num_heads)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Encode past window into a context vector ``(batch, hidden)``."""
        lstm_out, _ = self.lstm(x)
        attn_out = self.attention(lstm_out)
        # Global average pooling over time
        return attn_out.mean(dim=1)


class LSTMForecasterNet(nn.Module):
    """Full LSTM forecaster: encoder + linear decoder."""

    def __init__(
        self,
        input_size: int = 10,
        hidden_size: int = 128,
        num_layers: int = 2,
        num_heads: int = 4,
        dropout: float = 0.3,
        bidirectional: bool = True,
        forecast_horizon: int = 50,
        n_signals: int = 10,
    ):
        super().__init__()
        self.forecast_horizon = forecast_horizon
        self.n_signals = n_signals

        self.encoder = BiLSTMEncoderNet(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            num_heads=num_heads,
            dropout=dropout,
            bidirectional=bidirectional,
        )
        enc_size = self.encoder.lstm_output_size
        self.decoder = nn.Sequential(
            nn.Linear(enc_size, enc_size),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(enc_size, forecast_horizon * n_signals),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass: ``(batch, past_len, input_size)`` -> ``(batch, horizon, n_signals)``."""
        context = self.encoder(x)
        flat = self.decoder(context)
        return flat.view(-1, self.forecast_horizon, self.n_signals)


class LSTMForecaster(ForecastingInterface):
    """bi-LSTM+attention forecaster for TokaMark Group 4 tasks.

    Encoder: same BiLSTM+Attention architecture as the classification model.
    Decoder: MLP mapping context vector to ``(forecast_horizon, n_signals)``.
    Loss: MSE.
    """

    def __init__(self, hyperparams: dict | None = None):
        self.hyperparams = hyperparams or {
            "input_size": 10,
            "hidden_size": 128,
            "num_layers": 2,
            "bidirectional": True,
            "dropout": 0.3,
            "attention_heads": 4,
            "forecast_horizon": 50,
            "n_signals": 10,
            "learning_rate": 1e-3,
            "batch_size": 32,
            "epochs": 50,
            "early_stopping_patience": 10,
            "weight_decay": 1e-4,
        }
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = self._build_net().to(self.device)
        self.metrics: dict = {}
        self.trained_at: str | None = None
        self.dataset_hash: str | None = None

    def _build_net(self) -> LSTMForecasterNet:
        return LSTMForecasterNet(
            input_size=self.hyperparams["input_size"],
            hidden_size=self.hyperparams["hidden_size"],
            num_layers=self.hyperparams["num_layers"],
            num_heads=self.hyperparams["attention_heads"],
            dropout=self.hyperparams["dropout"],
            bidirectional=self.hyperparams["bidirectional"],
            forecast_horizon=self.hyperparams["forecast_horizon"],
            n_signals=self.hyperparams["n_signals"],
        )

    def fit(
        self,
        X_past: np.ndarray,
        X_future: np.ndarray,
        X_val_past: np.ndarray | None = None,
        X_val_future: np.ndarray | None = None,
        hyperparams: dict | None = None,
        progress_callback: Any = None,
    ) -> dict:
        if hyperparams:
            self.hyperparams.update(hyperparams)
            self.model = self._build_net().to(self.device)

        self.dataset_hash = hashlib.sha256(
            X_past.tobytes()[:10000]
        ).hexdigest()[:16]

        X_p = torch.FloatTensor(X_past).to(self.device)
        X_f = torch.FloatTensor(X_future).to(self.device)

        dataset = torch.utils.data.TensorDataset(X_p, X_f)
        loader = torch.utils.data.DataLoader(
            dataset, batch_size=self.hyperparams["batch_size"], shuffle=True,
        )

        optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=self.hyperparams["learning_rate"],
            weight_decay=self.hyperparams["weight_decay"],
        )
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, factor=0.5, patience=5,
        )
        criterion = nn.MSELoss()

        best_val_loss = float("inf")
        patience_counter = 0
        history: dict[str, list[float]] = {"train_loss": [], "val_loss": []}

        self.model.train()
        for epoch in range(self.hyperparams["epochs"]):
            epoch_loss = 0.0
            for X_batch, Y_batch in loader:
                optimizer.zero_grad()
                output = self.model(X_batch)
                loss = criterion(output, Y_batch)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                optimizer.step()
                epoch_loss += loss.item()

            avg_loss = epoch_loss / len(loader)
            history["train_loss"].append(avg_loss)

            # Validation
            val_loss = avg_loss
            if X_val_past is not None and X_val_future is not None:
                self.model.eval()
                with torch.no_grad():
                    X_vp = torch.FloatTensor(X_val_past).to(self.device)
                    X_vf = torch.FloatTensor(X_val_future).to(self.device)
                    val_output = self.model(X_vp)
                    val_loss = criterion(val_output, X_vf).item()
                history["val_loss"].append(val_loss)
                self.model.train()

            scheduler.step(val_loss)

            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
            else:
                patience_counter += 1
                if patience_counter >= self.hyperparams["early_stopping_patience"]:
                    break

            if progress_callback:
                progress_callback(epoch + 1, self.hyperparams["epochs"], avg_loss, val_loss)

        self.trained_at = datetime.now(timezone.utc).isoformat()
        self.metrics = {
            "final_train_loss": history["train_loss"][-1],
            "best_val_loss": best_val_loss,
            "epochs_trained": len(history["train_loss"]),
            "history": history,
        }
        return self.metrics

    def predict(self, X_past: np.ndarray) -> np.ndarray:
        self.model.eval()
        with torch.no_grad():
            X_t = torch.FloatTensor(X_past).to(self.device)
            output = self.model(X_t)
            return output.cpu().numpy()

    def save(self, path: str) -> None:
        torch.save({
            "model_state_dict": self.model.state_dict(),
            "hyperparams": self.hyperparams,
            "metrics": self.metrics,
            "trained_at": self.trained_at,
            "dataset_hash": self.dataset_hash,
        }, path)

    def load(self, path: str) -> "LSTMForecaster":
        checkpoint = torch.load(path, map_location=self.device, weights_only=False)
        self.hyperparams = checkpoint["hyperparams"]
        self.model = self._build_net().to(self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.metrics = checkpoint["metrics"]
        self.trained_at = checkpoint["trained_at"]
        self.dataset_hash = checkpoint["dataset_hash"]
        return self

    def metadata(self) -> dict:
        return {
            "architecture": "LSTMForecaster",
            "hyperparameters": self.hyperparams,
            "trained_at": self.trained_at,
            "metrics": self.metrics,
            "dataset_hash": self.dataset_hash,
            "device": str(self.device),
            "total_parameters": sum(p.numel() for p in self.model.parameters()),
        }


# ---------------------------------------------------------------------------
# Transformer Forecaster — encoder-only + linear decoder
# ---------------------------------------------------------------------------


class TransformerForecasterNet(nn.Module):
    """Encoder-only Transformer for time-series forecasting."""

    def __init__(
        self,
        input_size: int = 10,
        d_model: int = 128,
        num_heads: int = 8,
        num_layers: int = 4,
        dim_feedforward: int = 512,
        dropout: float = 0.1,
        max_seq_len: int = 1000,
        forecast_horizon: int = 50,
        n_signals: int = 10,
    ):
        super().__init__()
        self.forecast_horizon = forecast_horizon
        self.n_signals = n_signals

        self.input_proj = nn.Linear(input_size, d_model)
        self.pos_encoding = RotaryPositionalEncoding(d_model, max_seq_len)
        self.dropout = nn.Dropout(dropout)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=num_heads,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            batch_first=True,
            activation="gelu",
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)

        # Pool over time then project to forecast
        self.decoder = nn.Sequential(
            nn.Linear(d_model, d_model),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model, forecast_horizon * n_signals),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """``(batch, past_len, input_size)`` -> ``(batch, horizon, n_signals)``."""
        x = self.input_proj(x)
        x = self.pos_encoding(x)
        x = self.dropout(x)
        x = self.transformer(x)

        # Global average pooling over time dimension
        pooled = x.mean(dim=1)
        flat = self.decoder(pooled)
        return flat.view(-1, self.forecast_horizon, self.n_signals)


class TransformerForecaster(ForecastingInterface):
    """Encoder-only Transformer forecaster for TokaMark Group 4 tasks.

    Uses the same positional encoding as the classification Transformer.
    Loss: MSE.
    """

    def __init__(self, hyperparams: dict | None = None):
        self.hyperparams = hyperparams or {
            "input_size": 10,
            "d_model": 128,
            "num_heads": 8,
            "num_layers": 4,
            "dim_feedforward": 512,
            "dropout": 0.1,
            "max_seq_len": 1000,
            "forecast_horizon": 50,
            "n_signals": 10,
            "learning_rate": 5e-4,
            "warmup_steps": 1000,
            "batch_size": 16,
            "epochs": 40,
            "early_stopping_patience": 8,
            "weight_decay": 1e-4,
        }
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = self._build_net().to(self.device)
        self.metrics: dict = {}
        self.trained_at: str | None = None
        self.dataset_hash: str | None = None

    def _build_net(self) -> TransformerForecasterNet:
        return TransformerForecasterNet(
            input_size=self.hyperparams["input_size"],
            d_model=self.hyperparams["d_model"],
            num_heads=self.hyperparams["num_heads"],
            num_layers=self.hyperparams["num_layers"],
            dim_feedforward=self.hyperparams["dim_feedforward"],
            dropout=self.hyperparams["dropout"],
            max_seq_len=self.hyperparams.get("max_seq_len", 1000),
            forecast_horizon=self.hyperparams["forecast_horizon"],
            n_signals=self.hyperparams["n_signals"],
        )

    def fit(
        self,
        X_past: np.ndarray,
        X_future: np.ndarray,
        X_val_past: np.ndarray | None = None,
        X_val_future: np.ndarray | None = None,
        hyperparams: dict | None = None,
        progress_callback: Any = None,
    ) -> dict:
        if hyperparams:
            self.hyperparams.update(hyperparams)
            self.model = self._build_net().to(self.device)

        self.dataset_hash = hashlib.sha256(
            X_past.tobytes()[:10000]
        ).hexdigest()[:16]

        X_p = torch.FloatTensor(X_past).to(self.device)
        X_f = torch.FloatTensor(X_future).to(self.device)

        dataset = torch.utils.data.TensorDataset(X_p, X_f)
        loader = torch.utils.data.DataLoader(
            dataset, batch_size=self.hyperparams["batch_size"], shuffle=True,
        )

        optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=self.hyperparams["learning_rate"],
            weight_decay=self.hyperparams["weight_decay"],
        )

        # Cosine annealing with warmup
        warmup = self.hyperparams["warmup_steps"]
        total_steps = len(loader) * self.hyperparams["epochs"]

        def lr_lambda(step: int) -> float:
            if step < warmup:
                return step / max(warmup, 1)
            progress = (step - warmup) / max(total_steps - warmup, 1)
            return 0.5 * (1 + math.cos(math.pi * progress))

        scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)
        criterion = nn.MSELoss()

        best_val_loss = float("inf")
        patience_counter = 0
        history: dict[str, list[float]] = {"train_loss": [], "val_loss": []}

        self.model.train()
        for epoch in range(self.hyperparams["epochs"]):
            epoch_loss = 0.0
            for X_batch, Y_batch in loader:
                optimizer.zero_grad()
                output = self.model(X_batch)
                loss = criterion(output, Y_batch)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                optimizer.step()
                scheduler.step()
                epoch_loss += loss.item()

            avg_loss = epoch_loss / len(loader)
            history["train_loss"].append(avg_loss)

            val_loss = avg_loss
            if X_val_past is not None and X_val_future is not None:
                self.model.eval()
                with torch.no_grad():
                    X_vp = torch.FloatTensor(X_val_past).to(self.device)
                    X_vf = torch.FloatTensor(X_val_future).to(self.device)
                    val_output = self.model(X_vp)
                    val_loss = criterion(val_output, X_vf).item()
                history["val_loss"].append(val_loss)
                self.model.train()

            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
            else:
                patience_counter += 1
                if patience_counter >= self.hyperparams["early_stopping_patience"]:
                    break

            if progress_callback:
                progress_callback(epoch + 1, self.hyperparams["epochs"], avg_loss, val_loss)

        self.trained_at = datetime.now(timezone.utc).isoformat()
        self.metrics = {
            "final_train_loss": history["train_loss"][-1],
            "best_val_loss": best_val_loss,
            "epochs_trained": len(history["train_loss"]),
            "history": history,
        }
        return self.metrics

    def predict(self, X_past: np.ndarray) -> np.ndarray:
        self.model.eval()
        with torch.no_grad():
            X_t = torch.FloatTensor(X_past).to(self.device)
            output = self.model(X_t)
            return output.cpu().numpy()

    def save(self, path: str) -> None:
        torch.save({
            "model_state_dict": self.model.state_dict(),
            "hyperparams": self.hyperparams,
            "metrics": self.metrics,
            "trained_at": self.trained_at,
            "dataset_hash": self.dataset_hash,
        }, path)

    def load(self, path: str) -> "TransformerForecaster":
        checkpoint = torch.load(path, map_location=self.device, weights_only=False)
        self.hyperparams = checkpoint["hyperparams"]
        self.model = self._build_net().to(self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.metrics = checkpoint["metrics"]
        self.trained_at = checkpoint["trained_at"]
        self.dataset_hash = checkpoint["dataset_hash"]
        return self

    def metadata(self) -> dict:
        return {
            "architecture": "TransformerForecaster",
            "hyperparameters": self.hyperparams,
            "trained_at": self.trained_at,
            "metrics": self.metrics,
            "dataset_hash": self.dataset_hash,
            "device": str(self.device),
            "total_parameters": sum(p.numel() for p in self.model.parameters()),
        }
