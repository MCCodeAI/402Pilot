"""Shared base for task loaders.

The cache format is one ``Task`` per JSONL line — same shape as
``data/pregen/`` records, so the same JSON tooling reads both. Each loader
honors the contract:

1. If ``cache_dir / "<name>.jsonl"`` exists, read it (no network).
2. Otherwise, download from the source dataset (lazy-imported inside the
   loader — keeps the tests environment-free) and write the cache.
3. Apply ``limit`` after loading so the cache is always complete.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from pilot402.core import Task, TaskType


@runtime_checkable
class TaskLoader(Protocol):
    """Loader for one task source."""

    @property
    def name(self) -> str:
        """Filesystem-safe identifier (e.g. ``"humaneval"``)."""
        ...

    @property
    def task_type(self) -> TaskType: ...

    def load(self, cache_dir: Path, limit: int | None = None) -> list[Task]: ...


def write_cache(path: Path, tasks: list[Task]) -> None:
    """Write ``tasks`` as JSONL. Creates parent directories as needed."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for task in tasks:
            fh.write(task.model_dump_json() + "\n")


def read_cache(path: Path, limit: int | None = None) -> list[Task]:
    """Read JSONL ``Task`` records; honor ``limit`` if provided.

    ``limit=0`` means "no records"; any non-positive limit short-circuits
    before opening the file. ``limit=None`` reads everything.
    """

    if limit is not None and limit <= 0:
        return []
    out: list[Task] = []
    with path.open("r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            out.append(Task.model_validate_json(line))
            if limit is not None and len(out) >= limit:
                break
    return out


def is_cache_stale(cache_path: Path, expected_version: int) -> bool:
    """Detect a cache file written by an older loader format.

    Each loader records ``metadata.loader_format_version`` in every Task it
    writes. Caches written before format-versioning was introduced (or by
    a deliberately older version) are missing this key and treated as
    version 1.

    Returns True if the cache should be rebuilt — either because the file
    is empty / unparseable, or because its first record carries a version
    older than ``expected_version``.

    A return of False does NOT imply the file is healthy past line 1; we
    sample the first non-blank line for cheapness. If a future format
    change is partial, write the new version into ALL records.
    """

    if not cache_path.is_file():
        return False  # absent is "no cache", not "stale cache"
    try:
        with cache_path.open("r", encoding="utf-8") as fh:
            first_line = ""
            for raw in fh:
                if raw.strip():
                    first_line = raw.strip()
                    break
        if not first_line:
            return True
        rec = Task.model_validate_json(first_line)
    except Exception:
        return True
    actual = int(rec.metadata.get("loader_format_version", 1))
    return actual < expected_version


def estimate_difficulty(prompt: str, *, scale_chars: int = 1000) -> float:
    """Heuristic difficulty in ``[0, 1]``.

    Longer prompts tend to be harder (more constraints, longer reasoning
    chains). Cap at 1.0 so the field stays in the unit interval. The bandit
    consumes this only as a context feature; the actual quality signal comes
    from the realized score, so a noisy heuristic is fine.
    """

    if scale_chars <= 0:
        raise ValueError("scale_chars must be positive")
    return min(len(prompt) / scale_chars, 1.0)
