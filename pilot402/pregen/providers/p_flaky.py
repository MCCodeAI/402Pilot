"""P-flaky: GPT-5.4-mini with mechanical 20% timeout injection.

Mechanism (decision Option C):

* Version ``{0}`` short-circuits — no LLM call. We return a billed timeout
  failure (``failure_flag=True``, ``failure_code=TIMEOUT``,
  ``charged_cost_usdc=base_price_usdc``, empty ``response``).
* Versions ``{1, 2, 3, 4}`` use the same prompt as P-mid and call the LLM
  normally.

This makes the per-call failure rate exactly 1/5 = 20% under uniform
version sampling, with full charge on failure (decision 2: payment is
irreversible under x402 semantics).
"""

from __future__ import annotations

from dataclasses import dataclass

from numpy.random import Generator

from pilot402.core import FailureCode, ProviderId, Task
from pilot402.pregen.providers.base import (
    ADVERSARIAL_VERSIONS,
    BaseProvider,
    LlmBackend,
    ProviderCallResult,
)
from pilot402.pregen.providers.prompts import P_FLAKY_PROMPT


@dataclass
class PFlakyProvider(BaseProvider):
    """Same tier as P-mid but version 0 is a forced billed timeout."""

    def generate(
        self,
        task: Task,
        version: int,
        *,
        rng: Generator,
    ) -> ProviderCallResult:
        if version in ADVERSARIAL_VERSIONS[ProviderId.P_FLAKY]:
            # No LLM call; force-fail the round at full price.
            return ProviderCallResult(
                response="",
                cost_usdc=self.base_price_usdc,
                latency_s=0.0,
                failure_flag=True,
                failure_code=FailureCode.TIMEOUT,
            )
        return super().generate(task, version, rng=rng)


def make_p_flaky(backend: LlmBackend, base_price_usdc: float) -> PFlakyProvider:
    return PFlakyProvider(
        provider_id=ProviderId.P_FLAKY,
        model_name="gpt-5.4-mini",
        base_price_usdc=base_price_usdc,
        system_prompt=P_FLAKY_PROMPT,
        backend=backend,
    )
