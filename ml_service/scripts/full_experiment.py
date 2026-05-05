from __future__ import annotations
"""Comprehensive experiment: all 3 models, 5-fold CV, latency, formatted tables.

Usage:
    python -m scripts.full_experiment --quick
    python scripts/full_experiment.py --data data/fair_mast_500.npz
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
from sklearn.model_selection import StratifiedKFold, train_test_split

# ---------------------------------------------------------------------------
# sys.path fix
# ---------------------------------------------------------------------------
_ml_service_root = str(Path(__file__).resolve().parent.parent)
if _ml_service_root not in sys.path:
    sys.path.insert(0, _ml_service_root)

from service.data.dataset import get_sample_dataset  # noqa: E402
from service.data.metrics import compute_metrics as _compute_metrics  # noqa: E402
from service.models.random_forest import RandomForestModel  # noqa: E402

# ---------------------------------------------------------------------------
# Optional torch
# ---------------------------------------------------------------------------
_HAS_TORCH = False
try:
    import torch

    from service.models.lstm_attention import LSTMAttentionModel  # noqa: E402
    from service.models.transformer import TransformerModel  # noqa: E402

    _HAS_TORCH = True
except ImportError:
    torch = None  # type: ignore[assignment]
    LSTMAttentionModel = None  # type: ignore[assignment,misc]
    TransformerModel = None  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def generate_synthetic(
    n_samples: int = 300,
    seq_len: int = 50,
    n_features: int = 10,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (X, y, shot_ids) with synthetic data."""
    rng = np.random.RandomState(seed)
    X = rng.randn(n_samples, seq_len, n_features).astype(np.float32)
    n_pos = n_samples // 3
    ramp = np.linspace(0, 3, seq_len).reshape(1, seq_len, 1)
    X[:n_pos] += ramp
    y = np.zeros(n_samples, dtype=np.float32)
    y[:n_pos] = 1.0
    shot_ids = np.sort(rng.randint(11000, 30000, size=n_samples))
    perm = rng.permutation(n_samples)
    return X[perm], y[perm], shot_ids[perm]


def load_or_generate(
    data_path: str | None,
    quick: bool = False,
) -> tuple[np.ndarray, np.ndarray, np.ndarray | None]:
    """Load .npz or fall back to synthetic data."""
    if data_path and os.path.isfile(data_path):
        data = np.load(data_path)
        X, y = data["X"], data["y"]
        shot_ids = data["shot_ids"] if "shot_ids" in data else None
        return X, y, shot_ids
    if data_path:
        print(f"WARNING: '{data_path}' not found, generating synthetic data.")
    n = 100 if quick else 300
    sl = 30 if quick else 50
    X, y, shot_ids = generate_synthetic(n_samples=n, seq_len=sl, n_features=10)
    return X, y, shot_ids


# ---------------------------------------------------------------------------
# Metrics helpers
# ---------------------------------------------------------------------------

def compute_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_proba: np.ndarray | None = None,
) -> dict:
    """Thin wrapper around service.data.metrics.compute_metrics."""
    return _compute_metrics(y_true, y_pred, y_proba)


def measure_latency(predict_fn, X_sample: np.ndarray, n_runs: int = 100) -> dict:
    """Measure single-sample inference latency in milliseconds."""
    x_single = X_sample[:1]
    # Warmup
    for _ in range(5):
        predict_fn(x_single)
    latencies = []
    for _ in range(n_runs):
        t0 = time.perf_counter()
        predict_fn(x_single)
        elapsed = (time.perf_counter() - t0) * 1000
        latencies.append(elapsed)
    arr = np.array(latencies)
    return {
        "mean_ms": float(np.mean(arr)),
        "p50_ms": float(np.percentile(arr, 50)),
        "p95_ms": float(np.percentile(arr, 95)),
        "p99_ms": float(np.percentile(arr, 99)),
    }


# ---------------------------------------------------------------------------
# RF helpers
# ---------------------------------------------------------------------------

def train_rf(X_train: np.ndarray, y_train: np.ndarray) -> RandomForestModel:
    """Train RF on flattened input."""
    X_flat = X_train.reshape(len(X_train), -1)
    model = RandomForestModel()
    model.fit(X_flat, y_train)
    return model


def eval_rf(model: RandomForestModel, X: np.ndarray, y: np.ndarray) -> dict:
    X_flat = X.reshape(len(X), -1)
    y_pred = model.predict(X_flat)
    y_proba = model.predict_proba(X_flat)
    return compute_metrics(y, y_pred, y_proba)


# ---------------------------------------------------------------------------
# Neural helpers
# ---------------------------------------------------------------------------

def _neural_device() -> str:
    if _HAS_TORCH and torch.cuda.is_available():
        return "cuda"
    return "cpu"


