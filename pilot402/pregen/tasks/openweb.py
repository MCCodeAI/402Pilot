"""OpenAssistant-derived loader (T3b — open-ended web search, ~220 rows).

Source: ``OpenAssistant/oasst1`` ``train`` split. We filter for English
prompter messages whose text starts with one of a handful of question
stems likely to benefit from web context (``what is``, ``how does``,
``why``, ``compare``, ``explain``, ``what are``). T3b deliberately has no
gold answer; quality is scored by LLM-as-judge during pregen.
"""

from __future__ import annotations

from pathlib import Path

from pilot402.core import Task, TaskType
from pilot402.pregen.tasks.base import estimate_difficulty, read_cache, write_cache

_SAMPLE_SEED_INT = 0xC24E0F03

# Lower-cased prefixes used to filter for explanation / comparison /
# fact-grounded queries. Anything else is dropped.
_QUESTION_STEMS: tuple[str, ...] = (
    "what is",
    "what are",
    "how does",
    "how do",
    "why ",
    "why is",
    "why are",
    "compare ",
    "explain ",
    "describe ",
    "what's ",
    "tell me about",
)


class OpenWebLoader:
    """Loader for the open-ended T3b web-search prompts."""

    name = "openweb"
    task_type = TaskType.T3B_WEBSEARCH_OPEN

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

        ds = load_dataset("OpenAssistant/oasst1", split="train")

        eligible: list[dict[str, object]] = []
        for row in ds:
            if row.get("role") != "prompter":
                continue
            if row.get("lang") != "en":
                continue
            text = row.get("text") or ""
            if not isinstance(text, str):
                continue
            stripped = text.strip().lower()
            if any(stripped.startswith(stem) for stem in _QUESTION_STEMS):
                eligible.append(row)

        rng = default_rng(_SAMPLE_SEED_INT)
        indices = list(range(len(eligible)))
        rng.shuffle(indices)
        chosen = sorted(indices[: self._sample_size])

        out: list[Task] = []
        for idx in chosen:
            row = eligible[idx]
            text = str(row["text"]).strip()
            message_id = row.get("message_id") or f"oasst_{idx}"
            out.append(
                Task(
                    task_id=f"openweb/{message_id}",
                    task_type=TaskType.T3B_WEBSEARCH_OPEN,
                    prompt=text,
                    gold_answer=None,
                    difficulty=estimate_difficulty(text),
                    metadata={
                        "source": "OpenAssistant/oasst1",
                        "message_id": message_id,
                    },
                )
            )
        return out
