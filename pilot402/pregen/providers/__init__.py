"""Provider package — registry of factories and shared types.

Public surface:

* ``make_provider(provider_id, backend, base_price_usdc)`` — single entry
  point used by the orchestrator and by tests.
* ``ADVERSARIAL_VERSIONS`` — locked version-level mechanism for P-adv and
  P-flaky degraded behavior.
"""

from __future__ import annotations

from collections.abc import Callable

from pilot402.core import ProviderId
from pilot402.pregen.providers.base import (
    ADVERSARIAL_VERSIONS,
    BaseProvider,
    LlmBackend,
    LlmRequest,
    LlmResponse,
    ProviderCallResult,
)
from pilot402.pregen.providers.mocks import MockLlmBackend, RecordingMockBackend
from pilot402.pregen.providers.p_adv import PAdvProvider, make_p_adv
from pilot402.pregen.providers.p_cheap import PCheapProvider, make_p_cheap
from pilot402.pregen.providers.p_flaky import PFlakyProvider, make_p_flaky
from pilot402.pregen.providers.p_mid import PMidProvider, make_p_mid
from pilot402.pregen.providers.p_premium import PPremiumProvider, make_p_premium

ProviderFactory = Callable[[LlmBackend, float], BaseProvider]

PROVIDER_REGISTRY: dict[ProviderId, ProviderFactory] = {
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
) -> BaseProvider:
    """Construct the configured provider for ``provider_id``.

    Raises ``KeyError`` if the provider id is unknown — fail loud rather
    than silently substituting a default.
    """

    return PROVIDER_REGISTRY[provider_id](backend, base_price_usdc)


__all__ = [
    "ADVERSARIAL_VERSIONS",
    "PROVIDER_REGISTRY",
    "BaseProvider",
    "LlmBackend",
    "LlmRequest",
    "LlmResponse",
    "MockLlmBackend",
    "PAdvProvider",
    "PCheapProvider",
    "PFlakyProvider",
    "PMidProvider",
    "PPremiumProvider",
    "ProviderCallResult",
    "ProviderFactory",
    "RecordingMockBackend",
    "make_p_adv",
    "make_p_cheap",
    "make_p_flaky",
    "make_p_mid",
    "make_p_premium",
    "make_provider",
]
