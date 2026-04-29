"""Tests for ``pilot402.core.types``.

The most important guarantee here is that wire-format types
(``LogRecord`` and ``PregenRecord``) round-trip through JSON without loss.
A schema drift in either of these silently invalidates downstream
artifacts (analysis pipeline reads ``LogRecord``; Phase 2+ env reads
``PregenRecord``), so these tests exist to make any drift loud.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pilot402.core import (
    Decision,
    EvaluatorBackend,
    FailureCode,
    LogRecord,
    Outcome,
    PregenRecord,
    ProviderId,
    QualityScore,
    Reward,
    Task,
    TaskType,
)


def test_logrecord_json_roundtrip(sample_log_record: LogRecord) -> None:
    line = sample_log_record.model_dump_json()
    parsed = LogRecord.model_validate_json(line)
    assert parsed == sample_log_record


def test_pregen_record_json_roundtrip(sample_pregen_record: PregenRecord) -> None:
    line = sample_pregen_record.model_dump_json()
    parsed = PregenRecord.model_validate_json(line)
    assert parsed == sample_pregen_record


def test_logrecord_has_schema_version(sample_log_record: LogRecord) -> None:
    """Schema version must be present and equal to 1 in v1."""
    assert sample_log_record.schema_version == 1


def test_pregen_record_has_schema_version(sample_pregen_record: PregenRecord) -> None:
    assert sample_pregen_record.schema_version == 1


def test_types_are_frozen(sample_task: Task) -> None:
    with pytest.raises(ValidationError):
        sample_task.task_id = "mutated"  # type: ignore[misc]


def test_quality_score_q_bounds() -> None:
    QualityScore(q=0.0, backend=EvaluatorBackend.EM_F1)
    QualityScore(q=1.0, backend=EvaluatorBackend.EM_F1)
    with pytest.raises(ValidationError):
        QualityScore(q=-0.01, backend=EvaluatorBackend.EM_F1)
    with pytest.raises(ValidationError):
        QualityScore(q=1.01, backend=EvaluatorBackend.EM_F1)


def test_outcome_rejects_zero_attempts() -> None:
    with pytest.raises(ValidationError):
        Outcome(
            response="x",
            charged_cost_usdc=0.0,
            latency_s=0.1,
            failure_flag=False,
            failure_code=FailureCode.NONE,
            attempt_count=0,
        )


def test_decision_context_is_tuple_immutable() -> None:
    d = Decision(
        round=0,
        task_id="t",
        context=(0.1, 0.2, 0.3),
        chosen_arm=ProviderId.P_MID,
        affordable_arms=(ProviderId.P_CHEAP, ProviderId.P_MID),
    )
    assert isinstance(d.context, tuple)
    with pytest.raises(ValidationError):
        d.context = (9.9,)  # type: ignore[misc]


def test_reward_weights_non_negative() -> None:
    Reward(utility=0.5, payment_aware_reward=0.4, lambda_t=0.0, mu=0.0, nu=0.0)
    with pytest.raises(ValidationError):
        Reward(utility=0.5, payment_aware_reward=0.4, lambda_t=-0.1, mu=0.0, nu=0.0)


def test_task_difficulty_in_unit_interval() -> None:
    Task(task_id="t", task_type=TaskType.T1_CODING, prompt="", difficulty=0.0)
    Task(task_id="t", task_type=TaskType.T1_CODING, prompt="", difficulty=1.0)
    with pytest.raises(ValidationError):
        Task(task_id="t", task_type=TaskType.T1_CODING, prompt="", difficulty=1.5)


def test_extra_fields_forbidden() -> None:
    """Schema drift guard: unknown fields must raise, not silently pass through."""
    with pytest.raises(ValidationError):
        Task.model_validate(  # type: ignore[call-arg]
            {
                "task_id": "t",
                "task_type": "T1",
                "prompt": "",
                "difficulty": 0.0,
                "unknown_field": "x",
            }
        )


def test_enum_values_are_stable_strings() -> None:
    """Wire format depends on these exact strings; locking them down here."""
    assert ProviderId.P_CHEAP.value == "P-cheap"
    assert ProviderId.P_MID.value == "P-mid"
    assert ProviderId.P_PREMIUM.value == "P-premium"
    assert ProviderId.P_ADV.value == "P-adv"
    assert ProviderId.P_FLAKY.value == "P-flaky"
    assert TaskType.T1_CODING.value == "T1"
    assert TaskType.T2_MULTIHOP_QA.value == "T2"
    assert TaskType.T3A_WEBSEARCH_CLOSED.value == "T3a"
    assert TaskType.T3B_WEBSEARCH_OPEN.value == "T3b"
    assert FailureCode.TIMEOUT.value == "timeout"
