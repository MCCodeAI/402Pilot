"""Read-only access to the pregen dataset on disk.

Implements the ``PregenStore`` Protocol from ``pilot402.core.interfaces``.
The constructor scans ``data/pregen/*.jsonl`` once and builds an in-memory
index keyed by ``(task_id, provider_id) -> {version: PregenRecord}``.

A ~20K-row dataset fits in well under 200 MB of process memory; if pregen
ever grows by an order of magnitude, swap the in-memory dict for a SQLite
table without changing the public API.
"""

from __future__ import annotations

from pathlib import Path

from pilot402.core import PregenRecord, ProviderId


class JsonlPregenStore:
    """In-memory index over per-(provider × task_type) JSONL files."""

    def __init__(self, pregen_dir: Path) -> None:
        self._index: dict[tuple[str, ProviderId], dict[int, PregenRecord]] = {}
        if not pregen_dir.is_dir():
            raise FileNotFoundError(
                f"Pregen directory does not exist: {pregen_dir}. "
                f"Run `python -m scripts.run_pregen ...` first."
            )
        for path in sorted(pregen_dir.glob("*.jsonl")):
            # judge_cache.jsonl lives in the same directory but holds judge
            # scoring entries (not PregenRecord rows); skip it.
            if path.name == "judge_cache.jsonl":
                continue
            self._load_file(path)

    def _load_file(self, path: Path) -> None:
        with path.open("r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line:
                    continue
                rec = PregenRecord.model_validate_json(line)
                key = (rec.task_id, rec.provider_id)
                bucket = self._index.setdefault(key, {})
                if rec.version in bucket:
                    raise ValueError(
                        f"Duplicate pregen record for {key} version {rec.version} "
                        f"in {path}; bump schema_version or rerun pregen."
                    )
                bucket[rec.version] = rec

    def get(
        self,
        task_id: str,
        provider_id: ProviderId,
        version: int,
    ) -> PregenRecord:
        try:
            return self._index[(task_id, provider_id)][version]
        except KeyError as exc:
            raise KeyError(
                f"No pregen record for task_id={task_id!r}, "
                f"provider_id={provider_id.value!r}, version={version}"
            ) from exc

    def versions(
        self,
        task_id: str,
        provider_id: ProviderId,
    ) -> tuple[int, ...]:
        bucket = self._index.get((task_id, provider_id), {})
        return tuple(sorted(bucket.keys()))

    def __len__(self) -> int:
        return sum(len(versions) for versions in self._index.values())
