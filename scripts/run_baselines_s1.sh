#!/usr/bin/env bash
# M3.C — Run all 5 baselines on S1 (stationary), 30 seeds × 10,000 rounds.
#
# Idempotent: --resume in run_baselines_s1.py skips already-complete cells.
# Expected: ~8 min wall clock, $0 spend (no API calls — pure replay).

set -euo pipefail

cd "$(dirname "$0")/.."
LOG_DIR="$(pwd)/logs"
mkdir -p "$LOG_DIR"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG="$LOG_DIR/baselines_s1_${TIMESTAMP}.log"
ln -sfn "$LOG" "$LOG_DIR/latest_baselines_s1.log"

echo "Logging to: $LOG"
echo

{
    echo "=== Baselines S1 sweep started at $(date) ==="
    echo
    python -m scripts.run_baselines_s1
    echo
    echo "=== Baselines S1 sweep finished at $(date) ==="
} 2>&1 | tee "$LOG"

echo "[BASELINES_S1_DONE]" >> "$LOG"
