"""Pregen orchestrator.

Drives the full ``provider × task × version`` loop:

1. Load tasks via ``load_all_tasks`` (cache-first; downloads from
   HuggingFace on first run if no cache exists).
2. For each (provider, task, version) cell:
   - Derive a deterministic per-cell RNG from the master seed.
   - Call ``provider.generate(task, version, rng=...)``.
   - On success, score the response via ``CompositeEvaluator.score``.
   - On failure (timeout / payment_failure / etc.), record q=0 with the
     task's natural backend — never invoke the scorer on a failed call.
3. Append a ``PregenRecord`` to ``data/pregen/<provider>__<task_type>.jsonl``.

The output JSONL files are exactly what ``JsonlPregenStore`` reads at
experiment time. The orchestrator is sync today; concurrency comes from
running multiple ``run_pregen`` calls in parallel (one per provider) at
the CLI level, which is simpler than driving asyncio through the call
chain and respects per-provider rate limits naturally.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

from pilot402.core import (
    ExperimentConfig,
    PregenRecord,
    ProviderId,
    QualityScore,
    SeedSource,
    Task,
    TaskType,
)
from pilot402.eval.composite import CompositeEvaluator, backend_for
from pilot402.eval.judge_backend import JudgeBackend
from pilot402.pregen.providers import LlmBackend, make_provider
from pilot402.pregen.tasks import load_all_tasks
from pilot402.pregen.tasks.loader import DEFAULT_LIMITS

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_pregen(
    cfg: ExperimentConfig,
    *,
    backends: dict[ProviderId, LlmBackend],
    judge: JudgeBackend,
    task_cache_dir: Path | None = None,
    pregen_out_dir: Path | None = None,
    limits: dict[str, int | None] | None = None,
    provider_subset: tuple[ProviderId, ...] | None = None,
    version_count: int = 5,
    dry_run: bool = False,
) -> int:
    """Run pregen and return the number of (provider, task, version) cells emitted.

    Args:
        cfg: frozen experiment config; provides seed and per-provider prices.
        backends: per-provider ``LlmBackend`` (real or mock). Must have an
            entry for every provider in ``provider_subset`` (or all
            providers in ``cfg`` if no subset is given).
        judge: judge backend used to score T3b open-ended responses. Wrap
            an ``AnthropicJudgeClient`` in a ``CachedJudgeBackend`` for
            real runs; ``MockJudgeClient`` works for tests.
        task_cache_dir: where ``data/tasks/`` lives. Defaults to
            ``cfg.paths.tasks_dir``.
        pregen_out_dir: where to write ``data/pregen/`` JSONL files.
            Defaults to ``cfg.paths.pregen_dir``.
        limits: per-source caps. Missing keys fall back to
            ``DEFAULT_LIMITS``; pass ``{"hotpotqa": 0}`` etc. for thin
            pregen runs that skip a source entirely.
        provider_subset: only run these providers. ``None`` means "all
            providers in cfg.providers".
        version_count: versions per (provider, task) pair. Defaults to 5
            per the design spec.
        dry_run: if True, build the work plan and return its size without
            calling any LLMs.

    Returns:
        Number of cells emitted (or planned, for ``dry_run``).
    """

    if version_count < 1:
        raise ValueError("version_count must be >= 1")

    task_cache_dir = task_cache_dir or cfg.paths.tasks_dir
    pregen_out_dir = pregen_out_dir or cfg.paths.pregen_dir

    effective_limits = dict(DEFAULT_LIMITS)
    if limits is not None:
        effective_limits.update(limits)

    tasks = load_all_tasks(task_cache_dir, limits=effective_limits)

    selected_providers = tuple(
        provider_subset
        if provider_subset is not None
        else (p.provider_id for p in cfg.providers)
    )
    for pid in selected_providers:
        if pid not in backends:
            raise KeyError(f"No backend supplied for provider {pid.value!r}")

    cells = sum(1 for _ in _iter_cells(selected_providers, tasks, version_count))
    if dry_run:
        return cells

    seeds = SeedSource(cfg.seed)
    composite = CompositeEvaluator(judge=judge)
    pregen_out_dir.mkdir(parents=True, exist_ok=True)

    written = 0
    open_files: dict[tuple[ProviderId, TaskType], TextIO] = {}
    try:
        for provider_id, task, version in _iter_cells(selected_providers, tasks, version_count):
            spec = cfg.provider(provider_id)
            provider = make_provider(provider_id, backends[provider_id], spec.base_price_usdc)
            rng = seeds.derive(
                f"pregen/{provider_id.value}/{task.task_id}/v{version}"
            ).rng
            outcome = provider.generate(task, version, rng=rng)

            if outcome.failure_flag:
                quality = QualityScore(q=0.0, backend=backend_for(task.task_type))
            else:
                quality = composite.score(task, outcome.response)

            record = PregenRecord(
                task_id=task.task_id,
                task_type=task.task_type,
                provider_id=provider_id,
                version=version,
                response=outcome.response,
                cost_usdc=outcome.cost_usdc,
                latency_s=outcome.latency_s,
                failure_flag=outcome.failure_flag,
                failure_code=outcome.failure_code,
                quality_score=quality,
                generated_at=datetime.now(timezone.utc),
            )
            fh = _open_for(open_files, pregen_out_dir, provider_id, task.task_type)
            fh.write(record.model_dump_json() + "\n")
            written += 1
    finally:
        for fh in open_files.values():
            fh.close()
    return written


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _iter_cells(
    providers: tuple[ProviderId, ...],
    tasks: list[Task],
    version_count: int,
) -> Iterable[tuple[ProviderId, Task, int]]:
    for provider_id in providers:
        for task in tasks:
            for version in range(version_count):
                yield provider_id, task, version


def _open_for(
    open_files: dict[tuple[ProviderId, TaskType], TextIO],
    pregen_out_dir: Path,
    provider_id: ProviderId,
    task_type: TaskType,
) -> TextIO:
    key = (provider_id, task_type)
    fh = open_files.get(key)
    if fh is None:
        path = pregen_out_dir / f"{provider_id.value}__{task_type.value}.jsonl"
        fh = path.open("a", encoding="utf-8")
        open_files[key] = fh
    return fh


__all__ = ["run_pregen"]
