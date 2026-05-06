"""PA-DCT ablation matrix — 4 named components × 3 scenarios × 30 seeds.

PA-DCT = Payment-Aware Discounted Contextual Thompson Sampling. For each of
the four named components, we run a sweep with that component disabled, on
each of the three scenarios. Compared to the full method, each ablation
isolates the contribution of one component.

Ablations:
  - no_p:  enable_payment_aware=False — λ_norm forced to 0 at decision time;
           policy ranks arms by sampled utility only (no cost-quality trade-off).
  - no_d:  enable_discount=False — γ = 1 for both q and c posteriors. The
           policy never forgets old observations (vanilla TS, no adaptation).
  - no_c:  enable_contextual=False — collapse to a single posterior per arm
           (loses per-task-type granularity).
  - no_ts: enable_ts=False — use posterior_mean instead of sampling
           (Bayesian greedy; no exploration noise).

Scenarios:
  - S1: StationaryScenario()
  - S2: MidOutageScenario(outage_start=3000, outage_end=5500, rate=0.30)
  - S3: PremiumDropScenario(shock_round=1000, price_multiplier=0.2)

Output: results/ablation_matrix/<ablation>/<scenario>/padct/seed_NN.jsonl
And:    results/ablation_matrix/<ablation>/<scenario>/summary.jsonl
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

from numpy.random import default_rng

from pilot402.core import ProviderId
from pilot402.core.config import load_config
from pilot402.policies import PADCTPolicy
from pilot402.pregen import JsonlPregenStore
from pilot402.pregen.tasks import load_all_tasks
from pilot402.runtime import (
    JsonlRecorder,
    NaiveEncoder,
    RewardCalculator,
    Wallet,
    run_one_seed,
)
from pilot402.scenarios import (
    MidOutageScenario,
    PremiumDropScenario,
    StationaryScenario,
    build_scenario,
)
from pilot402.core import ScenarioConfig, ScenarioId


PROVIDER_PRICES = {
    ProviderId.P_CHEAP: 0.0005,
    ProviderId.P_MID: 0.002,
    ProviderId.P_PREMIUM: 0.01,
    ProviderId.P_ADV: 0.002,
    ProviderId.P_FLAKY: 0.002,
}

# Ablation name → kwargs to override on PADCTPolicy
ABLATIONS = {
    "no_p": {"enable_payment_aware": False},
    "no_d": {"enable_discount": False},
    "no_c": {"enable_contextual": False},
    "no_ts": {"enable_ts": False},
}


def _build_scenario_for(scen_name: str, master_seed: int):
    """Build the scenario object matching the locked S1/S2/S3 designs."""
    if scen_name == "S1":
        return StationaryScenario()
    if scen_name == "S2":
        # Same params as run_scenario_sweep.py uses for S2.
        cfg = ScenarioConfig(
            name=ScenarioId.S2_DEGRADATION,
            kwargs={"outage_start": 3000, "outage_end": 5500,
                    "outage_failure_rate": 0.30},
        )
        return build_scenario(cfg, master_seed=master_seed)
    if scen_name == "S3":
        return PremiumDropScenario(shock_round=1000, price_multiplier=0.2)
    raise ValueError(f"Unknown scenario: {scen_name}")


def _is_complete(log_path: Path, num_rounds: int) -> bool:
    """A cell is complete iff (a) it has all num_rounds lines, OR
    (b) it ended in bankruptcy (last record's budget_remaining < cheapest price).

    The bankruptcy case matters for the no_p ablation, which over-spends and
    runs out of budget around round 7000-9000 — those runs ARE complete
    (the loop legitimately stopped because no arm was affordable)."""
    if not log_path.is_file():
        return False
    lines = [l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    while lines:
        try:
            json.loads(lines[-1])
            break
        except json.JSONDecodeError:
            lines.pop()
    if not lines:
        return False
    if len(lines) >= num_rounds:
        return True
    # Bankruptcy check: last record's remaining budget is below the cheapest arm.
    last = json.loads(lines[-1])
    return last.get("budget_remaining_usdc", float("inf")) < min(PROVIDER_PRICES.values())


def _row_from_log(seed_idx: int, log_path: Path) -> dict:
    lines = [l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    while lines:
        try:
            json.loads(lines[-1])
            break
        except json.JSONDecodeError:
            lines.pop()
    n = len(lines)
    cum_pa, cum_q, total_spent, n_failures = 0.0, 0.0, 0.0, 0
    arm_counts: dict[str, int] = {}
    for line in lines:
        d = json.loads(line)
        cum_pa += d.get("payment_aware_reward", 0.0)
        cum_q += d.get("quality", 0.0)
        total_spent += d.get("charged_cost_usdc", 0.0)
        if d.get("failure_flag"):
            n_failures += 1
        arm = d.get("chosen_arm")
        if arm is not None:
            arm_counts[arm] = arm_counts.get(arm, 0) + 1
    return {
        "seed": seed_idx, "rounds": n, "total_spent": total_spent,
        "failures": n_failures, "cum_pa_reward": cum_pa,
        "mean_quality": cum_q / n if n else 0.0,
        "arm_counts": arm_counts,
    }


def run_one(cfg, ablation: str, scenario_name: str, seed: int,
            tasks: list, store, log_path: Path) -> dict:
    """Run one (ablation, scenario, seed) cell."""
    scenario = _build_scenario_for(scenario_name, master_seed=seed)
    sc_cfg = ScenarioConfig(
        name=getattr(ScenarioId, {
            "S1": "S1_STATIONARY", "S2": "S2_DEGRADATION", "S3": "S3_PRICE_SHOCK"
        }[scenario_name]),
    )
    cfg = cfg.model_copy(update={"scenario": sc_cfg})

    wallet = Wallet(
        total_usdc=cfg.budget.total_usdc, lambda_0=cfg.budget.lambda_0,
        alpha=cfg.budget.alpha, target_burn_rate=cfg.budget.target_burn_rate,
    )
    kwargs = ABLATIONS[ablation]
    policy = PADCTPolicy(
        rng=default_rng(seed * 6271 + 13),
        wallet=wallet,
        provider_costs=PROVIDER_PRICES,
        max_provider_cost=0.01,
        **kwargs,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.unlink(missing_ok=True)
    with JsonlRecorder(path=log_path) as rec:
        run_one_seed(
            cfg, tasks=tasks, store=store, policy=policy, wallet=wallet,
            encoder=NaiveEncoder(),
            reward_calc=RewardCalculator(nu=cfg.reward.nu),
            recorder=rec, seed=seed, scenario=scenario, progress_every=None,
        )
    return _row_from_log(seed, log_path)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("experiments/main.yaml"))
    parser.add_argument("--num-seeds", type=int, default=30)
    parser.add_argument("--out-dir", type=Path,
                        default=Path("results/ablation_matrix"))
    parser.add_argument("--ablations", nargs="+",
                        default=list(ABLATIONS.keys()),
                        choices=list(ABLATIONS.keys()))
    parser.add_argument("--scenarios", nargs="+", default=["S1", "S2", "S3"],
                        choices=["S1", "S2", "S3"])
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    if args.num_seeds is not None:
        cfg = cfg.model_copy(update={"num_seeds": args.num_seeds})

    tasks = load_all_tasks(cfg.paths.tasks_dir)
    store = JsonlPregenStore(cfg.paths.pregen_dir)
    print(f"Loaded {len(tasks)} tasks, {len(store)} pregen records.",
          file=sys.stderr)
    total_cells = len(args.ablations) * len(args.scenarios) * cfg.num_seeds
    print(f"Plan: {len(args.ablations)} ablations × {len(args.scenarios)} scenarios"
          f" × {cfg.num_seeds} seeds = {total_cells} cells",
          file=sys.stderr)

    rows_by_combo: dict[tuple[str, str], list[dict]] = defaultdict(list)
    completed = 0
    for abl in args.ablations:
        for scen in args.scenarios:
            for seed_idx in range(cfg.num_seeds):
                log_path = (args.out_dir / abl / scen / "padct"
                            / f"seed_{seed_idx:02d}.jsonl")
                if _is_complete(log_path, cfg.num_rounds):
                    rows_by_combo[(abl, scen)].append(
                        _row_from_log(seed_idx, log_path)
                    )
                    completed += 1

    if completed:
        print(f"resume: {completed}/{total_cells} cells complete; running rest",
              file=sys.stderr)

    done = completed
    for abl in args.ablations:
        for scen in args.scenarios:
            for seed_idx in range(cfg.num_seeds):
                if any(r["seed"] == seed_idx for r in rows_by_combo[(abl, scen)]):
                    continue
                log_path = (args.out_dir / abl / scen / "padct"
                            / f"seed_{seed_idx:02d}.jsonl")
                row = run_one(cfg, abl, scen, seed_idx, tasks, store, log_path)
                rows_by_combo[(abl, scen)].append(row)
                done += 1
                print(f"[{done}/{total_cells}] {abl} {scen} seed={seed_idx}"
                      f" PA={row['cum_pa_reward']:.0f}"
                      f" q={row['mean_quality']:.3f}",
                      file=sys.stderr)

    # Persist summaries per (ablation, scenario)
    for (abl, scen), rows in rows_by_combo.items():
        summary_path = args.out_dir / abl / scen / "summary.jsonl"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        with summary_path.open("w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")

    # Print full matrix
    print()
    print("=" * 90)
    print(f"{'Ablation':<10}{'S1 PA':>16}{'S2 PA':>16}{'S3 PA':>16}{'note':>16}")
    print("-" * 74)
    for abl in args.ablations:
        line = f"{abl:<10}"
        for scen in args.scenarios:
            seeds = rows_by_combo[(abl, scen)]
            if not seeds:
                line += f"{'--':>16}"
                continue
            pa = [s["cum_pa_reward"] for s in seeds]
            mean = statistics.mean(pa)
            std = statistics.stdev(pa) if len(pa) > 1 else 0
            line += f"{mean:>10.0f}±{std:>4.0f}"
        print(line)
    print("=" * 90)
    return 0


if __name__ == "__main__":
    sys.exit(main())
