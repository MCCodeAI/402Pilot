"""Compute the 4 official metrics across all ablation cells (5 ablations).

Reproduces paper Table 6 (component ablations) from per-cell JSONL logs.
Metrics:

  1. PA-gap/T = (Oracle cum_PA − policy cum_PA) / T, paired by seed and
     aggregated as mean ± std across 30 seeds. This is the load-bearing
     metric for the ablation argument; lower is better.
  2. ROI = Σ q / Σ $ — raw quality per dollar (mean across seeds).
  3. q_bar_T = Σ q_t / T — full-horizon mean quality. Unserved rounds
     after wallet exhaustion contribute q_t = 0, so policies that
     bankrupt mid-run (e.g. the -P ablation in S1/S2) are correctly
     penalised. Suffix ${}^\\dagger$ marks ablations whose seeds
     bankrupt before T.
  4. AdaptT = trailing-200 ROI shock-response time:
     S2 reaches >= 95% of pre-outage ROI; S3 reaches >= 110% of
     pre-promotion ROI (NA for S1).

Per-cell JSONL log paths:
  - results/scenario_sweep/{S1,S2}/padct/seed_NN.jsonl        (full S1, S2)
  - results/scenario_sweep_s3promo_v2/padct/seed_NN.jsonl     (full S3)
  - results/ablation_matrix/<ablation>/{S1,S2,S3}/padct/seed_NN.jsonl
      (no_p, no_d, no_c, no_ts — all three scenarios)
  - results/scenario_sweep_s3promo_v2_ablation/padct/seed_NN.jsonl
      (no_c_post — S3 only; the S1/S2 variants were never run because
      pinning cost to spec only changes behaviour under a price shock)

Output: a wide-format table to stdout, plus markdown table written to
        logs/ablation_5metrics_table.md
"""

from __future__ import annotations

import json
import math
import statistics
from pathlib import Path


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ABLATION_LABELS = {
    "full":      "Full PA-DCT",
    "no_p":      "$-P$",
    "no_d":      "$-D$",
    "no_c":      "$-C$",
    "no_ts":     "$-TS$",
    "no_c_post": "$-C_{\\mathrm{post}}$",
}

# Ablation order in the rendered table (matches paper Table 6).
ABLATION_ORDER = ["full", "no_p", "no_d", "no_c", "no_ts", "no_c_post"]

# Which scenarios each ablation was run for. ``no_c_post`` is S3-only by
# design (pinning cost to the spec scalar only affects behaviour under a
# price shock); the other ablations were run across all three scenarios.
ABLATION_SCENARIOS = {
    "full":      ("S1", "S2", "S3"),
    "no_p":      ("S1", "S2", "S3"),
    "no_d":      ("S1", "S2", "S3"),
    "no_c":      ("S1", "S2", "S3"),
    "no_ts":     ("S1", "S2", "S3"),
    "no_c_post": ("S3",),
}

SCENARIOS = ["S1", "S2", "S3"]
SCENARIO_LABELS = {
    "S1": "S1 (stationary)",
    "S2": "S2 (outage 3000-5500)",
    "S3": "S3 (promo at round 1000)",
}

# Shock event rounds for AdaptT (S2/S3 only)
SHOCK_ROUND = {"S2": 3000, "S3": 1000}
# Pre-event window for baseline ROI (rounds before shock)
PRE_EVENT_WINDOW = {"S2": (1000, 3000), "S3": (0, 1000)}
# S2 recovery threshold: 5% below pre-event ROI. S3 uses 10% above pre-event.
RECOVERY_THRESHOLD_PCT = 0.05

HORIZON_T = 10000  # locked in experiments/main.yaml


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def get_log_dir(ablation: str, scenario: str) -> Path | None:
    """Per-seed JSONL log directory for one (ablation, scenario) cell.

    Returns ``None`` when the (ablation, scenario) combination was not run
    (e.g. ``no_c_post`` for S1/S2).
    """
    if scenario not in ABLATION_SCENARIOS.get(ablation, ()):
        return None  # not run for this scenario by design
    if ablation == "full":
        if scenario in ("S1", "S2"):
            return Path(f"results/scenario_sweep/{scenario}/padct")
        return Path("results/scenario_sweep_s3promo_v2/padct")
    if ablation == "no_c_post":
        # The S3-only price-shock-diagnostic variant lives in its own dir.
        return Path("results/scenario_sweep_s3promo_v2_ablation/padct")
    return Path(f"results/ablation_matrix/{ablation}/{scenario}/padct")


