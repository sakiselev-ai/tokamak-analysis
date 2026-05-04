from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def compute_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_proba: np.ndarray | None = None,
) -> dict:
    """Compute standard classification metrics.

    Args:
        y_true: Ground-truth labels (1-D).
        y_pred: Predicted labels (1-D).
        y_proba: Predicted probabilities.  Can be 1-D (positive-class
            probability) or 2-D ``(n_samples, n_classes)``.

    Returns:
        Dictionary with ``accuracy``, ``precision``, ``recall``, ``f1``,
        and optionally ``auc_roc``.
    """
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)

    results: dict = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, average="weighted", zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, average="weighted", zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, average="weighted", zero_division=0)),
    }

    if y_proba is not None:
        y_proba = np.asarray(y_proba)
        try:
            # Use positive-class probability for binary case
            if y_proba.ndim == 2 and y_proba.shape[1] == 2:
                score = roc_auc_score(y_true, y_proba[:, 1])
            elif y_proba.ndim == 1:
                score = roc_auc_score(y_true, y_proba)
            else:
                score = roc_auc_score(
                    y_true, y_proba, multi_class="ovr", average="weighted"
                )
            results["auc_roc"] = float(score)
        except ValueError:
            # AUC is undefined when only one class present in y_true
            results["auc_roc"] = None

    return results


def format_confusion_matrix(
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> dict:
    """Build a JSON-friendly confusion matrix.

    Returns:
        Dictionary with ``matrix`` (list of lists), ``labels``
        (sorted unique labels), ``true_positives``, ``false_positives``,
        ``true_negatives``, ``false_negatives`` (for binary case).
    """
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    labels = sorted(set(y_true.tolist()) | set(y_pred.tolist()))
    cm = confusion_matrix(y_true, y_pred, labels=labels)

    result: dict = {
        "matrix": cm.tolist(),
        "labels": labels,
    }

    # Provide convenience fields for binary classification
    if len(labels) == 2:
        tn, fp, fn, tp = cm.ravel()
        result.update({
            "true_positives": int(tp),
            "false_positives": int(fp),
            "true_negatives": int(tn),
            "false_negatives": int(fn),
        })

    return result
