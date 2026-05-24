"""S3 validation: Premium Promo at round 1000 (dual-posterior PA-DCT).

Pre-shock 0-1000: original calibration (cheap $0.0005, mid $0.002, premium $0.01).
Post-shock 1000-10000: premium price drops to $0.002 (matches mid). 9000 rounds
of post-shock learning give the dual-posterior PA-DCT time to update its cost
posterior, detect the price shift, and migrate.

Implemented via ``PremiumDropScenario(shock_round=1000, price_multiplier=0.2)``.

Paper claim with this scenario: in S3, PA-DCT attains the best non-oracle
PA-gap/$T$ in Table~\\ref{tab:main} (0.121, lower than Always-P-mid at
0.129) and migrates its premium share from ~4% pre-shock to ~60% by
round 10000 (see Appendix D premium-share trajectory). The combined
quality, ROI, and PA-gap/$T$ improvement over fixed-arm policies is
what evidences active price-shock adaptation via the cost posterior;
S3 numbers are taken as canonical from this run.

Output: results/scenario_sweep_s3promo/
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

from numpy.random import default_rng

from pilot402.core import ProviderId, ScenarioConfig, ScenarioId
from pilot402.core.config import load_config
from pilot402.policies import (
    BudgetRulePolicy,
    ContextualBTSPolicy,
    ContextualDSTSPolicy,
    LinCBwKPolicy,
    PADCTPolicy,
    PMGreedyPolicy,
    RandomPolicy,
    SWTSPolicy,
    always_cheapest,
    always_mid,
    always_premium,
)
from pilot402.pregen import JsonlPregenStore
from pilot402.pregen.tasks import load_all_tasks
from pilot402.runtime import (
    JsonlRecorder,
    NaiveEncoder,
    RewardCalculator,
    Wallet,
    run_one_seed,
    run_true_oracle_seed,
)
from pilot402.scenarios import PremiumDropScenario


PROVIDER_PRICES = {
    ProviderId.P_CHEAP: 0.0005,
    ProviderId.P_MID: 0.002,
    ProviderId.P_PREMIUM: 0.01,
    ProviderId.P_ADV: 0.002,
    ProviderId.P_FLAKY: 0.002,
}

POLICY_ORDER = [
    "random",
    "always_cheapest", "always_mid", "always_premium",
    "budget_rule",
    "pm_greedy",
    "lincbwk",
    "contextual_dsts", "contextual_bts",
    "sw_ts",
    "padct",
]


def _pm_greedy_threshold() -> float:
    import os
    raw = os.environ.get("PM_GREEDY_THRESHOLD")
    return float(raw) if raw else 0.7


def _lincbwk_beta() -> float:
    import os
    raw = os.environ.get("LINCBWK_BETA")
    return float(raw) if raw else 1.0


def _make_policy(name: str, *, wallet, seed: int, scenario=None, num_rounds: int = 10000):
    if name == "random":          return RandomPolicy(rng=default_rng(seed * 7919 + 1))
    if name == "always_cheapest": return always_cheapest()
    if name == "always_mid":      return always_mid()
    if name == "always_premium":  return always_premium()
    if name == "budget_rule":
        return BudgetRulePolicy(wallet=wallet, provider_prices=PROVIDER_PRICES)
    if name == "contextual_dsts":
        # Drift-aware but no wallet pressure / no cost learning.
        # Distinct prime keeps RNG stream independent from PA-DCT under the
        # same paired seed (paired-seed integrity from the loop's sampler).
        return ContextualDSTSPolicy(
            rng=default_rng(seed * 4861 + 17),
            provider_ids=tuple(PROVIDER_PRICES.keys()),
        )
    if name == "contextual_bts":
        # Cost-learning but no discount; raw r/c ratio scoring.
        return ContextualBTSPolicy(
            rng=default_rng(seed * 5023 + 19),
            provider_costs=PROVIDER_PRICES,
        )
    if name == "lincbwk":
        return LinCBwKPolicy(
            wallet=wallet,
            provider_ids=tuple(PROVIDER_PRICES.keys()),
            total_rounds=num_rounds,
            beta=_lincbwk_beta(),
        )
    if name == "pm_greedy":
        if scenario is None:
            raise ValueError("pm_greedy requires the scenario kwarg")
        spec_prices = dict(PROVIDER_PRICES)
        def _listed_price(round_idx: int, pid: ProviderId) -> float:
            return scenario.effective_price(round_idx, pid, spec_prices[pid])
        return PMGreedyPolicy(
            listed_price_fn=_listed_price,
            provider_ids=tuple(PROVIDER_PRICES.keys()),
            threshold=_pm_greedy_threshold(),
        )
    if name == "sw_ts":
        return SWTSPolicy(
            rng=default_rng(seed * 5867 + 23),
            provider_ids=tuple(PROVIDER_PRICES.keys()),
        )
    if name == "padct":
        return PADCTPolicy(
            rng=default_rng(seed * 6271 + 13),
            wallet=wallet,
            provider_costs=PROVIDER_PRICES,
            max_provider_cost=0.01,
        )
    raise ValueError(name)


def _build_scenario():
    """S3: premium price drops to mid price at round 1000.
    From round 1000 onward, premium $0.01 × 0.2 = $0.002 = mid price.
    """
    return PremiumDropScenario(
        shock_round=1000,
        price_multiplier=0.2,
    )


def _is_complete(log_path: Path, num_rounds: int) -> bool:
    if not log_path.is_file():
        return False
    lines = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    while lines:
        try:
            json.loads(lines[-1]); break
        except json.JSONDecodeError:
            lines.pop()
    if not lines: return False
    n = len(lines)
    if n >= num_rounds: return True
    last = json.loads(lines[-1])
    return last.get("budget_remaining_usdc", 0) < min(PROVIDER_PRICES.values())


def _row_from_log(policy_name: str, seed_idx: int, log_path: Path, num_rounds: int) -> dict:
    lines = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    while lines:
        try: json.loads(lines[-1]); break
        except json.JSONDecodeError: lines.pop()
    n = len(lines)
    cum_pa, cum_q, total_spent, n_failures = 0.0, 0.0, 0.0, 0
    arm_counts: dict[str, int] = {}
    last_remaining = 0.0
    for line in lines:
        d = json.loads(line)
        cum_pa += d.get("payment_aware_reward", 0.0)
        cum_q += d.get("quality", 0.0)
        total_spent += d.get("charged_cost_usdc", 0.0)
        if d.get("failure_flag"): n_failures += 1
        arm = d.get("chosen_arm")
        if arm is not None: arm_counts[arm] = arm_counts.get(arm, 0) + 1
        last_remaining = d.get("budget_remaining_usdc", 0.0)
    bankrupt = n < num_rounds and last_remaining < min(PROVIDER_PRICES.values())
    return {
        "policy": policy_name, "seed": seed_idx, "rounds": n,
        "bankrupt": bankrupt, "total_spent": total_spent,
        "failures": n_failures, "cum_pa_reward": cum_pa, "cum_q": cum_q,
        # Legacy: served-only mean (Σq / n). Downstream ROI = mean * rounds / spend works.
        "mean_quality": cum_q / n if n else 0.0,
        # New full-horizon fields, see run_scenario_sweep.py for schema rationale.
        "cum_quality": cum_q,
        "q_bar_T": cum_q / num_rounds if num_rounds else 0.0,
        "arm_counts": arm_counts,
    }


def _run_policy_cell(cfg, *, policy_name, seed, tasks, store, log_path):
    scenario = _build_scenario()
    wallet = Wallet(
        total_usdc=cfg.budget.total_usdc, lambda_0=cfg.budget.lambda_0,
        alpha=cfg.budget.alpha, target_burn_rate=cfg.budget.target_burn_rate,
    )
    policy = _make_policy(
        policy_name,
        wallet=wallet,
        seed=seed,
        scenario=scenario,
        num_rounds=cfg.num_rounds,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    # Truncate any leftover partial log instead of unlink so we work cleanly
    # on filesystems that allow create-but-not-delete (e.g. some FUSE mounts).
    try:
        log_path.unlink(missing_ok=True)
    except PermissionError:
        log_path.open("w").close()
    with JsonlRecorder(path=log_path) as rec:
        run_one_seed(
            cfg, tasks=tasks, store=store, policy=policy, wallet=wallet,
            encoder=NaiveEncoder(), reward_calc=RewardCalculator(nu=cfg.reward.nu),
            recorder=rec, seed=seed, scenario=scenario, progress_every=None,
        )
    return _row_from_log(policy_name, seed, log_path, cfg.num_rounds)


def _run_oracle_cell(cfg, *, seed, tasks, store, log_path):
    scenario = _build_scenario()
    wallet = Wallet(
        total_usdc=cfg.budget.total_usdc, lambda_0=cfg.budget.lambda_0,
        alpha=cfg.budget.alpha, target_burn_rate=cfg.budget.target_burn_rate,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        log_path.unlink(missing_ok=True)
    except PermissionError:
        log_path.open("w").close()
    with JsonlRecorder(path=log_path) as rec:
        run_true_oracle_seed(
            cfg, tasks=tasks, store=store, wallet=wallet,
            encoder=NaiveEncoder(), reward_calc=RewardCalculator(nu=cfg.reward.nu),
            recorder=rec, seed=seed, scenario=scenario,
        )
    return _row_from_log("oracle", seed, log_path, cfg.num_rounds)


def _summary(rows: list[dict]) -> str:
    by = defaultdict(list)
    for r in rows: by[r["policy"]].append(r)
    lines: list[str] = []
    header = (f"{'policy':<18}{'rounds':>8}{'bnkrpt':>9}{'spent':>10}"
              f"{'fails':>8}{'cum_PA':>16}{'mean_q':>9}{'q-rate':>10}")
    lines.append(header); lines.append("-"*len(header))
    for name in POLICY_ORDER + ["oracle"]:
        if name not in by: continue
        ss = by[name]
        rounds_avg = statistics.mean(s["rounds"] for s in ss)
        spent = statistics.mean(s["total_spent"] for s in ss)
        fails = statistics.mean(s["failures"] for s in ss)
        pa = [s["cum_pa_reward"] for s in ss]
        mq = [s["mean_quality"] for s in ss]
        bnkrpt = sum(1 for s in ss if s["bankrupt"])
        lines.append(
            f"{name:<18}{rounds_avg:>8.0f}{bnkrpt:>5}/{len(ss):<3}"
            f"${spent:>8.2f}{fails:>8.1f}"
            f"{statistics.mean(pa):>10.1f}±{(statistics.stdev(pa) if len(pa)>1 else 0):>5.1f}"
            f"{statistics.mean(mq):>9.3f}"
            f"{statistics.mean(mq):>10.3f}"
        )
    lines.append("")
    lines.append("=== Arm shares (mean across seeds, per 10000 rounds) ===")
    arm_h = f"{'policy':<18}" + "".join(f"{a.value:>11}" for a in ProviderId)
    lines.append(arm_h); lines.append("-"*len(arm_h))
    for name in POLICY_ORDER + ["oracle"]:
        if name not in by: continue
        row = f"{name:<18}"
        for arm in ProviderId:
            counts = [s["arm_counts"].get(arm.value, 0) for s in by[name]]
            row += f"{statistics.mean(counts):>11.0f}"
        lines.append(row)
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("experiments/main.yaml"))
    parser.add_argument("--num-seeds", type=int, default=30)
    parser.add_argument("--num-rounds", type=int, default=None)
    parser.add_argument("--out-dir", type=Path, default=Path("results/scenario_sweep_s3promo"))
    parser.add_argument("--policies", nargs="+", default=POLICY_ORDER)
    parser.add_argument("--skip-oracle", action="store_true")
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    # Logging fidelity: tag every JSONL row with the actual scenario being
    # run, not the YAML default (which is S1). The scenario *object* is
    # built separately in _build_scenario(); this just keeps cfg.scenario
    # metadata consistent with the simulation actually being run.
    cfg = cfg.model_copy(update={
        "scenario": ScenarioConfig(
            name=ScenarioId.S3_PRICE_SHOCK,
            kwargs={"shock_round": 1000, "price_multiplier": 0.2},
        )
    })
    if args.num_seeds is not None: cfg = cfg.model_copy(update={"num_seeds": args.num_seeds})
    if args.num_rounds is not None: cfg = cfg.model_copy(update={"num_rounds": args.num_rounds})

    tasks = load_all_tasks(cfg.paths.tasks_dir)
    store = JsonlPregenStore(cfg.paths.pregen_dir)
    print(f"Loaded {len(tasks)} tasks, {len(store)} pregen records.", file=sys.stderr)
    print(f"S3 Promo: cheap $0.0005, mid $0.002, premium $0.01 → $0.002 at round 1000",
          file=sys.stderr)
    print(f"  Pre-shock 0-1000: original calibration (premium expensive)",
          file=sys.stderr)
    print(f"  Post-shock 1000-10000: premium = mid price (9000 rounds for adaptation)",
          file=sys.stderr)

    total_cells = len(args.policies) * cfg.num_seeds + (0 if args.skip_oracle else cfg.num_seeds)
    rows: list[dict] = []
    completed = 0
    # Resume scan
    for policy_name in args.policies:
        for seed_idx in range(cfg.num_seeds):
            log_path = args.out_dir / policy_name / f"seed_{seed_idx:02d}.jsonl"
            if _is_complete(log_path, cfg.num_rounds):
                rows.append(_row_from_log(policy_name, seed_idx, log_path, cfg.num_rounds))
                completed += 1
    if not args.skip_oracle:
        for seed_idx in range(cfg.num_seeds):
            log_path = args.out_dir / "oracle" / f"seed_{seed_idx:02d}.jsonl"
            if _is_complete(log_path, cfg.num_rounds):
                rows.append(_row_from_log("oracle", seed_idx, log_path, cfg.num_rounds))
                completed += 1
    if completed:
        print(f"resume: {completed}/{total_cells} cells complete; running rest", file=sys.stderr)

    completed_keys = {(r["policy"], r["seed"]) for r in rows}
    done = completed
    for policy_name in args.policies:
        for seed_idx in range(cfg.num_seeds):
            if (policy_name, seed_idx) in completed_keys: continue
            log_path = args.out_dir / policy_name / f"seed_{seed_idx:02d}.jsonl"
            row = _run_policy_cell(cfg, policy_name=policy_name, seed=seed_idx,
                                   tasks=tasks, store=store, log_path=log_path)
            rows.append(row); done += 1
            print(f"[{done}/{total_cells}] {policy_name} seed={seed_idx}"
                  f" rounds={row['rounds']} spent=${row['total_spent']:.2f}"
                  f" PA={row['cum_pa_reward']:.0f} q={row['mean_quality']:.3f}",
                  file=sys.stderr)
    if not args.skip_oracle:
        for seed_idx in range(cfg.num_seeds):
            if ("oracle", seed_idx) in completed_keys: continue
            log_path = args.out_dir / "oracle" / f"seed_{seed_idx:02d}.jsonl"
            row = _run_oracle_cell(cfg, seed=seed_idx, tasks=tasks, store=store, log_path=log_path)
            rows.append(row); done += 1
            print(f"[{done}/{total_cells}] oracle seed={seed_idx}"
                  f" rounds={row['rounds']} spent=${row['total_spent']:.2f}"
                  f" PA={row['cum_pa_reward']:.0f}", file=sys.stderr)

    summary_path = args.out_dir / "summary.jsonl"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w", encoding="utf-8") as fh:
        for r in rows: fh.write(json.dumps(r) + "\n")

    print()
    print("=" * 100)
    print(_summary(rows))
    print("=" * 100)
    return 0


if __name__ == "__main__":
    sys.exit(main())
