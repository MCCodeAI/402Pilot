#!/usr/bin/env bash
# Tier 3 — full pregen sweep.
#
# Scale: 5 providers × 823 effective tasks × 5 versions = 20,575 cells.
# Output: data/pregen/ (the canonical location PregenStore reads from).
#
# Idempotent: --resume skips cells already on disk, so you can Ctrl+C the run
# at any time (eat dinner, sleep, debug something else) and rerun this script
# to continue. Worst-case loss per Ctrl+C is ~$0.10 from in-flight cells whose
# LLM call paid but record didn't reach disk.
#
# Expected: ~3.5–4 hours wall clock, with external LLM/judge API spend.
# Cost depends on provider pricing and judge configuration.

set -euo pipefail

cd "$(dirname "$0")/.."
LOG_DIR="$(pwd)/logs"
mkdir -p "$LOG_DIR"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG="$LOG_DIR/full_${TIMESTAMP}.log"

# Symlink so Claude / future tools can always find "the latest" full run.
ln -sfn "$LOG" "$LOG_DIR/latest_full.log"

echo "Logging to: $LOG"
echo "(symlink:   $LOG_DIR/latest_full.log)"
echo "Output:     data/pregen/"
echo
echo "Tip: Ctrl+C anytime is safe — rerun this script to resume."
echo

{
    echo "=== Full Tier 3 sweep started at $(date) ==="
    echo
    echo "==> Step 1/2: pregen full task set (20,575 cells)"
    python -m scripts.run_pregen experiments/main.yaml \
        --concurrency 8 \
        --resume

    echo
    echo "==> Step 2/2: calibration report on data/pregen/"
    python -m scripts.calibration_report --pregen-dir data/pregen

    echo
    echo "=== Full Tier 3 sweep finished at $(date) ==="
} 2>&1 | tee "$LOG"

# Sentinel marker: a final non-empty line our log-poller can grep for.
echo "[FULL_SWEEP_DONE]" >> "$LOG"
