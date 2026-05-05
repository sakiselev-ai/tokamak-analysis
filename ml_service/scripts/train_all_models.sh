#!/bin/bash
set -e
echo "=== Phase 1: Download FAIR-MAST data ==="
python scripts/download_fair_mast.py --shots 200 --seq-len 200 --n-features 20 --output data/fair_mast_dataset.npz

echo "=== Phase 2: Train RF Baseline ==="
python scripts/train_rf_baseline.py --data data/fair_mast_dataset.npz --output models/rf_baseline.joblib

echo "=== Phase 3: Training bi-LSTM+Attention ==="
python scripts/train_lstm.py --data data/fair_mast_dataset.npz --output models/lstm_attention.pt --epochs 50 --device cpu

echo "=== Phase 4: Training Transformer ==="
python scripts/train_transformer.py --data data/fair_mast_dataset.npz --output models/transformer.pt --epochs 40 --device cpu

echo "=== Phase 5: Benchmarking all models ==="
python scripts/benchmark_models.py --data data/fair_mast_dataset.npz --rf models/rf_baseline.joblib --lstm models/lstm_attention.pt --transformer models/transformer.pt

echo "=== DONE ==="
echo "Check models/ directory for trained artifacts"
echo "Check data/ directory for cached FAIR-MAST data"
