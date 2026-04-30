"""HumanEval loader (T1 — coding, ~165 sampled rows).

Source: ``openai_humaneval`` on Hugging Face. The full dataset has 164
problems; we sample down to 165 (or fewer for thin-pregen runs) using a
deterministic shuffle so a small subset still spans the difficulty
distribution. Without shuffling, ``--limits humaneval=5`` always returned
HumanEval/0..4, the five easiest warm-up problems — useless for
calibration because every provider gets 100%.

**Loader format version 2** (since 2026-04-30):

* Added deterministic shuffle (seeded by ``_SAMPLE_SEED_INT``).
* Stamped ``metadata.loader_format_version = 2`` on every record.

Caches written by v1 are auto-detected by ``is_cache_stale`` and rebuilt
on the next ``load``.
"""

from __future__ import annotations

from pathlib import Path

from pilot402.core import Task, TaskType
from pilot402.pregen.tasks.base import (
    estimate_difficulty,
    is_cache_stale,
    read_cache,
    write_cache,
)

# Deterministic shuffle seed. Picked once and never changed; rotating it
# would silently change which subset of HumanEval lands in any thin-pregen
# subset. Different from HotpotQA / TriviaQA / OpenWeb seeds so subset
# correlations don't accidentally line up across task types.
_SAMPLE_SEED_INT = 0xD35F1A04


class HumanEvalLoader:
    """Loader for the HumanEval coding benchmark (164 problems)."""

    name = "humaneval"
    task_type = TaskType.T1_CODING
    LOADER_FORMAT_VERSION = 2

    def __init__(self, sample_size: int = 165) -> None:
        if sample_size <= 0:
            raise ValueError("sample_size must be positive")
        self._sample_size = sample_size

    def load(self, cache_dir: Path, limit: int | None = None) -> list[Task]:
        cache_path = cache_dir / f"{self.name}.jsonl"
        if cache_path.is_file() and not is_cache_stale(
            cache_path, self.LOADER_FORMAT_VERSION
        ):
            return read_cache(cache_path, limit=limit)
        tasks = self._from_source()
        write_cache(cache_path, tasks)
        if limit is not None:
            tasks = tasks[:limit]
        return tasks

    def _from_source(self) -> list[Task]:
        from datasets import load_dataset  # lazy import; pregen-only
        from numpy.random import default_rng

        ds = load_dataset("openai_humaneval", split="test")

        # Deterministic shuffle, then cap. Capping after shuffle gives
        # subset-by-shuffle-prefix semantics: load(limit=N) is always the
        # first N rows of the shuffled order.
        rng = default_rng(_SAMPLE_SEED_INT)
        indices = list(range(len(ds)))
        rng.shuffle(indices)
        chosen = indices[: min(self._sample_size, len(ds))]

        out: list[Task] = []
        for idx in chosen:
            row = ds[idx]
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
                        "loader_format_version": self.LOADER_FORMAT_VERSION,
                    },
                )
            )
        return out
