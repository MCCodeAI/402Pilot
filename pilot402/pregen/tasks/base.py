"""Shared task-loader helpers."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Protocol

from pilot402.core import Task, TaskType


class TaskLoader(Protocol):
    name: str
    task_type: TaskType

    def load(self, cache_dir: Path, limit: int | None = None) -> list[Task]: ...


def estimate_difficulty(prompt: str) -> float:
    """Simple length-based proxy used only when source data lacks difficulty."""

    token_count = max(1, len(prompt.split()))
    return max(0.0, min(1.0, math.log1p(token_count) / math.log1p(220)))


def read_cache(path: Path, limit: int | None = None) -> list[Task]:
    tasks: list[Task] = []
    if not path.is_file():
        return tasks
    with path.open("r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            tasks.append(Task.model_validate_json(line))
            if limit is not None and len(tasks) >= limit:
                break
    return tasks


def write_cache(path: Path, tasks: list[Task]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for task in tasks:
            fh.write(task.model_dump_json() + "\n")


__all__ = ["TaskLoader", "estimate_difficulty", "read_cache", "write_cache"]

