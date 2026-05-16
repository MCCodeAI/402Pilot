"""Provider registry and test backends for pregen."""

from __future__ import annotations

from dataclasses import dataclass, field

from pilot402.core import ProviderId
from pilot402.pregen.providers.base import (
    ADVERSARIAL_VERSIONS,
    BaseProvider,
    LlmBackend,
    LlmRequest,
    LlmResponse,
)
from pilot402.pregen.providers.p_flaky import PFlakyProvider, make_p_flaky
from pilot402.pregen.providers.prompts import (
    P_ADV_ADVERSARIAL_PROMPT,
    P_ADV_NEUTRAL_PROMPT,
    P_CHEAP_PROMPT,
    P_MID_PROMPT,
    P_PREMIUM_PROMPT,
)


class PAdvProvider(BaseProvider):
    def _select_system_prompt(self, version: int) -> str:
        if version in ADVERSARIAL_VERSIONS[ProviderId.P_ADV]:
            return P_ADV_ADVERSARIAL_PROMPT
        return P_ADV_NEUTRAL_PROMPT


def make_p_cheap(backend: LlmBackend, base_price_usdc: float) -> BaseProvider:
    return BaseProvider(
        provider_id=ProviderId.P_CHEAP,
        model_name="qwen3.5-flash",
        base_price_usdc=base_price_usdc,
        system_prompt=P_CHEAP_PROMPT,
        backend=backend,
    )


def make_p_mid(backend: LlmBackend, base_price_usdc: float) -> BaseProvider:
    return BaseProvider(
        provider_id=ProviderId.P_MID,
        model_name="gpt-5.4-mini",
        base_price_usdc=base_price_usdc,
        system_prompt=P_MID_PROMPT,
        backend=backend,
    )


def make_p_premium(backend: LlmBackend, base_price_usdc: float) -> BaseProvider:
    return BaseProvider(
        provider_id=ProviderId.P_PREMIUM,
        model_name="gpt-5.4",
        base_price_usdc=base_price_usdc,
        system_prompt=P_PREMIUM_PROMPT,
        backend=backend,
    )


def make_p_adv(backend: LlmBackend, base_price_usdc: float) -> PAdvProvider:
    return PAdvProvider(
        provider_id=ProviderId.P_ADV,
        model_name="gpt-5.4-mini",
        base_price_usdc=base_price_usdc,
        system_prompt=P_ADV_NEUTRAL_PROMPT,
        backend=backend,
    )


PROVIDER_REGISTRY = {
    ProviderId.P_CHEAP: make_p_cheap,
    ProviderId.P_MID: make_p_mid,
    ProviderId.P_PREMIUM: make_p_premium,
    ProviderId.P_ADV: make_p_adv,
    ProviderId.P_FLAKY: make_p_flaky,
}


def make_provider(
    provider_id: ProviderId,
    backend: LlmBackend,
    base_price_usdc: float,
) -> BaseProvider | PAdvProvider | PFlakyProvider:
    try:
        factory = PROVIDER_REGISTRY[provider_id]
    except KeyError as exc:
        raise ValueError(f"Unknown provider id: {provider_id!r}") from exc
    return factory(backend, base_price_usdc)


@dataclass
class RecordingMockBackend:
    """Mock backend that records every request and returns deterministic text."""

    calls: list[LlmRequest] = field(default_factory=list)

    def complete(self, request: LlmRequest) -> LlmResponse:
        self.calls.append(request)
        return LlmResponse(
            text=f"mock response seed={request.seed}",
            prompt_tokens=len(request.system.split()) + len(request.user.split()),
            completion_tokens=4,
            latency_s=0.001,
        )


class MockLlmBackend(RecordingMockBackend):
    """Alias used by tests when the request log is not the main assertion."""


__all__ = [
    "ADVERSARIAL_VERSIONS",
    "BaseProvider",
    "LlmBackend",
    "LlmRequest",
    "LlmResponse",
    "MockLlmBackend",
    "PROVIDER_REGISTRY",
    "PAdvProvider",
    "PFlakyProvider",
    "RecordingMockBackend",
    "make_provider",
]

