"""Per-baseline allocation trace at checkpoint rounds.

For each (scenario, policy) cell, reports the empirical arm-share over a
small set of round checkpoints, plus running mean quality up to that
checkpoint. Used by Appendix D to support the narrative claims about
how PM-Greedy, LinCBwK-style, and SW-TS allocate over time relative
to PA-DCT in the three scenarios.

Output:
    - Markdown summary table to stdout
    - Per-(scenario, policy, checkpoint) rows as JSONL at
      results/baseline_diagnostics/allocation_trace.jsonl

Usage::

    python -m scripts.compute_baseline_diagnostics
    python -m scripts.compute_baseline_diagnostics \\
        --policies lincbwk pm_greedy sw_ts padct \\
        --scenarios S1 S2 S3 \\
        --checkpoints 500 1000 3000 5500 6000 9999
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
OUT_DIR = RESULTS / "baseline_diagnostics"

DEFAULT_POLICIES = [
    "pm_greedy",
    "lincbwk",
    "sw_ts",
    "padct",
    "contextual_dsts",
    "contextual_bts",
]

DEFAULT_SCENARIOS = ["S1", "S2", "S3"]
DEFAULT_CHECKPOINTS = (500, 1000, 3000, 5500, 6000, 9999)


def _scenario_log_dir(scenario: str) -> Path:
    """S3 lives under `results/scenario_sweep_s3promo/`; S1/S2 under
    `results/scenario_sweep/<scenario>/`.

    Matches the dispatch used by compute_main_table / compute_significance.
    """
    if scenario == "S3":
        return RESULTS / "scenario_sweep_s3promo"
    return RESULTS / "scenario_sweep" / scenario


def _list_seed_logs(scenario: str, policy: str) -> list[Path]:
    base = _scenario_log_dir(scenario) / policy
    if not base.is_dir():
        return []
    return sorted(base.glob("seed_*.jsonl"))


def _checkpoint_summary(log_path: Path, checkpoints: tuple[int, ...]) -> dict:
    """Per-checkpoint cumulative arm shares + running mean quality.

    For each checkpoint c, returns a dict with:
        {arm: share at first c rounds, ...}
        plus "q_bar_c": running mean quality over the first c served rounds.
    """
    rows = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        rows.append(d)
    out: dict[int, dict] = {}
    arms: dict[str, int] = defaultdict(int)
    q_sum = 0.0
    served = 0
    sorted_cps = sorted(checkpoints)
    cp_idx = 0
    for r_idx, d in enumerate(rows):
        arm = d.get("chosen_arm")
        if arm is not None:
            arms[arm] += 1
        q_sum += d.get("quality", 0.0)
        served += 1
        while cp_idx < len(sorted_cps) and r_idx + 1 == sorted_cps[cp_idx]:
            cp = sorted_cps[cp_idx]
            total = sum(arms.values())
            out[cp] = {
                "shares": {a: arms[a] / total for a in arms} if total else {},
                "q_bar_c": q_sum / served if served else 0.0,
                "served_rounds": served,
            }
            cp_idx += 1
    # Cells that hit bankruptcy before a checkpoint get a stub for that cp.
    for cp in sorted_cps[cp_idx:]:
        total = sum(arms.values())
        out[cp] = {
            "shares": {a: arms[a] / total for a in arms} if total else {},
            "q_bar_c": q_sum / served if served else 0.0,
            "served_rounds": served,
            "bankrupt_before_checkpoint": True,
        }
    return out


def _aggregate_across_seeds(
    scenario: str,
    policy: str,
    checkpoints: tuple[int, ...],
) -> dict[int, dict]:
    """Mean over seeds of (arm shares, q_bar_c) at each checkpoint.

    Arm-share aggregation imputes a share of ``0.0`` for any arm a given
    seed never selected. Without this imputation, the mean would be
    taken only over the subset of seeds where the arm appears at least
    once, inflating the reported share of low-frequency arms (e.g.
    P-flaky in PA-DCT runs, which most seeds never pull at all).
    """
    logs = _list_seed_logs(scenario, policy)
    if not logs:
        return {}
    per_seed: list[dict[int, dict]] = []
    for lp in logs:
        per_seed.append(_checkpoint_summary(lp, checkpoints))

    # Universe of arms ever observed across this (scenario, policy),
    # used to impute zero shares for seeds that never pulled the arm.
    all_arms: set[str] = set()
    for s in per_seed:
        for cell in s.values():
            all_arms.update(cell.get("shares", {}).keys())

    out: dict[int, dict] = {}
    for cp in checkpoints:
        share_lists: dict[str, list[float]] = {a: [] for a in all_arms}
        q_list: list[float] = []
        n_bankrupt = 0
        for s in per_seed:
            cell = s.get(cp)
            if not cell:
                continue
            seed_shares = cell["shares"]
            for a in all_arms:
                share_lists[a].append(seed_shares.get(a, 0.0))
            q_list.append(cell["q_bar_c"])
            if cell.get("bankrupt_before_checkpoint"):
                n_bankrupt += 1
        out[cp] = {
            "mean_shares": {
                a: statistics.mean(vs) for a, vs in share_lists.items() if vs
            },
            "mean_q_bar_c": statistics.mean(q_list) if q_list else float("nan"),
            "n_seeds_reporting": len(q_list),
            "n_seeds_bankrupt_at_cp": n_bankrupt,
        }
    return out


def _render_markdown(
    rows: list[dict],
    scenarios: list[str],
    policies: list[str],
    checkpoints: tuple[int, ...],
) -> str:
    """Allocation trace table — one block per (scenario, checkpoint)."""
    out: list[str] = []
    out.append("# Baseline allocation diagnostics")
    out.append("")
    for sc in scenarios:
        out.append(f"## {sc}")
        out.append("")
        # Column headers: policy, q̄_c, share columns per arm (sorted by id).
        all_arms = sorted({
            a
            for r in rows
            if r["scenario"] == sc
            for a in r["mean_shares"]
        })
        for cp in checkpoints:
            out.append(f"### round = {cp}")
            out.append("")
            header = "| Policy | q̄_c | " + " | ".join(all_arms) + " |"
            sep = "|---|---|" + "|".join(["---"] * len(all_arms)) + "|"
            out.append(header)
            out.append(sep)
            for pol in policies:
                match = [
                    r for r in rows
                    if r["scenario"] == sc and r["policy"] == pol and r["checkpoint"] == cp
                ]
                if not match:
                    continue
                r = match[0]
                shares_cells = [
                    f"{r['mean_shares'].get(a, 0):.2f}" for a in all_arms
                ]
                out.append(
                    f"| {pol} | {r['mean_q_bar_c']:.3f} | "
                    + " | ".join(shares_cells)
                    + " |"
                )
            out.append("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policies", nargs="+", default=DEFAULT_POLICIES)
    parser.add_argument("--scenarios", nargs="+", default=DEFAULT_SCENARIOS)
    parser.add_argument(
        "--checkpoints", nargs="+", type=int, default=list(DEFAULT_CHECKPOINTS),
    )
    parser.add_argument(
        "--out-dir", type=Path, default=OUT_DIR,
    )
    args = parser.parse_args(argv)

    checkpoints = tuple(sorted(set(args.checkpoints)))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_jsonl = args.out_dir / "allocation_trace.jsonl"

    rows: list[dict] = []
    for sc in args.scenarios:
        for pol in args.policies:
            agg = _aggregate_across_seeds(sc, pol, checkpoints)
            if not agg:
                print(
                    f"[skip] no logs for {sc}/{pol}",
                    file=sys.stderr,
                )
                continue
            for cp, cell in agg.items():
                rows.append({
                    "scenario": sc,
                    "policy": pol,
                    "checkpoint": cp,
                    "mean_shares": cell["mean_shares"],
                    "mean_q_bar_c": cell["mean_q_bar_c"],
                    "n_seeds_reporting": cell["n_seeds_reporting"],
                    "n_seeds_bankrupt_at_cp": cell["n_seeds_bankrupt_at_cp"],
                })

    with out_jsonl.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")

    md = _render_markdown(rows, args.scenarios, args.policies, checkpoints)
    print(md)
    print(f"\nWrote {out_jsonl}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