def get_oracle_dir(scenario: str) -> Path:
    if scenario in ("S1", "S2"):
        return Path(f"results/scenario_sweep/{scenario}/oracle")
    return Path("results/scenario_sweep_s3promo_v2/oracle")


# ---------------------------------------------------------------------------
# Log reading
# ---------------------------------------------------------------------------

def read_log(log_path: Path) -> list[dict]:
    """Read one JSONL log file, returning list of round records."""
    records: list[dict] = []
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


def load_all_seeds(log_dir: Path | None) -> dict[int, list[dict]]:
    """Return {seed_id: records}, keyed from seed_XX.jsonl filenames."""
    if log_dir is None:
        return {}
    all_seeds: dict[int, list[dict]] = {}
    for f in sorted(log_dir.glob("seed_*.jsonl")):
        try:
            seed_id = int(f.stem.split("_")[-1])
        except ValueError:
            continue
        recs = read_log(f)
        if recs:
            all_seeds[seed_id] = recs
    return all_seeds


# ---------------------------------------------------------------------------
# Per-seed metric computation
# ---------------------------------------------------------------------------

def compute_per_seed_metrics(seed_records: list[dict],
                             horizon_T: int = HORIZON_T) -> dict[str, float]:
    """Compute metrics for one seed.

    Returns: dict with cum_pa, cum_q, total_spent, q_bar_T, roi, n_rounds.
    ``q_bar_T`` is full-horizon (Σ q_t / T), penalising mid-run bankruptcy
    through the denominator T regardless of n_rounds < T.
    """
    n = len(seed_records)
    cum_pa = sum(r.get("payment_aware_reward", 0.0) for r in seed_records)
    cum_q = sum(r.get("quality", 0.0) for r in seed_records)
    total_spent = sum(r.get("charged_cost_usdc", 0.0) for r in seed_records)
    q_bar_T = cum_q / horizon_T if horizon_T else 0.0
    roi = cum_q / total_spent if total_spent > 0 else 0.0
    return {
        "n_rounds": n,
        "cum_pa": cum_pa,
        "cum_q": cum_q,
        "total_spent": total_spent,
        "q_bar_T": q_bar_T,
        "roi": roi,
    }


def compute_adaptation_time(
    seed_records: list[dict],
    scenario: str,
) -> float | None:
    """AdaptT: rounds after shock for trailing-200 ROI to cross the threshold.

    S2: trailing-200 ROI returns to >= (1 - 5%) × pre-event ROI.
    S3: trailing-200 ROI reaches >= 110% × pre-event ROI.
    Returns None for S1 (no shock); returns ``float('inf')`` when the
    threshold is never crossed within the horizon.

    NB: this metric measures when the trailing window's ROI crosses a
    threshold; for variants whose policy does not adapt but whose realized
    cost drops externally (e.g. -C_post under the S3 price drop, where
    premium calls cost less even at low premium share), the threshold can
    still be crossed quickly. Treat AdaptT alongside premium adoption and
    PA-gap/T for ablations whose decision rule cannot react to the shock.
    """
    if scenario not in SHOCK_ROUND:
        return None

    shock = SHOCK_ROUND[scenario]
    lo, hi = PRE_EVENT_WINDOW[scenario]
    if len(seed_records) <= shock:
        return float("inf")  # bankrupted before shock — can't measure
    pre_q = sum(r["quality"] for r in seed_records[lo:hi])
    pre_c = sum(r["charged_cost_usdc"] for r in seed_records[lo:hi])
    if pre_c <= 0:
        return float("inf")
    pre_roi = pre_q / pre_c

    W = 200
    n = len(seed_records)
    # Cumulative arrays for O(1) trailing-W ROI.
    cum_q_arr = [0.0] * (n + 1)
    cum_c_arr = [0.0] * (n + 1)
    for i, r in enumerate(seed_records):
        cum_q_arr[i + 1] = cum_q_arr[i] + r.get("quality", 0.0)
        cum_c_arr[i + 1] = cum_c_arr[i] + r.get("charged_cost_usdc", 0.0)

    def roi_at(t: int) -> float:
        if t < W:
            return 0.0
        q = cum_q_arr[t] - cum_q_arr[t - W]
        c = cum_c_arr[t] - cum_c_arr[t - W]
        return q / c if c > 0 else 0.0

    target = pre_roi * (1 - RECOVERY_THRESHOLD_PCT) if scenario == "S2" \
             else pre_roi * 1.10
    for t in range(shock + W, n):
        if roi_at(t) >= target:
            return t - shock
    return float("inf")


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def aggregate_cell(per_seed: dict[int, dict],
                   oracle_per_seed: dict[int, dict] | None,
                   horizon_T: int = HORIZON_T) -> dict:
    """Aggregate per-seed metrics into mean/std summaries.

    PA-gap is computed per-seed (paired by seed index) then aggregated;
    this yields a defensible mean ± std rather than a single deterministic
    mean-minus-mean.
    """
    out: dict[str, float | None] = {}

    # q_bar_T and ROI: simple means.
    policy_metrics = list(per_seed.values())
    q_bar_T_vals = [s["q_bar_T"] for s in policy_metrics]
    roi_vals = [s["roi"] for s in policy_metrics]
    out["q_bar_T_mean"] = statistics.mean(q_bar_T_vals)
    out["q_bar_T_std"] = (
        statistics.stdev(q_bar_T_vals) if len(q_bar_T_vals) > 1 else 0.0
    )
    out["roi_mean"] = statistics.mean(roi_vals)

    # Bankruptcy flag: any seed run shorter than T means at least some
    # seeds bankrupted; we report mean rounds and mark in the table.
    n_rounds = [s["n_rounds"] for s in policy_metrics]
    out["bankrupt_any"] = any(n < horizon_T for n in n_rounds)
    out["n_rounds_mean"] = statistics.mean(n_rounds)

    # PA-gap per seed: oracle cum_PA[seed] − policy cum_PA[seed].
    if oracle_per_seed is not None:
        paired_seed_ids = sorted(set(per_seed) & set(oracle_per_seed))
        if paired_seed_ids:
            pa_gaps = [
                oracle_per_seed[seed_id]["cum_pa"] - per_seed[seed_id]["cum_pa"]
                for seed_id in paired_seed_ids
            ]
            pa_gap_per_T = [g / horizon_T for g in pa_gaps]
            out["pa_gap_per_T_mean"] = statistics.mean(pa_gap_per_T)
            out["pa_gap_per_T_std"] = (
                statistics.stdev(pa_gap_per_T) if len(pa_gap_per_T) > 1 else 0.0
            )
        else:
            out["pa_gap_per_T_mean"] = None
            out["pa_gap_per_T_std"] = None
    else:
        out["pa_gap_per_T_mean"] = None
        out["pa_gap_per_T_std"] = None

    return out


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

