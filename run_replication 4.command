#!/usr/bin/env bash
# Double-click launcher. Opens in Terminal and runs the replication script.
# Logs end up in ./logs/replication_<timestamp>.log

set -euo pipefail
cd "$(dirname "$0")"
exec bash scripts/run_replication.sh
