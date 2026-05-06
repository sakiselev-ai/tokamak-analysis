from __future__ import annotations
"""Temporal validation: train on early MAST campaigns, test on later ones.

Compares temporal split (early shots train, late shots test) vs random split
for all 3 models (RF, LSTM, Transformer). This validates that models generalize
across time periods, not just across random splits.

Usage:
    python -m scripts.temporal_validation --data data/fair_mast_500.npz
    python scripts/temporal_validation.py --quick
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
from sklearn.model_selection import train_test_split

# ---------------------------------------------------------------------------
# sys.path fix so the script works both as `python scripts/temporal_validation.py`
# and `python -m scripts.temporal_validation` from ml_service/
# ---------------------------------------------------------------------------
_ml_service_root = str(Path(__file__).resolve().parent.parent)
if _ml_service_root not in sys.path:
    sys.path.insert(0, _ml_service_root)

from service.data.dataset import get_sample_dataset  # noqa: E402
from service.data.metrics import compute_metrics  # noqa: E402
from service.models.random_forest import RandomForestModel  # noqa: E402

# ---------------------------------------------------------------------------
# Optional torch-based models
# ---------------------------------------------------------------------------
_HAS_TORCH = False
try:
    import torch  # noqa: F401

    from service.models.lstm_attention import LSTMAttentionModel  # noqa: E402
    from service.models.transformer import TransformerModel  # noqa: E402

    _HAS_TORCH = True
except ImportError:
    LSTMAttentionModel = None  # type: ignore[assignment,misc]
    TransformerModel = None  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def generate_synthetic_data(
    n_samples: int = 300,
    seq_len: int = 50,
    n_features: int = 10,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (X, y, shot_ids) with synthetic tokamak-like data."""
    rng = np.random.RandomState(seed)
    X = rng.randn(n_samples, seq_len, n_features).astype(np.float32)

    # Positive class: inject instability ramp
    n_pos = n_samples // 3
    ramp = np.linspace(0, 3, seq_len).reshape(1, seq_len, 1)
    X[:n_pos] += ramp
    y = np.zeros(n_samples, dtype=np.float32)
    y[:n_pos] = 1.0

    # Fake shot IDs spanning early/late campaigns
    shot_ids = np.sort(rng.randint(11000, 30000, size=n_samples))

    # Shuffle consistently
    perm = rng.permutation(n_samples)
    return X[perm], y[perm], shot_ids[perm]


