"""Base abstractions for the K=5 pregen providers.

The pregen-time pipeline talks to LLM APIs via a thin ``LlmBackend`` Protocol
so that:

* Tests inject ``MockLlmBackend`` / ``RecordingMockBackend`` and never hit
  the network.
* Real backends live in ``pilot402.pregen.providers.backends`` and lazy-import
  their SDKs, keeping the package importable without ``openai`` / ``anthropic``
  / ``dashscope`` installed.
* Each provider class consumes the backend uniformly — only its system prompt,
  model name, and optional version-aware behavior differ.

Behavioral mechanics for adversarial / flaky providers (decision Option C,
locked with the user):

* ``ADVERSARIAL_VERSIONS[ProviderId.P_ADV] = {0, 1, 2}`` — those versions
  use the adversarial system prompt; versions 3, 4 use the neutral prompt.
* ``ADVERSARIAL_VERSIONS[ProviderId.P_FLAKY] = {0, 1}`` — those versions
  are short-circuited to a billed timeout (no LLM call) so the empirical
  failure rate is exactly 2/5 = 40%. The 40% rate (raised from an earlier
  20% calibration on 2026-05-02) gives the bandit a clearly differentiated
  reliability signal versus P-mid (same cost, same model, 0% failures).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from numpy.random import Generator

from pilot402.core import FailureCode, ProviderId, Task

# ---------------------------------------------------------------------------
# Backend abstraction
# ---------------------------------------------------------------------------


DEFAULT_TEMPERATURE: float = 0.3
"""Default sampling temperature for all pregen calls.

Moderate sampling diversity so per-version seeds produce different
responses, while keeping coding pass@1 nearly as high as T=0. The chosen
temperature is persisted in each PregenRecord for provenance.
"""


@dataclass(frozen=True)
class LlmRequest:
    """One LLM completion request. Backend-agnostic."""

    system: str
    user: str
    model: str
    seed: int
    max_tokens: int = 1024
    temperature: float = DEFAULT_TEMPERATURE


@dataclass(frozen=True)
class LlmResponse:
    """One LLM completion response. Latency is wall-clock seconds."""

    text: str
    prompt_tokens: int
    completion_tokens: int
    latency_s: float


@runtime_checkable
class LlmBackend(Protocol):
    """Interface implemented by both mock and real backends."""

    def complete(self, request: LlmRequest) -> LlmResponse: ...


# ---------------------------------------------------------------------------
# Provider output schema (shared by every concrete provider)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProviderCallResult:
    """Tuple-equivalent return type from ``Provider.generate``.

    The orchestrator turns this plus the evaluator's ``QualityScore`` into a
    full ``PregenRecord``. ``temperature`` records the sampling temperature
    that the provider actually used; persisted in ``PregenRecord.temperature``
    so re-runs at different temps stay distinguishable.
    """

    response: str
    cost_usdc: float
    latency_s: float
    failure_flag: bool
    failure_code: FailureCode
    temperature: float


# ---------------------------------------------------------------------------
# Adversarial / failure version assignments
# ---------------------------------------------------------------------------


ADVERSARIAL_VERSIONS: dict[ProviderId, frozenset[int]] = {
    ProviderId.P_ADV: frozenset({0, 1, 2}),
    ProviderId.P_FLAKY: frozenset({0, 1}),
}
"""Locked version-level mechanism for degraded behavior (decision Option C).

Reproducibility note: this constant is the single source of truth for the
adversarial/flaky empirical rates reported in the paper. Changing the sets
silently changes those rates — bump the dataset ``schema_version`` if you
ever rotate them.
"""


# ---------------------------------------------------------------------------
# BaseProvider — concrete shared logic
# ---------------------------------------------------------------------------


@dataclass
class BaseProvider:
    """Shared implementation for all five providers.

    Subclasses customize via ``system_prompt`` (most providers) or by
    overriding ``_select_system_prompt`` (P-adv, version-aware).
    """

    provider_id: ProviderId
    model_name: str
    base_price_usdc: float
    system_prompt: str
    backend: LlmBackend
    extra_metadata: dict[str, str] = field(default_factory=dict)

    def generate(
        self,
        task: Task,
        version: int,
        *,
        rng: Generator,
    ) -> ProviderCallResult:
        """Drive one LLM call. The base implementation never injects failures;
        subclasses may override (see ``PFlakyProvider``)."""

        api_seed = int(rng.integers(0, 2**31 - 1))
        prompt = self._select_system_prompt(version)
        request = LlmRequest(
            system=prompt,
            user=task.prompt,
            model=self.model_name,
            seed=api_seed,
        )
        try:
            response = self.backend.complete(request)
        except Exception as exc:
            # Catch broadly: any backend exception during pregen is recorded
            # as a billed payment_failure rather than crashing the run. The
            # orchestrator decides whether to retry the (task, version) cell.
            #
            # Print to stderr so the user can diagnose which provider /
            # model / call is failing — without this, all backend errors
            # collapsed into identical empty PregenRecords and the cause
            # was invisible.
            print(
                f"[{self.provider_id.value} model={self.model_name} "
                f"task={task.task_id} v={version}] backend failed: {exc!r}",
                file=sys.stderr,
            )
            return ProviderCallResult(
                response="",
                cost_usdc=self.base_price_usdc,
                latency_s=0.0,
                failure_flag=True,
                failure_code=FailureCode.PAYMENT_FAILURE,
                temperature=request.temperature,
            )
        return ProviderCallResult(
            response=response.text,
            cost_usdc=self.base_price_usdc,
            latency_s=response.latency_s,
            failure_flag=False,
            failure_code=FailureCode.NONE,
            temperature=request.temperature,
        )

    def _select_system_prompt(self, version: int) -> str:
        """Hook for version-aware providers (only P-adv overrides today)."""

        return self.system_prompt
