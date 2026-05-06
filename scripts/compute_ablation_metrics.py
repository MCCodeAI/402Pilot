"""Compute the 4 official metrics across all ablation cells.

Metrics (from experiment_design.md):
  1. task_success_rate — fraction of rounds where quality exceeds per-type
     threshold. We approximate as mean_quality (continuous proxy) since we
     haven't formally defined per-type thresholds yet.
  2. ROI = Σ q / Σ $ — raw quality per dollar (policy-agnostic, no λ shaping).
  3. Cumulative regret = Oracle cum_PA − policy cum_PA — gap to Oracle.
  4. Adaptation time = rounds for ROI to recover to within 5% of pre-event
     level after a shock (S2/S3 only; NA for S1).

Loads per-cell JSONL logs from:
  - results/scenario_sweep/{S1,S2}/<policy>/seed_NN.jsonl  (full method + baselines)
  - results/scenario_sweep_s3promo_v2/<policy>/seed_NN.jsonl  (full method + baselines for S3)
  - results/ablation_matrix/<ablation>/{S1,S2,S3}/padct/seed_NN.jsonl  (4 ablations)

Output: a wide-format table to stdout, plus markdown table written to
        logs/ablation_4metrics_table.md
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from collections import defaultdict


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ABLATION_LABELS = {
    "full": "Full PA-DCT",
    "no_p": "−P (no payment-aware)",
    "no_d": "−D (no discount, γ=1)",
    "no_c": "−C (no contextual)",
    "no_ts": "−TS (greedy)",
}

SCENARIOS = ["S1", "S2", "S3"]
SCENARIO_LABELS = {
    "S1": "S1 (stationary)",
    "S2": "S2 (outage 3000-5500)",
    "S3": "S3 (promo at round 1000)",
}

# Shock event rounds for adaptation_time (S2/S3 only)
SHOCK_ROUND = {"S2": 3000, "S3": 1000}
# Pre-event window for baseline ROI (rounds before shock)
PRE_EVENT_WINDOW = {"S2": (1000, 3000), "S3": (0, 1000)}
# Recovery threshold: 5% of pre-event ROI
RECOVERY_THRESHOLD_PCT = 0.05


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def get_log_dir(ablation: str, scenario: str) -> Path:
    """Return directory containing per-seed JSONL logs for this (ablation, scenario)."""
    if ablation == "full":
        # Full PA-DCT: from main sweep
        if scenario in ("S1", "S2"):
            return Path(f"results/scenario_sweep/{scenario}/padct")
        if scenario == "S3":
            return Path("results/scenario_sweep_s3promo_v2/padct")
        raise ValueError(scenario)
    else:
        return Path(f"results/ablation_matrix/{ablation}/{scenario}/padct")


def get_oracle_dir(scenario: str) -> Path:
    if scenario in ("S1", "S2"):
        return Path(f"results/scenario_sweep/{scenario}/oracle")
    if scenario == "S3":
        return Path("results/scenario_sweep_s3promo_v2/oracle")
    raise ValueError(scenario)


# ---------------------------------------------------------------------------
# Log reading
# ---------------------------------------------------------------------------

def read_log(log_path: Path) -> list[dict]:
    """Read one JSONL log file, returning list of round records."""
    records = []
    if not log_path.is_file():
        return records
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            # tolerate truncated tail
            break
    return records


def load_all_seeds(log_dir: Path) -> list[list[dict]]:
    """Return list-of-records, one entry per seed file."""
    all_seeds = []
    for f in sorted(log_dir.glob("seed_*.jsonl")):
        recs = read_log(f)
        if recs:
            all_seeds.append(recs)
    return all_seeds


# ---------------------------------------------------------------------------
# Metric computations
# ---------------------------------------------------------------------------

def compute_per_seed_metrics(seed_records: list[dict]) -> dict[str, float]:
    """Compute metrics for one seed's full run.

    Returns: dict with keys cum_pa, cum_q, total_spent, mean_q, roi, n_rounds.
    """
    n = len(seed_records)
    cum_pa = sum(r.get("payment_aware_reward", 0.0) for r in seed_records)
    cum_q = sum(r.get("quality", 0.0) for r in seed_records)
    total_spent = sum(r.get("charged_cost_usdc", 0.0) for r in seed_records)
    mean_q = cum_q / n if n else 0.0
    roi = cum_q / total_spent if total_spent > 0 else 0.0
    return {
        "n_rounds": n,
        "cum_pa": cum_pa,
        "cum_q": cum_q,
        "total_spent": total_spent,
        "mean_q": mean_q,
        "roi": roi,
    }


def compute_adaptation_time(
    seed_records: list[dict],
    scenario: str,
) -> float | None:
    """Adaptation time: rounds after shock for windowed ROI to recover within
    RECOVERY_THRESHOLD_PCT of pre-event level.

    For S2 (drop): recover means ROI returns UP to >= (1 - 5%) × pre_event_ROI
    For S3 (jump up — premium becomes cheaper): recover means ROI rises
                                                to >= (1 + 5%) × pre_event_ROI
                                                (reaching the new opportunity)
    Returns None for S1 (no shock).
    """
    if scenario not in SHOCK_ROUND:
        return None

    shock = SHOCK_ROUND[scenario]
    lo, hi = PRE_EVENT_WINDOW[scenario]
    if len(seed_records) <= shock:
        return float("inf")  # bankrupted before shock — can't measure

    # Pre-event ROI: rolling sum over [lo, hi]
    pre_q = sum(r["quality"] for r in seed_records[lo:hi])
    pre_c = sum(r["charged_cost_usdc"] for r in seed_records[lo:hi])
    if pre_c <= 0:
        return float("inf")
    pre_roi = pre_q / pre_c

    # Vectorized rolling-window ROI via cumulative sums
    W = 200
    n = len(seed_records)
    # Precompute cumulative q and c
    cum_q_arr = [0.0] * (n + 1)
    cum_c_arr = [0.0] * (n + 1)
    for i, r in enumerate(seed_records):
        cum_q_arr[i + 1] = cum_q_arr[i] + r.get("quality", 0.0)
        cum_c_arr[i + 1] = cum_c_arr[i] + r.get("charged_cost_usdc", 0.0)

    def roi_at(t: int) -> float:
        """Trailing-W ROI ending at round t, computed in O(1) via cumulative sums."""
        if t < W:
            return 0.0
        q = cum_q_arr[t] - cum_q_arr[t - W]
        c = cum_c_arr[t] - cum_c_arr[t - W]
        return q / c if c > 0 else 0.0

    if scenario == "S2":
        target = pre_roi * (1 - RECOVERY_THRESHOLD_PCT)
        for t in range(shock + W, n):
            if roi_at(t) >= target:
                return t - shock
        return float("inf")
    else:  # S3
        target = pre_roi * 1.10
        for t in range(shock + W, n):
            if roi_at(t) >= target:
                return t - shock
        return float("inf")


def aggregate_seeds(per_seed: list[dict]) -> dict[str, tuple[float, float]]:
    """Return mean ± std for each metric across seeds."""
    out = {}
    keys = ("cum_pa", "mean_q", "total_spent", "roi")
    for k in keys:
        vals = [s[k] for s in per_seed]
        out[k] = (
            statistics.mean(vals),
            statistics.stdev(vals) if len(vals) > 1 else 0.0,
        )
    return out


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

def analyze_cell(ablation: str, scenario: str) -> dict:
    """Compute all metrics for one (ablation, scenario) cell."""
    log_dir = get_log_dir(ablation, scenario)
    seeds = load_all_seeds(log_dir)
    if not seeds:
        return {"ablation": ablation, "scenario": scenario, "n_seeds": 0}

    per_seed = [compute_per_seed_metrics(s) for s in seeds]
    agg = aggregate_seeds(per_seed)

    # Adaptation time
    adapt_times = [compute_adaptation_time(s, scenario) for s in seeds]
    adapt_times_finite = [t for t in adapt_times if t is not None and t != float("inf")]
    adapt_mean = (
        statistics.mean(adapt_times_finite) if adapt_times_finite else None
    )
    adapt_count = len(adapt_times_finite)

    # Cumulative regret (vs Oracle)
    oracle_dir = get_oracle_dir(scenario)
    oracle_seeds = load_all_seeds(oracle_dir)
    if oracle_seeds:
        oracle_pas = [
            sum(r.get("payment_aware_reward", 0.0) for r in s) for s in oracle_seeds
        ]
        oracle_pa_mean = statistics.mean(oracle_pas)
    else:
        oracle_pa_mean = None
    cum_regret = (
        oracle_pa_mean - agg["cum_pa"][0] if oracle_pa_mean is not None else None
    )

    return {
        "ablation": ablation,
        "scenario": scenario,
        "n_seeds": len(seeds),
        "cum_pa_mean": agg["cum_pa"][0],
        "cum_pa_std": agg["cum_pa"][1],
        "mean_q": agg["mean_q"][0],
        "roi": agg["roi"][0],
        "total_spent": agg["total_spent"][0],
        "cum_regret": cum_regret,
        "adapt_time_mean": adapt_mean,
        "adapt_time_count": adapt_count,
        "adapt_time_total": len(seeds),
    }


def render_markdown(rows: list[dict]) -> str:
    """Build the 4-metric ablation table as markdown."""
    lines: list[str] = []
    lines.append("# Ablation Matrix: 4 metrics × 4 ablations × 3 scenarios")
    lines.append("")
    lines.append("**Metrics:**")
    lines.append("- **task_q** = mean quality (proxy for task_success_rate)")
    lines.append("- **ROI** = Σ q / Σ $ (raw quality per dollar)")
    lines.append("- **CumRegret** = Oracle cum_PA − policy cum_PA")
    lines.append(
        "- **AdaptT** = rounds after shock for trailing-200 ROI to "
        "recover within 5% of pre-event level (S2/S3 only)"
    )
    lines.append("")

    # Group rows by scenario, columns by ablation
    by_scen: dict[str, dict[str, dict]] = defaultdict(dict)
    for r in rows:
        by_scen[r["scenario"]][r["ablation"]] = r

    abl_order = ["full", "no_p", "no_d", "no_c", "no_ts"]

    for scen in SCENARIOS:
        lines.append(f"## {SCENARIO_LABELS[scen]}")
        lines.append("")
        # Header
        header = f"| Ablation | cum_PA | task_q | ROI (q/$) | CumRegret | AdaptT |"
        sep = "|---|---|---|---|---|---|"
        lines.append(header)
        lines.append(sep)
        for abl in abl_order:
            row = by_scen[scen].get(abl)
            if row is None or row["n_seeds"] == 0:
                lines.append(f"| {ABLATION_LABELS[abl]} | -- | -- | -- | -- | -- |")
                continue
            cum_pa = f"{row['cum_pa_mean']:.0f}±{row['cum_pa_std']:.0f}"
            mean_q = f"{row['mean_q']:.3f}"
            roi = f"{row['roi']:.0f}"
            regret = (
                f"{row['cum_regret']:.0f}" if row["cum_regret"] is not None else "--"
            )
            adapt = ""
            if scen == "S1":
                adapt = "n/a"
            else:
                if row["adapt_time_mean"] is None:
                    adapt = f"never ({row['adapt_time_count']}/{row['adapt_time_total']})"
                else:
                    adapt = (
                        f"{row['adapt_time_mean']:.0f} "
                        f"({row['adapt_time_count']}/{row['adapt_time_total']})"
                    )
            lines.append(
                f"| {ABLATION_LABELS[abl]} | {cum_pa} | {mean_q} | {roi} | {regret} | {adapt} |"
            )
        lines.append("")

    # Cross-scenario summary table for D and C specifically
    lines.append("## Cross-scenario adaptation_time comparison (D and C)")
    lines.append("")
    lines.append("| Scenario | full | −D | −C | full vs −D Δ | full vs −C Δ |")
    lines.append("|---|---|---|---|---|---|")
    for scen in ("S2", "S3"):
        full = by_scen[scen].get("full", {}).get("adapt_time_mean")
        no_d = by_scen[scen].get("no_d", {}).get("adapt_time_mean")
        no_c = by_scen[scen].get("no_c", {}).get("adapt_time_mean")
        d_diff = (
            f"{full - no_d:+.0f}" if full is not None and no_d is not None else "--"
        )
        c_diff = (
            f"{full - no_c:+.0f}" if full is not None and no_c is not None else "--"
        )
        lines.append(
            f"| {scen} | {full:.0f} | {no_d:.0f} | {no_c:.0f} | "
            f"{d_diff} | {c_diff} |"
            if (full is not None and no_d is not None and no_c is not None)
            else f"| {scen} | -- | -- | -- | -- | -- |"
        )
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    cache_path = Path("logs/.ablation_metrics_cache.json")
    if cache_path.exists():
        cache = json.loads(cache_path.read_text())
    else:
        cache = {}

    rows = []
    for abl in ABLATION_LABELS:
        for scen in SCENARIOS:
            key = f"{abl}/{scen}"
            if key in cache:
                rows.append(cache[key])
                print(f"  [cache] {key}: cum_PA={cache[key].get('cum_pa_mean', 0):7.0f}", flush=True)
                continue
            print(f"  computing {key}...", flush=True)
            row = analyze_cell(abl, scen)
            rows.append(row)
            cache[key] = row
            cache_path.write_text(json.dumps(cache, indent=2))  # incremental save
            if row["n_seeds"] == 0:
                print(f"    NO DATA")
                continue
            regret_str = f"regret={row['cum_regret']:6.0f}" if row["cum_regret"] is not None else "(no oracle)"
            adapt_str = f"adaptT={row['adapt_time_mean']:.0f}" if row.get("adapt_time_mean") else "(n/a)"
            print(
                f"    n={row['n_seeds']:>2} | cum_PA={row['cum_pa_mean']:7.0f} ± {row['cum_pa_std']:5.0f}"
                f" | q={row['mean_q']:.3f} | ROI={row['roi']:5.0f}"
                f" | {regret_str} | {adapt_str}"
            )

    md = render_markdown(rows)
    out_path = Path("logs/ablation_4metrics_table.md")
    out_path.write_text(md, encoding="utf-8")
    print(f"\nMarkdown table written: {out_path}")
    print()
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
