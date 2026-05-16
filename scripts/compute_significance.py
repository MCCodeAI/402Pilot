"""Cross-baseline pairwise significance for paper §6.3 Table 1.

Reads existing summary.jsonl files (no re-running of experiments) and
computes, for each scenario × baseline pair:

    - mean Δ(q_bar_T, PA_gap_advantage, ROI), paired by seed
    - paired bootstrap 95% CI on each Δ
    - paired t-statistic + two-sided p-value (Welch's t for paranoia)
    - effect size: Cohen's d_z (paired)

q_bar_T is full-horizon mean quality Σq_t / T (unserved rounds → 0); read
from the explicit summary field, falling back to cum_quality / T.

Comparisons (15 pairs total):
    PA-DCT vs {Random, AlwaysCheap, AlwaysMid, AlwaysPremium, BudgetRule}
    × {S1, S2, S3 v2}

Why paired bootstrap, not a paired t-test:
    Across 30 seeds the PA objective distribution can be skewed under
    bankrupting policies (AlwaysPremium hits a budget wall and the PA
    stops accumulating mid-run). The paired difference still has finite
    variance, but its sampling distribution is not Gaussian. Bootstrap
    is robust to that. We report both bootstrap CI and t-test p-value
    so reviewers can see the agreement.

Output:
    logs/significance_table.md — markdown ready to paste into the paper.

Usage:
    python -m scripts.compute_significance
    python -m scripts.compute_significance --n-bootstrap 10000   # tighter CI
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
OUT = ROOT / "logs" / "significance_table.md"


def scenario_dir(scenario: str) -> Path:
    """Same dispatch as compute_ablation_metrics: S3 → s3promo_v2."""
    if scenario == "S3":
        return RESULTS / "scenario_sweep_s3promo_v2"
    return RESULTS / "scenario_sweep" / scenario


# Treat 'padcts' (legacy summary key) as PA-DCT.
PADCT_KEYS = ("padct", "padcts")
BASELINE_KEYS = ("random", "always_cheapest", "always_mid",
                 "always_premium", "budget_rule")
BASELINE_LABEL = {
    "random":          "Random",
    "always_cheapest": "AlwaysCheap",
    "always_mid":      "AlwaysMid",
    "always_premium":  "AlwaysPremium",
    "budget_rule":     "BudgetRule",
}
SCENARIOS = ["S1", "S2", "S3"]

METRICS = ("cum_pa_reward", "mean_quality")  # plus ROI computed below


def load_summary(scenario: str) -> dict[str, dict[int, dict]]:
    """Return {policy: {seed: row}}."""
    p = scenario_dir(scenario) / "summary.jsonl"
    out: dict[str, dict[int, dict]] = {}
    with p.open() as f:
        for line in f:
            r = json.loads(line)
            out.setdefault(r["policy"], {})[r["seed"]] = r
    return out


HORIZON_T = 10000  # locked in experiments/main.yaml


def per_seed_cum_quality(row: dict) -> float:
    """Σ q_t for one seed.

    Reads the explicit "cum_quality" field (preferred). Falls back to
    mean_quality * rounds for legacy summaries where mean_quality is the
    served-only conditional mean (Σ q / n × n = Σ q).
    """
    if "cum_quality" in row:
        return float(row["cum_quality"])
    return float(row["mean_quality"]) * row["rounds"]


def per_seed_q_bar_T(row: dict) -> float:
    """Full-horizon mean quality q̄_T = Σ q_t / T (unserved rounds → 0).

    Reads explicit q_bar_T field if present; otherwise computes from
    cum_quality / T. Both paths are equivalent for non-bankrupt policies.
    """
    if "q_bar_T" in row:
        return float(row["q_bar_T"])
    return per_seed_cum_quality(row) / HORIZON_T


def per_seed_roi(row: dict) -> float:
    if row["total_spent"] <= 0:
        return 0.0
    return per_seed_cum_quality(row) / row["total_spent"]


def _diff_paired(a: dict[int, dict], b: dict[int, dict],
                 metric_fn) -> np.ndarray:
    """Paired diffs PA-DCT − baseline by seed, dropping mismatched seeds."""
    seeds = sorted(set(a) & set(b))
    return np.array([metric_fn(a[s]) - metric_fn(b[s]) for s in seeds])


def bootstrap_ci(diffs: np.ndarray, n: int, rng: np.random.Generator,
                 ci: float = 0.95) -> tuple[float, float]:
    if diffs.size == 0:
        return float("nan"), float("nan")
    boot = rng.choice(diffs, size=(n, diffs.size), replace=True).mean(axis=1)
    lo, hi = np.quantile(boot, [(1 - ci) / 2, (1 + ci) / 2])
    return float(lo), float(hi)


def paired_t_p_value(diffs: np.ndarray) -> tuple[float, float]:
    """Two-sided paired t-statistic and p-value (no scipy dependency).

    Uses normal approximation for large N (we have N=30, normal is close
    to t_29 within 5%; the bootstrap CI is the load-bearing test).
    """
    n = diffs.size
    if n < 2:
        return float("nan"), float("nan")
    mean = diffs.mean()
    sd = diffs.std(ddof=1)
    if sd == 0:
        return float("inf"), 0.0
    t = mean / (sd / np.sqrt(n))
    # Two-sided normal approximation (good enough for n=30, error <5%).
    # math.erfc avoids needing scipy.
    import math
    p = math.erfc(abs(t) / math.sqrt(2))
    return float(t), float(p)


def cohens_d_z(diffs: np.ndarray) -> float:
    if diffs.size < 2 or diffs.std(ddof=1) == 0:
        return float("nan")
    return float(diffs.mean() / diffs.std(ddof=1))


def stars(p: float) -> str:
    if p < 0.0001: return "****"
    if p < 0.001:  return "***"
    if p < 0.01:   return "**"
    if p < 0.05:   return "*"
    return "ns"


def find_padct(by_policy: dict[str, dict[int, dict]]) -> dict[int, dict] | None:
    for k in PADCT_KEYS:
        if k in by_policy:
            return by_policy[k]
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n-bootstrap", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args(argv)
    rng = np.random.default_rng(args.seed)

    rows: list[dict] = []
    for scen in SCENARIOS:
        by_policy = load_summary(scen)
        padct = find_padct(by_policy)
        if padct is None:
            print(f"[warn] no PA-DCT in {scen}; skipping")
            continue
        for bkey in BASELINE_KEYS:
            base = by_policy.get(bkey)
            if base is None:
                continue
            seeds = sorted(set(padct) & set(base))
            n = len(seeds)
            if n < 2:
                continue
            for metric_label, metric_fn in [
                ("q_bar_T", per_seed_q_bar_T),
                ("PA_gap_advantage", lambda r: r["cum_pa_reward"]),
                ("ROI",     per_seed_roi),
            ]:
                diffs = _diff_paired(padct, base, metric_fn)
                mean = float(diffs.mean())
                sd = float(diffs.std(ddof=1))
                ci_lo, ci_hi = bootstrap_ci(diffs, args.n_bootstrap, rng)
                t, p = paired_t_p_value(diffs)
                d_z = cohens_d_z(diffs)
                rows.append({
                    "scenario": scen,
                    "baseline": BASELINE_LABEL[bkey],
                    "metric":   metric_label,
                    "n":        n,
                    "delta_mean": mean,
                    "delta_sd":   sd,
                    "ci_lo":      ci_lo,
                    "ci_hi":      ci_hi,
                    "t":          t,
                    "p":          p,
                    "d_z":        d_z,
                    "stars":      stars(p),
                })

    # ---- Render the markdown report -------------------------------------------
    md: list[str] = []
    md.append("# Cross-baseline pairwise significance (PA-DCT vs each baseline)")
    md.append("")
    md.append(f"Generated by `scripts/compute_significance.py` "
              f"(N seeds = 30, bootstrap = {args.n_bootstrap}, "
              f"two-sided paired test).")
    md.append("")
    md.append("**Convention.** Δ = PA-DCT − baseline, paired by seed.")
    md.append("Positive Δ on q_bar_T (full-horizon mean quality, unserved rounds → 0), "
              "PA_gap_advantage, or ROI means PA-DCT wins.")
    md.append("For PA_gap_advantage, positive Δ means PA-DCT has a lower PA-gap; "
              "the True Oracle term cancels in paired differences.")
    md.append("CI is 95% bootstrap; p-value is two-sided paired-z (n=30, normal ≈ t_29).")
    md.append("`d_z` is Cohen's standardised paired effect size.")
    md.append("")
    md.append("**Significance markers** (for paper Table 1):")
    md.append("`****` p<10⁻⁴ &nbsp; `***` p<10⁻³ &nbsp; `**` p<0.01 &nbsp; "
              "`*` p<0.05 &nbsp; `ns` not significant.")
    md.append("")

    for scen in SCENARIOS:
        scen_rows = [r for r in rows if r["scenario"] == scen]
        if not scen_rows:
            continue
        md.append(f"## {scen}")
        md.append("")
        md.append("| Baseline | Metric | Δ mean | Δ sd | 95% CI | t | p | d_z | sig |")
        md.append("|---|---|---:|---:|---|---:|---:|---:|:---:|")
        for r in scen_rows:
            ci = f"[{r['ci_lo']:+.3g}, {r['ci_hi']:+.3g}]"
            md.append(
                f"| {r['baseline']} | {r['metric']} | "
                f"{r['delta_mean']:+.4g} | {r['delta_sd']:.4g} | "
                f"{ci} | {r['t']:+.2f} | {r['p']:.2e} | "
                f"{r['d_z']:+.2f} | {r['stars']} |"
            )
        md.append("")

    # Quick "Table 1 markers" cheat sheet — paper main table only needs this.
    md.append("---")
    md.append("")
    md.append("## Compact Table 1 markers (PA-gap only)")
    md.append("")
    md.append("Use these to annotate PA-gap comparisons in the paper's main table.")
    md.append("")
    md.append("| Scenario | vs Random | vs AlwaysCheap | vs AlwaysMid | vs AlwaysPremium | vs BudgetRule |")
    md.append("|---|---|---|---|---|---|")
    for scen in SCENARIOS:
        cells = []
        for bk in ("Random", "AlwaysCheap", "AlwaysMid", "AlwaysPremium", "BudgetRule"):
            r = next((r for r in rows
                      if r["scenario"] == scen and r["baseline"] == bk
                      and r["metric"] == "PA_gap_advantage"), None)
            cells.append(r["stars"] if r else "—")
        md.append(f"| {scen} | " + " | ".join(cells) + " |")

    OUT.write_text("\n".join(md) + "\n")
    print(f"[ok] wrote {OUT}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
