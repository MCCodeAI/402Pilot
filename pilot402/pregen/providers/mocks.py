"""In-memory ``LlmBackend`` doubles for tests.

These are the only LLM backends used in CI; real network-bound backends
live in ``pilot402.pregen.providers.backends`` and lazy-import their SDKs.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from pilot402.pregen.providers.base import LlmBackend, LlmRequest, LlmResponse


@dataclass
class MockLlmBackend:
    """Returns canned text without ever hitting the network.

    By default the response text encodes the call inputs so tests can read it
    back deterministically. Pass a ``responder`` for richer behavior, e.g.
    returning different text per ``LlmRequest.system`` to simulate provider
    quality differences.
    """

    responder: Callable[[LlmRequest], str] | None = None
    fixed_latency_s: float = 0.01

    def complete(self, request: LlmRequest) -> LlmResponse:
        if self.responder is not None:
            text = self.responder(request)
        else:
            text = (
                f"[mock model={request.model} seed={request.seed} "
                f"sys_len={len(request.system)} user_len={len(request.user)}]"
            )
        return LlmResponse(
            text=text,
            prompt_tokens=len(request.system) + len(request.user),
            completion_tokens=len(text),
            latency_s=self.fixed_latency_s,
        )


@dataclass
class RecordingMockBackend(LlmBackend):
    """Captures every ``LlmRequest`` for assertion in tests.

    Wraps an inner backend (default: a plain ``MockLlmBackend``) so that any
    test can substitute richer behavior. The recorded ``calls`` list is
    append-only and read by tests after the provider runs.
    """

    inner: LlmBackend = field(default_factory=MockLlmBackend)
    calls: list[LlmRequest] = field(default_factory=list)

    def complete(self, request: LlmRequest) -> LlmResponse:
        self.calls.append(request)
        return self.inner.complete(request)
