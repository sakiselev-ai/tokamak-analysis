from __future__ import annotations
"""Download FAIR-MAST shot data and prepare ML-ready dataset.

FAIR-MAST S3: https://s3.echo.stfc.ac.uk, bucket: mast, anonymous access.
Data format: Zarr stores under mast/shots/{shot_id}/

Usage:
    python download_fair_mast.py --shots 100 --output data/fair_mast_dataset.npz
"""
import argparse
import os
import pickle
import numpy as np
import s3fs
import zarr

S3_ENDPOINT = "https://s3.echo.stfc.ac.uk"
BUCKET = "mast"

def list_available_shots(limit=200):
    """List available shot IDs from FAIR-MAST."""
    s3 = s3fs.S3FileSystem(anon=True, client_kwargs={"endpoint_url": S3_ENDPOINT})
    items = s3.ls(f"{BUCKET}/shots")
    shot_ids = []
    for item in items[:limit*2]:
        try:
            shot_ids.append(int(item.split("/")[-1]))
        except ValueError:
            continue
    return sorted(shot_ids)[:limit]

def load_shot_signals(shot_id, s3):
    """Load all signals for a shot, return dict of signal_name -> (timestamps, values)."""
    shot_path = f"{BUCKET}/shots/{shot_id}"
    signals = {}
    try:
        items = s3.ls(shot_path)
    except FileNotFoundError:
        return None

    for item_path in items:
        signal_name = item_path.split("/")[-1]
        try:
            store = s3fs.S3Map(root=item_path, s3=s3)
            root = zarr.open(store, mode='r')
            # Try to find time-dependent data
            for key in root.keys():
                arr = root[key]
                if hasattr(arr, 'shape') and len(arr.shape) >= 1:
                    values = np.array(arr, dtype=float)
                    # Look for time array
                    time_key = None
                    for tk in ['time', 'times', 't', 'dim_0']:
                        if tk in root:
                            time_key = tk
                            break
                    if time_key and time_key != key:
                        timestamps = np.array(root[time_key], dtype=float)
                        if len(timestamps) == len(values):
                            # Clean NaN/inf
                            valid = np.isfinite(timestamps) & np.isfinite(values)
                            if valid.sum() > 10:
                                signals[f"{signal_name}/{key}"] = (
                                    timestamps[valid], values[valid]
                                )
        except Exception:
            continue
    return signals if signals else None

def label_disruption(signals):
    """Determine if a shot had a disruption.

    Heuristic: if plasma current (amc_plasma current or ip) drops
    abruptly (>50% drop in <10ms), it's a disruption.
    If ip_duration is very short relative to pulse, also disruption.
    """
    # Look for plasma current signal
    ip_signal = None
    for name, (ts, vals) in signals.items():
        lower = name.lower()
        if 'plasma' in lower and 'current' in lower:
            ip_signal = (ts, vals)
            break
        if 'amc' in lower and ('ip' in lower or 'current' in lower):
            ip_signal = (ts, vals)
            break

    if ip_signal is None:
        # Look for any current-like signal
        for name, (ts, vals) in signals.items():
            if 'ip' in name.lower() or 'current' in name.lower():
                ip_signal = (ts, vals)
                break

    if ip_signal is None:
        return 0  # Can't determine, assume stable

    ts, vals = ip_signal
    if len(vals) < 50:
        return 0

    # Normalize
    max_val = np.max(np.abs(vals))
    if max_val < 1e-10:
        return 0
    normalized = vals / max_val

    # Check for sudden drop (disruption signature)
    # Look at the derivative
    dt = np.diff(ts)
    dt[dt < 1e-10] = 1e-10
    dI_dt = np.diff(normalized) / dt

    # If there's a very sharp negative derivative, it's a disruption
    if np.min(dI_dt) < -50:  # rapid current drop
        return 1  # disruption

    # Also check if current goes to near-zero before end of pulse
    last_quarter = normalized[int(0.75 * len(normalized)):]
    if np.mean(np.abs(last_quarter)) < 0.1 * np.mean(np.abs(normalized[:int(0.25 * len(normalized))])):
        return 1  # likely disruption

    return 0  # stable

