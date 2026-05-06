#!/usr/bin/env bash
# Replication run on a task slice that's disjoint from the previous validation.
#
# Baseline used limits=15, offset=0  → tasks 0..14 of each source.
# This run  uses limits=15, offset=15 → tasks 15..29 of each source.
#
# 0 overlap with the baseline (verified via dry-run).
# Output written to data/pregen_replicate/ so the original data/pregen/ stays clean.
#
# Idempotent: --resume skips cells already on disk, so Ctrl+C and rerun is safe.
# To force a fresh run, delete data/pregen_replicate/ first.
#
# Expected: ~2 min wall clock, ~$1 spend (all on Vercel/Gemini judge).

set -euo pipefail

cd "$(dirname "$0")/.."
LOG_DIR="$(pwd)/logs"
mkdir -p "$LOG_DIR"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG="$LOG_DIR/replication_${TIMESTAMP}.log"

# Symlink so Claude / future tools can always find "the latest" run.
ln -sfn "$LOG" "$LOG_DIR/latest_replication.log"

echo "Logging to: $LOG"
echo "(symlink:   $LOG_DIR/latest_replication.log)"
echo

{
    echo "=== Replication run started at $(date) ==="
    echo
    echo "==> Step 1/2: pregen on disjoint task slice (240 cells)"
    python -m scripts.run_pregen experiments/main.yaml \
        --providers P-cheap P-mid P-premium P-adv \
        --limits humaneval=15 hotpotqa=15 triviaqa=15 openweb=15 \
        --offsets humaneval=15 hotpotqa=15 triviaqa=15 openweb=15 \
        --output-dir data/pregen_replicate \
        --version-count 1 \
        --concurrency 8 \
        --resume

    echo
    echo "==> Step 2/2: calibration report on the replication slice"
    python -m scripts.calibration_report --pregen-dir data/pregen_replicate

    echo
    echo "=== Replication run finished at $(date) ==="
} 2>&1 | tee "$LOG"

# Sentinel marker: a final non-empty line our log-poller can grep for.
echo "[REPLICATION_DONE]" >> "$LOG"
