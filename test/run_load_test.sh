#!/bin/bash
# Helper script to run Locust load tests

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

PYTHON=/usr/bin/python3
LOCUST_FILE="locustfile.py"
HOST="${1:-http://localhost:8000}"
USERS="${2:-10}"
SPAWN_RATE="${3:-2}"
RUN_TIME="${4:-5m}"
HEADLESS="${5:-}"

echo "🚀 Starting Locust Load Test"
echo "   Host: $HOST"
echo "   File: $LOCUST_FILE"

if [ "$HEADLESS" == "--headless" ]; then
    echo "   Mode: Headless (automated)"
    echo "   Users: $USERS"
    echo "   Spawn Rate: $SPAWN_RATE users/sec"
    echo "   Duration: $RUN_TIME"
    echo ""
    $PYTHON -m locust \
        -f "$LOCUST_FILE" \
        --host "$HOST" \
        --users "$USERS" \
        --spawn-rate "$SPAWN_RATE" \
        --run-time "$RUN_TIME" \
        --headless
else
    echo "   Mode: Web UI (interactive)"
    echo "   Open browser at http://localhost:8089"
    echo ""
    $PYTHON -m locust \
        -f "$LOCUST_FILE" \
        --host "$HOST"
fi
