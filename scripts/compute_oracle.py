"""Post-hoc Oracle analysis (Plan B).

For each round in an existing baseline log, the Oracle peeks at all
affordable arms' realized rewards (looking up the same deterministic
version that the loop would have drawn) and picks the argmax. Cumulative
oracle reward is an UPPER BOUND on what any non-omniscient policy could
have achieved, given the same wallet/λ trajectory observed by that
baseline.

This implementation does NOT re-simulate. It uses each baseline's
``lambda_t`` and ``affordable_arms`` as logged, then asks: "given those
constraints, what's the best per-round arm choice?"

Why anchor on the baseline's λ trajectory: λ is endogenous to spending
choices, so a "fresh-simulation" oracle would have a different trajectory.
Anchoring keeps the comparison apples-to-apples — we're measuring the gap
between "what the baseline did" and "what an omniscient round-by-round
optimizer would have done with the same budget pressure."

Usage::

    python -m scripts.compute_oracle \\
        --log-dir results/baselines_s1 \\
        --reference always_mid

Output: a per-seed table of (baseline PA-reward, oracle PA-reward, gap).
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

from numpy.random import default_rng

from pilot402.core import LogRecord, ProviderId, SeedSource
from pilot402.core.config import load_config
from pilot402.pregen import JsonlPregenStore
from pilot402.pregen.tasks import load_all_tasks
from pilot402.runtime.reward import RewardCalculator
from pilot402.runtime.sampler import WorkloadSampler


def _pick_version(rng, available_versions: tuple[int, ...]) -> int:
    """Mirror runtime.loop._pick_version exactly."""
    if not available_versions:
        raise ValueError("No versions available.")
    idx = int(rng.integers(0, len(available_versions)))
    return available_versions[idx]


def compute_oracle_for_seed(
    log_path: Path,
    *,
    cfg,
    tasks: list,
    store: JsonlPregenStore,
    reward_calc: RewardCalculator,
    seed: int,
) -> dict:
    """Replay version_rng + peek-and-argmax over each round in the log.

    Returns a dict with the baseline's logged cum_PA_reward and the oracle's
    computed cum_PA_reward, plus arm choice counts.
    """

    # Reconstruct RNGs identically to runtime.loop.run_one_seed.
    seeds = SeedSource(seed)
    sampler_rng = seeds.derive(f"loop/{cfg.run_id}/sampler").rng
    version_rng = seeds.derive(f"loop/{cfg.run_id}/version").rng
    sampler = WorkloadSampler(tasks=tasks, rng=sampler_rng)

    baseline_pa = 0.0
    oracle_pa = 0.0
    oracle_arm_counts: dict[ProviderId, int] = {pid: 0 for pid in ProviderId}
    n_rounds = 0
    n_oracle_swaps = 0

    for raw in log_path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        log_rec = LogRecord.model_validate_json(raw)
        # Sanity: replay must agree on which task this round.
        replay_task = sampler.next()
        if replay_task.task_id != log_rec.task_id:
            raise RuntimeError(
                f"Replay diverged at round {log_rec.round}: replay sampled "
                f"{replay_task.task_id!r} but log has {log_rec.task_id!r}. "
                f"This means cfg.run_id or seed mismatch the original run."
            )
        # Replay version draw (same RNG state as the original loop).
        sample_versions = store.versions(log_rec.task_id, log_rec.affordable_arms[0])
        version = _pick_version(version_rng, sample_versions)

        # Compute oracle: argmax of payment-aware reward across affordable arms.
        best_reward = -float("inf")
        best_arm: ProviderId | None = None
        for arm in log_rec.affordable_arms:
            rec = store.get(log_rec.task_id, arm, version)
            r = reward_calc.compute(
                quality=rec.quality_score,
                cost_usdc=rec.cost_usdc,
                failure_flag=rec.failure_flag,
                lambda_t=log_rec.lambda_t,
            )
            if r.payment_aware_reward > best_reward:
                best_reward = r.payment_aware_reward
                best_arm = arm

        baseline_pa += log_rec.payment_aware_reward
        oracle_pa += best_reward
        if best_arm != log_rec.chosen_arm:
            n_oracle_swaps += 1
        if best_arm is not None:
            oracle_arm_counts[best_arm] += 1
        n_rounds += 1

    return {
        "seed": seed,
        "rounds": n_rounds,
        "baseline_pa_reward": baseline_pa,
        "oracle_pa_reward": oracle_pa,
        "gap": oracle_pa - baseline_pa,
        "oracle_arm_counts": {a.value: n for a, n in oracle_arm_counts.items()},
        "n_oracle_swaps": n_oracle_swaps,
        "swap_rate": n_oracle_swaps / n_rounds if n_rounds else 0.0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("experiments/main.yaml"))
    parser.add_argument(
        "--log-dir", type=Path, default=Path("results/baselines_s1"),
        help="Where the per-seed JSONL logs live (subdir per policy).",
    )
    parser.add_argument(
        "--reference", default="always_mid",
        choices=["random", "always_cheapest", "always_mid", "always_premium",
                 "budget_rule", "padct"],
        help="Which baseline's λ trajectory to anchor the oracle on. "
             "Default: always_mid (the strongest non-bankrupting baseline).",
    )
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    tasks = load_all_tasks(cfg.paths.tasks_dir)
    store = JsonlPregenStore(cfg.paths.pregen_dir)
    reward_calc = RewardCalculator(nu=cfg.reward.nu)

    log_subdir = args.log_dir / args.reference
    log_files = sorted(log_subdir.glob("seed_*.jsonl"))
    if not log_files:
        raise SystemExit(f"No log files found under {log_subdir}")

    print(
        f"Computing oracle PA-reward against {args.reference} "
        f"({len(log_files)} seed logs) ...",
        file=sys.stderr,
    )
    rows: list[dict] = []
    for log_path in log_files:
        seed_str = log_path.stem.split("_")[1]
        seed = int(seed_str)
        row = compute_oracle_for_seed(
            log_path,
            cfg=cfg,
            tasks=tasks,
            store=store,
            reward_calc=reward_calc,
            seed=seed,
        )
        rows.append(row)
        print(
            f"  seed={seed:02d}  "
            f"baseline={row['baseline_pa_reward']:.1f}  "
            f"oracle={row['oracle_pa_reward']:.1f}  "
            f"gap={row['gap']:.1f}  "
            f"swap_rate={row['swap_rate']:.1%}",
            file=sys.stderr,
        )

    # Summary table
    baseline_means = [r["baseline_pa_reward"] for r in rows]
    oracle_means = [r["oracle_pa_reward"] for r in rows]
    gaps = [r["gap"] for r in rows]
    swaps = [r["swap_rate"] for r in rows]
    n = len(rows)

    print()
    print("=" * 70)
    print(f"Oracle vs {args.reference} (n={n} seeds)")
    print("=" * 70)
    print(
        f"  baseline cum_PA_r:  {statistics.mean(baseline_means):>9.2f} "
        f"± {statistics.stdev(baseline_means) if n > 1 else 0:.2f}"
    )
    print(
        f"  oracle   cum_PA_r:  {statistics.mean(oracle_means):>9.2f} "
        f"± {statistics.stdev(oracle_means) if n > 1 else 0:.2f}"
    )
    print(
        f"  gap (oracle − base): {statistics.mean(gaps):>8.2f} "
        f"± {statistics.stdev(gaps) if n > 1 else 0:.2f}"
    )
    print(
        f"  oracle swap rate:    {statistics.mean(swaps):>8.1%} "
        f"(fraction of rounds where oracle would have picked differently)"
    )

    # Aggregated oracle arm choices
    print("\nOracle arm choices (mean across seeds):")
    for arm in ProviderId:
        counts = [r["oracle_arm_counts"].get(arm.value, 0) for r in rows]
        print(f"  {arm.value:<12} {statistics.mean(counts):>8.0f}")

    # Persist
    out = args.log_dir / f"oracle_vs_{args.reference}.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    print(f"\nPer-seed oracle results: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