def load_or_generate(
    data_path: str | None,
    quick: bool = False,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Load .npz data or fall back to synthetic."""
    if data_path and os.path.isfile(data_path):
        data = np.load(data_path)
        X, y = data["X"], data["y"]
        shot_ids = data["shot_ids"] if "shot_ids" in data else None
        if shot_ids is None:
            # Fabricate shot_ids from index
            shot_ids = np.linspace(11000, 30000, len(X)).astype(int)
        return X, y, shot_ids

    if data_path:
        print(f"WARNING: '{data_path}' not found, generating synthetic data.")
    n = 100 if quick else 300
    sl = 30 if quick else 50
    nf = 10
    return generate_synthetic_data(n_samples=n, seq_len=sl, n_features=nf)


# ---------------------------------------------------------------------------
# Split helpers
# ---------------------------------------------------------------------------

def temporal_split(
    X: np.ndarray,
    y: np.ndarray,
    shot_ids: np.ndarray,
    early_max: int = 18000,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Split by shot ID: early campaigns for train, late for test."""
    early_mask = shot_ids < early_max
    late_mask = ~early_mask
    return X[early_mask], y[early_mask], X[late_mask], y[late_mask]


def random_split(
    X: np.ndarray,
    y: np.ndarray,
    test_size: float = 0.2,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Standard random stratified split."""
    return train_test_split(X, y, test_size=test_size, random_state=seed, stratify=y)


# ---------------------------------------------------------------------------
# Train + evaluate helpers
# ---------------------------------------------------------------------------

def _eval_metrics(
    y_true: np.ndarray, y_pred: np.ndarray, y_proba: np.ndarray | None
) -> dict:
    """Compute accuracy, F1, AUC-ROC."""
    return compute_metrics(y_true, y_pred, y_proba)


def train_eval_rf(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
) -> dict:
    """Train RandomForestModel and evaluate."""
    X_tr_flat = X_train.reshape(len(X_train), -1)
    X_te_flat = X_test.reshape(len(X_test), -1)

    model = RandomForestModel()
    t0 = time.time()
    model.fit(X_tr_flat, y_train, X_te_flat, y_test)
    train_time = time.time() - t0

    y_pred = model.predict(X_te_flat)
    y_proba = model.predict_proba(X_te_flat)
    metrics = _eval_metrics(y_test, y_pred, y_proba)
    metrics["train_time_sec"] = round(train_time, 3)
    return metrics


def train_eval_lstm(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    epochs: int = 20,
) -> dict:
    """Train LSTMAttentionModel and evaluate."""
    if not _HAS_TORCH:
        return {"error": "torch not installed"}
    hp = {
        "input_size": X_train.shape[2],
        "hidden_size": 64,
        "num_layers": 1,
        "bidirectional": True,
        "dropout": 0.1,
        "attention_heads": 2,
        "sequence_length": X_train.shape[1],
        "learning_rate": 1e-3,
        "batch_size": 32,
        "epochs": epochs,
        "early_stopping_patience": 5,
        "weight_decay": 1e-4,
    }
    # Carve out 10% of train for early-stopping validation
    split_pt = max(1, int(len(X_train) * 0.9))
    X_tr, X_val = X_train[:split_pt], X_train[split_pt:]
    y_tr, y_val = y_train[:split_pt], y_train[split_pt:]

    model = LSTMAttentionModel(hyperparams=hp)
    t0 = time.time()
    model.fit(X_tr, y_tr, X_val, y_val)
    train_time = time.time() - t0

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)
    metrics = _eval_metrics(y_test, y_pred, y_proba)
    metrics["train_time_sec"] = round(train_time, 3)
    return metrics


def train_eval_transformer(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    epochs: int = 15,
) -> dict:
    """Train TransformerModel and evaluate."""
    if not _HAS_TORCH:
        return {"error": "torch not installed"}
    hp = {
        "input_size": X_train.shape[2],
        "d_model": 64,
        "num_heads": 4,
        "num_layers": 2,
        "dim_feedforward": 128,
        "dropout": 0.1,
        "sequence_length": X_train.shape[1],
        "learning_rate": 5e-4,
        "warmup_steps": 100,
        "batch_size": 16,
        "epochs": epochs,
        "early_stopping_patience": 5,
        "weight_decay": 1e-4,
    }
    split_pt = max(1, int(len(X_train) * 0.9))
    X_tr, X_val = X_train[:split_pt], X_train[split_pt:]
    y_tr, y_val = y_train[:split_pt], y_train[split_pt:]

    model = TransformerModel(hyperparams=hp)
    t0 = time.time()
    model.fit(X_tr, y_tr, X_val, y_val)
    train_time = time.time() - t0

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)
    metrics = _eval_metrics(y_test, y_pred, y_proba)
    metrics["train_time_sec"] = round(train_time, 3)
    return metrics


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Temporal validation: compare temporal vs random split"
    )
    parser.add_argument("--data", default=None,
                        help="Path to .npz file (X, y, shot_ids). Synthetic if missing.")
    parser.add_argument("--output", default="results/temporal_validation.json",
                        help="Path to save JSON results")
    parser.add_argument("--split-point", type=int, default=0,
                        help="Shot ID boundary between train/test periods (0=auto median)")
    parser.add_argument("--quick", action="store_true",
                        help="Smaller data, fewer epochs for fast testing")
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict:
    args = parse_args(argv)
    np.random.seed(args.seed)

    # Quick-mode epoch counts
    lstm_epochs = 5 if args.quick else 20
    tf_epochs = 5 if args.quick else 15

    X, y, shot_ids = load_or_generate(args.data, quick=args.quick)
    print(f"Dataset: {len(X)} shots, shape {X.shape}")
    print(f"Labels: {int(y.sum())} disruptions ({y.mean()*100:.1f}%)")
    print(f"Shot IDs: {int(shot_ids.min())}-{int(shot_ids.max())}")

    # --- Build model list ---
    model_runners = [
        ("Random Forest", train_eval_rf, {}),
    ]
    if _HAS_TORCH:
        model_runners.append(("LSTM+Attention", train_eval_lstm, {"epochs": lstm_epochs}))
        model_runners.append(("Transformer", train_eval_transformer, {"epochs": tf_epochs}))
    else:
        print("WARNING: torch not installed, skipping neural models.")

    # --- Temporal split ---
    if args.split_point == 0:
        args.split_point = int(np.median(shot_ids))
        print(f"Auto split point: median shot ID = {args.split_point}")
    X_tr_t, y_tr_t, X_te_t, y_te_t = temporal_split(X, y, shot_ids, args.split_point)
    n_early = len(X_tr_t)
    n_late = len(X_te_t)
    print(f"\nTemporal split (boundary: shot {args.split_point}):")
    print(f"  Train: {n_early} shots (IDs < {args.split_point}), "
          f"{y_tr_t.mean()*100:.1f}% disruptions")
    print(f"  Test:  {n_late} shots (IDs >= {args.split_point}), "
          f"{y_te_t.mean()*100:.1f}% disruptions")

    if n_early < 5 or n_late < 5:
        print("ERROR: Not enough samples for temporal split.")
        return {}

    # --- Random split ---
    X_tr_r, X_te_r, y_tr_r, y_te_r = random_split(X, y, seed=args.seed)
    print(f"\nRandom split: train={len(X_tr_r)}, test={len(X_te_r)}")

    # --- Run all models on both splits ---
    temporal_results: dict = {}
    random_results: dict = {}

    for name, runner, extra_kw in model_runners:
        print(f"\n{'='*55}")
        print(f"  {name}")
        print(f"{'='*55}")

        print(f"  [Temporal split]")
        t_metrics = runner(X_tr_t, y_tr_t, X_te_t, y_te_t, **extra_kw)
        if "error" not in t_metrics:
            print(f"    Accuracy: {t_metrics['accuracy']:.4f}  "
                  f"F1: {t_metrics['f1']:.4f}  "
                  f"AUC-ROC: {t_metrics.get('auc_roc', 'N/A')}")
        else:
            print(f"    Skipped: {t_metrics['error']}")
        temporal_results[name] = t_metrics

        print(f"  [Random split]")
        r_metrics = runner(X_tr_r, y_tr_r, X_te_r, y_te_r, **extra_kw)
        if "error" not in r_metrics:
            print(f"    Accuracy: {r_metrics['accuracy']:.4f}  "
                  f"F1: {r_metrics['f1']:.4f}  "
                  f"AUC-ROC: {r_metrics.get('auc_roc', 'N/A')}")
        else:
            print(f"    Skipped: {r_metrics['error']}")
        random_results[name] = r_metrics

    # --- Summary table ---
    print(f"\n{'='*72}")
    print(f"{'Model':<22} {'Split':<12} {'Accuracy':>10} {'F1':>8} {'AUC-ROC':>10}")
    print(f"{'='*72}")
    for name, _, _ in model_runners:
        for split_name, res_dict in [("Temporal", temporal_results),
                                     ("Random", random_results)]:
            m = res_dict.get(name, {})
            if "error" in m:
                continue
            auc = m.get("auc_roc")
            auc_str = f"{auc:.4f}" if auc is not None else "N/A"
            print(f"{name:<22} {split_name:<12} {m['accuracy']:>10.4f} "
                  f"{m['f1']:>8.4f} {auc_str:>10}")
    print(f"{'='*72}")

    # --- Save results ---
    results = {
        "dataset": {
            "total_shots": len(X),
            "timesteps": int(X.shape[1]),
            "features": int(X.shape[2]),
            "disruption_rate": float(y.mean()),
            "shot_id_range": [int(shot_ids.min()), int(shot_ids.max())],
        },
        "temporal_split": {
            "boundary_shot_id": args.split_point,
            "train_size": n_early,
            "test_size": n_late,
        },
        "temporal_validation": temporal_results,
        "random_split_comparison": random_results,
        "quick_mode": args.quick,
    }

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to {args.output}")

    return results


if __name__ == "__main__":
    main()
