from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

import numpy as np
import torch
import torch.nn as nn

from service.models.interface import ModelInterface


class AttentionLayer(nn.Module):
    """Multi-head attention over LSTM outputs."""

    def __init__(self, hidden_size: int, num_heads: int = 4):
        super().__init__()
        self.attention = nn.MultiheadAttention(
            embed_dim=hidden_size, num_heads=num_heads, batch_first=True
        )
        self.norm = nn.LayerNorm(hidden_size)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        attn_out, _ = self.attention(x, x, x)
        return self.norm(x + attn_out)


class BiLSTMAttentionNet(nn.Module):
    """Bidirectional LSTM with multi-head attention (ADR-004 §3.2.2).

    Based on HDL (Zhu et al., NC 2020) and FRNN (Kates-Harbeck et al., Nature 2019).
    """

    def __init__(
        self,
        input_size: int = 39,
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
        lstm_output_size = hidden_size * (2 if bidirectional else 1)
        self.attention = AttentionLayer(lstm_output_size, num_heads)
        self.classifier = nn.Sequential(
            nn.Linear(lstm_output_size, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        lstm_out, _ = self.lstm(x)
        attn_out = self.attention(lstm_out)
        # Global average pooling over time
        pooled = attn_out.mean(dim=1)
        return self.classifier(pooled).squeeze(-1)


class LSTMAttentionModel(ModelInterface):
    """bi-LSTM+attention model for classification and disruption prediction.

    Primary production model (ADR-004). GPU inference ≤ 30ms on T4.
    """

    def __init__(self, hyperparams: dict | None = None):
        self.hyperparams = hyperparams or {
            "input_size": 39,
            "hidden_size": 128,
            "num_layers": 2,
            "bidirectional": True,
            "dropout": 0.3,
            "attention_heads": 4,
            "sequence_length": 200,
            "learning_rate": 1e-3,
            "batch_size": 32,
            "epochs": 50,
            "early_stopping_patience": 10,
            "weight_decay": 1e-4,
        }
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = BiLSTMAttentionNet(
            input_size=self.hyperparams["input_size"],
            hidden_size=self.hyperparams["hidden_size"],
            num_layers=self.hyperparams["num_layers"],
            num_heads=self.hyperparams["attention_heads"],
            dropout=self.hyperparams["dropout"],
            bidirectional=self.hyperparams["bidirectional"],
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
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, factor=0.5, patience=5)

        # Class weights for imbalanced data
        pos_weight = torch.tensor([(y_train == 0).sum() / max((y_train == 1).sum(), 1)]).to(self.device)
        criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

        best_val_loss = float("inf")
        patience_counter = 0
        history = {"train_loss": [], "val_loss": []}

        self.model.train()
        for epoch in range(self.hyperparams["epochs"]):
            epoch_loss = 0.0
            for X_batch, y_batch in loader:
                optimizer.zero_grad()
                output = self.model(X_batch)
                loss = criterion(output, y_batch)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                optimizer.step()
                epoch_loss += loss.item()

            avg_loss = epoch_loss / len(loader)
            history["train_loss"].append(avg_loss)

            # Validation
            val_loss = avg_loss
            if X_val is not None and y_val is not None:
                self.model.eval()
                with torch.no_grad():
                    X_v = torch.FloatTensor(X_val).to(self.device)
                    y_v = torch.FloatTensor(y_val).to(self.device)
                    val_output = self.model(X_v)
                    val_loss = criterion(val_output, y_v).item()
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

    def predict(self, X: np.ndarray) -> np.ndarray:
        self.model.eval()
        with torch.no_grad():
            X_t = torch.FloatTensor(X).to(self.device)
            output = torch.sigmoid(self.model(X_t))
            return (output.cpu().numpy() > 0.5).astype(int)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        self.model.eval()
        with torch.no_grad():
            X_t = torch.FloatTensor(X).to(self.device)
            proba = torch.sigmoid(self.model(X_t)).cpu().numpy()
            return np.column_stack([1 - proba, proba])

    def save(self, path: str) -> None:
        torch.save({
            "model_state_dict": self.model.state_dict(),
            "hyperparams": self.hyperparams,
            "metrics": self.metrics,
            "trained_at": self.trained_at,
            "dataset_hash": self.dataset_hash,
        }, path)

    def load(self, path: str) -> "LSTMAttentionModel":
        checkpoint = torch.load(path, map_location=self.device, weights_only=False)
        self.hyperparams = checkpoint["hyperparams"]
        self.model = BiLSTMAttentionNet(
            input_size=self.hyperparams["input_size"],
            hidden_size=self.hyperparams["hidden_size"],
            num_layers=self.hyperparams["num_layers"],
            num_heads=self.hyperparams["attention_heads"],
            dropout=self.hyperparams["dropout"],
            bidirectional=self.hyperparams["bidirectional"],
        ).to(self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.metrics = checkpoint["metrics"]
        self.trained_at = checkpoint["trained_at"]
        self.dataset_hash = checkpoint["dataset_hash"]
        return self

    def metadata(self) -> dict:
        return {
            "architecture": "BiLSTM_Attention",
            "hyperparameters": self.hyperparams,
            "trained_at": self.trained_at,
            "metrics": self.metrics,
            "dataset_hash": self.dataset_hash,
            "device": str(self.device),
            "total_parameters": sum(p.numel() for p in self.model.parameters()),
        }
