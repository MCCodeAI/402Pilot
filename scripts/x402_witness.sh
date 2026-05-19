#!/usr/bin/env bash
#
# Convenience wrapper: bring up the local x402 stack, run the witness,
# tear the stack back down. Useful for one-shot demonstration runs.
#
# Usage (from repo root):
#     ./scripts/x402_witness.sh [--rounds N] [--seed S]
#
# All extra arguments are forwarded to scripts/run_x402_witness.py.
#
# This script does NOT touch the benchmark loop or results/. It is for
# the integration witness only.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STACK_DIR="${REPO_ROOT}/infrastructure/x402"

if [[ ! -f "${STACK_DIR}/.env" ]]; then
    echo "ERROR: ${STACK_DIR}/.env does not exist." >&2
    echo "Copy .env.example to .env and fill in the values." >&2
    exit 1
fi

cleanup() {
    echo
    echo "----- Tearing down x402 stack -----"
    docker compose --project-directory "${STACK_DIR}" down -v
}
trap cleanup EXIT

echo "----- Bringing up x402 stack -----"
docker compose --project-directory "${STACK_DIR}" up -d --wait

echo
echo "----- Funding buyer wallet with test USDC -----"
# Source the witness env so X402_WALLET_PRIVATE_KEY (and ANVIL_RPC_URL) are
# available to fund_buyer.py. Use `set -a` so the variables propagate to
# the child process.
set -a
# shellcheck disable=SC1091
source "${STACK_DIR}/.env"
set +a
python "${STACK_DIR}/fund_buyer.py" --amount 100.0

echo
echo "----- Running witness -----"
(cd "${REPO_ROOT}" && python -m scripts.run_x402_witness "$@")
