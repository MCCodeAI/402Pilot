"""HotpotQA loader (T2 multi-hop QA)."""

from __future__ import annotations

from pathlib import Path

from pilot402.core import Task, TaskType
from pilot402.pregen.tasks.base import estimate_difficulty, read_cache, write_cache

_SAMPLE_SEED_INT = 0xB13D0E02


class HotpotQaLoader:
    name = "hotpotqa"
    task_type = TaskType.T2_MULTIHOP_QA

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
        return tasks[:limit] if limit is not None else tasks

    def _from_source(self) -> list[Task]:
        from datasets import load_dataset  # lazy import; pregen-only
        from numpy.random import default_rng

        ds = load_dataset("hotpot_qa", "distractor", split="validation")
        rng = default_rng(_SAMPLE_SEED_INT)
        indices = list(range(len(ds)))
        rng.shuffle(indices)
        chosen = sorted(indices[: self._sample_size])

        out: list[Task] = []
        for idx in chosen:
            row = ds[idx]
            question = str(row["question"])
            out.append(
                Task(
                    task_id=f"hotpot/{row['id']}",
                    task_type=self.task_type,
                    prompt=question,
                    gold_answer=str(row["answer"]),
                    difficulty=estimate_difficulty(question),
                    metadata={"source": "hotpot_qa/distractor"},
                )
            )
        return out


__all__ = ["HotpotQaLoader"]