def train_neural(model_cls, hyperparams: dict,
                 X_train: np.ndarray, y_train: np.ndarray,
                 X_val: np.ndarray, y_val: np.ndarray,
                 device: str = "cpu"):
    """Train a neural model (LSTM or Transformer) and return it."""
    model = model_cls(hyperparams=hyperparams)
    model.device = torch.device(device)
    model.model = model.model.to(model.device)
    model.fit(X_train, y_train, X_val, y_val)
    return model


def eval_neural(model, X: np.ndarray, y: np.ndarray) -> dict:
    y_pred = model.predict(X)
    y_proba = model.predict_proba(X)
    return compute_metrics(y, y_pred, y_proba)


# ---------------------------------------------------------------------------
# Cross-validation
# ---------------------------------------------------------------------------

def cross_validate_rf(X: np.ndarray, y: np.ndarray, n_folds: int = 5) -> dict:
    """5-fold stratified CV for Random Forest."""
    X_flat = X.reshape(len(X), -1)
    skf = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)
    fold_metrics = []
    for fold_idx, (train_idx, test_idx) in enumerate(skf.split(X_flat, y)):
        model = RandomForestModel()
        model.fit(X_flat[train_idx], y[train_idx])
        y_pred = model.predict(X_flat[test_idx])
        y_proba = model.predict_proba(X_flat[test_idx])
        fm = compute_metrics(y[test_idx], y_pred, y_proba)
        fm["fold"] = fold_idx + 1
        fold_metrics.append(fm)
        auc = fm.get("auc_roc")
        auc_str = f"{auc:.4f}" if auc is not None else "N/A"
        print(f"    Fold {fold_idx+1}: acc={fm['accuracy']:.4f}  "
              f"f1={fm['f1']:.4f}  auc={auc_str}")
    return _aggregate_cv(fold_metrics)


def cross_validate_neural(model_cls, hyperparams_base: dict,
                          X: np.ndarray, y: np.ndarray,
                          n_folds: int = 5, device: str = "cpu") -> dict:
    """5-fold stratified CV for a neural model."""
    skf = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)
    fold_metrics = []
    for fold_idx, (train_idx, test_idx) in enumerate(skf.split(X, y)):
        X_tr, y_tr = X[train_idx], y[train_idx]
        X_te, y_te = X[test_idx], y[test_idx]
        split_pt = max(1, int(len(X_tr) * 0.9))
        X_train_fold, X_val_fold = X_tr[:split_pt], X_tr[split_pt:]
        y_train_fold, y_val_fold = y_tr[:split_pt], y_tr[split_pt:]

        hp = dict(hyperparams_base)
        hp["sequence_length"] = X.shape[1]
        hp["input_size"] = X.shape[2]

        model = train_neural(model_cls, hp, X_train_fold, y_train_fold,
                             X_val_fold, y_val_fold, device)
        fm = eval_neural(model, X_te, y_te)
        fm["fold"] = fold_idx + 1
        fold_metrics.append(fm)
        auc = fm.get("auc_roc")
        auc_str = f"{auc:.4f}" if auc is not None else "N/A"
        print(f"    Fold {fold_idx+1}: acc={fm['accuracy']:.4f}  "
              f"f1={fm['f1']:.4f}  auc={auc_str}")
    return _aggregate_cv(fold_metrics)


