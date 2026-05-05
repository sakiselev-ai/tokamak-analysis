from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split

# Allow imports from ml_service root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from service.models.lstm_attention import LSTMAttentionModel
from service.models.random_forest import RandomForestModel
from service.models.transformer import TransformerModel


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark all models on the same test set"
    )
    parser.add_argument(
        "--data",
        type=str,
        default="data/fair_mast_dataset.npz",
        help="Path to dataset (.npz with X, y arrays)",
    )
    parser.add_argument(
        "--rf",
        type=str,
        default="models/rf_baseline.joblib",
        help="Path to trained Random Forest model",
    )
    parser.add_argument(
        "--lstm",
        type=str,
        default="models/lstm_attention.pt",
        help="Path to trained LSTM model",
    )
    parser.add_argument(
        "--transformer",
        type=str,
        default="models/transformer.pt",
        help="Path to trained Transformer model",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="models/benchmark_results.json",
        help="Path to save benchmark results JSON",
    )
    parser.add_argument(
        "--n-latency-runs",
        type=int,
        default=100,
        help="Number of inference runs for latency measurement",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    return parser.parse_args(argv)


def load_test_set(
    data_path: str, seed: int = 42
) -> tuple[np.ndarray, np.ndarray]:
    """Load dataset and return the test split (same split as training scripts)."""
    data = np.load(data_path)
    X, y = data["X"], data["y"]

    # Reproduce the same 80/10/10 split used in training
    _, X_temp, _, y_temp = train_test_split(
        X, y, test_size=0.2, random_state=seed, stratify=y
    )
    _, X_test, _, y_test = train_test_split(
        X_temp, y_temp, test_size=0.5, random_state=seed, stratify=y_temp
    )
    return X_test, y_test


def measure_latency(
    predict_fn, X: np.ndarray, n_runs: int = 100
) -> dict[str, float]:
    """Measure inference latency statistics over n_runs single-sample predictions."""
    latencies = []
    # Use a single sample for latency measurement
    x_single = X[:1]

    # Warmup
    for _ in range(5):
        predict_fn(x_single)

    for _ in range(n_runs):
        start = time.perf_counter()
        predict_fn(x_single)
        elapsed = (time.perf_counter() - start) * 1000  # ms
        latencies.append(elapsed)

    latencies_arr = np.array(latencies)
    return {
        "mean_ms": float(np.mean(latencies_arr)),
        "p50_ms": float(np.percentile(latencies_arr, 50)),
        "p95_ms": float(np.percentile(latencies_arr, 95)),
        "p99_ms": float(np.percentile(latencies_arr, 99)),
    }


def evaluate_model(
    name: str,
    model,
    X_test: np.ndarray,
    y_test: np.ndarray,
    X_test_2d: np.ndarray | None = None,
    n_latency_runs: int = 100,
) -> dict:
    """Evaluate a single model: metrics + latency."""
    # For RF, use 2D input (flattened); for neural nets, use 3D
    X_eval = X_test_2d if X_test_2d is not None else X_test

    y_pred = model.predict(X_eval)
    y_proba = model.predict_proba(X_eval)

    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "f1": float(f1_score(y_test, y_pred, average="weighted")),
    }
    if y_proba.shape[1] == 2:
        metrics["auc_roc"] = float(roc_auc_score(y_test, y_proba[:, 1]))

    latency = measure_latency(
        lambda x: model.predict(x),
        X_eval,
        n_runs=n_latency_runs,
    )

    return {"name": name, "metrics": metrics, "latency": latency}


def format_table(results: list[dict]) -> str:
    """Format results as a markdown-style comparison table."""
    header = (
        "| Model        | Accuracy | F1    | AUC-ROC | P99 Latency |"
    )
    separator = (
        "|--------------|----------|-------|---------|-------------|"
    )

    rows = []
    for r in results:
        m = r["metrics"]
        p99 = r["latency"]["p99_ms"]
        row = (
            f"| {r['name']:<12s} | {m['accuracy']:.4f}   | "
            f"{m['f1']:.3f} | {m.get('auc_roc', 0.0):.3f}   | "
            f"{p99:.1f}ms{' ' * max(0, 6 - len(f'{p99:.1f}'))}|"
        )
        rows.append(row)

    lines = [
        "=== Model Comparison on FAIR-MAST Test Set ===",
        header,
        separator,
        *rows,
    ]
    return "\n".join(lines)


def benchmark(args: argparse.Namespace) -> list[dict]:
    """Run benchmark on all models. Returns list of result dicts."""
    np.random.seed(args.seed)

    # Load test set
    print("Loading test set...")
    X_test, y_test = load_test_set(args.data, args.seed)
    print(f"  Test set: {X_test.shape[0]} samples")

    # Flatten for RF (n_samples, seq_len * n_features)
    X_test_2d = X_test.reshape(X_test.shape[0], -1)

    results = []

    # Random Forest
    if Path(args.rf).exists():
        print("\nLoading Random Forest...")
        rf_model = RandomForestModel()
        rf_model.load(args.rf)
        rf_result = evaluate_model(
            "RandomForest", rf_model, X_test, y_test,
            X_test_2d=X_test_2d, n_latency_runs=args.n_latency_runs,
        )
        results.append(rf_result)
        print(f"  Accuracy: {rf_result['metrics']['accuracy']:.4f}")
    else:
        print(f"\nSkipping Random Forest: {args.rf} not found")

    # bi-LSTM+Attention
    if Path(args.lstm).exists():
        print("\nLoading bi-LSTM+Attention...")
        lstm_model = LSTMAttentionModel()
        lstm_model.load(args.lstm)
        lstm_result = evaluate_model(
            "bi-LSTM+Att", lstm_model, X_test, y_test,
            n_latency_runs=args.n_latency_runs,
        )
        results.append(lstm_result)
        print(f"  Accuracy: {lstm_result['metrics']['accuracy']:.4f}")
    else:
        print(f"\nSkipping bi-LSTM+Attention: {args.lstm} not found")

    # Transformer
    if Path(args.transformer).exists():
        print("\nLoading Transformer...")
        tf_model = TransformerModel()
        tf_model.load(args.transformer)
        tf_result = evaluate_model(
            "Transformer", tf_model, X_test, y_test,
            n_latency_runs=args.n_latency_runs,
        )
        results.append(tf_result)
        print(f"  Accuracy: {tf_result['metrics']['accuracy']:.4f}")
    else:
        print(f"\nSkipping Transformer: {args.transformer} not found")

    # Print comparison table
    if results:
        print("\n")
        print(format_table(results))

    # Save results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {output_path}")

    return results


if __name__ == "__main__":
    args = parse_args()
    benchmark(args)
