"""Download task corpora into ``data/tasks/``. No LLM calls.

Run this once before any pregen so the (potentially slow) HuggingFace
download is decoupled from the (paid) LLM step.

Usage::

    python -m scripts.prepare_tasks
    python -m scripts.prepare_tasks --cache-dir custom/path
    python -m scripts.prepare_tasks --sources humaneval triviaqa  # subset

Per-source caps come from ``DEFAULT_LIMITS``; overrides via
``--limits humaneval=10 hotpotqa=0``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pilot402.pregen.tasks import (
    DEFAULT_LIMITS,
    HotpotQaLoader,
    HumanEvalLoader,
    OpenWebLoader,
    TaskLoader,
    TriviaQaLoader,
)

_LOADERS: dict[str, TaskLoader] = {
    "humaneval": HumanEvalLoader(),
    "hotpotqa": HotpotQaLoader(),
    "triviaqa": TriviaQaLoader(),
    "openweb": OpenWebLoader(),
}


def _parse_limits(pairs: list[str]) -> dict[str, int | None]:
    out: dict[str, int | None] = {}
    for raw in pairs:
        key, _, value = raw.partition("=")
        if not key or not value:
            raise SystemExit(f"--limits expects KEY=VALUE pairs, got {raw!r}")
        out[key.strip()] = int(value)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("data/tasks"),
        help="where per-source JSONL caches are written (default: data/tasks).",
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=tuple(_LOADERS.keys()),
        default=tuple(_LOADERS.keys()),
        help="which task sources to prepare (default: all four).",
    )
    parser.add_argument(
        "--limits",
        nargs="*",
        default=[],
        metavar="KEY=N",
        help="per-source caps; e.g. `--limits humaneval=10 hotpotqa=0`.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="delete each selected source's cache before loading, forcing "
        "a re-download from HuggingFace. Useful when a loader format has "
        "been bumped.",
    )
    args = parser.parse_args(argv)

    overrides = _parse_limits(args.limits)
    effective_limits = {**DEFAULT_LIMITS, **overrides}

    args.cache_dir.mkdir(parents=True, exist_ok=True)
    total = 0
    for name in args.sources:
        loader = _LOADERS[name]
        cap = effective_limits.get(name)
        if args.force:
            stale = args.cache_dir / f"{name}.jsonl"
            if stale.is_file():
                stale.unlink()
                print(f"[{name}] removed cache {stale}", flush=True)
        print(f"[{name}] loading (limit={cap}) ...", flush=True)
        tasks = loader.load(args.cache_dir, limit=cap)
        print(f"[{name}] {len(tasks)} tasks → {args.cache_dir / f'{name}.jsonl'}")
        total += len(tasks)
    print(f"DONE: {total} tasks written under {args.cache_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
