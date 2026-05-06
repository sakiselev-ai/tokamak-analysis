from __future__ import annotations

"""Retrain all 3 models with n_features=10 and save to disk.

Eliminates the ~6-second cold start on first predict by ensuring saved
models match the feature count used by prepare_features (max_features=10).

Usage:
    cd ml_service
    python scripts/retrain_models.py
    python scripts/retrain_models.py --output-dir /opt/tokamak-analysis/models
"""

import argparse
import os
import sys
import time
from pathlib import Path

import numpy as np

# Allow imports from ml_service root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from service.data.dataset import get_sample_dataset
from service.models.random_forest import RandomForestModel
from service.models.lstm_attention import LSTMAttentionModel
from service.models.transformer import TransformerModel


N_FEATURES = 10
SEQ_LEN = 200
N_SAMPLES = 200


def train_rf(dataset, output_dir: str) -> dict:
    """Train Random Forest and save."""
    print("\n=== Random Forest ===")
    t0 = time.time()

    X_train, y_train = dataset.flat_train()
    X_val, y_val = dataset.flat_val()

    model = RandomForestModel(hyperparams={
        "n_estimators": 50,
        "max_depth": 10,
        "random_state": 42,
        "n_jobs": -1,
        "class_weight": "balanced",
    })
    metrics = model.fit(X_train, y_train, X_val, y_val)

    path = os.path.join(output_dir, "rf_baseline.joblib")
    model.save(path)
    elapsed = time.time() - t0

    print(f"  Saved to: {path}")
    print(f"  Time: {elapsed:.1f}s")
    for k, v in metrics.items():
        print(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")
    return metrics


def train_lstm(dataset, output_dir: str) -> dict:
    """Train LSTM+Attention and save."""
    print("\n=== LSTM+Attention ===")
    t0 = time.time()

    model = LSTMAttentionModel(hyperparams={
        "input_size": N_FEATURES,
        "hidden_size": 64,
        "num_layers": 2,
        "bidirectional": True,
        "dropout": 0.3,
        "attention_heads": 4,
        "sequence_length": SEQ_LEN,
        "learning_rate": 1e-3,
        "batch_size": 32,
        "epochs": 10,
        "early_stopping_patience": 10,
        "weight_decay": 1e-4,
    })
    metrics = model.fit(
        dataset.X_train, dataset.y_train,
        dataset.X_val, dataset.y_val,
    )

    path = os.path.join(output_dir, "lstm_attention.pt")
    model.save(path)
    elapsed = time.time() - t0

    print(f"  Saved to: {path}")
    print(f"  Time: {elapsed:.1f}s")
    for k, v in metrics.items():
        if k == "history":
            continue
        print(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")
    return metrics


def train_transformer(dataset, output_dir: str) -> dict:
    """Train Transformer and save."""
    print("\n=== Transformer ===")
    t0 = time.time()

    model = TransformerModel(hyperparams={
        "input_size": N_FEATURES,
        "d_model": 64,
        "num_heads": 4,
        "num_layers": 2,
        "dim_feedforward": 256,
        "dropout": 0.1,
        "sequence_length": SEQ_LEN,
        "learning_rate": 5e-4,
        "warmup_steps": 100,
        "batch_size": 32,
        "epochs": 10,
        "early_stopping_patience": 10,
        "weight_decay": 1e-4,
    })
    metrics = model.fit(
        dataset.X_train, dataset.y_train,
        dataset.X_val, dataset.y_val,
    )

    path = os.path.join(output_dir, "transformer.pt")
    model.save(path)
    elapsed = time.time() - t0

    print(f"  Saved to: {path}")
    print(f"  Time: {elapsed:.1f}s")
    for k, v in metrics.items():
        if k == "history":
            continue
        print(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")
    return metrics


def main():
    parser = argparse.ArgumentParser(
        description="Retrain all models with n_features=10 for cold-start elimination",
    )
    parser.add_argument(
        "--output-dir", default="models/",
        help="Directory to save model files (default: models/)",
    )
    args = parser.parse_args()

    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)

    print(f"Generating synthetic dataset: {N_SAMPLES} samples, "
          f"seq_len={SEQ_LEN}, n_features={N_FEATURES}")
    dataset = get_sample_dataset(
        n_samples=N_SAMPLES,
        seq_len=SEQ_LEN,
        n_features=N_FEATURES,
    )
    print(f"  Train: {dataset.X_train.shape}, Val: {dataset.X_val.shape}, "
          f"Test: {dataset.X_test.shape}")

    train_rf(dataset, output_dir)
    train_lstm(dataset, output_dir)
    train_transformer(dataset, output_dir)

    print("\n=== All models saved ===")
    for name in ["rf_baseline.joblib", "lstm_attention.pt", "transformer.pt"]:
        p = os.path.join(output_dir, name)
        size = os.path.getsize(p) / 1024
        print(f"  {p} ({size:.0f} KB)")


if __name__ == "__main__":
    main()
