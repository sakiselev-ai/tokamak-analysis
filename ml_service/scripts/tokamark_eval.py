from __future__ import annotations
"""TokaMark benchmark evaluation: train forecasting models, compute NRMSE.

Usage:
    python -m scripts.tokamark_eval --quick
    python scripts/tokamark_eval.py --data data/forecasting.npz --past-len 20 --future-len 10
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# sys.path fix
# ---------------------------------------------------------------------------
_ml_service_root = str(Path(__file__).resolve().parent.parent)
if _ml_service_root not in sys.path:
    sys.path.insert(0, _ml_service_root)

from service.data.tokamark import (  # noqa: E402
    ForecastingDataset,
    compute_nrmse,
    prepare_forecasting_dataset,
)

# ---------------------------------------------------------------------------
# Optional torch
# ---------------------------------------------------------------------------
_HAS_TORCH = False
try:
    import torch

    from service.models.forecasting import (  # noqa: E402
        LSTMForecaster,
        TransformerForecaster,
    )

    _HAS_TORCH = True
except ImportError:
    torch = None  # type: ignore[assignment]
    LSTMForecaster = None  # type: ignore[assignment,misc]
    TransformerForecaster = None  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# Synthetic data
# ---------------------------------------------------------------------------


def generate_synthetic_forecasting(
    n_shots: int = 50,
    seq_len: int = 60,
    n_features: int = 5,
    seed: int = 42,
) -> np.ndarray:
    """Generate synthetic time-series data with trends and oscillations.

    Returns:
        ``(n_shots, seq_len, n_features)`` array.
    """
    rng = np.random.RandomState(seed)
    t = np.linspace(0, 4 * np.pi, seq_len).reshape(1, seq_len, 1)

    X = np.zeros((n_shots, seq_len, n_features), dtype=np.float32)
    for f in range(n_features):
        freq = 1.0 + rng.rand() * 2
        phase = rng.rand(n_shots, 1, 1) * 2 * np.pi
        amplitude = 0.5 + rng.rand(n_shots, 1, 1) * 2
        trend = rng.randn(n_shots, 1, 1) * 0.1
        X[:, :, f : f + 1] = (
            amplitude * np.sin(freq * t + phase) + trend * t + rng.randn(n_shots, seq_len, 1) * 0.1
        )

    return X


def load_or_generate(
    data_path: str | None,
    quick: bool = False,
    n_features: int = 5,
) -> np.ndarray:
    """Load .npz or fall back to synthetic data."""
    if data_path and os.path.isfile(data_path):
        data = np.load(data_path)
        if "X" in data:
            return data["X"]
        # Try first available array
        key = list(data.keys())[0]
        return data[key]
    if data_path:
        print(f"WARNING: '{data_path}' not found, generating synthetic data.")
    n_shots = 30 if quick else 100
    seq_len = 40 if quick else 80
    return generate_synthetic_forecasting(
        n_shots=n_shots, seq_len=seq_len, n_features=n_features,
    )


# ---------------------------------------------------------------------------
# Training helpers
# ---------------------------------------------------------------------------


def train_and_eval_lstm(
    ds: ForecastingDataset,
    hyperparams: dict,
    device: str = "cpu",
) -> tuple[dict, dict]:
    """Train LSTMForecaster and evaluate on test set.

    Returns (metrics_from_fit, nrmse_dict).
    """
    model = LSTMForecaster(hyperparams=hyperparams)
    model.device = torch.device(device)
    model.model = model.model.to(model.device)

    fit_metrics = model.fit(
        ds.X_train_past, ds.X_train_future,
        ds.X_val_past, ds.X_val_future,
    )

    y_pred = model.predict(ds.X_test_past)
    nrmse = compute_nrmse(ds.X_test_future, y_pred)
    return fit_metrics, nrmse


def train_and_eval_transformer(
    ds: ForecastingDataset,
    hyperparams: dict,
    device: str = "cpu",
) -> tuple[dict, dict]:
    """Train TransformerForecaster and evaluate on test set.

    Returns (metrics_from_fit, nrmse_dict).
    """
    model = TransformerForecaster(hyperparams=hyperparams)
    model.device = torch.device(device)
    model.model = model.model.to(model.device)

    fit_metrics = model.fit(
        ds.X_train_past, ds.X_train_future,
        ds.X_val_past, ds.X_val_future,
    )

    y_pred = model.predict(ds.X_test_past)
    nrmse = compute_nrmse(ds.X_test_future, y_pred)
    return fit_metrics, nrmse


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="TokaMark benchmark: train forecasting models and evaluate NRMSE",
    )
    parser.add_argument("--data", default=None,
                        help="Path to .npz file with 'X' array. Synthetic if missing.")
    parser.add_argument("--past-len", type=int, default=20,
                        help="Past window length (default: 20)")
    parser.add_argument("--future-len", type=int, default=10,
                        help="Future window / forecast horizon (default: 10)")
    parser.add_argument("--output", default="results/tokamark_eval.json",
                        help="Path to save results JSON")
    parser.add_argument("--device", default="auto",
                        choices=["auto", "cpu", "cuda"])
    parser.add_argument("--quick", action="store_true",
                        help="Smaller data, fewer epochs, fast run")
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict:
    args = parse_args(argv)
    np.random.seed(args.seed)
    if _HAS_TORCH:
        torch.manual_seed(args.seed)

    if args.device == "auto":
        device = "cuda" if _HAS_TORCH and torch.cuda.is_available() else "cpu"
    else:
        device = args.device
    print(f"Device: {device}")
    print(f"Quick mode: {args.quick}")
    if not _HAS_TORCH:
        print("WARNING: torch not installed, forecasting models will be skipped.")
        return {}

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)

    # ---- Load data ----
    n_features = 3 if args.quick else 5
    X = load_or_generate(args.data, quick=args.quick, n_features=n_features)
    print(f"Raw data: {X.shape[0]} shots, {X.shape[1]} timesteps, {X.shape[2]} features")

    past_len = args.past_len
    future_len = args.future_len
    print(f"Windows: past_len={past_len}, future_len={future_len}")

    ds = prepare_forecasting_dataset(X, past_len=past_len, future_len=future_len, seed=args.seed)
    print(f"Dataset: train={len(ds.X_train_past)}, "
          f"val={len(ds.X_val_past)}, test={len(ds.X_test_past)}")

    n_signals = ds.n_features
    lstm_epochs = 5 if args.quick else 30
    tf_epochs = 5 if args.quick else 25

    results: dict = {
        "dataset": {
            "raw_shots": int(X.shape[0]),
            "raw_timesteps": int(X.shape[1]),
            "n_features": int(X.shape[2]),
            "past_len": past_len,
            "future_len": future_len,
            "train_samples": len(ds.X_train_past),
            "val_samples": len(ds.X_val_past),
            "test_samples": len(ds.X_test_past),
        },
        "device": device,
        "seed": args.seed,
        "quick_mode": args.quick,
    }

    # ==================================================================
    # 1. LSTM Forecaster
    # ==================================================================
    print("\n" + "=" * 60)
    print("1. LSTM FORECASTER")
    print("=" * 60)

    lstm_hp = {
        "input_size": n_signals,
        "hidden_size": 32 if args.quick else 64,
        "num_layers": 1,
        "bidirectional": True,
        "dropout": 0.1,
        "attention_heads": 2,
        "forecast_horizon": future_len,
        "n_signals": n_signals,
        "learning_rate": 1e-3,
        "batch_size": 32,
        "epochs": lstm_epochs,
        "early_stopping_patience": 5 if args.quick else 10,
        "weight_decay": 1e-4,
    }

    t0 = time.time()
    lstm_fit, lstm_nrmse = train_and_eval_lstm(ds, lstm_hp, device)
    lstm_time = time.time() - t0

    print(f"  Train time: {lstm_time:.1f}s")
    print(f"  Final train loss: {lstm_fit['final_train_loss']:.6f}")
    print(f"  Best val loss:    {lstm_fit['best_val_loss']:.6f}")
    print(f"  Epochs trained:   {lstm_fit['epochs_trained']}")
    print(f"  NRMSE (mean):     {lstm_nrmse['nrmse_mean']:.4f}")
    for i, nrmse_val in enumerate(lstm_nrmse["nrmse_per_signal"]):
        print(f"    Signal {i}: NRMSE={nrmse_val:.4f}")

    results["lstm_forecaster"] = {
        "fit_metrics": {k: v for k, v in lstm_fit.items() if k != "history"},
        "nrmse": lstm_nrmse,
        "train_time_sec": round(lstm_time, 3),
    }

    # ==================================================================
    # 2. Transformer Forecaster
    # ==================================================================
    print("\n" + "=" * 60)
    print("2. TRANSFORMER FORECASTER")
    print("=" * 60)

    tf_hp = {
        "input_size": n_signals,
        "d_model": 32 if args.quick else 64,
        "num_heads": 2 if args.quick else 4,
        "num_layers": 1 if args.quick else 2,
        "dim_feedforward": 64 if args.quick else 128,
        "dropout": 0.1,
        "max_seq_len": past_len * 2,
        "forecast_horizon": future_len,
        "n_signals": n_signals,
        "learning_rate": 5e-4,
        "warmup_steps": 10 if args.quick else 100,
        "batch_size": 32,
        "epochs": tf_epochs,
        "early_stopping_patience": 5 if args.quick else 8,
        "weight_decay": 1e-4,
    }

    t0 = time.time()
    tf_fit, tf_nrmse = train_and_eval_transformer(ds, tf_hp, device)
    tf_time = time.time() - t0

    print(f"  Train time: {tf_time:.1f}s")
    print(f"  Final train loss: {tf_fit['final_train_loss']:.6f}")
    print(f"  Best val loss:    {tf_fit['best_val_loss']:.6f}")
    print(f"  Epochs trained:   {tf_fit['epochs_trained']}")
    print(f"  NRMSE (mean):     {tf_nrmse['nrmse_mean']:.4f}")
    for i, nrmse_val in enumerate(tf_nrmse["nrmse_per_signal"]):
        print(f"    Signal {i}: NRMSE={nrmse_val:.4f}")

    results["transformer_forecaster"] = {
        "fit_metrics": {k: v for k, v in tf_fit.items() if k != "history"},
        "nrmse": tf_nrmse,
        "train_time_sec": round(tf_time, 3),
    }

    # ==================================================================
    # Summary table
    # ==================================================================
    print("\n" + "=" * 60)
    print(f"{'Model':<25} {'NRMSE':>10} {'Train Loss':>12} {'Val Loss':>12} {'Time (s)':>10}")
    print("=" * 60)
    for name, key in [("LSTM Forecaster", "lstm_forecaster"),
                      ("Transformer Forecaster", "transformer_forecaster")]:
        m = results[key]
        nrmse_val = m["nrmse"]["nrmse_mean"]
        status = "< 1.0 GOOD" if nrmse_val < 1.0 else ">= 1.0"
        print(f"{name:<25} {nrmse_val:>10.4f} "
              f"{m['fit_metrics']['final_train_loss']:>12.6f} "
              f"{m['fit_metrics']['best_val_loss']:>12.6f} "
              f"{m['train_time_sec']:>10.1f}")
        print(f"{'':>25} ({status})")
    print("=" * 60)
    print("\nNRMSE < 1.0 means better than predicting the mean (TokaMark target).")

    # ---- Save ----
    with open(args.output, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to {args.output}")

    return results


if __name__ == "__main__":
    main()