def _aggregate_cv(fold_metrics: list[dict]) -> dict:
    keys = ["accuracy", "f1", "precision", "recall", "auc_roc"]
    summary: dict = {}
    for k in keys:
        vals = [fm[k] for fm in fold_metrics if k in fm and fm[k] is not None]
        if vals:
            summary[f"{k}_mean"] = float(np.mean(vals))
            summary[f"{k}_std"] = float(np.std(vals))
    summary["folds"] = fold_metrics
    return summary


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run full experiment suite")
    parser.add_argument("--data", default=None,
                        help="Path to .npz file. Synthetic if missing.")
    parser.add_argument("--output", default="results/full_experiment.json",
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
        device = _neural_device()
    else:
        device = args.device
    print(f"Device: {device}")
    print(f"Quick mode: {args.quick}")
    if not _HAS_TORCH:
        print("WARNING: torch not installed, neural models will be skipped.")

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)

    # ---- Load data ----
    X, y, shot_ids = load_or_generate(args.data, quick=args.quick)
    print(f"Dataset: {X.shape[0]} shots, {X.shape[1]} timesteps, "
          f"{X.shape[2]} features")
    print(f"Labels: {int(y.sum())} disruptions ({y.mean()*100:.1f}%)")

    # ---- Train/val/test split ----
    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=0.2, random_state=args.seed, stratify=y
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.5, random_state=args.seed, stratify=y_temp
    )
    print(f"Split: train={len(X_train)}, val={len(X_val)}, test={len(X_test)}")

    results: dict = {
        "dataset": {
            "total_shots": len(X),
            "timesteps": int(X.shape[1]),
            "features": int(X.shape[2]),
            "disruption_rate": float(y.mean()),
            "train_size": len(X_train),
            "val_size": len(X_val),
            "test_size": len(X_test),
        },
        "device": device,
        "seed": args.seed,
        "quick_mode": args.quick,
    }

    # Quick-mode params
    lstm_epochs = 5 if args.quick else 50
    tf_epochs = 5 if args.quick else 40
    cv_folds = 3 if args.quick else 5
    latency_runs = 20 if args.quick else 100

    # ==================================================================
    # 1. Random Forest
    # ==================================================================
    print("\n" + "=" * 60)
    print("1. RANDOM FOREST")
    print("=" * 60)

    t0 = time.time()
    rf_model = train_rf(X_train, y_train)
    rf_train_time = time.time() - t0
    rf_metrics = eval_rf(rf_model, X_test, y_test)
    rf_metrics["train_time_sec"] = round(rf_train_time, 3)
    rf_latency = measure_latency(
        lambda x: rf_model.predict(x.reshape(len(x), -1)), X_test, n_runs=latency_runs
    )
    rf_metrics["latency"] = rf_latency
    print(f"  Accuracy: {rf_metrics['accuracy']:.4f}")
    print(f"  F1:       {rf_metrics['f1']:.4f}")
    auc = rf_metrics.get("auc_roc")
    print(f"  AUC-ROC:  {auc:.4f}" if auc is not None else "  AUC-ROC:  N/A")
    print(f"  P99 latency: {rf_latency['p99_ms']:.2f} ms "
          f"(target: <=5 ms {'PASS' if rf_latency['p99_ms'] <= 5 else 'FAIL'})")
    results["random_forest"] = rf_metrics

    # ==================================================================
    # 2. bi-LSTM+Attention
    # ==================================================================
    if _HAS_TORCH:
        print("\n" + "=" * 60)
        print("2. bi-LSTM+ATTENTION")
        print("=" * 60)

        lstm_hp = {
            "input_size": X.shape[2],
            "hidden_size": 64 if args.quick else 128,
            "num_layers": 1 if args.quick else 2,
            "bidirectional": True,
            "dropout": 0.1 if args.quick else 0.3,
            "attention_heads": 2 if args.quick else 4,
            "sequence_length": X.shape[1],
            "learning_rate": 1e-3,
            "batch_size": 32,
            "epochs": lstm_epochs,
            "early_stopping_patience": 3 if args.quick else 10,
            "weight_decay": 1e-4,
        }

        t0 = time.time()
        lstm_model = train_neural(LSTMAttentionModel, lstm_hp,
                                  X_train, y_train, X_val, y_val, device)
        lstm_train_time = time.time() - t0
        lstm_metrics = eval_neural(lstm_model, X_test, y_test)
        lstm_metrics["train_time_sec"] = round(lstm_train_time, 3)
        lstm_latency = measure_latency(
            lambda x: lstm_model.predict(x), X_test, n_runs=latency_runs
        )
        lstm_metrics["latency"] = lstm_latency
        print(f"  Accuracy: {lstm_metrics['accuracy']:.4f}")
        print(f"  F1:       {lstm_metrics['f1']:.4f}")
        auc = lstm_metrics.get("auc_roc")
        print(f"  AUC-ROC:  {auc:.4f}" if auc is not None else "  AUC-ROC:  N/A")
        print(f"  P99 latency: {lstm_latency['p99_ms']:.2f} ms "
              f"(target: <=30 ms {'PASS' if lstm_latency['p99_ms'] <= 30 else 'FAIL'})")
        results["lstm_attention"] = lstm_metrics

        # ==============================================================
        # 3. Autoregressive Transformer
        # ==============================================================
        print("\n" + "=" * 60)
        print("3. AUTOREGRESSIVE TRANSFORMER")
        print("=" * 60)

        tf_hp = {
            "input_size": X.shape[2],
            "d_model": 64 if args.quick else 128,
            "num_heads": 4 if args.quick else 8,
            "num_layers": 2 if args.quick else 4,
            "dim_feedforward": 128 if args.quick else 512,
            "dropout": 0.1,
            "sequence_length": X.shape[1],
            "learning_rate": 5e-4,
            "warmup_steps": 50 if args.quick else 1000,
            "batch_size": 16,
            "epochs": tf_epochs,
            "early_stopping_patience": 3 if args.quick else 8,
            "weight_decay": 1e-4,
        }

        t0 = time.time()
        tf_model = train_neural(TransformerModel, tf_hp,
                                X_train, y_train, X_val, y_val, device)
        tf_train_time = time.time() - t0
        tf_metrics = eval_neural(tf_model, X_test, y_test)
        tf_metrics["train_time_sec"] = round(tf_train_time, 3)
        tf_latency = measure_latency(
            lambda x: tf_model.predict(x), X_test, n_runs=latency_runs
        )
        tf_metrics["latency"] = tf_latency
        print(f"  Accuracy: {tf_metrics['accuracy']:.4f}")
        print(f"  F1:       {tf_metrics['f1']:.4f}")
        auc = tf_metrics.get("auc_roc")
        print(f"  AUC-ROC:  {auc:.4f}" if auc is not None else "  AUC-ROC:  N/A")
        print(f"  P99 latency: {tf_latency['p99_ms']:.2f} ms")
        results["transformer"] = tf_metrics

    # ==================================================================
    # 4. 5-fold Cross-validation
    # ==================================================================
    print("\n" + "=" * 60)
    print(f"4. {cv_folds}-FOLD CROSS-VALIDATION")
    print("=" * 60)

    print("  RF cross-validation:")
    cv_rf = cross_validate_rf(X, y, n_folds=cv_folds)
    print(f"    Mean accuracy: {cv_rf['accuracy_mean']:.4f} "
          f"+/- {cv_rf['accuracy_std']:.4f}")
    auc_mean = cv_rf.get("auc_roc_mean")
    if auc_mean is not None:
        print(f"    Mean AUC-ROC:  {auc_mean:.4f} "
              f"+/- {cv_rf.get('auc_roc_std', 0):.4f}")
    results["cross_validation_rf"] = cv_rf

    if _HAS_TORCH:
        print("\n  LSTM cross-validation:")
        lstm_cv_hp = {
            "hidden_size": 64 if args.quick else 128,
            "num_layers": 1 if args.quick else 2,
            "bidirectional": True,
            "dropout": 0.1 if args.quick else 0.3,
            "attention_heads": 2 if args.quick else 4,
            "learning_rate": 1e-3,
            "batch_size": 32,
            "epochs": max(3, lstm_epochs // 3),
            "early_stopping_patience": 3,
            "weight_decay": 1e-4,
        }
        cv_lstm = cross_validate_neural(
            LSTMAttentionModel, lstm_cv_hp, X, y, n_folds=cv_folds, device=device
        )
        print(f"    Mean accuracy: {cv_lstm['accuracy_mean']:.4f} "
              f"+/- {cv_lstm['accuracy_std']:.4f}")
        results["cross_validation_lstm"] = cv_lstm

        print("\n  Transformer cross-validation:")
        tf_cv_hp = {
            "d_model": 64 if args.quick else 128,
            "num_heads": 4 if args.quick else 8,
            "num_layers": 2 if args.quick else 4,
            "dim_feedforward": 128 if args.quick else 512,
            "dropout": 0.1,
            "learning_rate": 5e-4,
            "warmup_steps": 50 if args.quick else 500,
            "batch_size": 16,
            "epochs": max(3, tf_epochs // 3),
            "early_stopping_patience": 3,
            "weight_decay": 1e-4,
        }
        cv_tf = cross_validate_neural(
            TransformerModel, tf_cv_hp, X, y, n_folds=cv_folds, device=device
        )
        print(f"    Mean accuracy: {cv_tf['accuracy_mean']:.4f} "
              f"+/- {cv_tf['accuracy_std']:.4f}")
        results["cross_validation_transformer"] = cv_tf

    # ==================================================================
    # Summary table
    # ==================================================================
    print("\n" + "=" * 72)
    print(f"{'Model':<22} {'Accuracy':>10} {'F1':>8} {'AUC-ROC':>10} "
          f"{'P99 (ms)':>10} {'Latency':>8}")
    print("=" * 72)

    latency_targets = {
        "random_forest": 5.0,
        "lstm_attention": 30.0,
        "transformer": None,
    }
    for name, key in [("Random Forest", "random_forest"),
                      ("bi-LSTM+Att", "lstm_attention"),
                      ("Transformer", "transformer")]:
        if key not in results:
            continue
        m = results[key]
        lat = m.get("latency", {}).get("p99_ms", 0)
        target = latency_targets.get(key)
        if target is not None:
            status = "PASS" if lat <= target else "FAIL"
        else:
            status = "---"
        auc = m.get("auc_roc")
        auc_str = f"{auc:>10.4f}" if auc is not None else f"{'N/A':>10}"
        print(f"{name:<22} {m['accuracy']:>10.4f} {m['f1']:>8.4f} "
              f"{auc_str} {lat:>10.2f} {status:>8}")
    print("=" * 72)

    # ---- Save ----
    with open(args.output, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nFull results saved to {args.output}")

    return results


if __name__ == "__main__":
    main()
