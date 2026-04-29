"""TriviaQA-web loader (T3a — closed-form web search, ~220 sampled rows).

Source: ``trivia_qa`` (``rc.web`` config), ``validation`` split. We use the
canonical answer ``value`` as the gold answer; alias strings are also
stashed in metadata so EM/F1 can be computed against the alias set if a
later evaluator wants to.
"""

from __future__ import annotations

from pathlib import Path

from pilot402.core import Task, TaskType
from pilot402.pregen.tasks.base import estimate_difficulty, read_cache, write_cache

_SAMPLE_SEED_INT = 0xB13D0E02  # see hotpotqa.py for rationale


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
            return read_cache(cache_path, limit=limit)
        tasks = self._from_source()
        write_cache(cache_path, tasks)
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
