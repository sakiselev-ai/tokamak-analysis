from __future__ import annotations
"""Inference latency benchmark.

TC-NF-002: 1000 sequential disruption predictions.
Target: P99 ≤ 50ms, P50 ≤ 20ms.

Usage:
    python inference_benchmark.py --host http://186.246.31.81 --iterations 1000
"""

import argparse
import json
import time
import statistics
import requests
import numpy as np
import os


def register_and_login(host):
    """Register a test user and get JWT token."""
    email = f"bench_{int(time.time())}@test.mephi.ru"
    requests.post(f"{host}/api/v1/auth/register", json={
        "email": email, "password": "benchtest123",
        "full_name": "Benchmark User", "consent_given": True,
    })
    res = requests.post(f"{host}/api/v1/auth/login", json={
        "email": email, "password": "benchtest123",
    })
    return res.json()["access_token"]


def load_experiment(host, headers):
    """Load a shot to get experiment_id for predictions."""
    res = requests.post(f"{host}/api/v1/experiments/load",
        json={"shot_id": 30420, "source": "mast"}, headers=headers, timeout=60)
    if res.status_code == 201:
        return res.json()["id"]
    # Try listing existing
    res = requests.get(f"{host}/api/v1/experiments/", headers=headers)
    experiments = res.json().get("experiments", [])
    if experiments:
        return experiments[0]["id"]
    return None


def benchmark_classify(host, headers, experiment_id, iterations):
    """Benchmark classification inference."""
    latencies = []
    errors = 0

    for i in range(iterations):
        start = time.perf_counter()
        res = requests.post(f"{host}/api/v1/predictions/classify",
            json={"experiment_id": experiment_id}, headers=headers, timeout=30)
        latency_ms = (time.perf_counter() - start) * 1000

        if res.status_code == 200:
            latencies.append(latency_ms)
        else:
            errors += 1

        if (i + 1) % 100 == 0:
            print(f"  {i+1}/{iterations} completed, P50={statistics.median(latencies):.1f}ms")

    return latencies, errors


def benchmark_disruption(host, headers, experiment_id, iterations):
    """Benchmark disruption prediction inference."""
    latencies = []
    errors = 0

    for i in range(iterations):
        start = time.perf_counter()
        res = requests.post(f"{host}/api/v1/predictions/disruption",
            json={"experiment_id": experiment_id, "threshold": 0.7},
            headers=headers, timeout=30)
        latency_ms = (time.perf_counter() - start) * 1000

        if res.status_code == 200:
            latencies.append(latency_ms)
        else:
            errors += 1

        if (i + 1) % 100 == 0:
            print(f"  {i+1}/{iterations} completed, P50={statistics.median(latencies):.1f}ms")

    return latencies, errors


def compute_percentiles(latencies):
    if not latencies:
        return {}
    arr = sorted(latencies)
    n = len(arr)
    return {
        "min": arr[0],
        "p50": arr[int(n * 0.50)],
        "p90": arr[int(n * 0.90)],
        "p95": arr[int(n * 0.95)],
        "p99": arr[min(int(n * 0.99), n-1)],
        "max": arr[-1],
        "mean": statistics.mean(arr),
        "stdev": statistics.stdev(arr) if len(arr) > 1 else 0,
        "count": n,
    }


def main():
    parser = argparse.ArgumentParser(description="Inference latency benchmark")
    parser.add_argument("--host", default="http://186.246.31.81")
    parser.add_argument("--iterations", type=int, default=100, help="Number of inference calls")
    parser.add_argument("--output", default="results/inference_benchmark.json")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)

    print(f"=== Inference Latency Benchmark ===")
    print(f"Host: {args.host}")
    print(f"Iterations: {args.iterations}")

    # Setup
    print("\nSetting up test user...")
    token = register_and_login(args.host)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    print("Loading experiment...")
    exp_id = load_experiment(args.host, headers)
    if not exp_id:
        print("ERROR: Could not load experiment. Ensure FAIR-MAST is accessible.")
        return
    print(f"Using experiment_id={exp_id}")

    # Benchmark classification
    print(f"\n--- Classification ({args.iterations} calls) ---")
    classify_latencies, classify_errors = benchmark_classify(
        args.host, headers, exp_id, args.iterations)
    classify_stats = compute_percentiles(classify_latencies)

    # Benchmark disruption
    print(f"\n--- Disruption Prediction ({args.iterations} calls) ---")
    disruption_latencies, disruption_errors = benchmark_disruption(
        args.host, headers, exp_id, args.iterations)
    disruption_stats = compute_percentiles(disruption_latencies)

    # Results
    results = {
        "host": args.host,
        "iterations": args.iterations,
        "classification": {**classify_stats, "errors": classify_errors},
        "disruption": {**disruption_stats, "errors": disruption_errors},
    }

    print(f"\n{'='*60}")
    print(f"{'Metric':<20} {'Classification':>15} {'Disruption':>15}")
    print(f"{'='*60}")
    for metric in ["min", "p50", "p90", "p95", "p99", "max", "mean"]:
        c = classify_stats.get(metric, 0)
        d = disruption_stats.get(metric, 0)
        print(f"{metric:<20} {c:>12.1f}ms {d:>12.1f}ms")
    print(f"{'errors':<20} {classify_errors:>15} {disruption_errors:>15}")
    print(f"{'='*60}")

    # NFR compliance check
    print(f"\n=== NFR Compliance ===")
    classify_p99_ok = classify_stats.get("p99", 999) <= 2000  # NFR-002: ≤ 2s
    disruption_p99_ok = disruption_stats.get("p99", 999) <= 50  # NFR-003: ≤ 50ms
    print(f"NFR-002 Classification P99 ≤ 2000ms: {'PASS' if classify_p99_ok else 'FAIL'} ({classify_stats.get('p99', 0):.1f}ms)")
    print(f"NFR-003 Disruption P99 ≤ 50ms:      {'PASS' if disruption_p99_ok else 'FAIL'} ({disruption_stats.get('p99', 0):.1f}ms)")

    with open(args.output, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
