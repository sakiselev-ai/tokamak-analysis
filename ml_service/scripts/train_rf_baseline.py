from __future__ import annotations
"""Train Random Forest baseline on FAIR-MAST data.

Usage:
    python train_rf_baseline.py --data data/fair_mast_dataset.npz --output models/rf_baseline.joblib
"""
import argparse
import json
import os
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score, GridSearchCV, train_test_split
from sklearn.metrics import (
    accuracy_score, f1_score, roc_auc_score, precision_score,
    recall_score, classification_report, confusion_matrix
)
import joblib

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/fair_mast_dataset.npz")
    parser.add_argument("--output", default="models/rf_baseline.joblib")
    parser.add_argument("--quick", action="store_true", help="Quick training (no grid search)")
    args = parser.parse_args()

    # Load data
    dataset = np.load(args.data)
    X_raw, y = dataset['X'], dataset['y']
    print(f"Dataset: {X_raw.shape[0]} samples, {X_raw.shape[1]}x{X_raw.shape[2]} features")
    print(f"Class distribution: {int(y.sum())} disruptions ({y.mean()*100:.1f}%), {int(len(y)-y.sum())} stable")

    # Flatten for RF: (n_samples, seq_len * n_features)
    X = X_raw.reshape(X_raw.shape[0], -1)

    # Train/test split (80/20)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"Train: {len(X_train)}, Test: {len(X_test)}")

    if args.quick:
        # Quick training with defaults
        model = RandomForestClassifier(
            n_estimators=200, max_depth=20, class_weight='balanced',
            random_state=42, n_jobs=-1
        )
        model.fit(X_train, y_train)
    else:
        # Grid search
        param_grid = {
            'n_estimators': [100, 200, 500],
            'max_depth': [10, 20, None],
            'min_samples_split': [2, 5],
            'class_weight': ['balanced', 'balanced_subsample'],
        }
        grid = GridSearchCV(
            RandomForestClassifier(random_state=42, n_jobs=-1),
            param_grid, cv=5, scoring='roc_auc', verbose=1, n_jobs=1
        )
        grid.fit(X_train, y_train)
        model = grid.best_estimator_
        print(f"\nBest params: {grid.best_params_}")
        print(f"Best CV AUC-ROC: {grid.best_score_:.4f}")

    # Cross-validation on full training set
    cv_scores = cross_val_score(model, X_train, y_train, cv=5, scoring='accuracy')
    print(f"\n5-fold CV accuracy: {cv_scores.mean():.4f} +/- {cv_scores.std():.4f}")

    cv_auc = cross_val_score(model, X_train, y_train, cv=5, scoring='roc_auc')
    print(f"5-fold CV AUC-ROC: {cv_auc.mean():.4f} +/- {cv_auc.std():.4f}")

    # Test set evaluation
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    metrics = {
        "accuracy": accuracy_score(y_test, y_pred),
        "f1": f1_score(y_test, y_pred, average='weighted'),
        "precision": precision_score(y_test, y_pred, average='weighted', zero_division=0),
        "recall": recall_score(y_test, y_pred, average='weighted', zero_division=0),
        "auc_roc": roc_auc_score(y_test, y_proba) if len(np.unique(y_test)) > 1 else 0.0,
        "cv_accuracy_mean": float(cv_scores.mean()),
        "cv_accuracy_std": float(cv_scores.std()),
        "cv_auc_mean": float(cv_auc.mean()),
        "cv_auc_std": float(cv_auc.std()),
    }

    print(f"\n=== Test Set Results ===")
    print(f"Accuracy: {metrics['accuracy']:.4f}")
    print(f"F1:       {metrics['f1']:.4f}")
    print(f"AUC-ROC:  {metrics['auc_roc']:.4f}")
    print(f"\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=['Stable', 'Disruption']))
    print(f"Confusion Matrix:")
    print(confusion_matrix(y_test, y_pred))

    # Save
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    artifact = {
        "model": model,
        "metrics": metrics,
        "hyperparams": model.get_params(),
        "feature_importances": model.feature_importances_.tolist(),
        "n_features": X_raw.shape[2],
        "seq_len": X_raw.shape[1],
    }
    joblib.dump(artifact, args.output)

    # Save metrics as JSON
    metrics_file = args.output.replace('.joblib', '_metrics.json')
    with open(metrics_file, 'w') as f:
        json.dump(metrics, f, indent=2)

    print(f"\nModel saved to {args.output}")
    print(f"Metrics saved to {metrics_file}")

if __name__ == "__main__":
    main()
