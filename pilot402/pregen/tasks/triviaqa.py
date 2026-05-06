"""TriviaQA-web loader (T3a — closed-form web search, ~220 sampled rows).

Source: ``trivia_qa`` (``rc.web`` config), ``validation`` split. We use the
canonical answer ``value`` as the gold answer; alias strings are also
stashed in metadata so EM/F1 can be computed against the alias set if a
later evaluator wants to.

**Content-filter skip list** (introduced 2026-05-02):

Aliyun's DashScope API (used by P-cheap → Qwen) runs a stricter content
inspection than OpenAI/Anthropic. A small subset of TriviaQA questions
trip ``DataInspectionFailed`` and return HTTP 400 unconditionally,
regardless of how the question is phrased — this is upstream policy, not
something we can prompt-engineer around.

To keep the provider quality comparison fair (P-cheap can't be silently
penalized for content-filter rejections that other providers don't see),
we maintain a static skip list and exclude these tasks at load time
**for every provider**. The cache file on disk still contains the full
220 sampled tasks; the skip list is applied as a post-read filter, so
removing a task from the list later restores it without rebuilding the
cache.

Rules for adding to the skip list:
1. The task must have failed with ``DataInspectionFailed`` in pregen.
2. Add the exact ``task_id`` (``trivia/<question_id>``) and a one-line
   note explaining the trigger (helpful for the paper's appendix).
3. Bump no version: cache stays the same, only the load-time filter changes.
"""

from __future__ import annotations

from pathlib import Path

from pilot402.core import Task, TaskType
from pilot402.pregen.tasks.base import estimate_difficulty, read_cache, write_cache

_SAMPLE_SEED_INT = 0xB13D0E02  # see hotpotqa.py for rationale

# Tasks that DashScope's content filter unconditionally rejects. Excluded
# from EVERY provider's task set so quality comparisons stay apples-to-apples.
# Each entry pairs the task_id with the documented trigger reason.
_DASHSCOPE_BLOCKED_TASKS: dict[str, str] = {
    "trivia/jp_3954": (
        "DashScope DataInspectionFailed (status=400) on all 5 versions during "
        "Tier 3 sweep on 2026-05-02. Removed for fairness with P-cheap."
    ),
}


class TriviaQaLoader:
    """Loader for the TriviaQA-web closed-form QA benchmark."""

    name = "triviaqa"
    task_type = TaskType.T3A_WEBSEARCH_CLOSED

    def __init__(self, sample_size: int = 220) -> None:
        if sample_size <= 0:
            raise ValueError("sample_size must be positive")
        self._sample_size = sample_size

    def load(self, cache_dir: Path, limit: int | None = None) -> list[Task]:
        cache_path = cache_dir / f"{self.name}.jsonl"
        if cache_path.is_file():
            tasks = read_cache(cache_path, limit=None)
        else:
            tasks = self._from_source()
            write_cache(cache_path, tasks)
        # Apply the DashScope content-filter skip list AFTER the cache read,
        # so the on-disk file is the canonical 220-task sample and the filter
        # is a separately-versioned configuration choice.
        if _DASHSCOPE_BLOCKED_TASKS:
            tasks = [t for t in tasks if t.task_id not in _DASHSCOPE_BLOCKED_TASKS]
        if limit is not None:
            tasks = tasks[:limit]
        return tasks

    def _from_source(self) -> list[Task]:
        from datasets import load_dataset  # lazy import; pregen-only
        from numpy.random import default_rng

        ds = load_dataset("trivia_qa", "rc.web", split="validation")
        rng = default_rng(_SAMPLE_SEED_INT)
        indices = list(range(len(ds)))
        rng.shuffle(indices)
        chosen = sorted(indices[: self._sample_size])

        out: list[Task] = []
        for idx in chosen:
            row = ds[idx]
            answer = row["answer"]
            value = answer["value"] if isinstance(answer, dict) else str(answer)
            aliases = answer.get("aliases", []) if isinstance(answer, dict) else []
            out.append(
                Task(
                    task_id=f"trivia/{row['question_id']}",
                    task_type=TaskType.T3A_WEBSEARCH_CLOSED,
                    prompt=row["question"],
                    gold_answer=str(value),
                    difficulty=estimate_difficulty(row["question"]),
                    metadata={
                        "source": "trivia_qa/rc.web",
                        "aliases": list(aliases),
                    },
                )
            )
        return out
