"""Tests for ``pilot402.eval.composite.CompositeEvaluator``.

Verifies the two-mode contract from system_design §2.5:

* ``score(task, response)`` dispatches by task type to the right backend.
* ``lookup(task_id, provider_id, version)`` reads cached scores from the
  bound ``PregenStore`` and refuses to operate without one.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from pilot402.core import (
    Evaluator,
    EvaluatorBackend,
    ProviderId,
    Task,
    TaskType,
)
from pilot402.eval import CachedJudgeBackend, CompositeEvaluator, MockJudgeClient
from pilot402.pregen.dataset import JsonlPregenStore
from pilot402.pregen.tasks import read_cache

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def composite(tmp_path: Path) -> CompositeEvaluator:
    judge = CachedJudgeBackend(
        client=MockJudgeClient(),
        cache_path=tmp_path / "judge_cache.jsonl",
        model_id="claude-test",
        seed=0,
    )
    return CompositeEvaluator(judge=judge)


def test_composite_satisfies_evaluator_protocol(composite: CompositeEvaluator) -> None:
    assert isinstance(composite, Evaluator)


def test_t1_dispatches_to_pass_at_1(composite: CompositeEvaluator) -> None:
    [task] = read_cache(FIXTURES / "tasks" / "humaneval.jsonl", limit=1)
    score = composite.score(task, "    return a + b\n")
    assert score.q == 1.0
    assert score.backend is EvaluatorBackend.PASS_AT_1


def test_t2_dispatches_to_em_f1(composite: CompositeEvaluator) -> None:
    [task] = read_cache(FIXTURES / "tasks" / "hotpotqa.jsonl", limit=1)
    score = composite.score(task, task.gold_answer or "")
    assert score.q == 1.0
    assert score.backend is EvaluatorBackend.EM_F1


def test_t3a_dispatches_to_em_f1(composite: CompositeEvaluator) -> None:
    [task] = read_cache(FIXTURES / "tasks" / "triviaqa.jsonl", limit=1)
    score = composite.score(task, "Au")
    assert score.q == 1.0
    assert score.backend is EvaluatorBackend.EM_F1


def test_t3b_dispatches_to_judge(composite: CompositeEvaluator) -> None:
    [task] = read_cache(FIXTURES / "tasks" / "openweb.jsonl", limit=1)
    score = composite.score(task, "a thoughtful answer")
    assert score.backend is EvaluatorBackend.JUDGE
    assert 0.0 <= score.q <= 1.0


def test_em_f1_without_gold_raises(composite: CompositeEvaluator) -> None:
    bad = Task(
        task_id="t",
        task_type=TaskType.T2_MULTIHOP_QA,
        prompt="?",
        gold_answer=None,
        difficulty=0.1,
    )
    with pytest.raises(ValueError):
        composite.score(bad, "anything")


def test_lookup_requires_pregen_store(composite: CompositeEvaluator) -> None:
    with pytest.raises(RuntimeError):
        composite.lookup("trivia/test_001", ProviderId.P_CHEAP, version=0)


def test_lookup_returns_cached_score(tmp_path: Path) -> None:
    out = tmp_path / "pregen"
    out.mkdir()
    shutil.copy(FIXTURES / "pregen_records.jsonl", out / "mixed.jsonl")
    store = JsonlPregenStore(out)

    judge = CachedJudgeBackend(
        client=MockJudgeClient(),
        cache_path=tmp_path / "judge.jsonl",
        model_id="m",
    )
    composite = CompositeEvaluator(judge=judge, pregen_store=store)

    score = composite.lookup("trivia/test_001", ProviderId.P_CHEAP, version=0)
    assert score.q == 1.0
    assert score.backend is EvaluatorBackend.EM_F1
