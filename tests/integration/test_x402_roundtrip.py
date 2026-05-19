"""Live x402 round-trip integration test.

This test actually contacts the local x402 stack (Anvil + facilitator +
FastAPI resource server) brought up by
``infrastructure/x402/docker-compose.yml``. It is **skipped by default**;
opt in with:

    X402_INTEGRATION_TEST=1 pytest tests/integration/ -m integration -v

The test asserts:

* ``X402PaymentExecutor.pay_and_call`` returns a non-failure ``Outcome``.
* The receipt carries a positive ``amount_usdc`` and a hex ``tx_id``.
* The **buyer's USDC balance on Anvil actually decreases** by the
  settled amount. This is the strongest evidence that the witness is
  not just shuffling HTTP headers — the chain state changed.
"""

from __future__ import annotations

import os
import re
import socket
from pathlib import Path

import pytest

from pilot402.core.config import X402Settings
from pilot402.core.types import FailureCode, Outcome, ProviderId
from pilot402.runtime.x402_executor import X402PaymentExecutor

pytestmark = pytest.mark.integration


_RESOURCE_URLS = {
    ProviderId.P_CHEAP:   "http://127.0.0.1:8000/p-cheap",
    ProviderId.P_MID:     "http://127.0.0.1:8000/p-mid",
    ProviderId.P_PREMIUM: "http://127.0.0.1:8000/p-premium",
}

# Same constants as infrastructure/x402/fund_buyer.py; duplicated to keep
# the test free of cross-imports into infrastructure code.
_USDC_MAINNET = os.environ.get(
    "USDC_CONTRACT_ADDRESS",
    "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
)
_USDC_DECIMALS = 6

# EVM tx hash is 32 bytes (64 hex chars). The x402 facilitator returns
# the hash without an ``0x`` prefix; accept either form.
_HEX_TX = re.compile(r"^(0x)?[0-9a-fA-F]{64}$")

_X402_ENV_FILE = (
    Path(__file__).resolve().parents[2]
    / "infrastructure" / "x402" / ".env"
)


def _skip_unless_opted_in() -> None:
    if os.environ.get("X402_INTEGRATION_TEST") != "1":
        pytest.skip(
            "Set X402_INTEGRATION_TEST=1 (and bring up infrastructure/x402 "
            "via docker compose) to enable.",
        )


def _assert_stack_listening(host: str, port: int, label: str) -> None:
    """Raise a clear failure if a stack component isn't accepting connections."""
    try:
        with socket.create_connection((host, port), timeout=2.0):
            return
    except OSError as e:
        pytest.fail(
            f"{label} not reachable at {host}:{port} ({e}). "
            f"Bring up the stack with `docker compose up -d` in "
            f"infrastructure/x402/ before running this test."
        )


def _usdc_balance(rpc_url: str, account: str) -> int:
    """Query USDC.balanceOf(account) on the Anvil fork, atomic units."""
    from web3 import Web3

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    abi = [{
        "type": "function",
        "name": "balanceOf",
        "stateMutability": "view",
        "inputs": [{"type": "address", "name": "account"}],
        "outputs": [{"type": "uint256", "name": ""}],
    }]
    contract = w3.eth.contract(address=Web3.to_checksum_address(_USDC_MAINNET), abi=abi)
    return int(contract.functions.balanceOf(Web3.to_checksum_address(account)).call())


def _buyer_address(private_key: str) -> str:
    from eth_account import Account
    return Account.from_key(private_key).address


def _fast_forward_anvil_to_now(rpc_url: str) -> int:
    """Advance the Anvil fork's clock to current wall-clock time + mine a block.

    Anvil mainnet-forks inherit the fork block's timestamp (months/years in
    the past). x402 EIP-3009 authorizations are signed with current
    wall-clock ``validAfter`` / ``validBefore``. Without this fast-forward,
    USDC.transferWithAuthorization simulation reverts during the
    facilitator's ``/verify`` call with ``invalid_exact_evm_transaction_
    simulation_failed``. ``infrastructure/x402/fund_buyer.py`` does the
    same thing once at funding time; the test repeats it so a stale stack
    (left running for hours since fund_buyer) still works.
    """
    import time

    from web3 import Web3

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    target = int(time.time())
    w3.provider.make_request("anvil_setNextBlockTimestamp", [target])
    w3.provider.make_request("anvil_mine", [])
    return target


