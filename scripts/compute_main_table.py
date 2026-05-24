"""Compute the main-results table metrics from per-cell JSONL logs.

For each (scenario, policy) cell, aggregates the per-round logs into:

    q_bar_T   = (1/T) * sum_t quality_t           (unserved rounds count as 0)
    budget %  = 100 * total_spent / B0
    ROI       = sum_t quality_t / sum_t cost_t    (= q_bar_T * T / total_spent)
    PA-gap/T  = (R_oracle - R_policy) / T         (lower is better)
                where R = sum_t payment_aware_reward, paired by seed

Default policy order matches the paper's main table (Table 3 of §6):
SW-TS is *not* in the default set — it appears only in Appendix D
because, without budget pressure, it bankrupts under all 30 seeds in
S1 and S2 and is reported as a drift-only family representative
rather than as a main-table comparator. Pass ``--include-appendix``
(or list policies explicitly with ``--policies ...``) to add SW-TS
when reproducing Appendix D numbers.

Outputs:
    - Markdown table to stdout (table-formatted ordering)
    - Raw per-cell rows as JSONL at results/main_table/per_cell.jsonl
    - Aggregated stats as JSON at results/main_table/agg.json

Usage::

    python -m scripts.compute_main_table                       # paper main table
    python -m scripts.compute_main_table --include-appendix    # + SW-TS row
    python -m scripts.compute_main_table --policies contextual_dsts contextual_bts
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

T = 10000
B0 = 50.0

# Policy order that mirrors the paper's main table (§6, Table 3).
# SW-TS is in APPENDIX_POLICIES, not here, because the paper relegates
# it to Appendix D (no budget pressure → S1/S2 bankrupt under all seeds).
MAIN_TABLE_POLICIES = [
    "random",
    "always_cheapest",
    "always_mid",
    "always_premium",
    "budget_rule",
    "pm_greedy",
    "lincbwk",
    "contextual_dsts",
    "contextual_bts",
    "padct",
    "oracle",
]

# Policies reported in appendices rather than the main table. Add with
# ``--include-appendix`` or by listing them in ``--policies``.
APPENDIX_POLICIES = ["sw_ts"]

# Back-compat alias for downstream callers that imported ``POLICY_ORDER``.
POLICY_ORDER = MAIN_TABLE_POLICIES

DISPLAY = {
    "random": "Random",
    "always_cheapest": "Always-P-cheap",
    "always_mid": "Always-P-mid",
    "always_premium": "Always-P-premium",
    "budget_rule": "BudgetRule",
    "pm_greedy": "PM-Greedy",
    "lincbwk": "LinCBwK-Adapt.",
    "contextual_dsts": "Contextual DS-TS",
    "contextual_bts": "Contextual BTS",
    "sw_ts": "SW-TS",
    "padct": "PA-DCT (ours)",
    "oracle": "True Oracle (UB)",
}


def _aggregate_seed(path: Path) -> dict:
    """Aggregate one seed log into per-seed totals."""
    quality_sum = 0.0
    cost_sum = 0.0
    pa_sum = 0.0
    n_rounds = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        quality_sum += d.get("quality", 0.0)
        cost_sum += d.get("charged_cost_usdc", 0.0)
        pa_sum += d.get("payment_aware_reward", 0.0)
        n_rounds += 1
    return {
        "quality_sum": quality_sum,
        "cost_sum": cost_sum,
        "pa_sum": pa_sum,
        "rounds": n_rounds,
    }


def _resolve_log(in_dir: Path, scenario: str, policy: str, seed: int) -> Path:
    """Resolve the per-cell log path for a (scenario, policy, seed).

    Historical note: the paper's S3 column uses
    ``results/scenario_sweep_s3promo/<policy>/seed_NN.jsonl`` (no
    scenario subdirectory; the directory itself is S3-specific) because
    that run was produced after a scenario-config update and is the
    canonical S3 data. S1 and S2 still live under the standard
    ``results/scenario_sweep/<scenario>/<policy>/`` layout.
    """
    if scenario == "S3":
        s3promo = Path("results/scenario_sweep_s3promo") / policy / f"seed_{seed:02d}.jsonl"
        if not s3promo.is_file():
            raise FileNotFoundError(
                f"Canonical S3 log missing: {s3promo}. "
                "Run `python -m scripts.run_s3_promo`; refusing to fall back "
                "to the legacy S3 directory."
            )
        return s3promo
    return in_dir / scenario / policy / f"seed_{seed:02d}.jsonl"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in-dir", type=Path,
                        default=Path("results/scenario_sweep"))
    parser.add_argument("--out-dir", type=Path,
                        default=Path("results/main_table"))
    parser.add_argument(
        "--policies",
        nargs="+",
        default=None,
        help=(
            "Policies to include. Default = paper's main table (no SW-TS); "
            "use --include-appendix to add SW-TS, or list policies explicitly."
        ),
    )
    parser.add_argument(
        "--include-appendix",
        action="store_true",
        help=(
            "Append APPENDIX_POLICIES (SW-TS) to the default main-table "
            "policy order. Ignored when --policies is given explicitly."
        ),
    )
    parser.add_argument("--scenarios", nargs="+", default=["S1", "S2", "S3"])
    parser.add_argument("--num-seeds", type=int, default=30)
    args = parser.parse_args(argv)

    # Resolve effective policy order.
    if args.policies is None:
        args.policies = list(MAIN_TABLE_POLICIES)
        if args.include_appendix:
            # Insert appendix policies just before PA-DCT so the printed
            # ordering still ends with PA-DCT and the oracle.
            insert_at = args.policies.index("padct")
            for p in APPENDIX_POLICIES:
                if p not in args.policies:
                    args.policies.insert(insert_at, p)
                    insert_at += 1

    args.out_dir.mkdir(parents=True, exist_ok=True)
    per_cell_rows: list[dict] = []

    # First pass: aggregate every seed log.
    by_cell: dict[tuple[str, str], list[dict]] = {}
    for scenario in args.scenarios:
        for policy in args.policies:
            for seed in range(args.num_seeds):
                log = _resolve_log(args.in_dir, scenario, policy, seed)
                if not log.is_file():
                    continue
                agg = _aggregate_seed(log)
                row = {
                    "scenario": scenario,
                    "policy": policy,
                    "seed": seed,
                    "source": str(log),
                    **agg,
                }
                per_cell_rows.append(row)
                by_cell.setdefault((scenario, policy), []).append(row)

    # Persist per-cell rows for traceability.
    with (args.out_dir / "per_cell.jsonl").open("w", encoding="utf-8") as fh:
        for row in per_cell_rows:
            fh.write(json.dumps(row) + "\n")

    # Compute aggregated stats per (scenario, policy).
    aggregated: dict[str, dict[str, dict[str, float]]] = {}
    for scenario in args.scenarios:
        aggregated[scenario] = {}
        # Oracle PA-reward sums, indexed by seed, for PA-gap computation.
        oracle_pa_by_seed: dict[int, float] = {}
        for r in by_cell.get((scenario, "oracle"), []):
            oracle_pa_by_seed[r["seed"]] = r["pa_sum"]

        for policy in args.policies:
            seeds = by_cell.get((scenario, policy), [])
            if not seeds:
                aggregated[scenario][policy] = {}
                continue

            q_bar_T = [s["quality_sum"] / T for s in seeds]
            budget_pct = [100.0 * s["cost_sum"] / B0 for s in seeds]
            roi = [
                (s["quality_sum"] / s["cost_sum"]) if s["cost_sum"] > 0 else 0.0
                for s in seeds
            ]
            # PA-gap/T paired by seed: oracle - policy, /T
            pa_gap_per_T_list = []
            for s in seeds:
                oracle_pa = oracle_pa_by_seed.get(s["seed"])
                if oracle_pa is None:
                    continue
                pa_gap_per_T_list.append((oracle_pa - s["pa_sum"]) / T)

            agg = {
                "q_bar_T_mean": statistics.mean(q_bar_T),
                "q_bar_T_std": statistics.stdev(q_bar_T) if len(q_bar_T) > 1 else 0.0,
                "budget_pct_mean": statistics.mean(budget_pct),
                "budget_pct_std": statistics.stdev(budget_pct) if len(budget_pct) > 1 else 0.0,
                "roi_mean": statistics.mean(roi),
                "roi_std": statistics.stdev(roi) if len(roi) > 1 else 0.0,
                "pa_gap_per_T_mean": (
                    statistics.mean(pa_gap_per_T_list) if pa_gap_per_T_list else float("nan")
                ),
                "pa_gap_per_T_std": (
                    statistics.stdev(pa_gap_per_T_list)
                    if len(pa_gap_per_T_list) > 1 else 0.0
                ),
                "n_seeds": len(seeds),
            }
            aggregated[scenario][policy] = agg

    with (args.out_dir / "agg.json").open("w", encoding="utf-8") as fh:
        json.dump(aggregated, fh, indent=2)

    # Pretty-print a compact main-results table.
    print("Main-results table")
    print("=" * 110)
    print(
        f"{'Policy':<24} | "
        f"{'S1 q_bar_T':>10} {'bud%':>5} {'ROI':>6} {'PA-gap/T':>9} | "
        f"{'S2 q_bar_T':>10} {'bud%':>5} {'ROI':>6} {'PA-gap/T':>9} | "
        f"{'S3 q_bar_T':>10} {'bud%':>5} {'ROI':>6} {'PA-gap/T':>9}"
    )
    print("-" * 110)
    for policy in args.policies:
        row_parts = [f"{DISPLAY.get(policy, policy):<24}"]
        for scenario in args.scenarios:
            agg = aggregated[scenario].get(policy, {})
            if not agg:
                row_parts.append(f"{'(n/a)':>40}")
                continue
            row_parts.append(
                f"{agg['q_bar_T_mean']:>10.3f} "
                f"{agg['budget_pct_mean']:>5.0f} "
                f"{agg['roi_mean']:>6.0f} "
                f"{agg['pa_gap_per_T_mean']:>9.3f}"
            )
        print(" | ".join(row_parts))
    print()

    print(f"Per-cell rows: {args.out_dir / 'per_cell.jsonl'}")
    print(f"Aggregated:    {args.out_dir / 'agg.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
