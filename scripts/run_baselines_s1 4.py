"""Run all M3.C baselines on S1 (stationary) and produce a summary table.

5 policies × 30 seeds × 10,000 rounds (or as configured in main.yaml).
Logs land in ``results/baselines_s1/<policy>/seed_<n>.jsonl``.

Output (stdout): a per-policy comparison table summarizing
* mean / std cumulative payment-aware reward
* mean / std cumulative utility (policy-internal signal)
* arm-share distribution
* bankruptcy rate
* mean total spend

Usage::

    python -m scripts.run_baselines_s1                    # full sweep
    python -m scripts.run_baselines_s1 --num-seeds 5      # quick smoke
    python -m scripts.run_baselines_s1 --num-rounds 1000  # short rounds
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

from numpy.random import default_rng

from pilot402.core import ExperimentConfig, ProviderId, SeedSource
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
)


def _make_policy(name: str, *, wallet, seed: int):
    """Construct a fresh policy instance for this seed."""
    if name == "random":
        return RandomPolicy(rng=default_rng(seed * 7919 + 1))  # 7919 is prime
    if name == "always_cheapest":
        return always_cheapest()
    if name == "always_mid":
        return always_mid()
    if name == "always_premium":
        return always_premium()
    prices = {
        ProviderId.P_CHEAP: 0.0005,
        ProviderId.P_MID: 0.002,
        ProviderId.P_PREMIUM: 0.01,  # recalibrated 2026-05-02 (was 0.02)
        ProviderId.P_ADV: 0.002,
        ProviderId.P_FLAKY: 0.002,
    }
    if name == "budget_rule":
        return BudgetRulePolicy(wallet=wallet, provider_prices=prices)
    if name == "padct":
        return PADCTPolicy(
            rng=default_rng(seed * 6271 + 13),  # different prime, different stream
            wallet=wallet,
            provider_costs=prices,
            max_provider_cost=0.01,
        )
    raise ValueError(f"Unknown policy name: {name!r}")


def run_one(
    cfg: ExperimentConfig,
    *,
    policy_name: str,
    seed: int,
    tasks: list,
    store: JsonlPregenStore,
    log_path: Path,
) -> dict:
    """Run one (policy, seed) trace and return a summary dict."""
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
        stats = run_one_seed(
            cfg,
            tasks=tasks,
            store=store,
            policy=policy,
            wallet=wallet,
            encoder=encoder,
            reward_calc=reward_calc,
            recorder=rec,
            seed=seed,
            progress_every=None,
        )

    # Aggregate from the log for analysis (cheap; tens of MB max).
    cum_pa_reward = 0.0
    cum_utility = 0.0
    quality_sum = 0.0
    n_rounds = 0
    for line in log_path.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        cum_pa_reward += rec["payment_aware_reward"]
        cum_utility += rec["utility"]
        quality_sum += rec["quality"]
        n_rounds += 1
    return {
        "policy": policy_name,
        "seed": seed,
        "rounds": stats.rounds_completed,
        "bankrupt": stats.bankruptcy_round is not None,
        "bankruptcy_round": stats.bankruptcy_round,
        "total_spent": stats.total_charged_usdc,
        "failures": stats.failure_count,
        "cum_pa_reward": cum_pa_reward,
        "cum_utility": cum_utility,
        "mean_quality": quality_sum / n_rounds if n_rounds else 0.0,
        "arm_counts": {a.value: n for a, n in stats.arm_counts.items()},
    }


def _summarize(rows: list[dict]) -> str:
    """Format a per-policy comparison table."""
    by_policy: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_policy[r["policy"]].append(r)

    lines: list[str] = []
    header = (
        f"{'policy':<18}{'rounds':>10}{'bnkrpt':>8}{'spent':>10}"
        f"{'fails':>8}{'cum_PA_r':>14}{'cum_util':>14}{'mean_q':>9}"
    )
    lines.append(header)
    lines.append("-" * len(header))
    order = ["random", "always_cheapest", "always_mid", "always_premium",
             "budget_rule", "padct"]
    for name in order:
        if name not in by_policy:
            continue
        seeds = by_policy[name]
        rounds = [s["rounds"] for s in seeds]
        spent = [s["total_spent"] for s in seeds]
        fails = [s["failures"] for s in seeds]
        pa = [s["cum_pa_reward"] for s in seeds]
        util = [s["cum_utility"] for s in seeds]
        q = [s["mean_quality"] for s in seeds]
        bnkrpt = sum(1 for s in seeds if s["bankrupt"])
        lines.append(
            f"{name:<18}"
            f"{statistics.mean(rounds):>10.0f}"
            f"{bnkrpt:>4}/{len(seeds):<3}"
            f"${statistics.mean(spent):>8.2f}"
            f"{statistics.mean(fails):>8.1f}"
            f"{statistics.mean(pa):>10.2f}±{statistics.stdev(pa) if len(pa) > 1 else 0:.2f}"
            f"{statistics.mean(util):>10.2f}±{statistics.stdev(util) if len(util) > 1 else 0:.2f}"
            f"{statistics.mean(q):>9.3f}"
        )

    # Per-policy arm-share table
    lines.append("")
    lines.append("=== Arm share (mean across seeds) ===")
    arm_header = f"{'policy':<18}" + "".join(f"{a.value:>11}" for a in ProviderId)
    lines.append(arm_header)
    lines.append("-" * len(arm_header))
    for name in order:
        if name not in by_policy:
            continue
        row = f"{name:<18}"
        seeds = by_policy[name]
        for arm in ProviderId:
            counts = [s["arm_counts"].get(arm.value, 0) for s in seeds]
            row += f"{statistics.mean(counts):>11.0f}"
        lines.append(row)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("experiments/main.yaml"))
    parser.add_argument(
        "--num-seeds", type=int, default=None,
        help="Override cfg.num_seeds (e.g. 5 for a quick smoke).",
    )
    parser.add_argument(
        "--num-rounds", type=int, default=None,
        help="Override cfg.num_rounds (e.g. 500 for a quick smoke).",
    )
    parser.add_argument(
        "--out-dir", type=Path, default=Path("results/baselines_s1"),
        help="Where to write per-(policy, seed) JSONL logs.",
    )
    parser.add_argument(
        "--policies", nargs="+", default=None,
        choices=["random", "always_cheapest", "always_mid", "always_premium",
                 "budget_rule", "padct"],
        help="Subset of policies to run (default: all 6 including PA-DCT).",
    )
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    if args.num_seeds is not None:
        cfg = cfg.model_copy(update={"num_seeds": args.num_seeds})
    if args.num_rounds is not None:
        cfg = cfg.model_copy(update={"num_rounds": args.num_rounds})

    tasks = load_all_tasks(cfg.paths.tasks_dir)
    store = JsonlPregenStore(cfg.paths.pregen_dir)
    print(
        f"Loaded {len(tasks)} tasks and {len(store)} pregen records.",
        file=sys.stderr,
    )

    policies = args.policies or [
        "random",
        "always_cheapest",
        "always_mid",
        "always_premium",
        "budget_rule",
        "padct",
    ]

    # Resume support: scan per-(policy, seed) JSONL files for completed cells.
    # A cell is "complete" if its log file has at least cfg.num_rounds lines
    # (full run) or its last record's `budget_remaining_usdc` is below the
    # cheapest provider's price (bankrupted before reaching num_rounds).
    summary_json = args.out_dir / "summary.jsonl"
    rows: list[dict] = []
    completed_keys: set[tuple[str, int]] = set()
    cheapest_price = min(p.base_price_usdc for p in cfg.providers)
    for policy_name in policies:
        for seed_idx in range(cfg.num_seeds):
            log_path = args.out_dir / policy_name / f"seed_{seed_idx:02d}.jsonl"
            if not log_path.is_file():
                continue
            lines = log_path.read_text(encoding="utf-8").splitlines()
            lines = [line for line in lines if line.strip()]
            if not lines:
                continue
            n_lines = len(lines)
            last = json.loads(lines[-1])
            full_run = n_lines >= cfg.num_rounds
            bankrupted = last.get("budget_remaining_usdc", 0) < cheapest_price
            if not (full_run or bankrupted):
                continue
            # Reconstruct the summary row from the per-cell log.
            cum_pa = sum(json.loads(line).get("payment_aware_reward", 0) for line in lines)
            cum_util = sum(json.loads(line).get("utility", 0) for line in lines)
            mean_q = sum(json.loads(line).get("quality", 0) for line in lines) / n_lines
            total_spent = sum(json.loads(line).get("charged_cost_usdc", 0) for line in lines)
            n_failures = sum(1 for line in lines if json.loads(line).get("failure_flag"))
            arm_counts: dict[str, int] = {}
            for line in lines:
                arm = json.loads(line).get("chosen_arm")
                if arm is not None:
                    arm_counts[arm] = arm_counts.get(arm, 0) + 1
            rows.append({
                "policy": policy_name,
                "seed": seed_idx,
                "rounds": n_lines,
                "bankrupt": not full_run,
                "bankruptcy_round": n_lines if not full_run else None,
                "total_spent": total_spent,
                "failures": n_failures,
                "cum_pa_reward": cum_pa,
                "cum_utility": cum_util,
                "mean_quality": mean_q,
                "arm_counts": arm_counts,
            })
            completed_keys.add((policy_name, seed_idx))
    if completed_keys:
        print(
            f"resume: skipping {len(completed_keys)}/{len(policies) * cfg.num_seeds} "
            f"already-complete cells (rebuilt from per-cell logs)",
            file=sys.stderr,
        )

    total = len(policies) * cfg.num_seeds
    done = len(completed_keys)
    for policy_name in policies:
        for seed_idx in range(cfg.num_seeds):
            if (policy_name, seed_idx) in completed_keys:
                continue
            log_path = args.out_dir / policy_name / f"seed_{seed_idx:02d}.jsonl"
            row = run_one(
                cfg,
                policy_name=policy_name,
                seed=seed_idx,
                tasks=tasks,
                store=store,
                log_path=log_path,
            )
            rows.append(row)
            done += 1
            print(
                f"[{done}/{total}] {policy_name} seed={seed_idx} "
                f"rounds={row['rounds']} spent=${row['total_spent']:.2f} "
                f"PA_reward={row['cum_pa_reward']:.1f}",
                file=sys.stderr,
            )

    # Persist the raw summary alongside the logs for later analysis.
    # ``summary_json`` was already pinned above for resume detection; rewrite
    # the full set so any partial-run rows that were resumed past stay in.
    summary_json.parent.mkdir(parents=True, exist_ok=True)
    with summary_json.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")

    print()
    print("=" * 80)
    print(_summarize(rows))
    print("=" * 80)
    print(f"\nPer-seed JSONL logs: {args.out_dir}/<policy>/seed_*.jsonl")
    print(f"Summary JSONL:       {summary_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
