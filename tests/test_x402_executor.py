"""Unit tests for ``pilot402.runtime.x402_executor.X402PaymentExecutor``.

These tests run without any x402 SDK installed. All transport is
provided via the ``session_factory`` constructor hook; the test stubs
mimic the shape of an ``x402_requests`` session (a ``post`` method
returning a response-like object with ``status_code``, ``text``, and
``headers``).

The corresponding live round-trip exercise lives in
``tests/integration/test_x402_roundtrip.py`` and is gated behind the
``integration`` marker.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from typing import Any

import pytest

from pilot402.core.interfaces import PaymentExecutor
from pilot402.core.types import FailureCode, Outcome, PaymentReceipt, ProviderId
from pilot402.runtime.x402_executor import (
    X402PaymentExecutor,
    _parse_settlement_response,
    _safe_response_text,
)

# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


@dataclass
class _StubResponse:
    """Minimal response shape consumed by X402PaymentExecutor."""

    status_code: int
    text: str = ""
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class _StubSession:
    """Records calls and returns a pre-canned response or raises."""

    canned_response: _StubResponse | None = None
    raise_on_post: Exception | None = None
    calls: list[tuple[str, dict[str, Any], float]] = field(default_factory=list)

    def post(self, url: str, *, json: dict[str, Any], timeout: float) -> _StubResponse:
        self.calls.append((url, json, timeout))
        if self.raise_on_post is not None:
            raise self.raise_on_post
        assert self.canned_response is not None, "stub has no canned response"
        return self.canned_response


def _make_executor(session: _StubSession) -> X402PaymentExecutor:
    """Build an executor wired to a stub session.

    The wallet key is a non-empty placeholder; the stub session never
    calls the SDK so the value is never inspected.
    """
    return X402PaymentExecutor(
        resource_urls={
            ProviderId.P_CHEAP: "http://localhost:8000/p-cheap",
            ProviderId.P_MID:   "http://localhost:8000/p-mid",
        },
        facilitator_url="http://localhost:4021",
        wallet_private_key="0x" + "00" * 32,
        session_factory=lambda: session,
    )


def _encode_settlement(amount_micros: int, tx_id: str, decimals: int = 6) -> str:
    """Build a base64 PAYMENT-RESPONSE header value."""
    payload = json.dumps({
        "success": True,
        "transaction": tx_id,
        "amount": str(amount_micros),
        "decimals": decimals,
    }).encode("utf-8")
    return base64.b64encode(payload).decode("ascii")


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_implements_payment_executor_protocol() -> None:
    """The executor must satisfy the runtime_checkable Protocol."""
    executor = _make_executor(_StubSession(canned_response=_StubResponse(200)))
    assert isinstance(executor, PaymentExecutor)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_happy_path_populates_all_outcome_fields() -> None:
    header = _encode_settlement(amount_micros=1_000, tx_id="0xabc123")
    session = _StubSession(
        canned_response=_StubResponse(
            status_code=200,
            text='{"provider":"p-mid","response_text":"ok"}',
            headers={"PAYMENT-RESPONSE": header},
        )
    )
    executor = _make_executor(session)

    outcome = executor.pay_and_call(
        provider_id=ProviderId.P_MID,
        request_payload={"task_id": "t-1", "prompt": "hi"},
    )

    assert isinstance(outcome, Outcome)
    assert outcome.provider_id is ProviderId.P_MID
    assert outcome.response.startswith("{")
    assert outcome.cost_usdc == pytest.approx(0.001)  # 1_000 micros / 10^6
    assert outcome.latency_s >= 0.0
    assert outcome.failure_flag is False
    assert outcome.failure_code is FailureCode.NONE
    assert outcome.quality_score is None  # scorer fills this elsewhere
    assert isinstance(outcome.receipt, PaymentReceipt)
    assert outcome.receipt.provider_id is ProviderId.P_MID
    assert outcome.receipt.amount_usdc == pytest.approx(0.001)
    assert outcome.receipt.tx_id == "0xabc123"
    assert outcome.receipt.accepted is True
    assert outcome.receipt.metadata["raw_payment_response"] == header


def test_happy_path_calls_correct_url() -> None:
    session = _StubSession(
        canned_response=_StubResponse(
            status_code=200,
            text="{}",
            headers={"PAYMENT-RESPONSE": _encode_settlement(2_000, "0xdef")},
        )
    )
    executor = _make_executor(session)
    executor.pay_and_call(
        provider_id=ProviderId.P_CHEAP,
        request_payload={"task_id": "t-x"},
    )
    assert len(session.calls) == 1
    url, payload, timeout = session.calls[0]
    assert url == "http://localhost:8000/p-cheap"
    assert payload == {"task_id": "t-x"}
    assert timeout == 30.0


# ---------------------------------------------------------------------------
# Failure paths
# ---------------------------------------------------------------------------


def test_unknown_provider_returns_timeout_failure() -> None:
    session = _StubSession(canned_response=_StubResponse(200))
    executor = _make_executor(session)
    outcome = executor.pay_and_call(
        provider_id=ProviderId.P_PREMIUM,   # not registered in resource_urls
        request_payload={"task_id": "t"},
    )
    assert outcome.failure_flag is True
    assert outcome.failure_code is FailureCode.TIMEOUT
    assert outcome.cost_usdc == 0.0
    assert outcome.receipt is None
    assert "unknown provider" in outcome.response
    # Session must not be touched on unknown-provider short-circuit
    assert session.calls == []


def test_transport_exception_returns_timeout_failure() -> None:
    session = _StubSession(
        canned_response=None,
        raise_on_post=ConnectionError("anvil unreachable"),
    )
    executor = _make_executor(session)
    outcome = executor.pay_and_call(
        provider_id=ProviderId.P_MID,
        request_payload={"task_id": "t"},
    )
    assert outcome.failure_flag is True
    assert outcome.failure_code is FailureCode.TIMEOUT
    assert outcome.cost_usdc == 0.0
    assert outcome.receipt is None
    assert "ConnectionError" in outcome.response
    assert "anvil unreachable" in outcome.response


def test_non_200_returns_payment_failure() -> None:
    session = _StubSession(
        canned_response=_StubResponse(
            status_code=402,
            text="payment rejected",
            headers={},
        )
    )
    executor = _make_executor(session)
    outcome = executor.pay_and_call(
        provider_id=ProviderId.P_MID,
        request_payload={"task_id": "t"},
    )
    assert outcome.failure_flag is True
    assert outcome.failure_code is FailureCode.PAYMENT_FAILURE
    assert outcome.cost_usdc == 0.0
    assert outcome.receipt is None
    assert "status=402" in outcome.response


def test_missing_receipt_header_is_payment_failure() -> None:
    """A 200 without a parseable PAYMENT-RESPONSE = PAYMENT_FAILURE.

    The witness's value is demonstrating a *complete* quote/pay/receipt
    cycle. A 200 with no settlement receipt would leave the policy
    updating with cost=0, which would be misleading evidence of success.
    """
    session = _StubSession(
        canned_response=_StubResponse(
            status_code=200,
            text="ok",
            headers={},   # no receipt header
        )
    )
    executor = _make_executor(session)
    outcome = executor.pay_and_call(
        provider_id=ProviderId.P_MID,
        request_payload={"task_id": "t"},
    )
    assert outcome.failure_flag is True
    assert outcome.failure_code is FailureCode.PAYMENT_FAILURE
    assert outcome.cost_usdc == 0.0
    assert outcome.receipt is None
    assert "settlement receipt is invalid" in outcome.response


def test_malformed_receipt_header_is_payment_failure() -> None:
    """Garbage in PAYMENT-RESPONSE → PAYMENT_FAILURE (not a silent success)."""
    session = _StubSession(
        canned_response=_StubResponse(
            status_code=200,
            text="ok",
            headers={"PAYMENT-RESPONSE": "not-base64!@#"},
        )
    )
    executor = _make_executor(session)
    outcome = executor.pay_and_call(
        provider_id=ProviderId.P_MID,
        request_payload={"task_id": "t"},
    )
    assert outcome.failure_flag is True
    assert outcome.failure_code is FailureCode.PAYMENT_FAILURE
    assert outcome.cost_usdc == 0.0
    assert outcome.receipt is None


def test_receipt_with_zero_amount_is_payment_failure() -> None:
    """A receipt that parses but reports zero settlement is suspicious."""
    raw = _encode_settlement(amount_micros=0, tx_id="0xdeadbeef")
    session = _StubSession(
        canned_response=_StubResponse(
            status_code=200,
            text="ok",
            headers={"PAYMENT-RESPONSE": raw},
        )
    )
    executor = _make_executor(session)
    outcome = executor.pay_and_call(
        provider_id=ProviderId.P_MID,
        request_payload={"task_id": "t"},
    )
    assert outcome.failure_flag is True
    assert outcome.failure_code is FailureCode.PAYMENT_FAILURE


# ---------------------------------------------------------------------------
# _parse_settlement_response
# ---------------------------------------------------------------------------


def test_parse_settlement_empty_header() -> None:
    assert _parse_settlement_response("") == (0.0, None)


def test_parse_settlement_typical_usdc_payload() -> None:
    raw = _encode_settlement(amount_micros=2_500, tx_id="0xdeadbeef")
    amount, tx = _parse_settlement_response(raw)
    assert amount == pytest.approx(0.0025)
    assert tx == "0xdeadbeef"


def test_parse_settlement_alternate_field_names() -> None:
    """SDK variants may use ``txHash`` and ``value``; both should be parsed."""
    payload = json.dumps({
        "success": True,
        "txHash":  "0xbeef",
        "value":   "10000",
        "decimals": 6,
    }).encode("utf-8")
    raw = base64.b64encode(payload).decode("ascii")
    amount, tx = _parse_settlement_response(raw)
    assert amount == pytest.approx(0.01)
    assert tx == "0xbeef"


def test_parse_settlement_handles_garbage_base64() -> None:
    assert _parse_settlement_response("@@@") == (0.0, None)


def test_parse_settlement_handles_non_dict_json() -> None:
    raw = base64.b64encode(b"[1, 2, 3]").decode("ascii")
    assert _parse_settlement_response(raw) == (0.0, None)


def test_parse_settlement_handles_missing_amount() -> None:
    raw = base64.b64encode(json.dumps({"transaction": "0xabc"}).encode("utf-8")).decode("ascii")
    amount, tx = _parse_settlement_response(raw)
    assert amount == 0.0
    assert tx == "0xabc"


def test_parse_settlement_handles_non_numeric_amount() -> None:
    raw = base64.b64encode(json.dumps({"amount": "nope"}).encode("utf-8")).decode("ascii")
    amount, tx = _parse_settlement_response(raw)
    assert amount == 0.0
    assert tx is None


# ---------------------------------------------------------------------------
# _safe_response_text
# ---------------------------------------------------------------------------


def test_safe_response_text_from_text_attribute() -> None:
    @dataclass
    class _R:
        text: str = "hello"
    assert _safe_response_text(_R()) == "hello"


def test_safe_response_text_from_bytes_content() -> None:
    @dataclass
    class _R:
        content: bytes = b"hello"
    assert _safe_response_text(_R()) == "hello"


def test_safe_response_text_handles_no_body() -> None:
    @dataclass
    class _R:
        pass
    assert _safe_response_text(_R()) == ""


# ---------------------------------------------------------------------------
# Boundary: missing SDK at executor construction (production path)
# ---------------------------------------------------------------------------


def test_missing_sdk_falls_back_to_timeout_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """When no session_factory is injected and the SDK can't be imported,
    pay_and_call should return a TIMEOUT failure rather than crashing.

    Simulated by monkeypatching the production builder to raise ImportError.
    """
    executor = X402PaymentExecutor(
        resource_urls={ProviderId.P_MID: "http://localhost:8000/p-mid"},
        facilitator_url="http://localhost:4021",
        wallet_private_key="0x" + "11" * 32,
        # session_factory left at None to exercise the production code path
    )

    def _boom(self: X402PaymentExecutor) -> Any:
        raise ImportError("x402 SDK missing for test")

    monkeypatch.setattr(X402PaymentExecutor, "_build_payment_client", _boom)
    outcome = executor.pay_and_call(
        provider_id=ProviderId.P_MID,
        request_payload={"task_id": "t"},
    )
    assert outcome.failure_flag is True
    assert outcome.failure_code is FailureCode.TIMEOUT
    assert "x402 SDK" in outcome.response
