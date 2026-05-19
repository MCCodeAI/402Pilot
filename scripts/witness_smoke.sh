#!/usr/bin/env bash
#
# One-shot smoke probe for the x402 integration witness.
#
# What this script does (in order):
#   1. Rebuilds the resource-server image (picks up the AssetAmount fix).
#   2. Restarts the resource-server container.
#   3. Waits for /healthz.
#   4. POSTs /p-cheap without payment — expects HTTP 402 + PAYMENT-REQUIRED.
#   5. Funds the buyer wallet with test USDC on Anvil.
#   6. Runs the witness for 1 round.
#   7. Dumps the last 80 log lines of each container.
#
# This script does not tear the stack down (so you can iterate). To shut
# down: `docker compose --project-directory infrastructure/x402 down -v`.
#
# Usage (from repo root):
#     bash scripts/witness_smoke.sh

set -uo pipefail   # NOTE: -e is intentionally NOT set, so a failing step
                   # still prints the diagnostic tail at the end.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STACK_DIR="${REPO_ROOT}/infrastructure/x402"

bar() { printf '\n=========================================================\n  %s\n=========================================================\n' "$1"; }

if [[ ! -f "${STACK_DIR}/.env" ]]; then
    echo "ERROR: ${STACK_DIR}/.env not found. Copy .env.example and fill it in." >&2
    exit 1
fi

set -a
# shellcheck disable=SC1091
source "${STACK_DIR}/.env"
set +a

bar "1. docker compose build facilitator + resource-server"
docker compose --project-directory "${STACK_DIR}" build facilitator resource-server

bar "2. docker compose up -d (refresh facilitator + resource-server)"
docker compose --project-directory "${STACK_DIR}" up -d --force-recreate facilitator resource-server
sleep 3

bar "3. /healthz probe"
for i in 1 2 3 4 5; do
    if curl -fs http://127.0.0.1:8000/healthz >/dev/null; then
        echo "OK"
        break
    fi
    echo "  attempt $i: not ready yet, retrying..."
    sleep 1
done

bar "4. POST /p-cheap (expect 402 + PAYMENT-REQUIRED)"
curl -is -X POST http://127.0.0.1:8000/p-cheap \
     -H "Content-Type: application/json" \
     -d '{"task_id":"smoke"}' | head -25

bar "5. Fund buyer wallet with 100 USDC"
python "${STACK_DIR}/fund_buyer.py" || echo "(funding failed — keep going)"

bar "6. Run witness — 1 round"
(cd "${REPO_ROOT}" && python -m scripts.run_x402_witness --rounds 1) || echo "(witness exited non-zero)"

bar "7a. resource-server logs (last 80)"
docker compose --project-directory "${STACK_DIR}" logs resource-server --tail 80

bar "7b. facilitator logs (last 40)"
docker compose --project-directory "${STACK_DIR}" logs facilitator --tail 40

bar "DONE"
echo "Stack is still up. To stop:  docker compose --project-directory ${STACK_DIR} down -v"
