from __future__ import annotations
"""Comprehensive experiment script: trains all models, runs all validations.

Trains Random Forest, bi-LSTM+Attention, and Transformer models with:
- Standard random train/test split
- Temporal validation (train on early campaigns, test on later)
- 5-fold cross-validation
- Full metrics computation (accuracy, F1, AUC-ROC, latency)
- Results saved to JSON for paper generation

Usage:
    python full_experiment.py --data data/fair_mast_500.npz --output results/full_experiment.json
    python full_experiment.py --data data/fair_mast_500.npz --quick  # RF only, no grid search
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import torch
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, train_test_split

# Allow imports from ml_service root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from service.models.lstm_attention import LSTMAttentionModel
from service.models.random_forest import RandomForestModel
from service.models.transformer import TransformerModel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray, y_proba: np.ndarray | None = None) -> dict:
    """Compute standard classification metrics."""
    metrics: dict = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "f1": float(f1_score(y_true, y_pred, average="weighted", zero_division=0)),
        "precision": float(precision_score(y_true, y_pred, average="weighted", zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, average="weighted", zero_division=0)),
    }
    if y_proba is not None:
        try:
            proba_col = y_proba[:, 1] if y_proba.ndim == 2 else y_proba
            metrics["auc_roc"] = float(roc_auc_score(y_true, proba_col))
        except Exception:
            metrics["auc_roc"] = 0.0
    return metrics


def measure_latency(predict_fn, X_sample: np.ndarray, n_runs: int = 100) -> dict:
    """Measure single-sample inference latency."""
    x_single = X_sample[:1]
    # Warmup
    for _ in range(5):
        predict_fn(x_single)
    latencies = []
    for _ in range(n_runs):
        t0 = time.perf_counter()
        predict_fn(x_single)
        elapsed = (time.perf_counter() - t0) * 1000  # ms
        latencies.append(elapsed)
    arr = np.array(latencies)
    return {
        "mean_ms": float(np.mean(arr)),
        "p50_ms": float(np.percentile(arr, 50)),
        "p95_ms": float(np.percentile(arr, 95)),
        "p99_ms": float(np.percentile(arr, 99)),
    }


# ---------------------------------------------------------------------------
# Random Forest helpers
# ---------------------------------------------------------------------------

def train_rf(X_train: np.ndarray, y_train: np.ndarray, quick: bool = True) -> RandomForestClassifier:
    """Train a Random Forest classifier (on flattened input)."""
    X_flat = X_train.reshape(len(X_train), -1)
    model = RandomForestClassifier(
        n_estimators=200, max_depth=20, class_weight="balanced",
        random_state=42, n_jobs=-1,
    )
    model.fit(X_flat, y_train)
    return model


def eval_rf(model: RandomForestClassifier, X: np.ndarray, y: np.ndarray) -> dict:
    """Evaluate RF model (handles flattening)."""
    X_flat = X.reshape(len(X), -1)
    y_pred = model.predict(X_flat)
    y_proba = model.predict_proba(X_flat)
    return compute_metrics(y, y_pred, y_proba)


# ---------------------------------------------------------------------------
# Neural model helpers
# ---------------------------------------------------------------------------

def train_neural(model_cls, hyperparams: dict, X_train: np.ndarray, y_train: np.ndarray,
                 X_val: np.ndarray, y_val: np.ndarray, device: str = "cpu"):
    """Train a neural model (LSTM or Transformer) and return the model."""
    model = model_cls(hyperparams=hyperparams)
    model.device = torch.device(device)
    model.model = model.model.to(model.device)
    model.fit(X_train, y_train, X_val, y_val)
    return model


def eval_neural(model, X: np.ndarray, y: np.ndarray) -> dict:
    """Evaluate a neural model."""
    y_pred = model.predict(X)
    y_proba = model.predict_proba(X)
    return compute_metrics(y, y_pred, y_proba)


# ---------------------------------------------------------------------------
# Cross-validation
# ---------------------------------------------------------------------------

def cross_validate_rf(X: np.ndarray, y: np.ndarray, n_folds: int = 5) -> dict:
    """5-fold stratified cross-validation for Random Forest."""
    X_flat = X.reshape(len(X), -1)
    skf = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)
    fold_metrics = []
    for fold_idx, (train_idx, test_idx) in enumerate(skf.split(X_flat, y)):
        model = RandomForestClassifier(
            n_estimators=200, max_depth=20, class_weight="balanced",
            random_state=42, n_jobs=-1,
        )
        model.fit(X_flat[train_idx], y[train_idx])
        y_pred = model.predict(X_flat[test_idx])
        y_proba = model.predict_proba(X_flat[test_idx])
        fm = compute_metrics(y[test_idx], y_pred, y_proba)
        fm["fold"] = fold_idx + 1
        fold_metrics.append(fm)
        print(f"    Fold {fold_idx+1}: acc={fm['accuracy']:.4f}  f1={fm['f1']:.4f}  auc={fm.get('auc_roc', 0):.4f}")

    # Aggregate
    keys = ["accuracy", "f1", "precision", "recall", "auc_roc"]
    summary: dict = {}
    for k in keys:
        vals = [fm[k] for fm in fold_metrics if k in fm]
        if vals:
            summary[f"{k}_mean"] = float(np.mean(vals))
            summary[f"{k}_std"] = float(np.std(vals))
    summary["folds"] = fold_metrics
    return summary


def cross_validate_neural(model_cls, hyperparams_base: dict,
                          X: np.ndarray, y: np.ndarray,
                          n_folds: int = 5, device: str = "cpu") -> dict:
    """5-fold stratified cross-validation for a neural model."""
    skf = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)
    fold_metrics = []
    for fold_idx, (train_idx, test_idx) in enumerate(skf.split(X, y)):
        X_tr, y_tr = X[train_idx], y[train_idx]
        X_te, y_te = X[test_idx], y[test_idx]
        # Use 10% of train as validation for early stopping
        split_point = int(len(X_tr) * 0.9)
        X_train_fold, X_val_fold = X_tr[:split_point], X_tr[split_point:]
        y_train_fold, y_val_fold = y_tr[:split_point], y_tr[split_point:]

        hp = dict(hyperparams_base)
        hp["sequence_length"] = X.shape[1]
        hp["input_size"] = X.shape[2]

        model = model_cls(hyperparams=hp)
        model.device = torch.device(device)
        model.model = model.model.to(model.device)
        model.fit(X_train_fold, y_train_fold, X_val_fold, y_val_fold)

        y_pred = model.predict(X_te)
        y_proba = model.predict_proba(X_te)
        fm = compute_metrics(y_te, y_pred, y_proba)
        fm["fold"] = fold_idx + 1
        fold_metrics.append(fm)
        print(f"    Fold {fold_idx+1}: acc={fm['accuracy']:.4f}  f1={fm['f1']:.4f}  auc={fm.get('auc_roc', 0):.4f}")

    keys = ["accuracy", "f1", "precision", "recall", "auc_roc"]
    summary: dict = {}
    for k in keys:
        vals = [fm[k] for fm in fold_metrics if k in fm]
        if vals:
            summary[f"{k}_mean"] = float(np.mean(vals))
            summary[f"{k}_std"] = float(np.std(vals))
    summary["folds"] = fold_metrics
    return summary


# ---------------------------------------------------------------------------
# Temporal validation
# ---------------------------------------------------------------------------

def temporal_validation_rf(X: np.ndarray, y: np.ndarray, shot_ids: np.ndarray,
                           split_point: int = 18000) -> dict:
    """Train RF on early shots, test on later shots."""
    early_mask = shot_ids < split_point
    late_mask = ~early_mask
    X_train, y_train = X[early_mask], y[early_mask]
    X_test, y_test = X[late_mask], y[late_mask]

    if len(X_train) < 10 or len(X_test) < 10:
        return {"error": "Not enough samples for temporal split"}

    rf = train_rf(X_train, y_train)
    metrics = eval_rf(rf, X_test, y_test)
    metrics["train_size"] = len(X_train)
    metrics["test_size"] = len(X_test)
    metrics["train_disruption_rate"] = float(y_train.mean())
    metrics["test_disruption_rate"] = float(y_test.mean())
    return metrics


def temporal_validation_neural(model_cls, hyperparams_base: dict,
                               X: np.ndarray, y: np.ndarray, shot_ids: np.ndarray,
                               split_point: int = 18000, device: str = "cpu") -> dict:
    """Train neural model on early shots, test on later shots."""
    early_mask = shot_ids < split_point
    late_mask = ~early_mask
    X_train, y_train = X[early_mask], y[early_mask]
    X_test, y_test = X[late_mask], y[late_mask]

    if len(X_train) < 10 or len(X_test) < 10:
        return {"error": "Not enough samples for temporal split"}

    # 90/10 split within train for validation
    split_pt = int(len(X_train) * 0.9)
    X_tr, X_val = X_train[:split_pt], X_train[split_pt:]
    y_tr, y_val = y_train[:split_pt], y_train[split_pt:]

    hp = dict(hyperparams_base)
    hp["sequence_length"] = X.shape[1]
    hp["input_size"] = X.shape[2]

    model = train_neural(model_cls, hp, X_tr, y_tr, X_val, y_val, device)
    metrics = eval_neural(model, X_test, y_test)
    metrics["train_size"] = len(X_train)
    metrics["test_size"] = len(X_test)
    metrics["train_disruption_rate"] = float(y_train.mean())
    metrics["test_disruption_rate"] = float(y_test.mean())
    return metrics


# ---------------------------------------------------------------------------
# Main experiment
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run full experiment suite")
    parser.add_argument("--data", default="data/fair_mast_500.npz",
                        help="Path to dataset (.npz with X, y, shot_ids)")
    parser.add_argument("--output", default="results/full_experiment.json",
                        help="Path to save experiment results")
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"],
                        help="Device for neural models")
    parser.add_argument("--quick", action="store_true",
                        help="Quick mode: RF only, skip neural models")
    parser.add_argument("--skip-cv", action="store_true",
                        help="Skip cross-validation (faster)")
    parser.add_argument("--skip-temporal", action="store_true",
                        help="Skip temporal validation")
    parser.add_argument("--split-point", type=int, default=18000,
                        help="Shot ID boundary for temporal split")
    parser.add_argument("--lstm-epochs", type=int, default=50)
    parser.add_argument("--transformer-epochs", type=int, default=40)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict:
    args = parse_args(argv)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    if args.device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    else:
        device = args.device
    print(f"Device: {device}")

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)

    # ---- Load data ----
    data = np.load(args.data)
    X, y = data["X"], data["y"]
    shot_ids = data["shot_ids"] if "shot_ids" in data else None
    print(f"Dataset: {X.shape[0]} shots, {X.shape[1]} timesteps, {X.shape[2]} features")
    print(f"Labels: {int(y.sum())} disruptions ({y.mean()*100:.1f}%)")

    # ---- Standard random split ----
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
    }

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
    rf_metrics["train_time_sec"] = rf_train_time
    rf_latency = measure_latency(
        lambda x: rf_model.predict(x.reshape(len(x), -1)), X_test
    )
    rf_metrics["latency"] = rf_latency
    print(f"  Accuracy: {rf_metrics['accuracy']:.4f}")
    print(f"  F1:       {rf_metrics['f1']:.4f}")
    print(f"  AUC-ROC:  {rf_metrics.get('auc_roc', 0):.4f}")
    print(f"  P99 latency: {rf_latency['p99_ms']:.2f} ms")

    results["random_forest"] = rf_metrics

    # ==================================================================
    # 2. bi-LSTM+Attention
    # ==================================================================
    if not args.quick:
        print("\n" + "=" * 60)
        print("2. bi-LSTM+ATTENTION")
        print("=" * 60)

        lstm_hp = {
            "input_size": X.shape[2],
            "hidden_size": 128,
            "num_layers": 2,
            "bidirectional": True,
            "dropout": 0.3,
            "attention_heads": 4,
            "sequence_length": X.shape[1],
            "learning_rate": 1e-3,
            "batch_size": 32,
            "epochs": args.lstm_epochs,
            "early_stopping_patience": 10,
            "weight_decay": 1e-4,
        }

        t0 = time.time()
        lstm_model = train_neural(LSTMAttentionModel, lstm_hp, X_train, y_train, X_val, y_val, device)
        lstm_train_time = time.time() - t0
        lstm_metrics = eval_neural(lstm_model, X_test, y_test)
        lstm_metrics["train_time_sec"] = lstm_train_time
        lstm_latency = measure_latency(lambda x: lstm_model.predict(x), X_test)
        lstm_metrics["latency"] = lstm_latency
        lstm_metrics["hyperparams"] = lstm_hp
        print(f"  Accuracy: {lstm_metrics['accuracy']:.4f}")
        print(f"  F1:       {lstm_metrics['f1']:.4f}")
        print(f"  AUC-ROC:  {lstm_metrics.get('auc_roc', 0):.4f}")
        print(f"  P99 latency: {lstm_latency['p99_ms']:.2f} ms")

        results["lstm_attention"] = lstm_metrics

        # ==============================================================
        # 3. Autoregressive Transformer
        # ==============================================================
        print("\n" + "=" * 60)
        print("3. AUTOREGRESSIVE TRANSFORMER")
        print("=" * 60)

        transformer_hp = {
            "input_size": X.shape[2],
            "d_model": 128,
            "num_heads": 8,
            "num_layers": 4,
            "dim_feedforward": 512,
            "dropout": 0.1,
            "sequence_length": X.shape[1],
            "learning_rate": 5e-4,
            "warmup_steps": 1000,
            "batch_size": 16,
            "epochs": args.transformer_epochs,
            "early_stopping_patience": 8,
            "weight_decay": 1e-4,
        }

        t0 = time.time()
        tf_model = train_neural(TransformerModel, transformer_hp, X_train, y_train, X_val, y_val, device)
        tf_train_time = time.time() - t0
        tf_metrics = eval_neural(tf_model, X_test, y_test)
        tf_metrics["train_time_sec"] = tf_train_time
        tf_latency = measure_latency(lambda x: tf_model.predict(x), X_test)
        tf_metrics["latency"] = tf_latency
        tf_metrics["hyperparams"] = transformer_hp
        print(f"  Accuracy: {tf_metrics['accuracy']:.4f}")
        print(f"  F1:       {tf_metrics['f1']:.4f}")
        print(f"  AUC-ROC:  {tf_metrics.get('auc_roc', 0):.4f}")
        print(f"  P99 latency: {tf_latency['p99_ms']:.2f} ms")

        results["transformer"] = tf_metrics

    # ==================================================================
    # 4. Cross-validation
    # ==================================================================
    if not args.skip_cv:
        print("\n" + "=" * 60)
        print("4. 5-FOLD CROSS-VALIDATION")
        print("=" * 60)

        print("  RF cross-validation:")
        cv_rf = cross_validate_rf(X, y, n_folds=5)
        print(f"    Mean accuracy: {cv_rf['accuracy_mean']:.4f} +/- {cv_rf['accuracy_std']:.4f}")
        print(f"    Mean AUC-ROC:  {cv_rf.get('auc_roc_mean', 0):.4f} +/- {cv_rf.get('auc_roc_std', 0):.4f}")
        results["cross_validation_rf"] = cv_rf

        if not args.quick:
            print("\n  LSTM cross-validation:")
            lstm_cv_hp = {
                "hidden_size": 128, "num_layers": 2, "bidirectional": True,
                "dropout": 0.3, "attention_heads": 4, "learning_rate": 1e-3,
                "batch_size": 32, "epochs": max(10, args.lstm_epochs // 3),
                "early_stopping_patience": 5, "weight_decay": 1e-4,
            }
            cv_lstm = cross_validate_neural(LSTMAttentionModel, lstm_cv_hp, X, y, n_folds=5, device=device)
            print(f"    Mean accuracy: {cv_lstm['accuracy_mean']:.4f} +/- {cv_lstm['accuracy_std']:.4f}")
            results["cross_validation_lstm"] = cv_lstm

            print("\n  Transformer cross-validation:")
            tf_cv_hp = {
                "d_model": 128, "num_heads": 8, "num_layers": 4,
                "dim_feedforward": 512, "dropout": 0.1, "learning_rate": 5e-4,
                "warmup_steps": 500, "batch_size": 16,
                "epochs": max(10, args.transformer_epochs // 3),
                "early_stopping_patience": 5, "weight_decay": 1e-4,
            }
            cv_tf = cross_validate_neural(TransformerModel, tf_cv_hp, X, y, n_folds=5, device=device)
            print(f"    Mean accuracy: {cv_tf['accuracy_mean']:.4f} +/- {cv_tf['accuracy_std']:.4f}")
            results["cross_validation_transformer"] = cv_tf

    # ==================================================================
    # 5. Temporal validation
    # ==================================================================
    if not args.skip_temporal and shot_ids is not None:
        print("\n" + "=" * 60)
        print("5. TEMPORAL VALIDATION")
        print("=" * 60)

        print(f"  Split point: shot {args.split_point}")
        early_count = int((shot_ids < args.split_point).sum())
        late_count = int((shot_ids >= args.split_point).sum())
        print(f"  Early (train): {early_count} shots, Late (test): {late_count} shots")

        print("\n  RF temporal validation:")
        tv_rf = temporal_validation_rf(X, y, shot_ids, args.split_point)
        if "error" not in tv_rf:
            print(f"    Accuracy: {tv_rf['accuracy']:.4f}  F1: {tv_rf['f1']:.4f}  AUC: {tv_rf.get('auc_roc', 0):.4f}")
        else:
            print(f"    {tv_rf['error']}")
        results["temporal_validation_rf"] = tv_rf

        if not args.quick:
            print("\n  LSTM temporal validation:")
            tv_lstm = temporal_validation_neural(
                LSTMAttentionModel, lstm_cv_hp, X, y, shot_ids, args.split_point, device
            )
            if "error" not in tv_lstm:
                print(f"    Accuracy: {tv_lstm['accuracy']:.4f}  F1: {tv_lstm['f1']:.4f}  AUC: {tv_lstm.get('auc_roc', 0):.4f}")
            else:
                print(f"    {tv_lstm['error']}")
            results["temporal_validation_lstm"] = tv_lstm

            print("\n  Transformer temporal validation:")
            tv_tf = temporal_validation_neural(
                TransformerModel, tf_cv_hp, X, y, shot_ids, args.split_point, device
            )
            if "error" not in tv_tf:
                print(f"    Accuracy: {tv_tf['accuracy']:.4f}  F1: {tv_tf['f1']:.4f}  AUC: {tv_tf.get('auc_roc', 0):.4f}")
            else:
                print(f"    {tv_tf['error']}")
            results["temporal_validation_transformer"] = tv_tf
    elif shot_ids is None:
        print("\nSkipping temporal validation: no shot_ids in dataset")

    # ==================================================================
    # Summary table
    # ==================================================================
    print("\n" + "=" * 70)
    print(f"{'Model':<20} {'Accuracy':>10} {'F1':>8} {'AUC-ROC':>10} {'P99 (ms)':>10}")
    print("=" * 70)

    for name, key in [("Random Forest", "random_forest"),
                      ("bi-LSTM+Att", "lstm_attention"),
                      ("Transformer", "transformer")]:
        if key in results:
            m = results[key]
            lat = m.get("latency", {}).get("p99_ms", 0)
            print(f"{name:<20} {m['accuracy']:>10.4f} {m['f1']:>8.4f} {m.get('auc_roc', 0):>10.4f} {lat:>10.2f}")
    print("=" * 70)

    # ---- Save ----
    with open(args.output, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nFull results saved to {args.output}")

    return results


if __name__ == "__main__":
    main()
