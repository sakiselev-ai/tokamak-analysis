from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split

# Allow imports from ml_service root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from service.models.transformer import TransformerModel


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train autoregressive Transformer model for disruption prediction"
    )
    parser.add_argument(
        "--data",
        type=str,
        default="data/fair_mast_dataset.npz",
        help="Path to dataset (.npz with X, y arrays)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="models/transformer.pt",
        help="Path to save model artifact",
    )
    parser.add_argument("--epochs", type=int, default=40, help="Number of training epochs")
    parser.add_argument("--lr", type=float, default=5e-4, help="Learning rate")
    parser.add_argument("--d-model", type=int, default=128, help="Transformer model dimension")
    parser.add_argument("--num-heads", type=int, default=8, help="Number of attention heads")
    parser.add_argument("--num-layers", type=int, default=4, help="Number of transformer layers")
    parser.add_argument("--batch-size", type=int, default=16, help="Training batch size")
    parser.add_argument(
        "--warmup-steps", type=int, default=1000, help="Warmup steps for cosine scheduler"
    )
    parser.add_argument(
        "--device",
        type=str,
        default="auto",
        choices=["auto", "cpu", "cuda"],
        help="Device for training (auto-detects CUDA)",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    return parser.parse_args(argv)


def load_dataset(path: str) -> tuple[np.ndarray, np.ndarray]:
    """Load dataset from .npz file.

    Expected format: X shape (n_samples, seq_len, n_features), y shape (n_samples,).
    """
    data = np.load(path)
    X, y = data["X"], data["y"]
    print(f"Loaded dataset: X={X.shape}, y={y.shape}")
    print(f"  Class distribution: {dict(zip(*np.unique(y, return_counts=True)))}")
    return X, y


def split_dataset(
    X: np.ndarray, y: np.ndarray, seed: int = 42
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Split into train/val/test (80/10/10, stratified)."""
    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=0.2, random_state=seed, stratify=y
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.5, random_state=seed, stratify=y_temp
    )
    print(f"  Train: {X_train.shape[0]}, Val: {X_val.shape[0]}, Test: {X_test.shape[0]}")
    return X_train, X_val, X_test, y_train, y_val, y_test


def compute_metrics(
    model: TransformerModel, X_test: np.ndarray, y_test: np.ndarray
) -> dict:
    """Compute evaluation metrics on test set."""
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)

    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "f1": float(f1_score(y_test, y_pred, average="weighted")),
        "precision": float(precision_score(y_test, y_pred, average="weighted")),
        "recall": float(recall_score(y_test, y_pred, average="weighted")),
    }
    if y_proba.shape[1] == 2:
        metrics["auc_roc"] = float(roc_auc_score(y_test, y_proba[:, 1]))

    return metrics


def train(args: argparse.Namespace) -> dict:
    """Run the full training pipeline. Returns test metrics dict."""
    # Seed
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    # Device
    if args.device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    else:
        device = args.device
    print(f"Using device: {device}")

    # Load and split data
    X, y = load_dataset(args.data)
    X_train, X_val, X_test, y_train, y_val, y_test = split_dataset(X, y, args.seed)

    input_size = X_train.shape[2]

    # Create model with Transformer-specific hyperparams
    hyperparams = {
        "input_size": input_size,
        "d_model": args.d_model,
        "num_heads": args.num_heads,
        "num_layers": args.num_layers,
        "dim_feedforward": args.d_model * 4,
        "dropout": 0.1,
        "sequence_length": X_train.shape[1],
        "learning_rate": args.lr,
        "warmup_steps": args.warmup_steps,
        "batch_size": args.batch_size,
        "epochs": args.epochs,
        "early_stopping_patience": 8,
        "weight_decay": 1e-4,
    }

    model = TransformerModel(hyperparams=hyperparams)
    model.device = torch.device(device)
    model.model = model.model.to(model.device)

    # Output directory
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_dir = output_path.parent / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    # Best model state tracking for checkpoint saving
    best_val_loss = float("inf")
    best_model_state = None

    def progress_callback(
        epoch: int, total_epochs: int, train_loss: float, val_loss: float
    ) -> None:
        nonlocal best_val_loss, best_model_state

        # Compute validation accuracy
        val_preds = model.predict(X_val)
        val_acc = accuracy_score(y_val, val_preds)

        print(
            f"  Epoch {epoch:3d}/{total_epochs} | "
            f"loss={train_loss:.4f} | val_loss={val_loss:.4f} | val_acc={val_acc:.4f}"
        )

        # Track best model
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_model_state = {
                k: v.clone() for k, v in model.model.state_dict().items()
            }

        # Save checkpoint every 5 epochs
        if epoch % 5 == 0:
            ckpt_path = checkpoint_dir / f"transformer_epoch_{epoch:03d}.pt"
            model.save(str(ckpt_path))
            print(f"    Checkpoint saved: {ckpt_path}")

    # Train
    print("\n=== Training Autoregressive Transformer ===")
    start_time = time.time()
    train_metrics = model.fit(
        X_train, y_train, X_val, y_val, progress_callback=progress_callback
    )
    elapsed = time.time() - start_time
    print(f"\nTraining completed in {elapsed:.1f}s")
    print(f"  Epochs trained: {train_metrics['epochs_trained']}")
    print(f"  Best val loss: {train_metrics['best_val_loss']:.4f}")

    # Restore best model weights
    if best_model_state is not None:
        model.model.load_state_dict(best_model_state)
        print("  Restored best model weights")

    # Evaluate on test set
    print("\n=== Test Set Evaluation ===")
    test_metrics = compute_metrics(model, X_test, y_test)
    for name, value in test_metrics.items():
        print(f"  {name}: {value:.4f}")

    # Classification report
    y_pred = model.predict(X_test)
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))

    print("Confusion Matrix:")
    cm = confusion_matrix(y_test, y_pred)
    print(cm)

    # Save model
    model.save(str(output_path))
    print(f"\nModel saved to {output_path}")

    # Save metrics JSON
    all_metrics = {
        "model": "Autoregressive Transformer",
        "train_metrics": train_metrics,
        "test_metrics": test_metrics,
        "hyperparams": hyperparams,
        "confusion_matrix": cm.tolist(),
        "training_time_seconds": elapsed,
        "device": device,
    }

    metrics_path = output_path.with_suffix(".json")
    with open(metrics_path, "w") as f:
        json.dump(all_metrics, f, indent=2)
    print(f"Metrics saved to {metrics_path}")

    return test_metrics


if __name__ == "__main__":
    args = parse_args()
    train(args)
