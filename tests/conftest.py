"""Shared pytest fixtures for M1.

Kept intentionally small. As later milestones add modules, fixtures grow
under their own ``conftest.py`` files alongside the tests that need them.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from pilot402.core import (
    EvaluatorBackend,
    FailureCode,
    LogRecord,
    PregenRecord,
    ProviderId,
    ProviderSpec,
    QualityScore,
    ScenarioId,
    SeedSource,
    Task,
    TaskType,
)


@pytest.fixture
def repo_root() -> Path:
    """Path to the repository root, derived from this file's location."""
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def sample_task() -> Task:
    return Task(
        task_id="hu_001",
        task_type=TaskType.T1_CODING,
        prompt="def add(a, b):",
        gold_answer="return a + b",
        difficulty=0.3,
        metadata={"source": "HumanEval"},
    )


@pytest.fixture
def sample_provider() -> ProviderSpec:
    return ProviderSpec(
        provider_id=ProviderId.P_MID,
        model_name="GPT-5.4-mini",
        base_price_usdc=0.002,
        tier="mid",
    )


@pytest.fixture
def sample_quality_score() -> QualityScore:
    return QualityScore(q=0.85, backend=EvaluatorBackend.PASS_AT_1)


@pytest.fixture
def sample_pregen_record(sample_quality_score: QualityScore) -> PregenRecord:
    return PregenRecord(
        task_id="hu_001",
        task_type=TaskType.T1_CODING,
        provider_id=ProviderId.P_MID,
        version=0,
        response="def add(a, b):\n    return a + b",
        cost_usdc=0.0021,
        latency_s=1.42,
        failure_flag=False,
        failure_code=FailureCode.NONE,
        quality_score=sample_quality_score,
        generated_at=datetime(2026, 4, 30, 12, 0, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def sample_log_record() -> LogRecord:
    return LogRecord(
        run_id="test_run_0",
        seed=42,
        scenario=ScenarioId.S1_STATIONARY,
        round=7,
        task_id="hu_001",
        task_type=TaskType.T1_CODING,
        context=(0.1, 0.2, 0.3, 0.4),
        chosen_arm=ProviderId.P_MID,
        affordable_arms=(ProviderId.P_CHEAP, ProviderId.P_MID, ProviderId.P_PREMIUM),
        charged_cost_usdc=0.0021,
        latency_s=1.42,
        quality=0.85,
        failure_flag=False,
        failure_code=FailureCode.NONE,
        utility=0.78,
        payment_aware_reward=0.76,
        lambda_t=1.0,
        budget_remaining_usdc=99.5,
    )


@pytest.fixture
def seeds() -> SeedSource:
    return SeedSource(master_seed=42)
