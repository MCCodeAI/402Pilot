"""Tests for ``pilot402.runtime.encoder.NaiveEncoder``."""

from __future__ import annotations

import pytest

from pilot402.core import Task, TaskType
from pilot402.core.interfaces import Encoder
from pilot402.runtime.encoder import NaiveEncoder


def _task(tt: TaskType, difficulty: float = 0.5) -> Task:
    return Task(
        task_id=f"{tt.value}/x",
        task_type=tt,
        prompt="p",
        gold_answer="a",
        difficulty=difficulty,
    )


def test_implements_encoder_protocol() -> None:
    enc = NaiveEncoder()
    assert isinstance(enc, Encoder)


def test_feature_dim_is_seven() -> None:
    assert NaiveEncoder().feature_dim == 7


def test_t1_one_hot() -> None:
    enc = NaiveEncoder()
    vec = enc.encode(_task(TaskType.T1_CODING, 0.3), state={})
    assert vec[:4] == (1.0, 0.0, 0.0, 0.0)


def test_t2_one_hot() -> None:
    enc = NaiveEncoder()
    vec = enc.encode(_task(TaskType.T2_MULTIHOP_QA, 0.3), state={})
    assert vec[:4] == (0.0, 1.0, 0.0, 0.0)


def test_t3a_one_hot() -> None:
    enc = NaiveEncoder()
    vec = enc.encode(_task(TaskType.T3A_WEBSEARCH_CLOSED, 0.3), state={})
    assert vec[:4] == (0.0, 0.0, 1.0, 0.0)


def test_t3b_one_hot() -> None:
    enc = NaiveEncoder()
    vec = enc.encode(_task(TaskType.T3B_WEBSEARCH_OPEN, 0.3), state={})
    assert vec[:4] == (0.0, 0.0, 0.0, 1.0)


def test_difficulty_passed_through() -> None:
    enc = NaiveEncoder()
    vec = enc.encode(_task(TaskType.T1_CODING, 0.42), state={})
    assert vec[4] == pytest.approx(0.42)


def test_state_remaining_fraction_and_lambda_used() -> None:
    enc = NaiveEncoder()
    vec = enc.encode(
        _task(TaskType.T1_CODING),
        state={"remaining_fraction": 0.3, "lambda_t": 2.5},
    )
    assert vec[5] == pytest.approx(0.3)
    assert vec[6] == pytest.approx(2.5)


def test_state_defaults_when_missing_keys() -> None:
    enc = NaiveEncoder()
    vec = enc.encode(_task(TaskType.T1_CODING), state={})
    # Defaults: remaining_fraction=1.0, lambda_t=1.0
    assert vec[5] == 1.0
    assert vec[6] == 1.0


def test_lambda_clipped_at_threshold() -> None:
    enc = NaiveEncoder(lambda_clip=5.0)
    vec = enc.encode(_task(TaskType.T1_CODING), state={"lambda_t": 50.0})
    assert vec[6] == 5.0


def test_lambda_floor_at_zero() -> None:
    """Negative lambda is technically illegal but we should clamp at 0
    rather than propagate a negative feature into the policy."""
    enc = NaiveEncoder()
    vec = enc.encode(_task(TaskType.T1_CODING), state={"lambda_t": -1.0})
    assert vec[6] == 0.0