def analyze_cell(ablation: str, scenario: str) -> dict:
    """All metrics for one (ablation, scenario) cell.

    Returns a row dict; missing cells (e.g. ``no_c_post`` for S1/S2)
    return ``n_seeds = 0`` and the renderer prints ``n.r.``.
    """
    log_dir = get_log_dir(ablation, scenario)
    seeds = load_all_seeds(log_dir)
    base = {"ablation": ablation, "scenario": scenario, "n_seeds": len(seeds)}
    if not seeds:
        return base

    per_seed = {
        seed_id: compute_per_seed_metrics(records)
        for seed_id, records in seeds.items()
    }
    oracle_seeds = load_all_seeds(get_oracle_dir(scenario))
    oracle_per_seed = (
        {
            seed_id: compute_per_seed_metrics(records)
            for seed_id, records in oracle_seeds.items()
        }
        if oracle_seeds else None
    )
    agg = aggregate_cell(per_seed, oracle_per_seed)

    # AdaptT (per-seed mean over finite values; report (n_finite / n_total)
    # for non-trivial bookkeeping when seeds disagree).
    adapt_per_seed = [
        compute_adaptation_time(records, scenario)
        for records in seeds.values()
    ]
    adapt_finite = [t for t in adapt_per_seed
                    if t is not None and math.isfinite(t)]
    adapt_mean = statistics.mean(adapt_finite) if adapt_finite else None
    adapt_total = sum(1 for t in adapt_per_seed if t is not None)
    adapt_count = len(adapt_finite)

    base.update(agg)
    base["adapt_mean"] = adapt_mean
    base["adapt_count"] = adapt_count
    base["adapt_total"] = adapt_total
    return base


# ---------------------------------------------------------------------------
# Markdown rendering — matches paper Table 6
# ---------------------------------------------------------------------------

def _fmt_pa_gap(row: dict) -> str:
    """`mean±std` for PA-gap/T (3-decimal mean, 3-decimal std)."""
    m = row.get("pa_gap_per_T_mean")
    s = row.get("pa_gap_per_T_std")
    if m is None:
        return "n.r."
    return f"{m:.3f}±{s:.3f}"


def _fmt_roi(row: dict) -> str:
    m = row.get("roi_mean")
    return "n.r." if m is None else f"{m:.0f}"


def _fmt_q_bar_T(row: dict, mark_bankrupt: bool = True) -> str:
    m = row.get("q_bar_T_mean")
    if m is None:
        return "n.r."
    suffix = "†" if (mark_bankrupt and row.get("bankrupt_any")) else ""
    return f"{m:.3f}{suffix}"


