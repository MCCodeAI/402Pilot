"""HumanEval loader (T1 — coding, 164 problems).

Source: ``openai_humaneval`` on Hugging Face. Each row contains a function
signature + docstring (``prompt``), a ``canonical_solution`` we keep as the
gold answer, and a ``test`` block used by the pass@1 evaluator. Both
``entry_point`` and ``test`` are stashed in ``Task.metadata`` so the
evaluator can run the test harness without re-downloading.
"""

from __future__ import annotations

from pathlib import Path

from pilot402.core import Task, TaskType
from pilot402.pregen.tasks.base import estimate_difficulty, read_cache, write_cache


class HumanEvalLoader:
    """Loader for the HumanEval coding benchmark."""

    name = "humaneval"
    task_type = TaskType.T1_CODING

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

        ds = load_dataset("openai_humaneval", split="test")
        out: list[Task] = []
        for row in ds:
            out.append(
                Task(
                    task_id=row["task_id"],
                    task_type=TaskType.T1_CODING,
                    prompt=row["prompt"],
                    gold_answer=row["canonical_solution"],
                    difficulty=estimate_difficulty(row["prompt"]),
                    metadata={
                        "source": "openai/humaneval",
                        "entry_point": row["entry_point"],
                        "test": row["test"],
                    },
                )
            )
        return out