def prepare_features(signals, seq_len=200, n_features=None):
    """Convert signals dict to feature matrix (seq_len, n_signals)."""
    from scipy.interpolate import interp1d

    signal_names = sorted(signals.keys())
    if n_features:
        signal_names = signal_names[:n_features]

    features = np.zeros((seq_len, len(signal_names)))

    for i, name in enumerate(signal_names):
        ts, vals = signals[name]
        if len(ts) < 2:
            continue
        # Resample to uniform grid
        t_new = np.linspace(ts[0], ts[-1], seq_len)
        f = interp1d(ts, vals, kind='linear', fill_value='extrapolate', bounds_error=False)
        features[:, i] = f(t_new)

    # Normalize per-signal: zero mean, unit variance
    mean = features.mean(axis=0, keepdims=True)
    std = features.std(axis=0, keepdims=True)
    std[std < 1e-10] = 1.0
    features = (features - mean) / std

    return features

def main():
    parser = argparse.ArgumentParser(description="Download FAIR-MAST data for ML training")
    parser.add_argument("--shots", type=int, default=100, help="Number of shots to download")
    parser.add_argument("--seq-len", type=int, default=200, help="Sequence length for resampling")
    parser.add_argument("--n-features", type=int, default=20, help="Max number of signal features")
    parser.add_argument("--output", type=str, default="data/fair_mast_dataset.npz", help="Output file path")
    parser.add_argument("--cache-dir", type=str, default="data/cache", help="Cache directory for raw shots")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    os.makedirs(args.cache_dir, exist_ok=True)

    s3 = s3fs.S3FileSystem(anon=True, client_kwargs={"endpoint_url": S3_ENDPOINT})

    print(f"Listing available shots...")
    shot_ids = list_available_shots(limit=args.shots * 2)  # get extra in case some fail
    print(f"Found {len(shot_ids)} shots, will try to load {args.shots}")

    X_list = []
    y_list = []
    loaded_shots = []

    for i, shot_id in enumerate(shot_ids):
        if len(loaded_shots) >= args.shots:
            break

        cache_file = os.path.join(args.cache_dir, f"shot_{shot_id}.pkl")

        if os.path.exists(cache_file):
            with open(cache_file, 'rb') as f:
                signals = pickle.load(f)
        else:
            print(f"[{i+1}/{len(shot_ids)}] Loading shot {shot_id}...")
            signals = load_shot_signals(shot_id, s3)
            if signals:
                with open(cache_file, 'wb') as f:
                    pickle.dump(signals, f)

        if signals is None or len(signals) < 3:
            print(f"  Skipped (no/insufficient signals)")
            continue

        label = label_disruption(signals)
        features = prepare_features(signals, seq_len=args.seq_len, n_features=args.n_features)

        X_list.append(features)
        y_list.append(label)
        loaded_shots.append(shot_id)

        if len(loaded_shots) % 10 == 0:
            disruptions = sum(y_list)
            print(f"  Loaded {len(loaded_shots)} shots ({disruptions} disruptions, {len(loaded_shots)-disruptions} stable)")

    X = np.stack(X_list)
    y = np.array(y_list, dtype=np.float32)

    print(f"\nDataset: {X.shape[0]} shots, {X.shape[1]} timesteps, {X.shape[2]} features")
    print(f"Labels: {int(y.sum())} disruptions, {int(len(y) - y.sum())} stable")
    print(f"Disruption rate: {y.mean()*100:.1f}%")

    np.savez(args.output, X=X, y=y, shot_ids=np.array(loaded_shots))
    print(f"Saved to {args.output}")

if __name__ == "__main__":
    main()
