#!/usr/bin/env bash
# Double-click launcher. Opens in Terminal and runs M3.C baselines on S1.
# Logs end up in ./logs/baselines_s1_<timestamp>.log
# Safe to Ctrl+C — rerun this same launcher to resume.

set -euo pipefail
cd "$(dirname "$0")"
exec bash scripts/run_baselines_s1.sh
