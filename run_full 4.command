#!/usr/bin/env bash
# Double-click launcher. Opens in Terminal and runs the full Tier 3 sweep.
# Logs end up in ./logs/full_<timestamp>.log
# Safe to Ctrl+C — rerun this same launcher to resume.

set -euo pipefail
cd "$(dirname "$0")"
exec bash scripts/run_full.sh
