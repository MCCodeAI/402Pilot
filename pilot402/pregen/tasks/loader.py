"""Unified entry point for loading all task sources.

Composition fixed by PLAN §3.5: ~165 + 220 + 220 + 220 = 825 tasks total.
Override per-source caps via ``limits`` for thin-pregen runs.
"""

from __future__ import annotations

from pathlib import Path

from pilot402.core import Task
from pilot402.pregen.tasks.base import TaskLoader
from pilot402.pregen.tasks.hotpotqa import HotpotQaLoader
from pilot402.pregen.tasks.humaneval import HumanEvalLoader
from pilot402.pregen.tasks.openweb import OpenWebLoader
from pilot402.pregen.tasks.triviaqa import TriviaQaLoader

DEFAULT_LIMITS: dict[str, int | None] = {
    "humaneval": 164,  # HumanEval has exactly 164 problems; this is the dataset cap.
    "hotpotqa": 220,
    "triviaqa": 220,
    "openweb": 220,
}
# Total: 824 tasks per full pregen.


def _all_loaders() -> list[TaskLoader]:
    return [
        HumanEvalLoader(),
        HotpotQaLoader(),
        TriviaQaLoader(),
        OpenWebLoader(),
    ]


def load_all_tasks(
    cache_dir: Path,
    *,
    limits: dict[str, int | None] | None = None,
    offsets: dict[str, int] | None = None,
) -> list[Task]:
    """Load every configured task source and concatenate.

    Args:
        cache_dir: directory holding (or to receive) per-source JSONL caches.
        limits: per-source caps. A missing key means "use the source's full
            cached length"; an explicit ``None`` means the same. Passing a
            dict with smaller numbers is the standard thin-pregen pattern.
        offsets: per-source offsets into the deterministic cached order.
            Pairing ``offsets={"humaneval": 15}`` with ``limits={"humaneval": 15}``
            yields tasks at positions 15..29 — disjoint from a baseline run
            at offset 0. Used for replication / out-of-sample validation.
            Keys missing from this dict default to offset 0.

    Returns:
        A flat list of ``Task`` objects, one source after another in the
        order ``[humaneval, hotpotqa, triviaqa, openweb]``.
    """

    effective = dict(DEFAULT_LIMITS)
    if limits is not None:
        effective.update(limits)

    effective_offsets: dict[str, int] = {}
    if offsets is not None:
        for k, v in offsets.items():
            if v < 0:
                raise ValueError(
                    f"offsets[{k!r}] must be non-negative, got {v}"
                )
            effective_offsets[k] = int(v)

    out: list[Task] = []
    for loader in _all_loaders():
        cap = effective.get(loader.name)
        # limit=0 means "skip entirely" — short-circuit before the loader's
        # cache-vs-download logic kicks in. Without this, a thin pregen run
        # that disables a source would still trigger the HuggingFace download
        # path on first run.
        if cap == 0:
            continue
        off = effective_offsets.get(loader.name, 0)
        # Read cap+off rows from the loader, then drop the first ``off``.
        # Each loader's cache is a deterministic permutation, so this gives
        # us a disjoint slice when paired with a previous run at offset 0.
        read_limit = (cap + off) if cap is not None else None
        chunk = loader.load(cache_dir, limit=read_limit)
        if off > 0:
            chunk = chunk[off:]
        out.extend(chunk)
    return out