def test_real_x402_roundtrip_returns_valid_outcome() -> None:
    _skip_unless_opted_in()

    if _X402_ENV_FILE.exists():
        settings = X402Settings(_env_file=str(_X402_ENV_FILE))
    else:
        settings = X402Settings()

    assert settings.x402_wallet_private_key, (
        "X402_WALLET_PRIVATE_KEY is empty. Source infrastructure/x402/.env "
        "or export the variable before running."
    )

    # Fail fast with a helpful message if any of the three services is down.
    _assert_stack_listening("127.0.0.1", 8545, "anvil")
    _assert_stack_listening("127.0.0.1", 4021, "facilitator")
    _assert_stack_listening("127.0.0.1", 8000, "resource server")

    buyer = _buyer_address(settings.x402_wallet_private_key)
    balance_before_atomic = _usdc_balance(settings.anvil_rpc_url, buyer)
    assert balance_before_atomic > 0, (
        f"buyer {buyer} has zero USDC on Anvil. Run "
        f"`python infrastructure/x402/fund_buyer.py` (or the x402_witness.sh "
        f"wrapper) before this test."
    )

    # Bring Anvil's clock to current wall-clock time so EIP-3009's
    # validAfter / validBefore window matches the buyer SDK's signed
    # timestamps. See _fast_forward_anvil_to_now docstring for the
    # full rationale.
    _fast_forward_anvil_to_now(settings.anvil_rpc_url)

    executor = X402PaymentExecutor(
        resource_urls=_RESOURCE_URLS,
        facilitator_url=settings.x402_facilitator_url,
        wallet_private_key=settings.x402_wallet_private_key,
        anvil_rpc_url=settings.anvil_rpc_url,
        timeout_s=20.0,
    )

    outcome = executor.pay_and_call(
        provider_id=ProviderId.P_MID,
        request_payload={"task_id": "integration-1", "prompt": "ping"},
    )

    assert isinstance(outcome, Outcome)
    assert outcome.failure_flag is False, (
        f"round-trip failed: code={outcome.failure_code.value} body={outcome.response!r}"
    )
    assert outcome.failure_code is FailureCode.NONE
    assert outcome.provider_id is ProviderId.P_MID
    assert outcome.latency_s > 0.0
    assert outcome.quality_score is None  # scorer fills this elsewhere

    receipt = outcome.receipt
    assert receipt is not None, "successful round-trip must carry a receipt"
    assert receipt.provider_id is ProviderId.P_MID
    assert receipt.accepted is True
    assert receipt.amount_usdc > 0.0, "facilitator should report a positive settled amount"
    assert receipt.tx_id is not None, "receipt should carry a settlement tx hash"
    assert _HEX_TX.match(receipt.tx_id), f"tx_id is not a hex string: {receipt.tx_id!r}"
    assert outcome.cost_usdc == receipt.amount_usdc

    # The real witness condition: the buyer's USDC balance on Anvil
    # actually went down by the settled amount.
    balance_after_atomic = _usdc_balance(settings.anvil_rpc_url, buyer)
    delta_atomic = balance_before_atomic - balance_after_atomic
    settled_atomic = int(round(receipt.amount_usdc * (10 ** _USDC_DECIMALS)))

    assert delta_atomic > 0, (
        f"USDC balance unchanged. Before={balance_before_atomic} "
        f"After={balance_after_atomic}. The facilitator may have reported "
        f"success without performing on-chain settlement."
    )
    # Allow ±1 atomic unit slack for rounding when re-serializing through
    # the receipt's float field.
    assert abs(delta_atomic - settled_atomic) <= 1, (
        f"USDC balance change ({delta_atomic} atomic) does not match "
        f"receipt amount ({settled_atomic} atomic)."
    )