def _fmt_adapt(row: dict, scenario: str) -> str:
    if scenario == "S1":
        return "n/a"
    m = row.get("adapt_mean")
    if m is None:
        return "n.r." if row.get("n_seeds", 0) == 0 else "∞"
    return f"{m:.0f}"


def render_markdown(rows: list[dict]) -> str:
    """Build paper-Table-6-style markdown with mean±std PA-gap/T."""
    lines: list[str] = []
    lines.append("# Ablation Matrix: 4 metrics × 5 ablations + Full × 3 scenarios")
    lines.append("")
    lines.append("Reproduces paper Table 6 (component ablations).")
    lines.append("")
    lines.append("**Metrics:**")
    lines.append(
        "- **PA-gap/T** = (Oracle cum_PA − policy cum_PA)/T, paired by seed; "
        "reported as mean ± std over 30 seeds. Lower is better."
    )
    lines.append("- **ROI** = Σ q / Σ $ (raw quality per dollar, mean across seeds)")
    lines.append(
        "- **q̄_T** = Σ q_t / T (full-horizon mean quality). "
        "†  marks ablations with any mid-run bankruptcy."
    )
    lines.append(
        "- **AdaptT** = trailing-200 ROI shock-response time (rounds). "
        "S2 ≥95% of pre-outage ROI; S3 ≥110% of pre-promotion ROI. "
        "∞ if never reached."
    )
    lines.append(
        "- **n.r.** means the (ablation, scenario) combination was not run "
        "(e.g. -C_post is S3-only by design)."
    )
    lines.append("")

    by_scen_abl: dict[tuple[str, str], dict] = {
        (r["scenario"], r["ablation"]): r for r in rows
    }

    for scen in SCENARIOS:
        lines.append(f"## {SCENARIO_LABELS[scen]}")
        lines.append("")
        lines.append("| Variant | PA-gap/T | ROI | q̄_T | AdaptT |")
        lines.append("|---|---|---|---|---|")
        for abl in ABLATION_ORDER:
            row = by_scen_abl.get((scen, abl), {"n_seeds": 0})
            if row.get("n_seeds", 0) == 0:
                lines.append(
                    f"| {ABLATION_LABELS[abl]} | n.r. | n.r. | n.r. | n.r. |"
                )
                continue
            lines.append(
                f"| {ABLATION_LABELS[abl]} | {_fmt_pa_gap(row)} | "
                f"{_fmt_roi(row)} | {_fmt_q_bar_T(row)} | "
                f"{_fmt_adapt(row, scen)} |"
            )
        lines.append("")

    # Compact cross-scenario AdaptT summary for the closing paragraph.
    lines.append("## AdaptT cross-scenario summary (Full + D/C/C_post focus)")
    lines.append("")
    lines.append(
        "| Scenario | Full | $-D$ | $-C$ | $-TS$ | $-C_{\\mathrm{post}}$ |"
    )
    lines.append("|---|---|---|---|---|---|")
    for scen in ("S2", "S3"):
        cells = []
        for abl in ("full", "no_d", "no_c", "no_ts", "no_c_post"):
            row = by_scen_abl.get((scen, abl), {"n_seeds": 0})
            cells.append(_fmt_adapt(row, scen))
        lines.append(f"| {scen} | " + " | ".join(cells) + " |")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    rows: list[dict] = []
    for abl in ABLATION_ORDER:
        for scen in SCENARIOS:
            key = f"{abl}/{scen}"
            print(f"  computing {key}...", flush=True)
            row = analyze_cell(abl, scen)
            rows.append(row)
            if row.get("n_seeds", 0) == 0:
                print("    n.r. (not run for this scenario)")
                continue
            pa_str = (
                f"PA-gap/T={row['pa_gap_per_T_mean']:.3f}±{row['pa_gap_per_T_std']:.3f}"
                if row.get("pa_gap_per_T_mean") is not None else "(no oracle)"
            )
            adapt_str = (
                f"AdaptT={row['adapt_mean']:.0f}"
                if row.get("adapt_mean") is not None
                else ("AdaptT=n/a" if scen == "S1" else "AdaptT=∞")
            )
            print(
                f"    n={row['n_seeds']:>2} | {pa_str} | "
                f"q̄_T={row['q_bar_T_mean']:.3f} | "
                f"ROI={row['roi_mean']:5.0f} | {adapt_str}"
            )

    md = render_markdown(rows)
    out_path = Path("logs/ablation_5metrics_table.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
    print(f"\nMarkdown table written: {out_path}")
    print()
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
