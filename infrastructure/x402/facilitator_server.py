"""Local FastAPI facilitator for the 402Pilot x402 witness.

The benchmark never touches this service. It exists only for the live
integration witness so that the resource server can verify and settle a
real x402 EVM exact payment against the local Anvil fork.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException
from x402 import x402Facilitator
from x402.mechanisms.evm import FacilitatorWeb3Signer
from x402.mechanisms.evm.exact.register import register_exact_evm_facilitator
from x402.schemas import (
    SettleRequest,
    SettleResponse,
    SupportedResponse,
    VerifyRequest,
    VerifyResponse,
)

FACILITATOR_PRIVATE_KEY = os.environ.get("FACILITATOR_PRIVATE_KEY", "")
ANVIL_RPC_URL = os.environ.get("ANVIL_RPC_URL", "http://anvil:8545")
X402_NETWORK = os.environ.get("X402_NETWORK", "eip155:31337")

if not FACILITATOR_PRIVATE_KEY:
    raise RuntimeError("FACILITATOR_PRIVATE_KEY is required")


_signer = FacilitatorWeb3Signer(
    private_key=FACILITATOR_PRIVATE_KEY,
    rpc_url=ANVIL_RPC_URL,
)
_facilitator = x402Facilitator()
register_exact_evm_facilitator(_facilitator, _signer, networks=X402_NETWORK)


app = FastAPI(
    title="402Pilot local x402 facilitator",
    description="Local-only facilitator for the x402 integration witness.",
)


@app.get("/supported")
def supported() -> dict[str, Any]:
    """Return the payment kinds this local facilitator supports."""
    response: SupportedResponse = _facilitator.get_supported()
    return response.model_dump(by_alias=True, exclude_none=True)


@app.post("/verify")
async def verify(request: VerifyRequest) -> dict[str, Any]:
    """Verify an x402 payment payload."""
    if request.x402_version != 2:
        raise HTTPException(status_code=400, detail="Only x402 v2 is supported")

    response: VerifyResponse = await _facilitator.verify(
        request.payment_payload,
        request.payment_requirements,
    )
    body = response.model_dump(by_alias=True, exclude_none=True)
    # Diagnostic logging — surfaces is_valid + error reason so we can tell
    # apart "signature accepted" from "signature rejected" in docker logs.
    # The x402 server middleware treats HTTP 200 + isValid=False as a
    # payment rejection (re-issue 402), so HTTP 200 alone is not success.
    print(
        f"=== /verify => isValid={body.get('isValid')} "
        f"invalidReason={body.get('invalidReason')!r} "
        f"payer={body.get('payer')!r} "
        f"network={request.payment_requirements.network!r} "
        f"asset={request.payment_requirements.asset!r} "
        f"amount={request.payment_requirements.amount!r} ===",
        flush=True,
    )
    return body


@app.post("/settle")
async def settle(request: SettleRequest) -> dict[str, Any]:
    """Settle an x402 payment and include the settled atomic amount."""
    if request.x402_version != 2:
        raise HTTPException(status_code=400, detail="Only x402 v2 is supported")

    response: SettleResponse = await _facilitator.settle(
        request.payment_payload,
        request.payment_requirements,
    )
    print(
        f"=== /settle => success={response.success} "
        f"transaction={response.transaction!r} "
        f"errorReason={getattr(response, 'error_reason', None)!r} ===",
        flush=True,
    )
    if response.success and response.amount is None:
        # The SDK's EVM exact settlement returns the transaction hash but
        # not the amount. The amount settled is exactly the requirement
        # amount, so include it for the PAYMENT-RESPONSE receipt header.
        response = response.model_copy(
            update={"amount": request.payment_requirements.amount},
        )
    return response.model_dump(by_alias=True, exclude_none=True)
