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

import sys
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

from tqdm import tqdm

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

# Rough USD cost estimates per LLM call. These are NOT the x402 charge price
# (PregenRecord.cost_usdc) — they are the underlying API bill we expect to
# pay during pregen. Used by the progress bar's running spend estimate.
# Values reflect ~1k-token average call (input + output) at 2026 pricing.
_ESTIMATED_USD_PER_CALL: dict[ProviderId, float] = {
    ProviderId.P_CHEAP: 0.0008,  # qwen3.5-flash via DashScope
    ProviderId.P_MID: 0.0008,  # GPT-5.4-mini
    ProviderId.P_PREMIUM: 0.012,  # GPT-5.4 (~15x mini)
    ProviderId.P_ADV: 0.0008,
    ProviderId.P_FLAKY: 0.0008,  # but only ~60% actually call the LLM (v=0,1 timeout)
}
_ESTIMATED_USD_PER_JUDGE_CALL: float = 0.002  # Gemini 2.5 Pro per evaluation

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _CellWork:
    """Pre-baked inputs for one (provider, task, version) cell.

    Computed in the submission thread so that the worker thread only has
    to call into the backend + evaluator. RNG is materialized here so
    that determinism is preserved regardless of completion order.
    """

    provider_id: ProviderId
    task: Task
    version: int
    api_seed: int


def _do_cell_work(
    work: _CellWork,
    *,
    cfg: ExperimentConfig,
    backends: dict[ProviderId, LlmBackend],
    composite: CompositeEvaluator,
) -> tuple[_CellWork, PregenRecord]:
    """Worker function: drive one cell end-to-end.

    Runs in a thread pool worker. The LLM call (the slow part) and the
    quality evaluation both happen here; the calling thread only does
    JSON serialization + file write, which is fast and keeps writes
    single-threaded so the JSONL stays well-formed.
    """

    spec = cfg.provider(work.provider_id)
    provider = make_provider(work.provider_id, backends[work.provider_id], spec.base_price_usdc)
    # Re-seed a single-call RNG from the api_seed so the provider sees the
    # same draw it would in the sequential path.
    from numpy.random import default_rng

    rng = default_rng(work.api_seed)
    outcome = provider.generate(work.task, work.version, rng=rng)

    if outcome.failure_flag:
        quality = QualityScore(q=0.0, backend=backend_for(work.task.task_type))
    else:
        quality = composite.score(work.task, outcome.response)

    record = PregenRecord(
        task_id=work.task.task_id,
        task_type=work.task.task_type,
        provider_id=work.provider_id,
        version=work.version,
        response=outcome.response,
        cost_usdc=outcome.cost_usdc,
        latency_s=outcome.latency_s,
        failure_flag=outcome.failure_flag,
        failure_code=outcome.failure_code,
        quality_score=quality,
        generated_at=datetime.now(timezone.utc),
        temperature=outcome.temperature,
    )
    return work, record


