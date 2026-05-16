"""HumanEval loader (T1 coding)."""

from __future__ import annotations

from pathlib import Path

from pilot402.core import Task, TaskType
from pilot402.pregen.tasks.base import estimate_difficulty, read_cache, write_cache


class HumanEvalLoader:
    name = "humaneval"
    task_type = TaskType.T1_CODING

    def load(self, cache_dir: Path, limit: int | None = None) -> list[Task]:
        cache_path = cache_dir / f"{self.name}.jsonl"
        if cache_path.is_file():
            return read_cache(cache_path, limit=limit)
        tasks = self._from_source()
        write_cache(cache_path, tasks)
        return tasks[:limit] if limit is not None else tasks

    def _from_source(self) -> list[Task]:
        from datasets import load_dataset  # lazy import; pregen-only

        ds = load_dataset("openai_humaneval", split="test")
        out: list[Task] = []
        for row in ds:
            prompt = str(row["prompt"])
            out.append(
                Task(
                    task_id=f"HumanEval/{row['task_id'].split('/')[-1]}",
                    task_type=self.task_type,
                    prompt=prompt,
                    gold_answer=str(row.get("canonical_solution", "")),
                    difficulty=estimate_difficulty(prompt),
                    metadata={
                        "source": "openai_humaneval",
                        "entry_point": row["entry_point"],
                        "test": row["test"],
                    },
                )
            )
        return out


__all__ = ["HumanEvalLoader"]

