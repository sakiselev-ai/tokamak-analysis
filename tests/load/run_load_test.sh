#!/bin/bash
# TC-NF-001: Load test with 50 concurrent users for 15 minutes
# Target: P95 ≤ 5s, 0 errors 5xx

HOST=${1:-"http://186.246.31.81"}
USERS=${2:-50}
DURATION=${3:-"15m"}

echo "=== Tokamak Analysis Load Test ==="
echo "Host: $HOST"
echo "Users: $USERS"
echo "Duration: $DURATION"
echo ""

locust -f locustfile.py \
  --host "$HOST" \
  --users "$USERS" \
  --spawn-rate 5 \
  --run-time "$DURATION" \
  --headless \
  --csv "results/loadtest_$(date +%Y%m%d_%H%M%S)" \
  --html "results/loadtest_$(date +%Y%m%d_%H%M%S).html"

echo ""
echo "Results saved to results/ directory"
