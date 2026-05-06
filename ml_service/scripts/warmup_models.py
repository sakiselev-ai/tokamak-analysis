from __future__ import annotations

"""Verify all 3 models load correctly with input_size=10.

Use as a container startup check to catch dimension mismatches early.

Usage:
    cd ml_service
    python scripts/warmup_models.py
    python scripts/warmup_models.py --models-dir /opt/tokamak-analysis/models
"""

import argparse
import os
import sys
import time
from pathlib import Path

import numpy as np

# Allow imports from ml_service root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from service.models.random_forest import RandomForestModel
from service.models.lstm_attention import LSTMAttentionModel
from service.models.transformer import TransformerModel

N_FEATURES = 10
SEQ_LEN = 10  # short sequence is enough for a smoke test


def main():
    parser = argparse.ArgumentParser(description="Warmup: load and smoke-test all models")
    parser.add_argument("--models-dir", default="models/", help="Directory with model files")
    args = parser.parse_args()

    models_dir = args.models_dir
    dummy_seq = np.random.randn(1, SEQ_LEN, N_FEATURES).astype(np.float32)
    dummy_flat = dummy_seq.reshape(1, -1)
    ok = True

    # --- Random Forest ---
    rf_path = os.path.join(models_dir, "rf_baseline.joblib")
    try:
        t0 = time.time()
        rf = RandomForestModel()
        rf.load(rf_path)
        pred = rf.predict(dummy_flat)
        print(f"[OK] RF loaded from {rf_path} in {time.time()-t0:.3f}s, pred={pred}")
    except Exception as e:
        print(f"[FAIL] RF: {e}")
        ok = False

    # --- LSTM+Attention ---
    lstm_path = os.path.join(models_dir, "lstm_attention.pt")
    try:
        t0 = time.time()
        lstm = LSTMAttentionModel()
        lstm.load(lstm_path)
        pred = lstm.predict(dummy_seq)
        print(f"[OK] LSTM loaded from {lstm_path} in {time.time()-t0:.3f}s, pred={pred}")
    except Exception as e:
        print(f"[FAIL] LSTM: {e}")
        ok = False

    # --- Transformer ---
    tf_path = os.path.join(models_dir, "transformer.pt")
    try:
        t0 = time.time()
        tf = TransformerModel()
        tf.load(tf_path)
        pred = tf.predict(dummy_seq)
        print(f"[OK] Transformer loaded from {tf_path} in {time.time()-t0:.3f}s, pred={pred}")
    except Exception as e:
        print(f"[FAIL] Transformer: {e}")
        ok = False

    if ok:
        print("\nAll models loaded and predicted successfully.")
    else:
        print("\nSome models failed to load!")
        sys.exit(1)


if __name__ == "__main__":
    main()
