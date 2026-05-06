"""Tests for ``pilot402.runtime.sampler.WorkloadSampler``."""

from __future__ import annotations

from collections import Counter

import pytest
from numpy.random import default_rng

from pilot402.core import Task, TaskType
from pilot402.runtime import WorkloadSampler


def _make_pool() -> list[Task]:
    out: list[Task] = []
    for tt in (
        TaskType.T1_CODING,
        TaskType.T2_MULTIHOP_QA,
        TaskType.T3A_WEBSEARCH_CLOSED,
        TaskType.T3B_WEBSEARCH_OPEN,
    ):
        for i in range(50):
            out.append(
                Task(
                    task_id=f"{tt.value}/task_{i:03d}",
                    task_type=tt,
                    prompt="dummy",
                    gold_answer="dummy",
                    difficulty=0.5,
                )
            )
    return out


def test_sampler_is_deterministic_for_fixed_seed() -> None:
    pool = _make_pool()
    seq_a = [WorkloadSampler(pool, default_rng(7)).next().task_id for _ in range(20)]
    seq_b = [WorkloadSampler(pool, default_rng(7)).next().task_id for _ in range(20)]
    # Same seed → same sequence (each call rebuilds Generator from same seed).
    assert seq_a == seq_b


def test_sampler_diverges_for_different_seeds() -> None:
    pool = _make_pool()
    seq_a = [WorkloadSampler(pool, default_rng(0)).next().task_id for _ in range(50)]
    seq_b = [WorkloadSampler(pool, default_rng(1)).next().task_id for _ in range(50)]
    assert seq_a != seq_b


def test_flat_uniform_visits_all_task_types() -> None:
    pool = _make_pool()
    sampler = WorkloadSampler(pool, default_rng(42))
    types = Counter(sampler.next().task_type for _ in range(2000))
    # All 4 types should be hit at least 100 times in 2000 draws (each type is 25%).
    for tt in TaskType:
        assert types[tt] > 100, f"task type {tt} undersampled: {types}"


def test_explicit_mix_respected() -> None:
    pool = _make_pool()
    # Force 90% T1, 10% T2, 0% others.
    sampler = WorkloadSampler(
        pool,
        default_rng(0),
        mix={
            TaskType.T1_CODING: 0.9,
            TaskType.T2_MULTIHOP_QA: 0.1,
        },
    )
    counts = Counter(sampler.next().task_type for _ in range(1000))
    assert 850 < counts[TaskType.T1_CODING] < 950
    assert 50 < counts[TaskType.T2_MULTIHOP_QA] < 150
    assert counts[TaskType.T3A_WEBSEARCH_CLOSED] == 0
    assert counts[TaskType.T3B_WEBSEARCH_OPEN] == 0


def test_empty_pool_rejected() -> None:
    with pytest.raises(ValueError):
        WorkloadSampler(tasks=[], rng=default_rng(0))


def test_mix_with_missing_task_type_rejected() -> None:
    pool = [
        Task(
            task_id="t1/0",
            task_type=TaskType.T1_CODING,
            prompt="p",
            gold_answer="a",
            difficulty=0.1,
        )
    ]
    with pytest.raises(ValueError, match="no such tasks"):
        WorkloadSampler(
            tasks=pool,
            rng=default_rng(0),
            mix={TaskType.T2_MULTIHOP_QA: 1.0},
        )
