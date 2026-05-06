#!/usr/bin/env bash
# 402Pilot — start a local Anvil fork of Base for the viz/Explainer/DevnetDemo
# reproducibility witness.
#
# This script is NOT used by the experiments. The benchmark replays from
# pre-generated fixtures only (see docs/experiment_design.md §8).
# Its sole purpose is to give the viz a real RPC to talk to so the
# Explainer page can show one round of x402 settlement against a live chain.
#
# Requirements:
#   - foundry (anvil + cast):   https://book.getfoundry.sh/getting-started/installation
#   - jq                         (only for pretty-printing diagnostics)
#
# Usage:
#   ./scripts/devnet/start_anvil.sh                                       # default Base RPC
#   BASE_RPC_URL=https://... ./scripts/devnet/start_anvil.sh              # override
#   PINNED_BLOCK=20000000     ./scripts/devnet/start_anvil.sh             # pin fork block
#
# Exposes:
#   RPC      http://127.0.0.1:8545
#   chainId  84532                  (Base Sepolia by default)
set -euo pipefail

BASE_RPC_URL="${BASE_RPC_URL:-https://sepolia.base.org}"
PORT="${PORT:-8545}"
HOST="${HOST:-127.0.0.1}"
PINNED_BLOCK="${PINNED_BLOCK:-}"
CHAIN_ID="${CHAIN_ID:-84532}"

if ! command -v anvil >/dev/null 2>&1; then
  echo "error: anvil not found. Install foundry: https://book.getfoundry.sh/getting-started/installation" >&2
  exit 1
fi

ARGS=(
  --host "$HOST"
  --port "$PORT"
  --chain-id "$CHAIN_ID"
  --fork-url "$BASE_RPC_URL"
  --accounts 5
  --balance 100
)

if [[ -n "$PINNED_BLOCK" ]]; then
  ARGS+=(--fork-block-number "$PINNED_BLOCK")
fi

echo "402Pilot devnet — anvil fork of $BASE_RPC_URL"
echo "                  RPC: http://$HOST:$PORT  (chainId $CHAIN_ID)"
echo "                  pinned block: ${PINNED_BLOCK:-latest}"
echo
exec anvil "${ARGS[@]}"
