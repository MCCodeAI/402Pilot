"""HotpotQA loader (T2 — multi-hop QA, ~220 sampled rows).

**Loader format version 2** (since 2026-04-30):

The original v1 of this loader produced a closed-book setting (question only,
no context). HotpotQA's intended use is reading comprehension over 10
provided paragraphs, so v2 bakes the context into ``Task.prompt`` and stores
``supporting_facts`` in ``Task.metadata`` for analysis.

Caches written by v1 are auto-detected by ``is_cache_stale`` (looks for
``metadata.loader_format_version >= 2``) and rebuilt on next ``load``. To
manually wipe a stale cache, run ``python -m scripts.prepare_tasks
--force --sources hotpotqa``.

Sampling is deterministic: ``numpy.random.default_rng(_SAMPLE_SEED_INT)``
produces the same 220-question subset on any machine.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pilot402.core import Task, TaskType
from pilot402.pregen.tasks.base import (
    estimate_difficulty,
    is_cache_stale,
    read_cache,
    write_cache,
)

_LEVEL_TO_DIFFICULTY = {"easy": 0.3, "medium": 0.6, "hard": 0.9}
# Deterministic shuffle seed. Picked once and never changed; rotating it
# would silently change the 220-question subset without bumping a schema.
_SAMPLE_SEED_INT = 0xA02C0F01


def _format_context(context: dict[str, Any]) -> str:
    """Render the HotpotQA ``context`` dict as a readable passages block.

    Input shape (from HuggingFace ``hotpot_qa``):
        ``context["title"]``    : list[str]    (10 paragraph titles)
        ``context["sentences"]``: list[list[str]] (10 lists of sentences)

    Output: ``[1] {title_1}\n{paragraph_1}\n\n[2] ...`` — 10 numbered passages.
    """

    titles = context.get("title", []) or []
    sentence_lists = context.get("sentences", []) or []
    parts: list[str] = []
    for idx, (title, sentences) in enumerate(
        zip(titles, sentence_lists, strict=False), start=1
    ):
        paragraph = "".join(sentences) if isinstance(sentences, list) else str(sentences)
        parts.append(f"[{idx}] {title}\n{paragraph.strip()}")
    return "\n\n".join(parts)


def _build_prompt(context: dict[str, Any], question: str) -> str:
    return (
        "Read the following passages and answer the question that follows.\n\n"
        f"{_format_context(context)}\n\n"
        f"Question: {question.strip()}"
    )


class HotpotQaLoader:
    """Loader for the HotpotQA multi-hop QA benchmark (reading comprehension)."""

    name = "hotpotqa"
    task_type = TaskType.T2_MULTIHOP_QA
    LOADER_FORMAT_VERSION = 2

    def __init__(self, sample_size: int = 220) -> None:
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

        ds = load_dataset("hotpot_qa", "distractor", split="validation")
        rng = default_rng(_SAMPLE_SEED_INT)
        # Deterministic subset selection independent of dataset row order.
        indices = list(range(len(ds)))
        rng.shuffle(indices)
        chosen = sorted(indices[: self._sample_size])

        out: list[Task] = []
        for idx in chosen:
            row = ds[idx]
            level = row.get("level")
            difficulty = _LEVEL_TO_DIFFICULTY.get(
                level if isinstance(level, str) else "",
                estimate_difficulty(row["question"]),
            )
            prompt = _build_prompt(row.get("context") or {}, row["question"])
            supporting = row.get("supporting_facts") or {}
            out.append(
                Task(
                    task_id=f"hotpot/{row['id']}",
                    task_type=TaskType.T2_MULTIHOP_QA,
                    prompt=prompt,
                    gold_answer=row["answer"],
                    difficulty=float(difficulty),
                    metadata={
                        "source": "hotpot_qa/distractor",
                        "level": level,
                        "type": row.get("type"),
                        "loader_format_version": self.LOADER_FORMAT_VERSION,
                        # Supporting facts: which titles + sentence ids are the
                        # gold reasoning chain. Logged for analysis; NOT shown
                        # to the model (would leak the answer).
                        "supporting_titles": list(supporting.get("title", [])),
                        "supporting_sent_ids": list(supporting.get("sent_id", [])),
                        "question_only": row["question"],
                    },
                )
            )
        return out
