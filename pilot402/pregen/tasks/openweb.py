"""Open-ended web-search prompt loader (T3b)."""

from __future__ import annotations

from pathlib import Path

from pilot402.core import Task, TaskType
from pilot402.pregen.tasks.base import estimate_difficulty, read_cache, write_cache


class OpenWebLoader:
    name = "openweb"
    task_type = TaskType.T3B_WEBSEARCH_OPEN

    def load(self, cache_dir: Path, limit: int | None = None) -> list[Task]:
        cache_path = cache_dir / f"{self.name}.jsonl"
        if cache_path.is_file():
            return read_cache(cache_path, limit=limit)
        tasks = self._fallback_tasks()
        write_cache(cache_path, tasks)
        return tasks[:limit] if limit is not None else tasks

    def _fallback_tasks(self) -> list[Task]:
        prompts = [
            "Explain the basic rules of field hockey.",
            "Summarize how a solar eclipse occurs and why it is rare.",
            "Describe the main trade-offs of using electric vehicles.",
        ]
        return [
            Task(
                task_id=f"openweb/fallback_{idx:03d}",
                task_type=self.task_type,
                prompt=prompt,
                gold_answer="",
                difficulty=estimate_difficulty(prompt),
                metadata={"source": "fallback_openweb"},
            )
            for idx, prompt in enumerate(prompts)
        ]


__all__ = ["OpenWebLoader"]

