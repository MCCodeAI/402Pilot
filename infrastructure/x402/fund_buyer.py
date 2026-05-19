"""Fund the witness buyer wallet with test USDC on the local Anvil fork.

Anvil starts with USDC contract state inherited from the mainnet fork,
but the buyer wallet (Anvil test account 0) holds zero USDC because
that's the real-world state at the fork block. The x402 ``exact``
scheme on EVM requires a real USDC transfer, so without funding the
witness round-trip would fail at settlement.

This script writes the buyer's USDC balance directly via the standard
EVM cheat code ``anvil_setStorageAt``. USDC (FiatTokenV2_2 on Ethereum
mainnet) stores its balanceOf mapping at slot 9; we compute the storage
key as ``keccak256(abi.encode(holder, slot))`` and overwrite it with
the desired balance in atomic units (USDC has 6 decimals).

Usage (from infrastructure/x402/ or anywhere)::

    python infrastructure/x402/fund_buyer.py
    python infrastructure/x402/fund_buyer.py --amount 1000

Environment variables (matching ``X402Settings`` and ``.env.example``):

    ANVIL_RPC_URL              default: http://127.0.0.1:8545
    X402_WALLET_PRIVATE_KEY    used to derive the buyer address
    USDC_CONTRACT_ADDRESS      default: mainnet USDC

This is a one-shot setup step; the witness script does not call it
automatically (so an operator always knows when balances change).
``scripts/x402_witness.sh`` invokes it after the stack comes up.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

# USDC (FiatTokenV2_2) on Ethereum mainnet.
USDC_MAINNET = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
USDC_DECIMALS = 6

# Storage slot of the balanceOf mapping in FiatTokenV2_2. Verified via
# Etherscan-published source as slot 9. If we ever fork at a block where
# USDC's proxy implementation differs, this constant needs revisiting.
USDC_BALANCE_SLOT = 9


def _to_addr(private_key: str) -> str:
    """Derive a checksummed address from a hex private key."""
    from eth_account import Account
    return Account.from_key(private_key).address


def _storage_key_for_balance(holder: str) -> str:
    """Compute the EVM storage key for ``balances[holder]``.

    Solidity mapping layout: keccak256(abi.encode(key, slot)).
    """
    from eth_utils import keccak, to_bytes

    holder_bytes = to_bytes(hexstr=holder.lower()).rjust(32, b"\x00")
    slot_bytes = USDC_BALANCE_SLOT.to_bytes(32, "big")
    return "0x" + keccak(holder_bytes + slot_bytes).hex()


def fund(
    rpc_url: str,
    holder: str,
    amount_usdc: float,
    *,
    contract: str = USDC_MAINNET,
) -> int:
    """Set ``holder``'s USDC balance to ``amount_usdc`` on the Anvil fork.

    Returns the resulting on-chain balance in atomic units (so the caller
    can sanity-check the write).
    """
    from web3 import Web3

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise RuntimeError(f"cannot reach Anvil at {rpc_url}")

    atomic_amount = int(amount_usdc * (10 ** USDC_DECIMALS))
    value_hex = "0x" + atomic_amount.to_bytes(32, "big").hex()
    storage_key = _storage_key_for_balance(holder)

    # Anvil-specific RPC. Other backends (Hardhat) use a different name.
    w3.provider.make_request(
        "anvil_setStorageAt",
        [contract, storage_key, value_hex],
    )

    # Verify via standard ERC-20 balanceOf call.
    balance_of_abi = [{
        "type": "function",
        "name": "balanceOf",
        "stateMutability": "view",
        "inputs": [{"type": "address", "name": "account"}],
        "outputs": [{"type": "uint256", "name": ""}],
    }]
    erc20 = w3.eth.contract(address=Web3.to_checksum_address(contract), abi=balance_of_abi)
    return int(erc20.functions.balanceOf(Web3.to_checksum_address(holder)).call())


def fast_forward_to_now(rpc_url: str) -> int:
    """Advance the Anvil fork's clock to current wall-clock time.

    The fork inherits ``block.timestamp`` from the source block (which on a
    mainnet fork is months or years in the past). The x402 SDK signs EIP-3009
    authorizations using *current* wall-clock validAfter / validBefore. If
    the Anvil clock is far behind, USDC.transferWithAuthorization reverts
    its ``block.timestamp > validAfter`` precondition during the facilitator's
    /verify simulation — surfacing as
    ``invalid_exact_evm_transaction_simulation_failed``.

    Calling this once after fund() makes the next block's timestamp match
    real time, which keeps the EIP-3009 time window valid for the witness's
    payment authorizations.
    """
    from web3 import Web3

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    target = int(time.time())
    # ``anvil_setNextBlockTimestamp`` sets the timestamp the NEXT mined block
    # will adopt; ``anvil_mine`` mines a block so the new timestamp becomes
    # the head block's timestamp for subsequent ``eth_call`` simulations.
    w3.provider.make_request("anvil_setNextBlockTimestamp", [target])
    w3.provider.make_request("anvil_mine", [])
    return target


def main() -> int:
    p = argparse.ArgumentParser(description="Fund the witness buyer with test USDC.")
    p.add_argument(
        "--amount", type=float, default=100.0,
        help="USDC amount to set as balance (default: 100).",
    )
    p.add_argument(
        "--rpc-url", default=os.environ.get("ANVIL_RPC_URL", "http://127.0.0.1:8545"),
    )
    p.add_argument(
        "--holder", default=os.environ.get("X402_BUYER_ADDRESS", ""),
        help="Buyer address. If omitted, derived from X402_WALLET_PRIVATE_KEY.",
    )
    p.add_argument(
        "--contract", default=os.environ.get("USDC_CONTRACT_ADDRESS", USDC_MAINNET),
    )
    args = p.parse_args()

    holder = args.holder
    if not holder:
        key = os.environ.get("X402_WALLET_PRIVATE_KEY", "")
        if not key:
            print(
                "ERROR: need either --holder or X402_WALLET_PRIVATE_KEY",
                file=sys.stderr,
            )
            return 1
        holder = _to_addr(key)

    print(f"Funding {holder} with {args.amount:.4f} USDC at {args.contract} via {args.rpc_url}")
    balance_atomic = fund(args.rpc_url, holder, args.amount, contract=args.contract)
    print(f"Post-fund balance: {balance_atomic / (10 ** USDC_DECIMALS):.6f} USDC")

    # Mainnet forks inherit the fork block's timestamp (months/years in the
    # past). x402 EIP-3009 authorizations sign current-wall-clock validAfter,
    # so without fast-forwarding the facilitator's transferWithAuthorization
    # simulation reverts on "authorization not yet valid".
    ts = fast_forward_to_now(args.rpc_url)
    print(f"Anvil clock advanced to {ts} ({time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(ts))} UTC)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
