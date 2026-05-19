"""X402PaymentExecutor — integration-witness implementation of ``PaymentExecutor``.

This module is **not** used by the benchmark loop. The replay path in
``pilot402/runtime/loop.py`` reads cached ``PregenRecord`` rows directly
from ``PregenStore`` and constructs ``Outcome`` instances inline; it does
not invoke any ``PaymentExecutor`` implementation. This file therefore
provides the first concrete instance of the ``PaymentExecutor`` Protocol
from ``pilot402.core.interfaces`` — a witness that the abstract
decision-layer/substrate boundary described in the paper (Sec.~4) is
satisfiable on a real payment protocol, not only on the frozen-replay
benchmark.

Architecture (Sec.~4 of the paper):

    Decision Layer ──policy.select──▶ a_t
                                      │
                                      ▼
                              ┌───────────────┐
                              │ PaymentExecutor│ ◀── *this module is one impl*
                              │ pay_and_call  │
                              └───────┬───────┘
                                      │ HTTP 402 round-trip
                                      ▼
                          Resource Server ──▶ Facilitator ──▶ Anvil fork

The local stack (Resource Server + Facilitator + Anvil fork) is stood up
by ``infrastructure/x402/docker-compose.yml``. See ``infrastructure/x402/README.md``
for setup. The benchmark code never imports this module; failure here
cannot affect any reported experimental number.

Failure semantics
-----------------
The executor maps round-trip outcomes onto the existing ``FailureCode``
enum (defined in ``pilot402.core.types``):

* ``FailureCode.NONE``             — HTTP 200 received, receipt parsed.
* ``FailureCode.TIMEOUT``          — network/transport/timeout error,
                                     or x402 SDK import failure.
* ``FailureCode.PAYMENT_FAILURE``  — round-trip completed but the server
                                     returned a non-200 response indicating
                                     payment rejection.

x402 SDK boundary
-----------------
This module uses the official ``x402`` Python SDK
(``pip install "x402[requests]"``) to handle the cryptographic primitives
of x402 payment signing. The SDK is imported lazily inside
``_build_payment_client``; unit tests in ``tests/test_x402_executor.py``
mock that helper so the SDK is **not** required at unit-test time. Only
the integration test in ``tests/integration/test_x402_roundtrip.py``
exercises a real installation.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from pilot402.core.types import (
    FailureCode,
    Outcome,
    PaymentReceipt,
    ProviderId,
)

logger = logging.getLogger(__name__)


class _X402Session(Protocol):
    """Structural interface the executor expects from a payment-enabled HTTP client.

    The x402 SDK's ``x402_requests`` adapter satisfies this shape (a
    ``requests.Session``-like object whose ``post`` automatically handles
    HTTP 402 challenge/response and returns the final 200 response).
    Unit tests provide a stub conforming to this Protocol so the executor
    can be exercised without the real SDK installed.
    """

    def post(self, url: str, *, json: dict[str, Any], timeout: float) -> Any: ...


@dataclass
class X402PaymentExecutor:
    """Real x402 ``PaymentExecutor`` implementation (integration witness only).

    Args:
        resource_urls:        mapping from ``ProviderId`` to the HTTP URL of
                              the corresponding paid endpoint on the local
                              resource server. Must match the endpoints
                              defined in
                              ``infrastructure/x402/resource_server.py``.
        facilitator_url:      base URL of the self-hosted x402 facilitator
                              (default matches ``X402Settings`` in
                              ``pilot402/core/config.py``: ``http://127.0.0.1:4021``).
        wallet_private_key:   hex-encoded EVM private key used by the
                              x402 SDK to sign payment payloads. For local
                              development this is the Anvil test account 0
                              key; see ``infrastructure/x402/.env.example``.
                              Never a real-funds key — the executor is a
                              witness running against a local fork.
        anvil_rpc_url:        recorded for receipt metadata; the SDK itself
                              reaches the chain via the facilitator, so the
                              executor does not directly use this URL.
        timeout_s:            per-request HTTP timeout. The whole 402 →
                              signed → 200 round-trip is bounded by this
                              value.
        session_factory:      optional override returning a ``_X402Session``.
                              Unit tests inject a stub here; production
                              callers leave this at its default (which
                              lazy-imports the x402 SDK).
    """

    resource_urls: dict[ProviderId, str]
    facilitator_url: str
    wallet_private_key: str
    anvil_rpc_url: str = "http://127.0.0.1:8545"
    timeout_s: float = 30.0
    session_factory: Any = None
    _session: Any = field(default=None, init=False, repr=False)

    # ------------------------------------------------------------------
    # PaymentExecutor Protocol
    # ------------------------------------------------------------------

    def pay_and_call(
        self,
        provider_id: ProviderId,
        request_payload: dict[str, Any],
    ) -> Outcome:
        """One x402 round-trip, returned as an ``Outcome``.

        See ``pilot402.core.interfaces.PaymentExecutor`` for the contract.
        All eight fields of ``Outcome`` are populated:

        * ``provider_id``    — echoed from the request
        * ``response``       — resource-server body text on success;
                               diagnostic string on failure
        * ``cost_usdc``      — facilitator-reported settled amount on
                               success; 0.0 on failure
        * ``latency_s``      — wall-clock elapsed for the round-trip
                               (``time.monotonic`` based)
        * ``failure_flag``   — True iff the round-trip did not yield a 200
        * ``failure_code``   — see module docstring
        * ``quality_score``  — None; the scorer (separate module) fills this
        * ``receipt``        — populated on success, None on failure
        """
        if provider_id not in self.resource_urls:
            return _failed(
                provider_id,
                elapsed=0.0,
                code=FailureCode.TIMEOUT,
                response=f"unknown provider {provider_id.value}; "
                f"configured providers: {sorted(p.value for p in self.resource_urls)}",
            )

        url = self.resource_urls[provider_id]
        start = time.monotonic()

        try:
            session = self._get_session()
        except ImportError as e:
            # Unit tests inject session_factory and never hit this path. The
            # witness script will hit this if x402[requests] is not installed.
            return _failed(
                provider_id,
                elapsed=0.0,
                code=FailureCode.TIMEOUT,
                response=f"x402 SDK not available: {e}. "
                f"Install via `pip install -r infrastructure/x402/requirements.txt`.",
            )

        try:
            response = session.post(url, json=request_payload, timeout=self.timeout_s)
        except Exception as e:  # noqa: BLE001 — intentional broad catch at network boundary
            elapsed = time.monotonic() - start
            logger.warning(
                "x402 round-trip raised %s for provider=%s: %s",
                type(e).__name__,
                provider_id.value,
                e,
            )
            return _failed(
                provider_id,
                elapsed=elapsed,
                code=FailureCode.TIMEOUT,
                response=f"transport error: {type(e).__name__}: {e}",
            )

        elapsed = time.monotonic() - start
        status_code = getattr(response, "status_code", None)

        if status_code != 200:
            body = _safe_response_text(response)
            return _failed(
                provider_id,
                elapsed=elapsed,
                code=FailureCode.PAYMENT_FAILURE,
                response=f"non-200 after x402 round-trip: status={status_code} body={body[:200]!r}",
            )

        receipt = self._extract_receipt(provider_id, response)
        # Strict-receipt rule: a 200 without a parseable settlement receipt
        # is treated as PAYMENT_FAILURE. The witness's value comes from
        # demonstrating a complete quote/pay/receipt cycle; a 200 with no
        # receipt would leave the policy updating with cost=0, which would
        # be misleading.
        if receipt.amount_usdc <= 0.0 or not receipt.tx_id:
            return _failed(
                provider_id,
                elapsed=elapsed,
                code=FailureCode.PAYMENT_FAILURE,
                response=(
                    f"200 received but settlement receipt is invalid: "
                    f"amount_usdc={receipt.amount_usdc} tx_id={receipt.tx_id!r}"
                ),
            )

        body = _safe_response_text(response)
        return Outcome(
            provider_id=provider_id,
            response=body,
            cost_usdc=receipt.amount_usdc,
            latency_s=elapsed,
            failure_flag=False,
            failure_code=FailureCode.NONE,
            quality_score=None,
            receipt=receipt,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_session(self) -> Any:
        """Return (and cache) a payment-enabled HTTP session.

        Resolution order:

        1. If a test has injected ``session_factory``, call it.
        2. Otherwise, lazy-import the x402 SDK and build a real session.
           The SDK call surface is captured in ``_build_payment_client``
           and is the single place to adjust if upstream SDK APIs change.
        """
        if self._session is not None:
            return self._session
        if self.session_factory is not None:
            self._session = self.session_factory()
        else:
            self._session = self._build_payment_client()
        return self._session

    def _build_payment_client(self) -> Any:
        """Construct a real x402-payment-aware HTTP session via the SDK.

        Verified against the official buyer quickstart (docs.x402.org,
        2026-05); the upstream sync API surface is::

            from x402 import x402ClientSync
            from x402.http.clients import x402_requests
            from x402.mechanisms.evm import EthAccountSigner
            from x402.mechanisms.evm.exact.register import register_exact_evm_client
            from eth_account import Account

        ``x402_requests(client)`` is a context manager that yields a
        ``requests``-style session whose ``post`` automatically handles
        the HTTP 402 challenge/response. We enter the context manager
        here and rely on garbage collection to call ``__exit__`` when
        the executor is destroyed; for the witness script this is fine
        because the process is short-lived.

        If a future SDK release renames any of these symbols, this is
        the only method that needs to change.
        """
        # Lazy imports: see module docstring for rationale.
        from eth_account import Account
        from x402 import x402ClientSync
        from x402.http.clients import x402_requests
        from x402.mechanisms.evm import EthAccountSigner
        from x402.mechanisms.evm.exact.register import register_exact_evm_client

        sdk_client = x402ClientSync()
        account = Account.from_key(self.wallet_private_key)
        register_exact_evm_client(sdk_client, EthAccountSigner(account))
        cm = x402_requests(sdk_client)
        # Enter the context manager; the session is what callers use.
        return cm.__enter__()

    def _extract_receipt(
        self,
        provider_id: ProviderId,
        response: Any,
    ) -> PaymentReceipt:
        """Map the x402 ``PAYMENT-RESPONSE`` header into a ``PaymentReceipt``.

        The x402 spec (Sec.~3 "Typical x402 flow") defines the
        ``PAYMENT-RESPONSE`` header carrying a Base64-encoded JSON
        Settlement Response. We extract:

        * ``amount_usdc`` — from the settlement response (authoritative;
          may differ from the original challenge price on partial
          settlements or scheme-specific adjustments).
        * ``tx_id``       — settlement transaction hash, when present.
        * ``accepted``    — True (we only enter this code path on 200).
        * ``metadata``    — the raw header value for forensic inspection.

        The helper is intentionally lenient about parsing: if any field
        is missing or malformed, it falls back to safe defaults rather
        than raising. The witness's job is to demonstrate that a receipt
        was produced, not to police every field.
        """
        headers = getattr(response, "headers", {}) or {}
        raw_header = headers.get("PAYMENT-RESPONSE") or headers.get("payment-response") or ""
        amount_usdc, tx_id = _parse_settlement_response(raw_header)
        return PaymentReceipt(
            provider_id=provider_id,
            amount_usdc=amount_usdc,
            tx_id=tx_id,
            accepted=True,
            metadata={
                "raw_payment_response": raw_header,
                "anvil_rpc_url": self.anvil_rpc_url,
            },
        )


# ----------------------------------------------------------------------
# Module-level helpers (kept outside the dataclass so they're easy to
# unit-test independently)
# ----------------------------------------------------------------------


def _failed(
    provider_id: ProviderId,
    *,
    elapsed: float,
    code: FailureCode,
    response: str,
) -> Outcome:
    """Construct a failure ``Outcome`` with consistent field population."""
    return Outcome(
        provider_id=provider_id,
        response=response,
        cost_usdc=0.0,
        latency_s=elapsed,
        failure_flag=True,
        failure_code=code,
        quality_score=None,
        receipt=None,
    )


def _safe_response_text(response: Any) -> str:
    """Return ``response.text`` if available, else a best-effort string.

    HTTP libraries differ slightly: ``requests.Response`` has ``.text``,
    other shapes may expose ``.content`` or ``.body``. Unit tests use
    minimal stubs; production uses ``requests.Response``.
    """
    text = getattr(response, "text", None)
    if isinstance(text, str):
        return text
    body = getattr(response, "content", None)
    if isinstance(body, (bytes, bytearray)):
        try:
            return body.decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            return repr(body)
    return str(body) if body is not None else ""


def _parse_settlement_response(raw_header: str) -> tuple[float, str | None]:
    """Decode a Base64 JSON x402 ``PAYMENT-RESPONSE`` header.

    Returns ``(amount_usdc, tx_id)``. On any parse failure returns
    ``(0.0, None)`` — the caller still produces a ``PaymentReceipt`` so
    the witness can demonstrate the round-trip completed; downstream
    consumers can decide whether to treat a zero amount as suspicious.

    The x402 settlement schema (as of 2026-05) commonly exposes:

        {"success": true,
         "transaction": "0x...",
         "network": "...",
         "payer": "0x...",
         "amount": "1000"}      # smallest-unit string (e.g. USDC has 6 decimals)

    USDC has 6 decimal places; the helper assumes that scaling unless
    the payload carries an explicit ``decimals`` field.
    """
    import base64
    import json

    if not raw_header:
        return 0.0, None

    try:
        decoded = base64.b64decode(raw_header).decode("utf-8")
        payload = json.loads(decoded)
    except Exception as e:  # noqa: BLE001
        logger.debug("could not decode PAYMENT-RESPONSE header: %s", e)
        return 0.0, None

    if not isinstance(payload, dict):
        return 0.0, None

    tx_id = payload.get("transaction") or payload.get("txHash") or None
    raw_amount = payload.get("amount") or payload.get("value") or "0"
    decimals = int(payload.get("decimals", 6))
    try:
        amount_usdc = float(int(raw_amount)) / (10 ** decimals)
    except (TypeError, ValueError):
        amount_usdc = 0.0

    return amount_usdc, tx_id if isinstance(tx_id, str) else None


__all__ = ["X402PaymentExecutor"]
