from __future__ import annotations
"""Temporal validation: train on early MAST campaigns, test on later ones.

This validates that models generalize across time periods, not just across
random splits. Required for peer-reviewed publication.

Usage:
    python temporal_validation.py --data data/fair_mast_500.npz --output results/temporal_validation.json
"""
import argparse
import json
import os
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score, classification_report
import joblib
import time

def temporal_split(X, y, shot_ids, early_max=18000):
    """Split by shot ID: early campaigns for train, late for test.

    MAST shot numbering roughly corresponds to chronological order:
    - Early: 11000-18000 (~1999-2009)
    - Late: 18000-30000 (~2009-2013)
    """
    early_mask = shot_ids < early_max
    late_mask = ~early_mask

    X_train, y_train = X[early_mask], y[early_mask]
    X_test, y_test = X[late_mask], y[late_mask]

    return X_train, y_train, X_test, y_test

def train_and_evaluate_rf(X_train, y_train, X_test, y_test):
    """Train RF and evaluate."""
    # Flatten for RF
    X_tr_flat = X_train.reshape(len(X_train), -1)
    X_te_flat = X_test.reshape(len(X_test), -1)

    model = RandomForestClassifier(
        n_estimators=200, max_depth=20, class_weight='balanced',
        random_state=42, n_jobs=-1
    )

    t0 = time.time()
    model.fit(X_tr_flat, y_train)
    train_time = time.time() - t0

    y_pred = model.predict(X_te_flat)
    y_proba = model.predict_proba(X_te_flat)

    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "f1": float(f1_score(y_test, y_pred, average='weighted', zero_division=0)),
        "train_time_sec": train_time,
        "train_size": len(X_train),
        "test_size": len(X_test),
        "train_disruption_rate": float(y_train.mean()),
        "test_disruption_rate": float(y_test.mean()),
    }

    try:
        metrics["auc_roc"] = float(roc_auc_score(y_test, y_proba[:, 1]))
    except Exception:
        metrics["auc_roc"] = 0.0

    return metrics, classification_report(y_test, y_pred, target_names=['Stable', 'Disruption'], output_dict=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/fair_mast_500.npz")
    parser.add_argument("--output", default="results/temporal_validation.json")
    parser.add_argument("--split-point", type=int, default=18000,
                       help="Shot ID boundary between train and test periods")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)

    data = np.load(args.data)
    X, y, shot_ids = data['X'], data['y'], data['shot_ids']

    print(f"Dataset: {len(X)} shots, shot IDs {shot_ids.min()}-{shot_ids.max()}")
    print(f"Labels: {int(y.sum())} disruptions ({y.mean()*100:.1f}%)")

    # Temporal split
    X_train, y_train, X_test, y_test = temporal_split(X, y, shot_ids, args.split_point)

    print(f"\nTemporal Split (boundary: shot {args.split_point}):")
    print(f"  Train: {len(X_train)} shots (IDs < {args.split_point}), {y_train.mean()*100:.1f}% disruptions")
    print(f"  Test:  {len(X_test)} shots (IDs >= {args.split_point}), {y_test.mean()*100:.1f}% disruptions")

    if len(X_train) < 10 or len(X_test) < 10:
        print("ERROR: Not enough samples for temporal split. Need shots from different campaigns.")
        return

    # Random Forest
    print(f"\n=== Random Forest (Temporal Validation) ===")
    rf_metrics, rf_report = train_and_evaluate_rf(X_train, y_train, X_test, y_test)
    print(f"  Accuracy: {rf_metrics['accuracy']:.4f}")
    print(f"  F1: {rf_metrics['f1']:.4f}")
    print(f"  AUC-ROC: {rf_metrics['auc_roc']:.4f}")

    # Also do standard random split for comparison
    print(f"\n=== Random Forest (Random Split - for comparison) ===")
    from sklearn.model_selection import train_test_split
    X_tr_r, X_te_r, y_tr_r, y_te_r = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    rf_random_metrics, rf_random_report = train_and_evaluate_rf(X_tr_r, y_tr_r, X_te_r, y_te_r)
    print(f"  Accuracy: {rf_random_metrics['accuracy']:.4f}")
    print(f"  F1: {rf_random_metrics['f1']:.4f}")
    print(f"  AUC-ROC: {rf_random_metrics['auc_roc']:.4f}")

    # Summary
    results = {
        "dataset": {
            "total_shots": len(X),
            "shot_id_range": [int(shot_ids.min()), int(shot_ids.max())],
            "features": X.shape[2],
            "timesteps": X.shape[1],
            "disruption_rate": float(y.mean()),
        },
        "temporal_split": {
            "boundary_shot_id": args.split_point,
            "train_size": len(X_train),
            "test_size": len(X_test),
        },
        "temporal_validation": {
            "random_forest": rf_metrics,
            "classification_report": rf_report,
        },
        "random_split_comparison": {
            "random_forest": rf_random_metrics,
            "classification_report": rf_random_report,
        },
    }

    print(f"\n{'='*50}")
    print(f"{'Validation Type':<25} {'Accuracy':>10} {'F1':>8} {'AUC-ROC':>10}")
    print(f"{'='*50}")
    print(f"{'Temporal (train<{})'.format(args.split_point):<25} {rf_metrics['accuracy']:>10.4f} {rf_metrics['f1']:>8.4f} {rf_metrics['auc_roc']:>10.4f}")
    print(f"{'Random (80/20)':<25} {rf_random_metrics['accuracy']:>10.4f} {rf_random_metrics['f1']:>8.4f} {rf_random_metrics['auc_roc']:>10.4f}")
    print(f"{'='*50}")

    with open(args.output, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {args.output}")

if __name__ == "__main__":
    main()
