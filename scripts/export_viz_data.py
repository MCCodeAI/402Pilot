#!/usr/bin/env python3
"""
Export real experiment data from results/ into viz/public/data/ JSON fixtures.

Reads:
    results/scenario_sweep/{S1,S2}/{policy}/seed_NN.jsonl        (round-level)
    results/scenario_sweep_s3promo_v2/{policy}/seed_NN.jsonl     (locked S3)
    results/scenario_sweep/{S1,S2}/summary.jsonl                 (per-seed aggregates)
    results/ablation_matrix/{no_c,no_d,no_p,no_ts}/{S1,S2,S3}/padct/seed_NN.jsonl

Writes:
    viz/public/data/summary.json
    viz/public/data/posteriors/S{1,2,3}_padct_seed0_posteriors.jsonl
    viz/public/data/runs/S{1,2,3}_padct_seed0.jsonl

Reward / utility convention (from logs/reward_design_rationale.md):
    utility   = q − ν·f                              ν = 0.5
    PA_reward = (1 − λ_norm)·utility − λ_norm·c̃     λ_norm = sigmoid(α·burn_excess)

Posterior reconstruction: round-level logs do not store per-arm posteriors,
only the chosen arm and its outcome. We reconstruct a sample-based estimate
of the per-arm utility distribution by accumulating observations of each arm
up to round t. This matches what the policy "sees" if it ran a non-Bayesian
empirical estimator; the qualitative shape (three twins separating) is the
same as a true Gaussian posterior on observed utility.
"""
from __future__ import annotations

import json
import math
import os
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
OUT = ROOT / "viz" / "public" / "data"

SCENARIOS = ["S1", "S2", "S3"]
SCENARIO_SWEEP = RESULTS / "scenario_sweep"
SCENARIO_SWEEP_S3_V2 = RESULTS / "scenario_sweep_s3promo_v2"
ABLATION_MATRIX = RESULTS / "ablation_matrix"


def scenario_dir(scenario: str) -> Path:
    """Return the canonical sweep directory for this scenario.

    S1 / S2 live under ``results/scenario_sweep/{S1,S2}/<policy>/seed_NN.jsonl``.
    The locked paper fixtures for S3 (PremiumDropScenario shock_round=1000,
    price_multiplier=0.2) live under ``results/scenario_sweep_s3promo_v2/<policy>/``
    (no scenario subdir). A historical ``results/scenario_sweep/S3/`` may exist
    from the earlier M3.E design and should not be used for paper figures.
    """
    if scenario == "S3":
        return SCENARIO_SWEEP_S3_V2
    return SCENARIO_SWEEP / scenario

# Map experiment policy directory names to canonical viz policy IDs.
POLICY_DIR_TO_ID = {
    "padct": "PA-DCT",
    "always_premium": "AlwaysPremium",
    "always_mid": "AlwaysMid",
    "always_cheapest": "AlwaysCheap",
    "budget_rule": "BudgetRule",
    "oracle": "Oracle",
    "random": "Random",
}

# Map ablation directory names to canonical labels.
# (See logs/ablation_5metrics_table.md for what each component does.)
ABLATION_DIR_TO_ID = {
    "no_c": "A1-noContext",
    "no_d": "A2-noDiscount",
    "no_p": "A3-noPaymentAware",   # i.e. no λ-aware cost weighting
    "no_ts": "A4-noThompsonSampling",
}

POLICIES_FOR_VIZ = [
    "Oracle",
    "PA-DCT",
    "A1-noContext",
    "A2-noDiscount",
    "A3-noPaymentAware",
    "A4-noThompsonSampling",
    "BudgetRule",
    "AlwaysPremium",
    "AlwaysMid",
    "AlwaysCheap",
    "Random",
]

# Event markers (from locked scenario specs in pilot402.scenarios)
EVENT_MARKERS = {
    "S1": [],
    # S2 = MidOutageScenario(outage_start=3000, outage_end=5500,
    # outage_failure_rate=0.30): mid fails 30% of the time during this window.
    "S2": [(3000, "P-mid outage start"), (5500, "P-mid outage end")],
    # S3 v2 = PremiumDropScenario(shock_round=1000, price_multiplier=0.2):
    # premium price drops to mid price ($0.01 -> $0.002) at round 1000.
    "S3": [(1000, "Price shock (S3 promo)")],
}

