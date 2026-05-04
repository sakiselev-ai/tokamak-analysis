from __future__ import annotations

import hashlib
import math
from datetime import datetime, timezone
from typing import Any

import numpy as np
import torch
import torch.nn as nn

from service.models.interface import ModelInterface


class RotaryPositionalEncoding(nn.Module):
    """Rotary Position Embedding (RoPE)."""

    def __init__(self, d_model: int, max_len: int = 5000):
        super().__init__()
        position = torch.arange(max_len).unsqueeze(1).float()
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe = torch.zeros(max_len, d_model)
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer("pe", pe.unsqueeze(0))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.pe[:, : x.size(1)]


class AutoregressiveTransformer(nn.Module):
    """Autoregressive Transformer for disruption prediction (ADR-004 §3.2.3).

    Based on Spangher et al. (arXiv:2401.00051).
    Causal attention mask for autoregressive prediction.
    """

    def __init__(
        self,
        input_size: int = 39,
        d_model: int = 128,
        num_heads: int = 8,
        num_layers: int = 4,
        dim_feedforward: int = 512,
        dropout: float = 0.1,
        max_seq_len: int = 1000,
    ):
        super().__init__()
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
        self.output_head = nn.Sequential(
            nn.Linear(d_model, d_model // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model // 2, 1),
        )

    def _generate_causal_mask(self, sz: int, device: torch.device) -> torch.Tensor:
        return torch.triu(torch.ones(sz, sz, device=device) * float("-inf"), diagonal=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.input_proj(x)
        x = self.pos_encoding(x)
        x = self.dropout(x)

        mask = self._generate_causal_mask(x.size(1), x.device)
        x = self.transformer(x, mask=mask)

        # Output per-timestep predictions
        return self.output_head(x).squeeze(-1)


class TransformerModel(ModelInterface):
    """Autoregressive Transformer for disruption prediction.

    Experimental model (ADR-004). GPU inference ≤ 50ms on T4.
    """

    def __init__(self, hyperparams: dict | None = None):
        self.hyperparams = hyperparams or {
            "input_size": 39,
            "d_model": 128,
            "num_heads": 8,
            "num_layers": 4,
            "dim_feedforward": 512,
            "dropout": 0.1,
            "sequence_length": 500,
            "learning_rate": 5e-4,
            "warmup_steps": 1000,
            "batch_size": 16,
            "epochs": 40,
            "early_stopping_patience": 8,
            "weight_decay": 1e-4,
        }
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = AutoregressiveTransformer(
            input_size=self.hyperparams["input_size"],
            d_model=self.hyperparams["d_model"],
            num_heads=self.hyperparams["num_heads"],
            num_layers=self.hyperparams["num_layers"],
            dim_feedforward=self.hyperparams["dim_feedforward"],
            dropout=self.hyperparams["dropout"],
            max_seq_len=self.hyperparams["sequence_length"],
        ).to(self.device)
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

        self.dataset_hash = hashlib.sha256(X_train.tobytes()[:10000]).hexdigest()[:16]

        X_t = torch.FloatTensor(X_train).to(self.device)
        y_t = torch.FloatTensor(y_train).to(self.device)

        dataset = torch.utils.data.TensorDataset(X_t, y_t)
        loader = torch.utils.data.DataLoader(
            dataset, batch_size=self.hyperparams["batch_size"], shuffle=True
        )

        optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=self.hyperparams["learning_rate"],
            weight_decay=self.hyperparams["weight_decay"],
        )

        # Cosine annealing with warmup
        def lr_lambda(step):
            if step < self.hyperparams["warmup_steps"]:
                return step / max(self.hyperparams["warmup_steps"], 1)
            progress = (step - self.hyperparams["warmup_steps"]) / max(
                len(loader) * self.hyperparams["epochs"] - self.hyperparams["warmup_steps"], 1
            )
            return 0.5 * (1 + math.cos(math.pi * progress))

        scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)
        criterion = nn.BCEWithLogitsLoss()

        best_val_loss = float("inf")
        patience_counter = 0
        history = {"train_loss": [], "val_loss": []}

        self.model.train()
        for epoch in range(self.hyperparams["epochs"]):
            epoch_loss = 0.0
            for X_batch, y_batch in loader:
                optimizer.zero_grad()
                output = self.model(X_batch)
                # Use last timestep prediction for classification
                if output.dim() > 1:
                    output = output[:, -1]
                loss = criterion(output, y_batch)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                optimizer.step()
                scheduler.step()
                epoch_loss += loss.item()

            avg_loss = epoch_loss / len(loader)
            history["train_loss"].append(avg_loss)

            val_loss = avg_loss
            if X_val is not None and y_val is not None:
                self.model.eval()
                with torch.no_grad():
                    X_v = torch.FloatTensor(X_val).to(self.device)
                    y_v = torch.FloatTensor(y_val).to(self.device)
                    val_output = self.model(X_v)
                    if val_output.dim() > 1:
                        val_output = val_output[:, -1]
                    val_loss = criterion(val_output, y_v).item()
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
        }
        return self.metrics

    def predict(self, X: np.ndarray) -> np.ndarray:
        self.model.eval()
        with torch.no_grad():
            X_t = torch.FloatTensor(X).to(self.device)
            output = torch.sigmoid(self.model(X_t))
            if output.dim() > 1:
                output = output[:, -1]
            return (output.cpu().numpy() > 0.5).astype(int)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        self.model.eval()
        with torch.no_grad():
            X_t = torch.FloatTensor(X).to(self.device)
            output = torch.sigmoid(self.model(X_t))
            if output.dim() > 1:
                output = output[:, -1]
            proba = output.cpu().numpy()
            return np.column_stack([1 - proba, proba])

    def save(self, path: str) -> None:
        torch.save({
            "model_state_dict": self.model.state_dict(),
            "hyperparams": self.hyperparams,
            "metrics": self.metrics,
            "trained_at": self.trained_at,
            "dataset_hash": self.dataset_hash,
        }, path)

    def load(self, path: str) -> "TransformerModel":
        checkpoint = torch.load(path, map_location=self.device, weights_only=False)
        self.hyperparams = checkpoint["hyperparams"]
        self.model = AutoregressiveTransformer(
            input_size=self.hyperparams["input_size"],
            d_model=self.hyperparams["d_model"],
            num_heads=self.hyperparams["num_heads"],
            num_layers=self.hyperparams["num_layers"],
            dim_feedforward=self.hyperparams["dim_feedforward"],
            dropout=self.hyperparams["dropout"],
            max_seq_len=self.hyperparams["sequence_length"],
        ).to(self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.metrics = checkpoint["metrics"]
        self.trained_at = checkpoint["trained_at"]
        self.dataset_hash = checkpoint["dataset_hash"]
        return self

    def metadata(self) -> dict:
        return {
            "architecture": "AutoregressiveTransformer",
            "hyperparameters": self.hyperparams,
            "trained_at": self.trained_at,
            "metrics": self.metrics,
            "dataset_hash": self.dataset_hash,
            "device": str(self.device),
            "total_parameters": sum(p.numel() for p in self.model.parameters()),
        }
