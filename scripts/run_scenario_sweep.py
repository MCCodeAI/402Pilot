"""M3.E full sweep: S1/S2/S3 × {baselines + PA-DCT} × N seeds + True Oracle.

For each scenario in {S1_STATIONARY, S2_DEGRADATION, S3_PRICE_SHOCK}:

* 6 policies × N seeds × ``cfg.num_rounds`` rounds via ``run_one_seed``.
* 1 True Oracle × N seeds × same rounds via ``run_true_oracle_seed``.

Logs land at::

    results/scenario_sweep/<scenario_id>/<policy>/seed_NN.jsonl
    results/scenario_sweep/<scenario_id>/oracle/seed_NN.jsonl
    results/scenario_sweep/<scenario_id>/summary.jsonl

A per-scenario comparison table prints to stdout.

Usage::

    python -m scripts.run_scenario_sweep                        # full sweep
    python -m scripts.run_scenario_sweep --num-seeds 3          # quick
    python -m scripts.run_scenario_sweep --num-rounds 1000      # short
    python -m scripts.run_scenario_sweep --scenarios S1 S3      # subset

Resume support: a (scenario, policy, seed) cell whose JSONL already exists
and is either complete (≥ num_rounds lines) or bankrupted (last
budget_remaining_usdc < cheapest price) is skipped on restart.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

from numpy.random import default_rng

from pilot402.core import (
    ExperimentConfig,
    ProviderId,
    ScenarioConfig,
    ScenarioId,
)
from pilot402.core.config import load_config
from pilot402.policies import (
    BudgetRulePolicy,
    PADCTPolicy,
    RandomPolicy,
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
from pilot402.scenarios import build_scenario


PROVIDER_PRICES = {
    ProviderId.P_CHEAP: 0.0005,
    ProviderId.P_MID: 0.002,
    ProviderId.P_PREMIUM: 0.01,
    ProviderId.P_ADV: 0.002,
    ProviderId.P_FLAKY: 0.002,
}


POLICY_ORDER = [
    "random",
    "always_cheapest",
    "always_mid",
    "always_premium",
    "budget_rule",
    "padct",
]


def _make_policy(name: str, *, wallet, seed: int):
    if name == "random":
        return RandomPolicy(rng=default_rng(seed * 7919 + 1))
    if name == "always_cheapest":
        return always_cheapest()
    if name == "always_mid":
        return always_mid()
    if name == "always_premium":
        return always_premium()
    if name == "budget_rule":
        return BudgetRulePolicy(wallet=wallet, provider_prices=PROVIDER_PRICES)
    if name == "padct":
        return PADCTPolicy(
            rng=default_rng(seed * 6271 + 13),
            wallet=wallet,
            provider_costs=PROVIDER_PRICES,
            max_provider_cost=0.01,
        )
    raise ValueError(f"Unknown policy name: {name!r}")


def _scenario_config(scenario_id: ScenarioId) -> ScenarioConfig:
    """Locked M3.E scenario parameters."""
    if scenario_id == ScenarioId.S1_STATIONARY:
        return ScenarioConfig(name=scenario_id)
    if scenario_id == ScenarioId.S2_DEGRADATION:
        return ScenarioConfig(
            name=scenario_id,
            kwargs={
                "outage_start": 3000,
                "outage_end": 5500,
                "outage_failure_rate": 0.30,
            },
        )
    if scenario_id == ScenarioId.S3_PRICE_SHOCK:
        return ScenarioConfig(
            name=scenario_id,
            kwargs={"shock_round": 1000, "price_multiplier": 0.2},
        )
    raise ValueError(scenario_id)


def _row_from_log(policy_name: str, seed_idx: int, log_path: Path,
                  num_rounds: int) -> dict:
    """Reconstruct a summary row from a per-cell JSONL log."""
    lines = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    # Drop a trailing truncated line (timeout mid-write).
    while lines:
        try:
            json.loads(lines[-1])
            break
        except json.JSONDecodeError:
            lines.pop()
    n = len(lines)
    cum_pa = 0.0
    cum_util = 0.0
    quality_sum = 0.0
    total_spent = 0.0
    n_failures = 0
    arm_counts: dict[str, int] = {}
    last_remaining = 0.0
    for line in lines:
        d = json.loads(line)
        cum_pa += d.get("payment_aware_reward", 0.0)
        cum_util += d.get("utility", 0.0)
        quality_sum += d.get("quality", 0.0)
        total_spent += d.get("charged_cost_usdc", 0.0)
        if d.get("failure_flag"):
            n_failures += 1
        arm = d.get("chosen_arm")
        if arm is not None:
            arm_counts[arm] = arm_counts.get(arm, 0) + 1
        last_remaining = d.get("budget_remaining_usdc", 0.0)
    bankrupted = n < num_rounds and last_remaining < min(PROVIDER_PRICES.values())
    return {
        "policy": policy_name,
        "seed": seed_idx,
        "rounds": n,
        "bankrupt": n < num_rounds and bankrupted,
        "bankruptcy_round": n if bankrupted else None,
        "total_spent": total_spent,
        "failures": n_failures,
        "cum_pa_reward": cum_pa,
        "cum_utility": cum_util,
        # Legacy semantics preserved: mean_quality is served-rounds-only mean
        # (Σ q_t / n). Downstream scripts that compute ROI as
        # mean_quality * rounds / total_spent continue to work unchanged.
        "mean_quality": (quality_sum / n) if n else 0.0,
        # New full-horizon fields. Use q_bar_T (= Σ q_t / T, unserved rounds
        # count as zero) for cross-policy quality comparisons; bankruptcy
        # mid-run is correctly penalised because the denominator stays at T.
        "cum_quality": quality_sum,
        "q_bar_T": (quality_sum / num_rounds) if num_rounds else 0.0,
        "arm_counts": arm_counts,
    }


def _is_complete(log_path: Path, num_rounds: int) -> bool:
    """A cell is complete iff its log is full-rounds OR cleanly bankrupted.

    Robust to a truncated trailing line (from a timeout mid-write): we drop
    any unparseable tail line and re-evaluate. If the resulting log is
    short of num_rounds and not bankrupted, the cell is treated as
    incomplete and will be re-run from scratch by the caller.
    """
    if not log_path.is_file():
        return False
    lines = [line for line in log_path.read_text(encoding="utf-8").splitlines()
             if line.strip()]
    # Drop a trailing truncated line if any.
    while lines:
        try:
            json.loads(lines[-1])
            break
        except json.JSONDecodeError:
            lines.pop()
    if not lines:
        return False
    n = len(lines)
    if n >= num_rounds:
        return True
    last = json.loads(lines[-1])
    return last.get("budget_remaining_usdc", 0) < min(PROVIDER_PRICES.values())


def run_one_cell(
    cfg: ExperimentConfig,
    scenario_id: ScenarioId,
    *,
    policy_name: str,
    seed: int,
    tasks: list,
    store: JsonlPregenStore,
    log_path: Path,
) -> dict:
    """Run one (scenario, policy, seed) trace and return its summary row."""
    sc_cfg = _scenario_config(scenario_id)
    scenario = build_scenario(sc_cfg, master_seed=seed)
    cfg = cfg.model_copy(update={"scenario": sc_cfg})

    wallet = Wallet(
        total_usdc=cfg.budget.total_usdc,
        lambda_0=cfg.budget.lambda_0,
        alpha=cfg.budget.alpha,
        target_burn_rate=cfg.budget.target_burn_rate,
    )
    policy = _make_policy(policy_name, wallet=wallet, seed=seed)
    encoder = NaiveEncoder()
    reward_calc = RewardCalculator(nu=cfg.reward.nu)

    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.unlink(missing_ok=True)
    with JsonlRecorder(path=log_path) as rec:
        run_one_seed(
            cfg, tasks=tasks, store=store,
            policy=policy, wallet=wallet,
            encoder=encoder, reward_calc=reward_calc,
            recorder=rec, seed=seed, scenario=scenario,
            progress_every=None,
        )
    return _row_from_log(policy_name, seed, log_path, cfg.num_rounds)


def run_oracle_cell(
    cfg: ExperimentConfig,
    scenario_id: ScenarioId,
    *,
    seed: int,
    tasks: list,
    store: JsonlPregenStore,
    log_path: Path,
) -> dict:
    sc_cfg = _scenario_config(scenario_id)
    scenario = build_scenario(sc_cfg, master_seed=seed)
    cfg = cfg.model_copy(update={"scenario": sc_cfg})

    wallet = Wallet(
        total_usdc=cfg.budget.total_usdc,
        lambda_0=cfg.budget.lambda_0,
        alpha=cfg.budget.alpha,
        target_burn_rate=cfg.budget.target_burn_rate,
    )
    encoder = NaiveEncoder()
    reward_calc = RewardCalculator(nu=cfg.reward.nu)

    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.unlink(missing_ok=True)
    with JsonlRecorder(path=log_path) as rec:
        run_true_oracle_seed(
            cfg, tasks=tasks, store=store,
            wallet=wallet, encoder=encoder,
            reward_calc=reward_calc,
            recorder=rec, seed=seed, scenario=scenario,
        )
    return _row_from_log("oracle", seed, log_path, cfg.num_rounds)


def _summarize_scenario(scenario_id: ScenarioId, rows: list[dict]) -> str:
    by_policy: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_policy[r["policy"]].append(r)

    lines: list[str] = []
    lines.append(f"=== {scenario_id.value} ===")
    header = (
        f"{'policy':<18}{'rounds':>8}{'bnkrpt':>9}"
        f"{'spent':>10}{'fails':>8}"
        f"{'cum_PA_reward':>22}{'mean_q':>9}"
    )
    lines.append(header)
    lines.append("-" * len(header))
    order = POLICY_ORDER + ["oracle"]
    for name in order:
        if name not in by_policy:
            continue
        ss = by_policy[name]
        rounds = [s["rounds"] for s in ss]
        spent = [s["total_spent"] for s in ss]
        fails = [s["failures"] for s in ss]
        pa = [s["cum_pa_reward"] for s in ss]
        q = [s["mean_quality"] for s in ss]
        bnkrpt = sum(1 for s in ss if s["bankrupt"])
        lines.append(
            f"{name:<18}"
            f"{statistics.mean(rounds):>8.0f}"
            f"{bnkrpt:>5}/{len(ss):<3}"
            f"${statistics.mean(spent):>8.2f}"
            f"{statistics.mean(fails):>8.1f}"
            f"{statistics.mean(pa):>14.1f}±{statistics.stdev(pa) if len(pa) > 1 else 0:>5.1f}"
            f"{statistics.mean(q):>9.3f}"
        )

    # Arm shares
    lines.append("")
    lines.append(f"--- {scenario_id.value} arm shares (mean across seeds) ---")
    arm_header = f"{'policy':<18}" + "".join(f"{a.value:>11}" for a in ProviderId)
    lines.append(arm_header)
    lines.append("-" * len(arm_header))
    for name in order:
        if name not in by_policy:
            continue
        row = f"{name:<18}"
        ss = by_policy[name]
        for arm in ProviderId:
            counts = [s["arm_counts"].get(arm.value, 0) for s in ss]
            row += f"{statistics.mean(counts):>11.0f}"
        lines.append(row)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("experiments/main.yaml"))
    parser.add_argument("--num-seeds", type=int, default=None)
    parser.add_argument("--num-rounds", type=int, default=None)
    parser.add_argument(
        "--out-dir", type=Path, default=Path("results/scenario_sweep"),
    )
    parser.add_argument(
        "--scenarios", nargs="+",
        default=["S1", "S2", "S3"],
        choices=["S1", "S2", "S3"],
    )
    parser.add_argument(
        "--policies", nargs="+",
        default=POLICY_ORDER,
        choices=POLICY_ORDER,
    )
    parser.add_argument(
        "--skip-oracle", action="store_true",
        help="Skip True Oracle runs (saves ~1/7 of total compute)",
    )
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    if args.num_seeds is not None:
        cfg = cfg.model_copy(update={"num_seeds": args.num_seeds})
    if args.num_rounds is not None:
        cfg = cfg.model_copy(update={"num_rounds": args.num_rounds})

    tasks = load_all_tasks(cfg.paths.tasks_dir)
    store = JsonlPregenStore(cfg.paths.pregen_dir)
    print(f"Loaded {len(tasks)} tasks and {len(store)} pregen records.",
          file=sys.stderr)

    scenarios = [ScenarioId(s) for s in args.scenarios]

    cells_per_scenario = len(args.policies) * cfg.num_seeds + (
        0 if args.skip_oracle else cfg.num_seeds
    )
    total_cells = cells_per_scenario * len(scenarios)
    print(
        f"Sweep plan: {len(scenarios)} scenarios × ({len(args.policies)} policies"
        f" + {'no oracle' if args.skip_oracle else 'oracle'}) × {cfg.num_seeds} seeds"
        f" = {total_cells} cells, {cfg.num_rounds} rounds each",
        file=sys.stderr,
    )

    all_rows_by_scenario: dict[ScenarioId, list[dict]] = {}
    completed = 0
    for sid in scenarios:
        scenario_dir = args.out_dir / sid.value
        rows: list[dict] = []
        # Resume scan
        for policy_name in args.policies:
            for seed_idx in range(cfg.num_seeds):
                log_path = scenario_dir / policy_name / f"seed_{seed_idx:02d}.jsonl"
                if _is_complete(log_path, cfg.num_rounds):
                    rows.append(_row_from_log(policy_name, seed_idx, log_path,
                                              cfg.num_rounds))
                    completed += 1
        if not args.skip_oracle:
            for seed_idx in range(cfg.num_seeds):
                log_path = scenario_dir / "oracle" / f"seed_{seed_idx:02d}.jsonl"
                if _is_complete(log_path, cfg.num_rounds):
                    rows.append(_row_from_log("oracle", seed_idx, log_path,
                                              cfg.num_rounds))
                    completed += 1
        all_rows_by_scenario[sid] = rows

    if completed:
        print(
            f"resume: {completed}/{total_cells} cells already complete; running rest",
            file=sys.stderr,
        )

    done = completed
    for sid in scenarios:
        scenario_dir = args.out_dir / sid.value
        rows = all_rows_by_scenario[sid]
        completed_keys = {(r["policy"], r["seed"]) for r in rows}
        for policy_name in args.policies:
            for seed_idx in range(cfg.num_seeds):
                if (policy_name, seed_idx) in completed_keys:
                    continue
                log_path = scenario_dir / policy_name / f"seed_{seed_idx:02d}.jsonl"
                row = run_one_cell(cfg, sid, policy_name=policy_name,
                                   seed=seed_idx, tasks=tasks, store=store,
                                   log_path=log_path)
                rows.append(row)
                done += 1
                print(
                    f"[{done}/{total_cells}] {sid.value}/{policy_name} seed={seed_idx}"
                    f" rounds={row['rounds']} spent=${row['total_spent']:.2f}"
                    f" PA={row['cum_pa_reward']:.0f} fails={row['failures']}",
                    file=sys.stderr,
                )
        if not args.skip_oracle:
            for seed_idx in range(cfg.num_seeds):
                if ("oracle", seed_idx) in completed_keys:
                    continue
                log_path = scenario_dir / "oracle" / f"seed_{seed_idx:02d}.jsonl"
                row = run_oracle_cell(cfg, sid, seed=seed_idx, tasks=tasks,
                                      store=store, log_path=log_path)
                rows.append(row)
                done += 1
                print(
                    f"[{done}/{total_cells}] {sid.value}/oracle seed={seed_idx}"
                    f" rounds={row['rounds']} spent=${row['total_spent']:.2f}"
                    f" PA={row['cum_pa_reward']:.0f}",
                    file=sys.stderr,
                )

        # Persist per-scenario summary.
        summary_path = scenario_dir / "summary.jsonl"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        with summary_path.open("w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")

    print()
    print("=" * 90)
    for sid in scenarios:
        print(_summarize_scenario(sid, all_rows_by_scenario[sid]))
        print()
    print("=" * 90)
    print(f"\nLogs: {args.out_dir}/<scenario>/<policy>/seed_*.jsonl")
    return 0


if __name__ == "__main__":
    sys.exit(main())
