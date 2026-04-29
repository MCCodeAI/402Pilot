"""P-cheap: Qwen3-8B without tools, parametric memory only."""

from __future__ import annotations

from dataclasses import dataclass

from pilot402.core import ProviderId
from pilot402.pregen.providers.base import BaseProvider, LlmBackend
from pilot402.pregen.providers.prompts import P_CHEAP_PROMPT


@dataclass
class PCheapProvider(BaseProvider):
    """Cheapest tier: small parametric model, no system-level reasoning aids."""


def make_p_cheap(backend: LlmBackend, base_price_usdc: float) -> PCheapProvider:
    return PCheapProvider(
        provider_id=ProviderId.P_CHEAP,
        model_name="qwen3-8b",
        base_price_usdc=base_price_usdc,
        system_prompt=P_CHEAP_PROMPT,
        backend=backend,
    )
