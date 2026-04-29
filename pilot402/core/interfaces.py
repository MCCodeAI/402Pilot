"""Cross-module Protocols.

Every replaceable component is exposed as a ``runtime_checkable`` Protocol so
that a unit test can stub it out and ``isinstance(stub, Protocol)`` works.
Each comparator policy, encoder, evaluator, and so on is a drop-in
implementation of one of these.

These contracts are stable; bumping any signature here is equivalent to a
schema change and requires updating every implementation.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pilot402.core.types import (
    LogRecord,
    Outcome,
    PregenRecord,
    ProviderId,
    QualityScore,
    Task,
)

# Type aliases to keep signatures readable.
ContextVector = tuple[float, ...]
"""Immutable feature vector produced by ``Encoder``."""

EncoderState = dict[str, Any]
"""Opaque state bag that ``Encoder`` consumes (e.g. EWMA stats, budget snapshot)."""


@runtime_checkable
class Policy(Protocol):
    """Service-selector policy (system_design §2.3).

    Implementations: ``policies/fixed.py``, ``policies/rule.py``,
    ``policies/eg.py``, ``policies/ts.py``, ``policies/dts.py``,
    ``policies/linucb.py``, ``policies/padcts.py``.
    """

    def select(
        self,
        context: ContextVector,
        affordable_arms: tuple[ProviderId, ...],
    ) -> ProviderId:
        """Choose one provider from the affordable set.

        ``affordable_arms`` is the subset of providers the budget manager has
        not blocked this round. The policy MUST return a member of this set.
        """
        ...

    def update(
        self,
        context: ContextVector,
        arm: ProviderId,
        utility: float,
    ) -> None:
        """Incorporate the post-call utility ``u_t`` into the posterior.

        Per system_design §2.6, the policy is updated with utility (not
        payment-aware reward) so that the posterior tracks provider quality
        independent of decision-time budget pressure.
        """
        ...


@runtime_checkable
class Encoder(Protocol):
    """Context encoder (system_design §2.1). Pure function: same inputs → same vector."""

    @property
    def feature_dim(self) -> int:
        """Fixed output dimension; constant across the run."""
        ...

    def encode(self, task: Task, state: EncoderState) -> ContextVector: ...


@runtime_checkable
class BudgetManager(Protocol):
    """Budget manager (system_design §2.2)."""

    def get_lambda(self) -> float:
        """Current cost-penalty multiplier λ_t."""
        ...

    def affordable(self, cost_usdc: float) -> bool:
        """True iff a candidate at this cost can be paid from the remaining budget."""
        ...

    def record_spend(self, cost_usdc: float) -> None:
        """Commit a charged amount. Called once per round, after the paid call resolves.

        A budget block or uncharged payment failure records zero spend.
        """
        ...

    def snapshot(self) -> dict[str, float]:
        """Read-only state snapshot for logging and feature extraction."""
        ...


@runtime_checkable
class Evaluator(Protocol):
    """Quality evaluator (system_design §2.5).

    Two modes:

    * ``score`` — used at pregen time only; calls into the underlying metric or judge.
    * ``lookup`` — used during experiments; returns the cached pregen score.

    A bandit loop MUST never call ``score``; if ``lookup`` raises,
    that is a missing-record bug, not a fallback trigger.
    """

    def score(self, task: Task, response: str) -> QualityScore: ...

    def lookup(
        self,
        task_id: str,
        provider_id: ProviderId,
        version: int,
    ) -> QualityScore: ...


@runtime_checkable
class PaymentExecutor(Protocol):
    """x402 payment executor (system_design §2.4).

    The only place a real x402 transaction is initiated. Benchmark runs disable
    retries by default so each round corresponds to one paid attempt.
    """

    def pay_and_call(
        self,
        provider_id: ProviderId,
        request_payload: dict[str, Any],
    ) -> Outcome: ...


@runtime_checkable
class PregenStore(Protocol):
    """Read-only access to the pregen dataset (data/pregen/*.jsonl).

    ``env/`` consumes this to serve replayed responses; it never imports
    ``pilot402.pregen`` directly (code_structure.md, env/providers.py note).
    """

    def get(
        self,
        task_id: str,
        provider_id: ProviderId,
        version: int,
    ) -> PregenRecord: ...

    def versions(
        self,
        task_id: str,
        provider_id: ProviderId,
    ) -> tuple[int, ...]:
        """All versions available for this (task, provider) pair, sorted ascending."""
        ...


@runtime_checkable
class Recorder(Protocol):
    """Per-round structured logger (system_design §3, code_structure runner/recorder.py)."""

    def write(self, record: LogRecord) -> None: ...

    def close(self) -> None: ...


__all__ = [
    "BudgetManager",
    "ContextVector",
    "Encoder",
    "EncoderState",
    "Evaluator",
    "PaymentExecutor",
    "Policy",
    "PregenStore",
    "Recorder",
]
