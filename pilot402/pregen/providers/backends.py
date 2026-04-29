"""Real LLM backends for the pregen pipeline.

Three backends, each implementing ``LlmBackend``:

* ``OpenAIBackend``    — drives GPT-5.4 / GPT-5.4-mini (P-mid, P-premium,
                          P-adv, P-flaky).
* ``AnthropicBackend`` — used for the LLM-as-judge path; exposed here for
                          symmetry but the actual judge wrapper lives in
                          ``pilot402.eval.judge_backend.AnthropicJudgeClient``.
* ``QwenBackend``      — drives Qwen3-8B via DashScope (P-cheap).

All three lazy-import their SDK in ``__post_init__``. Importing this module
does NOT require ``openai`` / ``anthropic`` / ``dashscope`` to be installed;
only instantiating a backend does. This lets ``make check`` stay green in
the sandbox without the heavier SDK stack.

To install the SDKs:

    pip install -e ".[pregen]"
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from pilot402.pregen.providers.base import LlmRequest, LlmResponse


def _missing_sdk(pkg: str) -> ImportError:
    return ImportError(
        f"The '{pkg}' package is required for this backend. Install with "
        f"`pip install -e \".[pregen]\"` before instantiating it."
    )


# ---------------------------------------------------------------------------
# OpenAI (GPT-5.4 / GPT-5.4-mini)
# ---------------------------------------------------------------------------


@dataclass
class OpenAIBackend:
    """Wraps the OpenAI Python SDK. Used by P-mid / P-premium / P-adv / P-flaky.

    The OpenAI API supports a ``seed`` parameter for "best-effort"
    determinism; we forward ``LlmRequest.seed`` directly. The provider
    also returns a ``system_fingerprint`` per response — we do not log
    it here because the per-call latency / token counts are sufficient
    provenance for our use.
    """

    api_key: str
    base_url: str | None = None
    timeout_s: float = 60.0
    _client: Any = field(init=False, repr=False, default=None)

    def __post_init__(self) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise _missing_sdk("openai") from exc
        kwargs: dict[str, Any] = {"api_key": self.api_key, "timeout": self.timeout_s}
        if self.base_url is not None:
            kwargs["base_url"] = self.base_url
        self._client = OpenAI(**kwargs)

    def complete(self, request: LlmRequest) -> LlmResponse:
        start = time.monotonic()
        resp = self._client.chat.completions.create(
            model=request.model,
            messages=[
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.user},
            ],
            seed=request.seed,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )
        elapsed = time.monotonic() - start
        choice = resp.choices[0]
        text = choice.message.content or ""
        usage = resp.usage
        return LlmResponse(
            text=text,
            prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            latency_s=elapsed,
        )


# ---------------------------------------------------------------------------
# Anthropic (used as judge backend; exposed here for completeness)
# ---------------------------------------------------------------------------


@dataclass
class AnthropicBackend:
    """Wraps the Anthropic Python SDK.

    Anthropic's Messages API does not expose a ``seed`` parameter, so the
    ``LlmRequest.seed`` we receive is logged as provenance only. With
    ``temperature=0`` Claude is highly but not bit-deterministic; the
    judge cache (``CachedJudgeBackend``) closes that gap by replaying
    cached scores rather than re-querying.
    """

    api_key: str
    timeout_s: float = 60.0
    _client: Any = field(init=False, repr=False, default=None)

    def __post_init__(self) -> None:
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise _missing_sdk("anthropic") from exc
        self._client = Anthropic(api_key=self.api_key, timeout=self.timeout_s)

    def complete(self, request: LlmRequest) -> LlmResponse:
        start = time.monotonic()
        resp = self._client.messages.create(
            model=request.model,
            system=request.system,
            messages=[{"role": "user", "content": request.user}],
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )
        elapsed = time.monotonic() - start
        # Concatenate any text blocks. Anthropic returns a list of content
        # blocks; for our prompts (no tool use) only text blocks appear.
        parts: list[str] = []
        for block in resp.content:
            text = getattr(block, "text", None)
            if isinstance(text, str):
                parts.append(text)
        usage = resp.usage
        return LlmResponse(
            text="".join(parts),
            prompt_tokens=int(getattr(usage, "input_tokens", 0) or 0),
            completion_tokens=int(getattr(usage, "output_tokens", 0) or 0),
            latency_s=elapsed,
        )


# ---------------------------------------------------------------------------
# DashScope (Qwen3-8B for P-cheap)
# ---------------------------------------------------------------------------


@dataclass
class QwenBackend:
    """Wraps the DashScope SDK for Qwen models.

    DashScope's ``Generation`` API takes a ``seed`` parameter for
    deterministic sampling at low temperature; we forward
    ``LlmRequest.seed``. The cost model in DashScope is per-token, but
    the pregen pipeline records ``cost_usdc`` from the provider's
    ``base_price_usdc`` (the x402 charge price), not the DashScope bill.
    """

    api_key: str
    timeout_s: float = 60.0
    _module: Any = field(init=False, repr=False, default=None)

    def __post_init__(self) -> None:
        try:
            import dashscope
            from dashscope import Generation
        except ImportError as exc:
            raise _missing_sdk("dashscope") from exc
        dashscope.api_key = self.api_key
        self._module = Generation

    def complete(self, request: LlmRequest) -> LlmResponse:
        start = time.monotonic()
        resp = self._module.call(
            model=request.model,
            messages=[
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.user},
            ],
            seed=request.seed,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            timeout=self.timeout_s,
            result_format="message",
        )
        elapsed = time.monotonic() - start
        # DashScope returns a Response with .output.choices[0].message.content
        # on success. Defensive extraction with empty-string fallback so a
        # surface-level format change shows up as a billed-but-empty record
        # rather than a crash.
        try:
            text = resp.output.choices[0].message.content
        except (AttributeError, IndexError, KeyError):
            text = ""
        usage = getattr(resp, "usage", None) or {}
        return LlmResponse(
            text=str(text or ""),
            prompt_tokens=int(usage.get("input_tokens", 0) if isinstance(usage, dict) else 0),
            completion_tokens=int(usage.get("output_tokens", 0) if isinstance(usage, dict) else 0),
            latency_s=elapsed,
        )


__all__ = ["AnthropicBackend", "OpenAIBackend", "QwenBackend"]
