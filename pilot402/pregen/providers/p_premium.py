"""P-premium: GPT-5.4 with chain-of-thought prompting."""

from __future__ import annotations

from dataclasses import dataclass

from pilot402.core import ProviderId
from pilot402.pregen.providers.base import BaseProvider, LlmBackend
from pilot402.pregen.providers.prompts import P_PREMIUM_PROMPT


@dataclass
class PPremiumProvider(BaseProvider):
    """Premium tier: full-size model, CoT system prompt.

    The paper's design also references code execution for T1; like P-mid's
    BM25, the executor is out of scope here and the CoT prompt is the
    surface mechanism. Realistic latency dominance over P-mid comes from
    the model itself, not from extra tool calls.
    """


def make_p_premium(backend: LlmBackend, base_price_usdc: float) -> PPremiumProvider:
    return PPremiumProvider(
        provider_id=ProviderId.P_PREMIUM,
        model_name="gpt-5.4",
        base_price_usdc=base_price_usdc,
        system_prompt=P_PREMIUM_PROMPT,
        backend=backend,
    )
