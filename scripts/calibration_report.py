"""Per-(provider, task_type) calibration report.

Reads all ``PregenRecord`` JSONL files under ``data/pregen/`` and produces:

* Mean quality, std, and sample count for each (provider, task_type) cell.
* Provider quality gap matrix relative to the P-mid baseline.
* P-flaky empirical failure rate (target ~40%).
* Per-provider total call count and cost (sum of ``cost_usdc``).

Used after the Tier 2 calibration probe to decide whether the adversarial
prompt strength is in the [0.3, 0.5] gap window and whether the
experiment can proceed to Tier 3 (full pregen).

Usage::

    python -m scripts.calibration_report
    python -m scripts.calibration_report --pregen-dir data/pregen
"""

from __future__ import annotations

import argparse
import statistics
import sys
from collections import defaultdict
from pathlib import Path

from pilot402.core import PregenRecord, ProviderId, TaskType


def _load_records(pregen_dir: Path) -> list[PregenRecord]:
    if not pregen_dir.is_dir():
        raise SystemExit(f"Pregen directory not found: {pregen_dir}")
    records: list[PregenRecord] = []
    for jsonl in sorted(pregen_dir.glob("*.jsonl")):
        # Skip judge cache; it is not a PregenRecord file.
        if jsonl.name == "judge_cache.jsonl":
            continue
        for raw in jsonl.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line:
                continue
            records.append(PregenRecord.model_validate_json(line))
    return records


def _print_quality_table(
    records: list[PregenRecord],
    providers: list[ProviderId],
    task_types: list[TaskType],
) -> dict[tuple[ProviderId, TaskType], float]:
    cells: dict[tuple[ProviderId, TaskType], list[float]] = defaultdict(list)
    for rec in records:
        cells[(rec.provider_id, rec.task_type)].append(rec.quality_score.q)

    print("\n=== Mean quality by (provider × task_type) ===\n")
    header = f"{'Provider':<12}" + "".join(f"{tt.value:>16}" for tt in task_types)
    print(header)
    print("-" * len(header))
    means: dict[tuple[ProviderId, TaskType], float] = {}
    for pid in providers:
        row = f"{pid.value:<12}"
        for tt in task_types:
            qs = cells.get((pid, tt), [])
            if not qs:
                row += f"{'-':>16}"
                continue
            mean = statistics.mean(qs)
            stdev = statistics.stdev(qs) if len(qs) > 1 else 0.0
            cell = f"{mean:.2f}±{stdev:.2f}(n={len(qs)})"
            row += f"{cell:>16}"
            means[(pid, tt)] = mean
        print(row)
    return means


def _print_gap_matrix(
    means: dict[tuple[ProviderId, TaskType], float],
    providers: list[ProviderId],
    task_types: list[TaskType],
) -> None:
    print("\n=== Quality gap to P-mid baseline (P-mid − P-x) ===\n")
    print("Target adversarial gap (P-mid − P-adv): [0.30, 0.50]\n")
    header = f"{'Provider':<12}" + "".join(f"{tt.value:>10}" for tt in task_types)
    print(header)
    print("-" * len(header))
    for pid in providers:
        row = f"{pid.value:<12}"
        for tt in task_types:
            mid = means.get((ProviderId.P_MID, tt))
            other = means.get((pid, tt))
            if mid is None or other is None:
                row += f"{'-':>10}"
            else:
                gap = mid - other
                row += f"{gap:>10.3f}"
        print(row)


def _print_failure_summary(
    records: list[PregenRecord],
    providers: list[ProviderId],
) -> None:
    print("\n=== Failure rates by provider ===\n")
    print("Target P-flaky rate: ~40% (2 in 5 versions force a billed timeout)\n")
    failures: dict[ProviderId, int] = defaultdict(int)
    totals: dict[ProviderId, int] = defaultdict(int)
    for rec in records:
        totals[rec.provider_id] += 1
        if rec.failure_flag:
            failures[rec.provider_id] += 1
    for pid in providers:
        if totals[pid] == 0:
            continue
        rate = failures[pid] / totals[pid]
        print(
            f"  {pid.value:<12} {failures[pid]:>3d} / {totals[pid]:<3d} = {rate:.2%}"
        )


def _print_cost_summary(
    records: list[PregenRecord],
    providers: list[ProviderId],
) -> None:
    print("\n=== Recorded charge by provider (sum of cost_usdc) ===\n")
    print("(This is the x402 charge price, not the underlying API bill.)\n")
    sums: dict[ProviderId, float] = defaultdict(float)
    counts: dict[ProviderId, int] = defaultdict(int)
    for rec in records:
        sums[rec.provider_id] += rec.cost_usdc
        counts[rec.provider_id] += 1
    grand_total = 0.0
    for pid in providers:
        if counts[pid] == 0:
            continue
        total = sums[pid]
        grand_total += total
        print(f"  {pid.value:<12} {counts[pid]:>3d} calls  =  ${total:.4f}")
    print(f"  {'GRAND TOTAL':<12}              =  ${grand_total:.4f}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pregen-dir",
        type=Path,
        default=Path("data/pregen"),
        help="directory containing per-provider JSONL files (default: data/pregen).",
    )
    args = parser.parse_args(argv)

    records = _load_records(args.pregen_dir)
    if not records:
        raise SystemExit(f"No PregenRecord rows found under {args.pregen_dir}")

    print(f"Loaded {len(records)} PregenRecords from {args.pregen_dir}")

    providers = list(ProviderId)
    task_types = list(TaskType)
    means = _print_quality_table(records, providers, task_types)
    _print_gap_matrix(means, providers, task_types)
    _print_failure_summary(records, providers)
    _print_cost_summary(records, providers)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
