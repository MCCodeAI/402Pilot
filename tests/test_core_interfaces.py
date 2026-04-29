"""Tests for ``pilot402.core.interfaces``.

These are contract tests: they construct minimal stubs that satisfy each
Protocol and check ``isinstance(stub, Protocol)``. When a real implementation
is dropped in later milestones, the same isinstance check is the first
gate it must pass.
"""

from __future__ import annotations

from typing import Any

from pilot402.core import (
    BudgetManager,
    ContextVector,
    Encoder,
    EncoderState,
    Evaluator,
    LogRecord,
    Outcome,
    PaymentExecutor,
    Policy,
    PregenRecord,
    PregenStore,
    ProviderId,
    QualityScore,
    Recorder,
    Task,
)


class _StubPolicy:
    def select(
        self,
        context: ContextVector,
        affordable_arms: tuple[ProviderId, ...],
    ) -> ProviderId:
        return affordable_arms[0]

    def update(self, context: ContextVector, arm: ProviderId, utility: float) -> None:
        return None


class _StubEncoder:
    feature_dim = 4

    def encode(self, task: Task, state: EncoderState) -> ContextVector:
        return (0.0, 0.0, 0.0, 0.0)


class _StubBudget:
    def get_lambda(self) -> float:
        return 1.0

    def affordable(self, cost_usdc: float) -> bool:
        return True

    def record_spend(self, cost_usdc: float) -> None:
        return None

    def snapshot(self) -> dict[str, float]:
        return {"remaining": 100.0}


class _StubEvaluator:
    def score(self, task: Task, response: str) -> QualityScore:
        from pilot402.core import EvaluatorBackend  # local import keeps stub minimal

        return QualityScore(q=0.5, backend=EvaluatorBackend.EM_F1)

    def lookup(
        self,
        task_id: str,
        provider_id: ProviderId,
        version: int,
    ) -> QualityScore:
        return self.score(task=None, response="")  # type: ignore[arg-type]


class _StubExecutor:
    def pay_and_call(
        self,
        provider_id: ProviderId,
        request_payload: dict[str, Any],
    ) -> Outcome:
        from pilot402.core import FailureCode

        return Outcome(
            response="",
            charged_cost_usdc=0.0,
            latency_s=0.0,
            failure_flag=False,
            failure_code=FailureCode.NONE,
            attempt_count=1,
        )


class _StubPregenStore:
    def get(
        self,
        task_id: str,
        provider_id: ProviderId,
        version: int,
    ) -> PregenRecord:
        raise NotImplementedError

    def versions(
        self,
        task_id: str,
        provider_id: ProviderId,
    ) -> tuple[int, ...]:
        return (0,)


class _StubRecorder:
    def write(self, record: LogRecord) -> None:
        return None

    def close(self) -> None:
        return None


def test_policy_stub_satisfies_protocol() -> None:
    assert isinstance(_StubPolicy(), Policy)


def test_encoder_stub_satisfies_protocol() -> None:
    assert isinstance(_StubEncoder(), Encoder)


def test_budget_stub_satisfies_protocol() -> None:
    assert isinstance(_StubBudget(), BudgetManager)


def test_evaluator_stub_satisfies_protocol() -> None:
    assert isinstance(_StubEvaluator(), Evaluator)


def test_executor_stub_satisfies_protocol() -> None:
    assert isinstance(_StubExecutor(), PaymentExecutor)


def test_pregen_store_stub_satisfies_protocol() -> None:
    assert isinstance(_StubPregenStore(), PregenStore)


def test_recorder_stub_satisfies_protocol() -> None:
    assert isinstance(_StubRecorder(), Recorder)


def test_policy_stub_returns_member_of_affordable_set() -> None:
    """Tightening the contract: the policy must pick from the affordable set."""
    p = _StubPolicy()
    affordable = (ProviderId.P_CHEAP, ProviderId.P_MID)
    arm = p.select(context=(0.0,), affordable_arms=affordable)
    assert arm in affordable


def test_object_missing_method_fails_protocol_check() -> None:
    """Negative case: an object without ``update`` is not a Policy."""

    class _Half:
        def select(
            self,
            context: ContextVector,
            affordable_arms: tuple[ProviderId, ...],
        ) -> ProviderId:
            return affordable_arms[0]

    assert not isinstance(_Half(), Policy)