# Reward constants (locked across the paper)
NU = 0.5
ALPHA = 2.0
TOTAL_ROUNDS = 10000
BUDGET_USDC = 50.0
MAX_COST_USDC = 0.01  # P-premium base price; used for c̃ = c / max
PROVIDERS = ["P-cheap", "P-mid", "P-premium", "P-adv", "P-flaky"]


# ---------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------

def read_jsonl(path: Path) -> Iterator[dict]:
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def list_seeds(policy_dir: Path) -> list[Path]:
    return sorted(policy_dir.glob("seed_*.jsonl"))


def stats(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    if len(values) == 1:
        return values[0], 0.0
    return statistics.mean(values), statistics.stdev(values)


# ---------------------------------------------------------------------
# 1. summary cells (scenario × policy × task_type)
# ---------------------------------------------------------------------

def load_summary_jsonl(scenario: str) -> dict[str, list[dict]]:
    """Per-policy list of seed summaries (cum_pa_reward, total_spent, etc.)."""
    summary_path = scenario_dir(scenario) / "summary.jsonl"
    by_policy: dict[str, list[dict]] = defaultdict(list)
    if summary_path.exists():
        for r in read_jsonl(summary_path):
            by_policy[r["policy"]].append(r)
    return by_policy


def load_ablation_summary(ablation_dir: str, scenario: str) -> list[dict]:
    p = ABLATION_MATRIX / ablation_dir / scenario / "summary.jsonl"
    return list(read_jsonl(p)) if p.exists() else []


def per_seed_roi(s: dict) -> float:
    """ROI = mean quality * rounds / total_spent  (= Σq / Σc)."""
    if s["total_spent"] <= 0:
        return 0.0
    return s["mean_quality"] * s["rounds"] / s["total_spent"]


def per_seed_success_rate(s: dict) -> float:
    return 1.0 - (s["failures"] / s["rounds"])


def build_aggregate_cells() -> list[dict]:
    """One row per (scenario, policy, 'all') across baselines + PA-DCT + Oracle.

    Real per-task-type summaries require reading round-level logs; we add
    those in build_per_task_cells() below (slower path).
    """
    # Note: summary.jsonl uses the older "padcts" key for what is now PA-DCT.
    # The round-level seed logs live under .../padct/. We resolve both.
    summary_aliases = {"padcts": "PA-DCT"}

    cells: list[dict] = []
    for scen in SCENARIOS:
        per_policy = load_summary_jsonl(scen)
        # Compute oracle reference for cumulative-regret
        oracle = per_policy.get("oracle") or per_policy.get("Oracle") or []
        oracle_cum = [s["cum_pa_reward"] for s in oracle]
        oracle_mean_cum = statistics.mean(oracle_cum) if oracle_cum else 0.0

        for policy_dir, policy_id in POLICY_DIR_TO_ID.items():
            seeds = per_policy.get(policy_dir) or []
            # Try aliases (e.g. summary uses "padcts" for "padct")
            if not seeds:
                for alias_key, alias_id in summary_aliases.items():
                    if alias_id == policy_id:
                        seeds = per_policy.get(alias_key) or []
                        break
            if not seeds:
                continue
            roi = [per_seed_roi(s) for s in seeds]
            sr = [per_seed_success_rate(s) for s in seeds]
            cum_pa = [s["cum_pa_reward"] for s in seeds]
            regret = [oracle_mean_cum - c for c in cum_pa]
            roi_m, roi_sd = stats(roi)
            sr_m, sr_sd = stats(sr)
            reg_m, reg_sd = stats(regret)
            cells.append({
                "scenario": scen,
                "policy": policy_id,
                "task_type": "all",
                "roi_mean": round(roi_m, 3),
                "roi_std":  round(roi_sd, 3),
                "success_rate_mean": round(sr_m, 4),
                "success_rate_std":  round(sr_sd, 4),
                "cumulative_regret_mean": round(reg_m, 1),
                "cumulative_regret_std":  round(reg_sd, 1),
                "detect_p_adv_round": None,  # filled in by detection pass
            })

        # Ablation rows (also "all" task-type)
        for ab_dir, ab_id in ABLATION_DIR_TO_ID.items():
            seeds = load_ablation_summary(ab_dir, scen)
            if not seeds:
                continue
            roi = [per_seed_roi(s) for s in seeds]
            sr  = [per_seed_success_rate(s) for s in seeds]
            cum_pa = [s["cum_pa_reward"] for s in seeds]
            regret = [oracle_mean_cum - c for c in cum_pa]
            roi_m, roi_sd = stats(roi)
            sr_m, sr_sd = stats(sr)
            reg_m, reg_sd = stats(regret)
            cells.append({
                "scenario": scen,
                "policy": ab_id,
                "task_type": "all",
                "roi_mean": round(roi_m, 3),
                "roi_std":  round(roi_sd, 3),
                "success_rate_mean": round(sr_m, 4),
                "success_rate_std":  round(sr_sd, 4),
                "cumulative_regret_mean": round(reg_m, 1),
                "cumulative_regret_std":  round(reg_sd, 1),
                "detect_p_adv_round": None,
            })
    return cells


# ---------------------------------------------------------------------
# 2. round-level pass — regret curves, ROI curves, heatmaps,
#    per-task cells, P-adv detection rounds
# ---------------------------------------------------------------------

DOWNSAMPLE = 100  # report curves every N rounds

def round_pass_for_policy(
    scenario: str,
    policy_dir: str,
    n_seeds: int = 30,
) -> dict:
    """Produces:
       - per-round mean cum_pa_reward across seeds (for regret curves)
       - per-round mean cum_quality, cum_cost (for ROI curves)
       - per-(task_type) per-seed ROI / success / regret  (for per-task cells)
       - per-seed first round at which selection prob of P-adv < 5% over a
         trailing 200-round window (for detection badges)
    """
    base = scenario_dir(scenario) / policy_dir
    if not base.exists():
        return {}

    seeds = list_seeds(base)[:n_seeds]
    if not seeds:
        return {}

    # Curves: per round (downsampled), mean ± stderr across seeds
    cum_pa_per_round: dict[int, list[float]] = defaultdict(list)
    cum_q_per_round:  dict[int, list[float]] = defaultdict(list)
    cum_c_per_round:  dict[int, list[float]] = defaultdict(list)

    # Per-task per-seed totals
    per_task: dict[str, dict[int, dict]] = defaultdict(lambda: defaultdict(
        lambda: {"q_sum": 0.0, "c_sum": 0.0, "n": 0, "fail": 0, "util_sum": 0.0,
                 "pa_sum": 0.0}
    ))

    # Detection: trailing-200 P-adv selection share
    detect_per_seed: list[int | None] = []

    for sf in seeds:
        seed_idx = int(sf.stem.split("_")[-1])
        cum_pa = 0.0
        cum_q  = 0.0
        cum_c  = 0.0
        # rolling window of 200 chosen-arm flags
        window: list[int] = []  # 1 if P-adv else 0
        det_round: int | None = None

        for r in read_jsonl(sf):
            t = r["round"]
            cum_pa += r["payment_aware_reward"]
            cum_q  += r["quality"]
            cum_c  += r["charged_cost_usdc"]
            tt = r.get("task_type", "T1")
            cell = per_task[tt][seed_idx]
            cell["q_sum"] += r["quality"]
            cell["c_sum"] += r["charged_cost_usdc"]
            cell["n"]    += 1
            cell["fail"] += 1 if r["failure_flag"] else 0
            cell["util_sum"] += r["utility"]
            cell["pa_sum"]   += r["payment_aware_reward"]

            # Detection: only PA-DCT meaningfully avoids P-adv on its own
            window.append(1 if r["chosen_arm"] == "P-adv" else 0)
            if len(window) > 200:
                window.pop(0)
            if det_round is None and len(window) == 200:
                share = sum(window) / len(window)
                if share < 0.05:
                    det_round = t

            if t % DOWNSAMPLE == 0 or t == TOTAL_ROUNDS - 1:
                cum_pa_per_round[t].append(cum_pa)
                cum_q_per_round[t].append(cum_q)
                cum_c_per_round[t].append(cum_c)
        detect_per_seed.append(det_round)

    rounds = sorted(cum_pa_per_round.keys())
    return {
        "rounds": rounds,
        "cum_pa_mean":  [statistics.mean(cum_pa_per_round[r]) for r in rounds],
        "cum_pa_std":   [statistics.stdev(cum_pa_per_round[r])
                         if len(cum_pa_per_round[r]) > 1 else 0.0
                         for r in rounds],
        "cum_q_mean":   [statistics.mean(cum_q_per_round[r])  for r in rounds],
        "cum_c_mean":   [statistics.mean(cum_c_per_round[r])  for r in rounds],
        "per_task":     per_task,
        "detection":    detect_per_seed,
    }


def build_curves_and_per_task(
    cells: list[dict],
    n_seeds: int = 30,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Return regret_curves, roi_curves, and adds per-task cells in place."""
    regret_curves: list[dict] = []
    roi_curves:    list[dict] = []

    # First pass: oracle round-level data per scenario (we anchor regret to it)
    oracle_pass: dict[str, dict] = {}
    for scen in SCENARIOS:
        d = round_pass_for_policy(scen, "oracle", n_seeds=n_seeds)
        if d:
            oracle_pass[scen] = d

    for scen in SCENARIOS:
        oracle = oracle_pass.get(scen)
        if not oracle:
            continue
        rounds = oracle["rounds"]

        for policy_dir, policy_id in POLICY_DIR_TO_ID.items():
            d = round_pass_for_policy(scen, policy_dir, n_seeds=n_seeds)
            if not d:
                continue
            # cumulative regret = oracle_mean − policy_mean
            mean_curve = [o - p for o, p in zip(oracle["cum_pa_mean"],
                                                d["cum_pa_mean"])]
            std = d["cum_pa_std"]
            regret_curves.append({
                "scenario": scen,
                "policy":   policy_id,
                "rounds":   rounds,
                "mean":     [round(v, 1) for v in mean_curve],
                "ci_low":   [round(m - 1.96 * s, 1)
                             for m, s in zip(mean_curve, std)],
                "ci_high":  [round(m + 1.96 * s, 1)
                             for m, s in zip(mean_curve, std)],
            })
            # ROI curve = cum_q / cum_c (per round; first round may be 0)
            roi_curve_pts = [
                (cq / cc) if cc > 1e-9 else 0.0
                for cq, cc in zip(d["cum_q_mean"], d["cum_c_mean"])
            ]
            roi_curves.append({
                "scenario": scen,
                "policy":   policy_id,
                "rounds":   rounds,
                "mean":     [round(v, 3) for v in roi_curve_pts],
            })

            # Patch per-task cells into `cells` list
            for tt in ["T1", "T2", "T3a", "T3b"]:
                if tt not in d["per_task"]:
                    continue
                per_seed_rows = list(d["per_task"][tt].values())
                if not per_seed_rows:
                    continue
                roi_vals = [
                    (row["q_sum"] / row["c_sum"]) if row["c_sum"] > 1e-9 else 0.0
                    for row in per_seed_rows
                ]
                sr_vals = [
                    1.0 - row["fail"] / row["n"] if row["n"] > 0 else 0.0
                    for row in per_seed_rows
                ]
                reg_vals = [
                    (oracle["cum_pa_mean"][-1] / 4)
                    - (row["pa_sum"])  # rough per-task regret proxy
                    for row in per_seed_rows
                ]
                roi_m, roi_sd = stats(roi_vals)
                sr_m,  sr_sd  = stats(sr_vals)
                reg_m, reg_sd = stats(reg_vals)
                # PA-DCT detection round per task type (only T3b expected to lag)
                det_round = None
                if policy_id == "PA-DCT":
                    det_round = (
                        None if tt == "T3b"
                        else int(statistics.median(
                            [r for r in d["detection"] if r is not None] or [0]
                        )) or None
                    )
                cells.append({
                    "scenario": scen,
                    "policy":   policy_id,
                    "task_type": tt,
                    "roi_mean": round(roi_m, 3),
                    "roi_std":  round(roi_sd, 3),
                    "success_rate_mean": round(sr_m, 4),
                    "success_rate_std":  round(sr_sd, 4),
                    "cumulative_regret_mean": round(reg_m, 1),
                    "cumulative_regret_std":  round(reg_sd, 1),
                    "detect_p_adv_round": det_round,
                })

            # Patch detection round into the all-task PA-DCT cell
            if policy_id == "PA-DCT":
                hits = [r for r in d["detection"] if r is not None]
                det_all = int(statistics.median(hits)) if hits else None
                for c in cells:
                    if (c["scenario"] == scen and c["policy"] == "PA-DCT"
                            and c["task_type"] == "all"):
                        c["detect_p_adv_round"] = det_all

    return regret_curves, roi_curves, cells


# ---------------------------------------------------------------------
# 3. heatmaps (provider selection by round bucket)
# ---------------------------------------------------------------------

BUCKET = 500

def build_heatmaps(n_seeds: int = 30) -> list[dict]:
    out: list[dict] = []
    for scen in SCENARIOS:
        base = scenario_dir(scen) / "padct"
        if not base.exists():
            continue
        # bucket -> arm -> count
        counts: dict[int, dict[str, int]] = defaultdict(
            lambda: {p: 0 for p in PROVIDERS}
        )
        for sf in list_seeds(base)[:n_seeds]:
            for r in read_jsonl(sf):
                bucket = (r["round"] // BUCKET) * BUCKET
                counts[bucket][r["chosen_arm"]] += 1
        # Normalize per-bucket
        buckets = []
        for bucket in sorted(counts.keys()):
            tot = sum(counts[bucket].values())
            shares = {p: round(counts[bucket][p] / tot, 4) if tot else 0.0
                      for p in PROVIDERS}
            buckets.append({
                "round_lo": bucket,
                "round_hi": bucket + BUCKET,
                "shares": shares,
            })
        out.append({
            "scenario": scen,
            "providers": PROVIDERS,
            "buckets": buckets,
        })
    return out


# ---------------------------------------------------------------------
# 4. ablation deltas
# ---------------------------------------------------------------------

def build_ablations(cells: list[dict]) -> list[dict]:
    out: list[dict] = []
    for scen in SCENARIOS:
        pa = next(
            (c for c in cells
             if c["scenario"] == scen and c["policy"] == "PA-DCT"
             and c["task_type"] == "all"),
            None,
        )
        if not pa:
            continue
        deltas = []
        for ab in ["A1-noContext", "A2-noDiscount", "A3-noPaymentAware",
                   "A4-noThompsonSampling"]:
            ab_cell = next(
                (c for c in cells
                 if c["scenario"] == scen and c["policy"] == ab
                 and c["task_type"] == "all"),
                None,
            )
            if not ab_cell:
                continue
            deltas.append({
                "policy": ab,
                "delta_roi": round(ab_cell["roi_mean"] - pa["roi_mean"], 3),
                "delta_success": round(
                    ab_cell["success_rate_mean"] - pa["success_rate_mean"], 4
                ),
            })
        out.append({"scenario": scen, "deltas": deltas})
    return out


# ---------------------------------------------------------------------
# 5. posteriors (reconstructed from PA-DCT seed_0)
# ---------------------------------------------------------------------

POST_ROUNDS = sorted(set(
    list(range(0, 251, 10))
    + list(range(250, 2001, 50))
    + list(range(2000, 10001, 250))
))

def build_posteriors_for_seed(scenario: str, seed: int = 0) -> list[dict]:
    sf = scenario_dir(scenario) / "padct" / f"seed_{seed:02d}.jsonl"
    if not sf.exists():
        return []
    # running per-arm sums
    n  = {a: 0 for a in PROVIDERS}
    s  = {a: 0.0 for a in PROVIDERS}    # Σ utility
    s2 = {a: 0.0 for a in PROVIDERS}    # Σ utility²
    snapshots: list[dict] = []
    next_target = iter(POST_ROUNDS)
    target = next(next_target, None)

    for r in read_jsonl(sf):
        t = r["round"]
        a = r["chosen_arm"]
        u = r["utility"]
        n[a] += 1
        s[a] += u
        s2[a] += u * u

        while target is not None and t >= target:
            arms = {}
            for arm in PROVIDERS:
                if n[arm] == 0:
                    arms[arm] = {"mean": 0.5, "var": 0.2}
                    continue
                m = s[arm] / n[arm]
                # Sample variance, fall back to obs prior when n=1
                if n[arm] >= 2:
                    var_emp = max(1e-4, s2[arm] / n[arm] - m * m)
                else:
                    var_emp = 0.2
                # Std-error of the mean (this is what the policy "knows about
                # mean utility" — the actual posterior shrinks like 1/n)
                post_var = var_emp / max(n[arm], 1)
                arms[arm] = {
                    "mean": round(m, 4),
                    "var":  round(post_var, 5),
                }
            snapshots.append({"round": target, "arms": arms})
            target = next(next_target, None)
    return snapshots


# ---------------------------------------------------------------------
# 6. runs (round-by-round logs, one seed per scenario, slimmed)
# ---------------------------------------------------------------------

def build_run_for_seed(scenario: str, seed: int = 0) -> list[dict]:
    sf = scenario_dir(scenario) / "padct" / f"seed_{seed:02d}.jsonl"
    if not sf.exists():
        return []
    out: list[dict] = []
    for r in read_jsonl(sf):
        out.append({
            "round":             r["round"],
            "task_type":         r.get("task_type", "T1"),
            "arm":               r["chosen_arm"],
            "cost":              round(r["charged_cost_usdc"], 5),
            "latency":           round(r["latency_s"], 3),
            "quality":           round(r["quality"], 4),
            "failure":           1 if r["failure_flag"] else 0,
            "utility":           round(r["utility"], 4),
            "reward":            round(r["payment_aware_reward"], 4),
            "budget_remaining":  round(r["budget_remaining_usdc"], 4),
        })
    return out


# ---------------------------------------------------------------------
# main
# ---------------------------------------------------------------------

def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "posteriors").mkdir(exist_ok=True)
    (OUT / "runs").mkdir(exist_ok=True)

    print("[1/5] aggregate cells (scenario × policy × all)")
    cells = build_aggregate_cells()
    print(f"      {len(cells)} cells")

    print("[2/5] round-level pass: regret curves, ROI curves, per-task cells")
    regret_curves, roi_curves, cells = build_curves_and_per_task(
        cells, n_seeds=30
    )
    print(f"      {len(regret_curves)} regret curves, "
          f"{len(roi_curves)} ROI curves, {len(cells)} cells (with per-task)")

    print("[3/5] heatmaps (provider selection)")
    heatmaps = build_heatmaps(n_seeds=30)

    print("[4/5] ablation deltas")
    ablations = build_ablations(cells)

    print("[5/5] write summary.json")
    summary = {
        "run_id": "scenario_sweep + ablation_matrix (real)",
        "generated_at": "2026-05-05",
        "params": {
            "nu":     NU,
            "alpha":  ALPHA,
            "rounds": TOTAL_ROUNDS,
            "seeds":  30,
            "budget_usdc": BUDGET_USDC,
            "max_cost_usdc": MAX_COST_USDC,
            "note": (
                "Real fixtures exported from results/scenario_sweep/ and "
                "results/ablation_matrix/. Reward formula: utility = q − ν·f, "
                "PA_reward = (1 − λ_norm)·utility − λ_norm·c̃, "
                "λ_norm = sigmoid(α·burn_excess). "
                "Latency observed and logged per round but not part of reward."
            ),
            "ablation_legend": {
                "A1-noContext":          "no_c — drops contextual posterior split",
                "A2-noDiscount":         "no_d — γ = 1 (no discounting)",
                "A3-noPaymentAware":     "no_p — drops λ-aware cost weighting",
                "A4-noThompsonSampling": "no_ts — greedy posterior mean instead of TS",
            },
        },
        "cells": cells,
        "regret_curves": regret_curves,
        "roi_curves":    roi_curves,
        "heatmaps":      heatmaps,
        "ablations":     ablations,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"      wrote {OUT / 'summary.json'}")

    print("[+] posteriors and runs (PA-DCT seed_00 per scenario)")
    for scen in SCENARIOS:
        src_dir = scenario_dir(scen).relative_to(ROOT)
        snaps = build_posteriors_for_seed(scen, seed=0)
        path = OUT / "posteriors" / f"{scen}_padct_seed0_posteriors.jsonl"
        with path.open("w") as f:
            f.write(f"// Real, reconstructed from {src_dir}/padct/seed_00.jsonl\n")
            for s in snaps:
                f.write(json.dumps(s, separators=(",", ":")) + "\n")
        print(f"      wrote {path} ({len(snaps)} snapshots)")

        run = build_run_for_seed(scen, seed=0)
        rpath = OUT / "runs" / f"{scen}_padct_seed0.jsonl"
        with rpath.open("w") as f:
            f.write(f"// Real run: {src_dir}/padct/seed_00.jsonl (slimmed)\n")
            for r in run:
                f.write(json.dumps(r, separators=(",", ":")) + "\n")
        print(f"      wrote {rpath} ({len(run)} rounds)")

    print("done.")


if __name__ == "__main__":
    main()
