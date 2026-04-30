"""Tests for ``pilot402.eval.metric_backend``.

The two non-trivial things to verify:

1. EM/F1 normalization matches the SQuAD-style reference (lowercase,
   articles/punctuation removed, whitespace collapsed) so independent
   re-implementation of the metric in any verification script lines up.
2. ``pass_at_1`` actually runs subprocess code and returns 1.0 / 0.0 for
   passing / failing solutions, with a hard timeout cap.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pilot402.core import Task, TaskType
from pilot402.eval.metric_backend import (
    em_score,
    f1_score,
    max_em_f1,
    pass_at_1,
)
from pilot402.pregen.tasks import read_cache

FIXTURES = Path(__file__).parent / "fixtures" / "tasks"


# ---------------------------------------------------------------------------
# EM / F1
# ---------------------------------------------------------------------------


def test_em_exact_match() -> None:
    assert em_score("Paris", "Paris") == 1.0


def test_em_normalization_strips_articles_and_case() -> None:
    assert em_score("the Paris", "paris") == 1.0
    assert em_score("Paris.", "paris") == 1.0


def test_em_mismatch() -> None:
    assert em_score("Paris", "London") == 0.0


def test_f1_partial_overlap() -> None:
    f = f1_score("Paris is the capital", "the capital city Paris")
    assert 0.5 < f < 1.0


def test_f1_perfect_match() -> None:
    assert f1_score("Charles Dickens", "Charles Dickens") == 1.0


def test_f1_no_overlap() -> None:
    assert f1_score("apple banana", "carrot daikon") == 0.0


def test_f1_both_empty() -> None:
    assert f1_score("", "") == 1.0


def test_f1_one_empty() -> None:
    assert f1_score("", "Paris") == 0.0
    assert f1_score("Paris", "") == 0.0


def test_max_em_f1_uses_higher_score() -> None:
    # EM = 0, F1 = 0.something; max should be F1.
    pred = "the city of Paris"
    gold = "Paris"
    assert max_em_f1(pred, gold) == max(em_score(pred, gold), f1_score(pred, gold))


# ---------------------------------------------------------------------------
# pass@1
# ---------------------------------------------------------------------------


def _humaneval_task() -> Task:
    [task] = read_cache(FIXTURES / "humaneval.jsonl", limit=1)
    assert task.task_type is TaskType.T1_CODING
    return task


def test_pass_at_1_correct_solution_scores_1() -> None:
    task = _humaneval_task()
    assert pass_at_1(task, "    return a + b\n") == 1.0


def test_pass_at_1_wrong_solution_scores_0() -> None:
    task = _humaneval_task()
    assert pass_at_1(task, "    return a - b\n") == 0.0


def test_pass_at_1_handles_full_function_response() -> None:
    """If the model emits a complete function (with signature), the runner
    should use it standalone instead of prepending the prompt."""
    task = _humaneval_task()
    full = "def add(a, b):\n    return a + b\n"
    assert pass_at_1(task, full) == 1.0


def test_pass_at_1_handles_code_fence_wrapping() -> None:
    task = _humaneval_task()
    fenced = "Here is the code:\n```python\ndef add(a, b):\n    return a + b\n```\n"
    assert pass_at_1(task, fenced) == 1.0


def test_pass_at_1_syntax_error_scores_0() -> None:
    task = _humaneval_task()
    assert pass_at_1(task, "    return a +\n") == 0.0


def test_pass_at_1_timeout_scores_0() -> None:
    task = _humaneval_task()
    # Infinite loop in the response; should be killed by timeout and score 0.
    response = "    while True: pass\n    return a + b\n"
    assert pass_at_1(task, response, timeout_s=1.0) == 0.0


def test_pass_at_1_missing_metadata_raises() -> None:
    bad = Task(
        task_id="bad",
        task_type=TaskType.T1_CODING,
        prompt="def f(x): pass",
        difficulty=0.1,
        # No entry_point / test in metadata.
    )
    with pytest.raises(ValueError):
        pass_at_1(bad, "pass")


def test_pass_at_1_determinism() -> None:
    """Same (task, response) → same score across repeated calls."""
    task = _humaneval_task()
    scores = {pass_at_1(task, "    return a + b\n") for _ in range(5)}
    assert scores == {1.0}


def test_pass_at_1_complete_function_inherits_prompt_imports() -> None:
    """Regression: a model that emits a complete ``def foo(...)`` block
    without re-emitting ``from typing import List`` should still pass.

    Before the import-prepend fix, this case scored 0.0 because ``List``
    was undefined in the standalone subprocess (``NameError: List``).
    Real-world example: HumanEval/3 from Qwen3-8B at T=0.3.
    """

    task = Task(
        task_id="test_humaneval/needs_typing",
        task_type=TaskType.T1_CODING,
        prompt=(
            "from typing import List\n\n"
            "def below_zero(operations: List[int]) -> bool:\n"
            "    \"\"\"Return True iff balance ever drops below 0.\"\"\"\n"
        ),
        gold_answer=(
            "    balance = 0\n"
            "    for op in operations:\n"
            "        balance += op\n"
            "        if balance < 0:\n"
            "            return True\n"
            "    return False\n"
        ),
        difficulty=0.2,
        metadata={
            "source": "test",
            "entry_point": "below_zero",
            "test": (
                "def check(candidate):\n"
                "    assert candidate([1, 2, -5, 4]) is True\n"
                "    assert candidate([1, 2, 3]) is False\n"
            ),
        },
    )
    # Response is a complete function but does NOT re-emit the import line.
    response = (
        "def below_zero(operations: List[int]) -> bool:\n"
        "    balance = 0\n"
        "    for op in operations:\n"
        "        balance += op\n"
        "        if balance < 0:\n"
        "            return True\n"
        "    return False\n"
    )
    assert pass_at_1(task, response) == 1.0


def test_pass_at_1_response_with_redundant_import_still_passes() -> None:
    """The import-prepend logic must NOT inject duplicate imports when
    the response already includes them."""

    task = Task(
        task_id="test_humaneval/dup_imports",
        task_type=TaskType.T1_CODING,
        prompt=(
            "from typing import List\n\n"
            "def first(items: List[int]) -> int:\n"
            "    \"\"\"Return the first item.\"\"\"\n"
        ),
        gold_answer="    return items[0]\n",
        difficulty=0.1,
        metadata={
            "source": "test",
            "entry_point": "first",
            "test": "def check(candidate):\n    assert candidate([7, 8]) == 7\n",
        },
    )
    response = (
        "from typing import List\n\n"
        "def first(items: List[int]) -> int:\n"
        "    return items[0]\n"
    )
    assert pass_at_1(task, response) == 1.0
