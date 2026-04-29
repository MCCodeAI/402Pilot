"""Tests for ``pilot402.pregen.tasks``.

The cache-read path is exercised against shipped JSONL fixtures so the
tests run completely offline and without ``datasets`` installed. The
network download path (``_from_source``) is intentionally not tested in
CI; it is exercised manually as part of the Tier 1 pregen run.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pilot402.core import Task, TaskType
from pilot402.pregen.tasks import (
    DEFAULT_LIMITS,
    HotpotQaLoader,
    HumanEvalLoader,
    OpenWebLoader,
    TriviaQaLoader,
    estimate_difficulty,
    is_cache_stale,
    load_all_tasks,
    read_cache,
    write_cache,
)

FIXTURES = Path(__file__).parent / "fixtures" / "tasks"


def test_humaneval_cache_load() -> None:
    tasks = HumanEvalLoader().load(FIXTURES, limit=5)
    assert len(tasks) == 2
    assert tasks[0].task_type is TaskType.T1_CODING
    assert "entry_point" in tasks[0].metadata
    assert "test" in tasks[0].metadata


def test_hotpotqa_cache_load() -> None:
    tasks = HotpotQaLoader().load(FIXTURES, limit=5)
    assert len(tasks) == 2
    assert all(t.task_type is TaskType.T2_MULTIHOP_QA for t in tasks)
    assert tasks[0].gold_answer is not None


def test_triviaqa_cache_load() -> None:
    tasks = TriviaQaLoader().load(FIXTURES, limit=5)
    assert len(tasks) == 2
    assert all(t.task_type is TaskType.T3A_WEBSEARCH_CLOSED for t in tasks)


def test_openweb_cache_load() -> None:
    tasks = OpenWebLoader().load(FIXTURES, limit=5)
    assert len(tasks) == 2
    assert all(t.task_type is TaskType.T3B_WEBSEARCH_OPEN for t in tasks)
    assert all(t.gold_answer is None for t in tasks)


def test_load_all_tasks_combines_sources() -> None:
    tasks = load_all_tasks(FIXTURES)
    types = [t.task_type for t in tasks]
    # Each fixture has 2 tasks, so 8 total in the order:
    # HumanEval, HotpotQA, TriviaQA, OpenWeb.
    assert types == [
        TaskType.T1_CODING,
        TaskType.T1_CODING,
        TaskType.T2_MULTIHOP_QA,
        TaskType.T2_MULTIHOP_QA,
        TaskType.T3A_WEBSEARCH_CLOSED,
        TaskType.T3A_WEBSEARCH_CLOSED,
        TaskType.T3B_WEBSEARCH_OPEN,
        TaskType.T3B_WEBSEARCH_OPEN,
    ]


def test_load_all_tasks_respects_limits() -> None:
    tasks = load_all_tasks(FIXTURES, limits={"humaneval": 1, "openweb": 0})
    assert sum(1 for t in tasks if t.task_type is TaskType.T1_CODING) == 1
    assert sum(1 for t in tasks if t.task_type is TaskType.T3B_WEBSEARCH_OPEN) == 0


def test_default_limits_sum_to_824() -> None:
    """Locked composition: 164 (full HumanEval) + 220 × 3 = 824 tasks total.

    Note: HumanEval has exactly 164 problems; we use the entire dataset
    rather than sampling. The original PLAN §3.5 estimate of 825 was an
    off-by-one rounding — the real cap is 824.
    """
    total = sum(int(v) for v in DEFAULT_LIMITS.values() if v is not None)
    assert total == 824


def test_estimate_difficulty_in_unit_interval() -> None:
    assert 0.0 <= estimate_difficulty("") <= 1.0
    assert estimate_difficulty("x" * 100) < 1.0
    assert estimate_difficulty("x" * 5000) == 1.0  # capped


def test_estimate_difficulty_rejects_bad_scale() -> None:
    with pytest.raises(ValueError):
        estimate_difficulty("x", scale_chars=0)


def test_read_cache_respects_limit(tmp_path: Path) -> None:
    src = FIXTURES / "humaneval.jsonl"
    out = read_cache(src, limit=1)
    assert len(out) == 1


# ---------------------------------------------------------------------------
# Cache staleness — protects against silent format drift across re-runs.
# ---------------------------------------------------------------------------


def test_hotpotqa_fixture_is_v2() -> None:
    """The shipped fixture must be at the current loader format version."""
    [task] = read_cache(FIXTURES / "hotpotqa.jsonl", limit=1)
    assert task.metadata.get("loader_format_version") == 2
    # v2 prompts are reading-comprehension: they include "Read the following".
    assert task.prompt.startswith("Read the following passages")
    # supporting_titles is logged for analysis, not exposed to the model.
    assert "supporting_titles" in task.metadata


def test_humaneval_fixture_is_v2() -> None:
    """HumanEval fixture must carry the v2 loader_format_version stamp.

    Without this, ``HumanEvalLoader.load`` would treat the fixture as
    stale on every test run and try to re-download from HuggingFace.
    """
    [task] = read_cache(FIXTURES / "humaneval.jsonl", limit=1)
    assert task.metadata.get("loader_format_version") == 2
    assert task.metadata.get("entry_point")
    assert task.metadata.get("test")


def test_hotpotqa_v1_cache_is_treated_as_stale(tmp_path: Path) -> None:
    """A cache file written by the old (closed-book) loader must be detected
    as stale so an in-place upgrade rebuilds rather than silently serving v1
    rows. The fixture is v2; we synthesize a v1 file inline to test."""
    v1_path = tmp_path / "hotpotqa.jsonl"
    v1_task = Task(
        task_id="hotpot/legacy",
        task_type=TaskType.T2_MULTIHOP_QA,
        prompt="Just a question?",  # no context, v1 style
        gold_answer="answer",
        difficulty=0.5,
        metadata={"source": "legacy"},  # no loader_format_version
    )
    write_cache(v1_path, [v1_task])
    assert is_cache_stale(v1_path, expected_version=2)
    assert not is_cache_stale(v1_path, expected_version=1)


def test_hotpotqa_v2_cache_is_not_stale() -> None:
    assert not is_cache_stale(FIXTURES / "hotpotqa.jsonl", expected_version=2)


def test_is_cache_stale_handles_missing_file(tmp_path: Path) -> None:
    """Missing file is 'no cache', not 'stale cache'."""
    assert not is_cache_stale(tmp_path / "nope.jsonl", expected_version=1)


def test_is_cache_stale_handles_empty_file(tmp_path: Path) -> None:
    """Empty file should be treated as stale to force a rebuild."""
    p = tmp_path / "empty.jsonl"
    p.write_text("", encoding="utf-8")
    assert is_cache_stale(p, expected_version=1)


def test_is_cache_stale_handles_corrupt_first_line(tmp_path: Path) -> None:
    p = tmp_path / "bad.jsonl"
    p.write_text("not json at all\n", encoding="utf-8")
    assert is_cache_stale(p, expected_version=1)
