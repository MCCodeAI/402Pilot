"""P-adv: GPT-5.4-mini, version-aware adversarial behavior.

Mechanism (decision Option C, locked with the user):

* Versions ``{0, 1, 2}`` use the adversarial system prompt
  (``P_ADV_ADVERSARIAL_PROMPT``) — every call attempts to inject subtle
  errors.
* Versions ``{3, 4}`` use the neutral prompt (identical to P-mid's prompt)
  — every call is a normal helpful response.

At experiment time the env samples versions uniformly; the empirical
degraded rate is therefore exactly 3/5 = 60% per call. Mean quality
emerges from the adversarial-prompt compliance rate, measured during the
Tier 2 calibration probe.
"""

from __future__ import annotations

from dataclasses import dataclass

from pilot402.core import ProviderId
from pilot402.pregen.providers.base import (
    ADVERSARIAL_VERSIONS,
    BaseProvider,
    LlmBackend,
)
from pilot402.pregen.providers.prompts import (
    P_ADV_ADVERSARIAL_PROMPT,
    P_ADV_NEUTRAL_PROMPT,
)


@dataclass
class PAdvProvider(BaseProvider):
    """Adversarial provider; same model+price tier as P-mid."""

    adversarial_prompt: str = P_ADV_ADVERSARIAL_PROMPT

    def _select_system_prompt(self, version: int) -> str:
        if version in ADVERSARIAL_VERSIONS[ProviderId.P_ADV]:
            return self.adversarial_prompt
        return self.system_prompt


def make_p_adv(backend: LlmBackend, base_price_usdc: float) -> PAdvProvider:
    return PAdvProvider(
        provider_id=ProviderId.P_ADV,
        model_name="gpt-5.4-mini",
        base_price_usdc=base_price_usdc,
        system_prompt=P_ADV_NEUTRAL_PROMPT,
        backend=backend,
    )