def run_pregen(
    cfg: ExperimentConfig,
    *,
    backends: dict[ProviderId, LlmBackend],
    judge: JudgeBackend,
    task_cache_dir: Path | None = None,
    pregen_out_dir: Path | None = None,
    limits: dict[str, int | None] | None = None,
    offsets: dict[str, int] | None = None,
    provider_subset: tuple[ProviderId, ...] | None = None,
    version_count: int = 5,
    concurrency: int = 8,
    dry_run: bool = False,
    resume: bool = False,
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
        offsets: per-source offsets into the deterministic cached order.
            Pair with ``limits`` to run a replication on a disjoint slice
            (e.g. ``limits={"humaneval": 15}`` + ``offsets={"humaneval": 15}``
            → tasks 15..29). Missing keys default to offset 0.
        provider_subset: only run these providers. ``None`` means "all
            providers in cfg.providers".
        version_count: versions per (provider, task) pair. Defaults to 5
            per the design spec.
        dry_run: if True, build the work plan and return its size without
            calling any LLMs.
        resume: if True, scan ``pregen_out_dir`` for existing records and
            skip any (provider_id, task_id, version) already on disk. Lets
            an interrupted run pick up where it left off without paying
            for completed cells again. The rare case of a cell whose LLM
            call succeeded but whose record didn't make it to disk before
            interruption WILL be re-charged once on resume — worst case
            ``concurrency`` cells, typically <$0.20 per resume.

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

    tasks = load_all_tasks(
        task_cache_dir, limits=effective_limits, offsets=offsets
    )

    selected_providers = tuple(
        provider_subset
        if provider_subset is not None
        else (p.provider_id for p in cfg.providers)
    )
    for pid in selected_providers:
        if pid not in backends:
            raise KeyError(f"No backend supplied for provider {pid.value!r}")

    plan_cells = list(_iter_cells(selected_providers, tasks, version_count))
    plan_total = len(plan_cells)

    if resume:
        completed = _scan_completed_cells(pregen_out_dir)
        plan_cells = [
            (pid, task, version)
            for (pid, task, version) in plan_cells
            if (pid, task.task_id, version) not in completed
        ]
        skipped = plan_total - len(plan_cells)
        if skipped > 0:
            print(
                f"resume: skipping {skipped}/{plan_total} cells already on "
                f"disk in {pregen_out_dir}",
                file=sys.stderr,
            )

    cells = len(plan_cells)
    if dry_run:
        return cells

    if concurrency < 1:
        raise ValueError("concurrency must be >= 1")

    seeds = SeedSource(cfg.seed)
    composite = CompositeEvaluator(judge=judge)
    pregen_out_dir.mkdir(parents=True, exist_ok=True)

    # Materialize work items with deterministic api_seed up-front so the
    # workers don't share the SeedSource (which is single-threaded by
    # design) and so write order = submission order regardless of which
    # cell completes first.
    work_items: list[_CellWork] = []
    for provider_id, task, version in plan_cells:
        sub_rng = seeds.derive(
            f"pregen/{provider_id.value}/{task.task_id}/v{version}"
        ).rng
        api_seed = int(sub_rng.integers(0, 2**31 - 1))
        work_items.append(
            _CellWork(
                provider_id=provider_id,
                task=task,
                version=version,
                api_seed=api_seed,
            )
        )

    written = 0
    failed = 0
    estimated_usd = 0.0
    open_files: dict[tuple[ProviderId, TaskType], TextIO] = {}

    # When stderr is a real terminal, tqdm uses ``\r`` for in-place updates.
    # When stderr is piped (e.g. through ``tee``), ``\r`` is ignored and each
    # update would create a new line — throttle to one update per 2 seconds
    # in that case so the log doesn't get spammed with hundreds of bars.
    is_tty = sys.stderr.isatty()
    progress = tqdm(
        total=cells,
        desc=f"pregen[c={concurrency}]",
        unit="call",
        file=sys.stderr,
        dynamic_ncols=True,
        mininterval=0.5 if is_tty else 2.0,
        miniters=1 if is_tty else 5,
    )
    try:
        # Submit all work, then iterate futures in submission order so that
        # writes happen in plan order regardless of completion order. Slow
        # cells (GPT-5.4) just delay the iteration at that point; meanwhile
        # other workers keep generating. Net effect: I/O serialized,
        # network parallelized.
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = [
                pool.submit(
                    _do_cell_work,
                    item,
                    cfg=cfg,
                    backends=backends,
                    composite=composite,
                )
                for item in work_items
            ]
            for fut in futures:
                work, record = fut.result()

                # Running cost estimate. P-flaky versions 0 and 1 force billed
                # timeouts without an actual LLM call (40% failure rate).
                if not (
                    work.provider_id is ProviderId.P_FLAKY
                    and record.failure_flag
                    and record.failure_code.value == "timeout"
                ):
                    estimated_usd += _ESTIMATED_USD_PER_CALL.get(
                        work.provider_id, 0.001
                    )
                if (
                    not record.failure_flag
                    and work.task.task_type is TaskType.T3B_WEBSEARCH_OPEN
                ):
                    estimated_usd += _ESTIMATED_USD_PER_JUDGE_CALL
                if record.failure_flag:
                    failed += 1

                fh = _open_for(open_files, pregen_out_dir, work.provider_id, work.task.task_type)
                fh.write(record.model_dump_json() + "\n")
                written += 1
                progress.set_postfix(
                    {
                        "fail": failed,
                        "est_$": f"{estimated_usd:.4f}",
                        "last": (
                            f"{work.provider_id.value}/"
                            f"{work.task.task_type.value}/v{work.version}"
                        ),
                    },
                    refresh=False,
                )
                progress.update(1)
    finally:
        progress.close()
        for fh in open_files.values():
            fh.close()
    return written


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _scan_completed_cells(
    pregen_out_dir: Path,
) -> set[tuple[ProviderId, str, int]]:
    """Return the set of (provider_id, task_id, version) cells that already
    have a record on disk. Used by ``resume=True`` to avoid re-charging for
    cells the previous (interrupted) run completed.

    Tolerates a partial / corrupted last line in any JSONL file — that line
    is skipped and the corresponding cell will be re-run. This gracefully
    handles the common case where the previous run was killed mid-write.
    """

    completed: set[tuple[ProviderId, str, int]] = set()
    if not pregen_out_dir.is_dir():
        return completed
    for jsonl in pregen_out_dir.glob("*.jsonl"):
        if jsonl.name == "judge_cache.jsonl":
            continue
        with jsonl.open("r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line:
                    continue
                try:
                    rec = PregenRecord.model_validate_json(line)
                except Exception:
                    # Truncated final line from an interrupted write, or a
                    # schema_version mismatch. Skip — the cell will rerun.
                    continue
                completed.add((rec.provider_id, rec.task_id, rec.version))
    return completed


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
