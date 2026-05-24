"""Aggregate metrics for PM-Greedy τ-sensitivity and LinCBwK β-robustness sweeps.

Reads per-cell logs from non-canonical sweep directories and reports the
key metrics (q_bar_T, budget%, ROI, PA-gap/T mean ± std) for the paper's
Appendix-D sensitivity tables.

Usage::

    python -m scripts.compute_sweep_summaries
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
T = 10000
B0 = 50.0


def _aggregate_seed(path: Path) -> dict:
    quality_sum = 0.0
    cost_sum = 0.0
    pa_sum = 0.0
    n = 0
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
        n += 1
    return {
        "quality_sum": quality_sum,
        "cost_sum": cost_sum,
        "pa_sum": pa_sum,
        "rounds": n,
    }


def _oracle_pa(scenario: str) -> list[float]:
    """Read the True Oracle cum_pa per seed for the given scenario.

    Used to compute PA-gap/T = (R_oracle - R_policy) / T paired by seed.
    """
    if scenario == "S3":
        base = ROOT / "results" / "scenario_sweep_s3promo" / "oracle"
    else:
        base = ROOT / "results" / "scenario_sweep" / scenario / "oracle"
    out = []
    if not base.is_dir():
        return out
    for p in sorted(base.glob("seed_*.jsonl")):
        out.append(_aggregate_seed(p)["pa_sum"])
    return out


def _summarize_cell(log_dir: Path, scenario: str) -> dict:
    logs = sorted(log_dir.glob("seed_*.jsonl"))
    if not logs:
        return {}
    qbars = []
    bud_pcts = []
    rois = []
    pa_sums = []
    for p in logs:
        s = _aggregate_seed(p)
        qbars.append(s["quality_sum"] / T)
        bud_pcts.append(100.0 * s["cost_sum"] / B0)
        rois.append(s["quality_sum"] / s["cost_sum"] if s["cost_sum"] > 0 else 0.0)
        pa_sums.append(s["pa_sum"])
    oracle_pa = _oracle_pa(scenario)
    pa_gap = []
    if oracle_pa:
        for o, p in zip(oracle_pa, pa_sums):
            pa_gap.append((o - p) / T)
    return {
        "n": len(logs),
        "q_bar_T_mean": statistics.mean(qbars),
        "q_bar_T_std": statistics.stdev(qbars) if len(qbars) > 1 else 0.0,
        "budget_pct_mean": statistics.mean(bud_pcts),
        "roi_mean": statistics.mean(rois),
        "pa_gap_mean": statistics.mean(pa_gap) if pa_gap else float("nan"),
        "pa_gap_std": statistics.stdev(pa_gap) if len(pa_gap) > 1 else 0.0,
    }


def main() -> int:
    # PM-Greedy τ sweep
    print("=" * 80)
    print("PM-Greedy τ sensitivity")
    print("=" * 80)
    print(f"{'τ':<5}{'scenario':<10}{'q̄_T':>10}{'bud%':>10}{'ROI':>10}{'PA-gap/T':>14}")
    print("-" * 60)
    for tau_label, tau_dir in [
        ("0.6", "pm_greedy_tau_06"),
        ("0.7", "scenario_sweep"),  # main canonical
        ("0.8", "pm_greedy_tau_08"),
    ]:
        for scenario in ("S1", "S2", "S3"):
            if tau_label == "0.7":
                if scenario == "S3":
                    base = ROOT / "results" / "scenario_sweep_s3promo" / "pm_greedy"
                else:
                    base = ROOT / "results" / "scenario_sweep" / scenario / "pm_greedy"
            else:
                if scenario == "S3":
                    base = ROOT / "results" / tau_dir / "S3" / "pm_greedy"
                else:
                    base = ROOT / "results" / tau_dir / scenario / "pm_greedy"
            cell = _summarize_cell(base, scenario)
            if not cell:
                print(f"{tau_label:<5}{scenario:<10}  (no logs)")
                continue
            print(
                f"{tau_label:<5}{scenario:<10}"
                f"{cell['q_bar_T_mean']:>10.3f}"
                f"{cell['budget_pct_mean']:>10.1f}"
                f"{cell['roi_mean']:>10.0f}"
                f"  {cell['pa_gap_mean']:>6.3f}±{cell['pa_gap_std']:.3f}"
            )
        print()

    # LinCBwK β sweep
    print("=" * 80)
    print("LinCBwK β robustness")
    print("=" * 80)
    print(f"{'β':<5}{'scenario':<10}{'q̄_T':>10}{'bud%':>10}{'ROI':>10}{'PA-gap/T':>14}{'n':>5}")
    print("-" * 65)
    for beta_label, beta_dir in [
        ("0.5", "lincbwk_beta_05"),
        ("1.0", "scenario_sweep"),  # canonical
        ("2.0", "lincbwk_beta_20"),
    ]:
        for scenario in ("S1", "S2", "S3"):
            if beta_label == "1.0":
                if scenario == "S3":
                    base = ROOT / "results" / "scenario_sweep_s3promo" / "lincbwk"
                else:
                    base = ROOT / "results" / "scenario_sweep" / scenario / "lincbwk"
            else:
                if scenario == "S3":
                    base = ROOT / "results" / beta_dir / "S3" / "lincbwk"
                else:
                    base = ROOT / "results" / beta_dir / scenario / "lincbwk"
            cell = _summarize_cell(base, scenario)
            if not cell:
                print(f"{beta_label:<5}{scenario:<10}  (no logs)")
                continue
            print(
                f"{beta_label:<5}{scenario:<10}"
                f"{cell['q_bar_T_mean']:>10.3f}"
                f"{cell['budget_pct_mean']:>10.1f}"
                f"{cell['roi_mean']:>10.0f}"
                f"  {cell['pa_gap_mean']:>6.3f}±{cell['pa_gap_std']:.3f}"
                f"{cell['n']:>5}"
            )
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
