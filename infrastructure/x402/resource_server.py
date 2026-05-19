"""FastAPI resource server for the 402Pilot x402 integration witness.

This is a tiny local server that exposes one paid endpoint per provider
(P-cheap / P-mid / P-premium) using the official x402 FastAPI middleware.
It is **not** part of the benchmark; it exists solely so that
``X402PaymentExecutor`` (in ``pilot402/runtime/x402_executor.py``) has a
real x402 server to talk to when the integration witness runs.

Run via the docker-compose stack in this directory:

    cd infrastructure/x402 && docker compose up -d

The server reads configuration from environment variables (see
``.env.example``); the docker-compose file injects them.

API surface verified against:
    https://docs.x402.org/getting-started/quickstart-for-sellers
"""

from __future__ import annotations

import os
import traceback
from typing import Any

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

# x402 SDK imports — verified against the official seller quickstart
# (docs.x402.org, 2026-05). If a future SDK release renames these, the
# imports here and ``_build_payment_client`` in
# ``pilot402/runtime/x402_executor.py`` are the two places to update.
from x402.http import FacilitatorConfig, HTTPFacilitatorClient, PaymentOption
from x402.http.middleware.fastapi import PaymentMiddlewareASGI
from x402.http.types import RouteConfig
from x402.mechanisms.evm.exact import ExactEvmServerScheme
from x402.schemas import Network
from x402.schemas.base import AssetAmount
from x402.server import x402ResourceServer

# ---------------------------------------------------------------------------
# Configuration (sourced from env; docker-compose populates them)
# ---------------------------------------------------------------------------

# The address that receives payments. Anvil test account 1 by default — the
# wallet (Anvil account 0) pays this account each round.
PAY_TO_ADDRESS = os.environ.get(
    "X402_PAY_TO_ADDRESS",
    "0x70997970C51812dc3A010C7d01b50e0d17dc79C8",  # Anvil test account 1
)

# Local facilitator that this server delegates verification + settlement to.
FACILITATOR_URL = os.environ.get(
    "X402_FACILITATOR_URL",
    "http://facilitator:4021",  # internal docker-compose hostname
)

# CAIP-2 network identifier. The local Python SDK facilitator is registered
# for the same identifier and routes settlement to the Anvil RPC.
ANVIL_NETWORK: Network = os.environ.get("X402_NETWORK", "eip155:31337")  # type: ignore[assignment]

# USDC (FiatTokenV2_2) on the Ethereum mainnet fork. We pass the asset
# explicitly because local chain id 31337 has no SDK default stablecoin.
USDC_CONTRACT_ADDRESS = os.environ.get(
    "USDC_CONTRACT_ADDRESS",
    "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
)
USDC_DECIMALS = 6
USDC_EIP712_NAME = "USD Coin"
USDC_EIP712_VERSION = "2"

# Per-provider prices in USDC. Match
# ``pilot402.core.types.ProviderSpec.base_price_usdc`` values from the
# benchmark config so the witness exercises realistic price points.
PRICES_USDC = {
    "p-cheap":   0.001,
    "p-mid":     0.002,
    "p-premium": 0.010,
}


def _price_asset_amount(price_usdc: float) -> AssetAmount:
    """Return an explicit x402 ``AssetAmount`` for mainnet-fork USDC.

    The x402 ``PaymentOption.price`` field accepts ``str | int | float |
    AssetAmount`` (see ``x402.schemas.base``). For the standard testnets /
    mainnet the SDK can resolve a ``$``-prefixed dollar string to USDC
    automatically, but on a custom CAIP-2 chain like ``eip155:31337``
    there is no default-asset registry, so we **must** pass an explicit
    ``AssetAmount`` instance — passing a raw dict slips past the dataclass
    constructor but blows up at request time inside the middleware.
    """
    return AssetAmount(
        amount=str(int(round(price_usdc * (10 ** USDC_DECIMALS)))),
        asset=USDC_CONTRACT_ADDRESS,
        extra={
            "name": USDC_EIP712_NAME,
            "version": USDC_EIP712_VERSION,
        },
    )


class _TracebackMiddleware(BaseHTTPMiddleware):
    """Surface the real exception when something below us crashes.

    The x402 middleware swallows downstream exceptions and returns a
    generic 500 with body ``{"error":"Failed to process request"}``.
    Registering this middleware **before** the x402 middleware (so the
    x402 middleware sits inside it) lets us log the traceback to stdout
    where ``docker compose logs resource-server`` will show it.
    """

    async def dispatch(self, request, call_next):
        try:
            return await call_next(request)
        except Exception as exc:  # noqa: BLE001 - intentional broad catch
            tb = traceback.format_exc()
            print(f"=== EXCEPTION on {request.url.path} ===\n{tb}", flush=True)
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Failed to process request",
                    "exception": f"{type(exc).__name__}: {exc}",
                },
            )


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

app = FastAPI(
    title="402Pilot x402 witness resource server",
    description=(
        "Local-only resource server for the x402 integration witness. "
        "Not part of the 402Pilot-Bench benchmark."
    ),
)


# Build the x402 resource server: a facilitator client + one registered
# scheme per network. We only support the EVM exact scheme on the local
# Anvil network; future witness scope expansion (Solana, batch-settlement,
# etc.) would register additional schemes here.
_facilitator = HTTPFacilitatorClient(FacilitatorConfig(url=FACILITATOR_URL))
_server = x402ResourceServer(_facilitator)
_server.register(ANVIL_NETWORK, ExactEvmServerScheme())


# Routes config maps "METHOD /path" → ``RouteConfig`` (per docs.x402.org
# seller quickstart). The middleware intercepts requests to these routes
# and returns HTTP 402 unless a valid PAYMENT-SIGNATURE header is present.
_routes: dict[str, RouteConfig] = {
    f"POST /{slug}": RouteConfig(
        accepts=[
            PaymentOption(
                scheme="exact",
                pay_to=PAY_TO_ADDRESS,
                price=_price_asset_amount(price_usdc),
                network=ANVIL_NETWORK,
            ),
        ],
        mime_type="application/json",
        description=f"402Pilot witness — provider {slug}",
    )
    for slug, price_usdc in PRICES_USDC.items()
}

app.add_middleware(PaymentMiddlewareASGI, routes=_routes, server=_server)
# Register the traceback wrapper LAST so it sits outermost (ASGI middleware
# is applied in reverse order of registration), catching anything the x402
# middleware raises.
app.add_middleware(_TracebackMiddleware)


# ---------------------------------------------------------------------------
# Endpoints — canned responses; witness validates transport, not quality.
# ---------------------------------------------------------------------------

def _canned_response(provider_slug: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Return a small deterministic response body.

    The witness scorer (``run_x402_witness.py``) only checks that the
    round-trip succeeded; the body contents are not graded. Keep this
    response small and stable so logs are easy to diff between runs.
    """
    return {
        "provider": provider_slug,
        "task_id": payload.get("task_id", "<missing>"),
        "echo_prompt": payload.get("prompt", ""),
        "response_text": f"[witness] {provider_slug} acknowledges task "
        f"{payload.get('task_id', '?')}",
    }


@app.post("/p-cheap")
async def p_cheap(payload: dict[str, Any]) -> dict[str, Any]:
    return _canned_response("p-cheap", payload)


@app.post("/p-mid")
async def p_mid(payload: dict[str, Any]) -> dict[str, Any]:
    return _canned_response("p-mid", payload)


@app.post("/p-premium")
async def p_premium(payload: dict[str, Any]) -> dict[str, Any]:
    return _canned_response("p-premium", payload)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness probe used by docker-compose and the integration test."""
    return {"status": "ok"}
