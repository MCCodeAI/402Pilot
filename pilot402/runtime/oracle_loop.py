"""True Oracle (Plan A) — single-number upper bound.

Unlike the post-hoc Oracle in ``scripts/compute_oracle.py`` (which is
anchored on a specific baseline's λ trajectory), the True Oracle runs
its own simulation:

1. It owns its own wallet (independent λ trajectory).
2. Each round, it peeks at all affordable arms' actual (q, c, f) at the
   deterministic version drawn for the round.
3. It picks the arm with the highest PA-reward at the wallet's current
   λ_t.
4. The wallet charges only the chosen arm's cost — λ evolves naturally
   with Oracle's choices.

The output is a single ``cum_PA_reward`` per seed, directly comparable
to any policy's cum_PA_reward.

This is the "best policy in hindsight" upper bound: no policy can do
better than this without seeing the future. PA-DCT's success is
measured by closing the gap to the True Oracle.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

from numpy.random import Generator

from pilot402.core import (
    ExperimentConfig,
    LogRecord,
    PregenRecord,
    ProviderId,
    SeedSource,
    Task,
)
from pilot402.core.interfaces import (
    BudgetManager,
    Encoder,
    PregenStore,
    Recorder,
)
from pilot402.runtime.reward import RewardCalculator
from pilot402.runtime.sampler import WorkloadSampler
from pilot402.scenarios import Scenario, StationaryScenario


@dataclass
class OracleRunStats:
    """Summary of one True Oracle run."""

    rounds_completed: int
    total_charged_usdc: float
    bankruptcy_round: int | None = None
    arm_counts: dict[ProviderId, int] = field(default_factory=dict)
    failure_count: int = 0
    cum_pa_reward: float = 0.0


def _pick_version(rng: Generator, available_versions: tuple[int, ...]) -> int:
    """Mirror runtime.loop._pick_version for trace alignment."""
    if not available_versions:
        raise ValueError("No versions available.")
    idx = int(rng.integers(0, len(available_versions)))
    return available_versions[idx]


def run_true_oracle_seed(
    cfg: ExperimentConfig,
    *,
    tasks: list[Task],
    store: PregenStore,
    wallet: BudgetManager,
    encoder: Encoder,
    reward_calc: RewardCalculator,
    recorder: Recorder | None,
    seed: int,
    scenario: Scenario | None = None,
) -> OracleRunStats:
    """Run a fresh Oracle simulation.

    Procedure per round:
      1. Sample task (same RNG path as run_one_seed for trace alignment).
      2. Determine affordable arms (scenario-aware prices).
      3. Pick deterministic version (same RNG path).
      4. For each affordable arm: lookup record, route through
         ``scenario.transform_record``, compute PA-reward at wallet's
         current λ_t.
      5. Pick argmax. Charge wallet (scenario-transformed cost). Log.

    The wallet here is Oracle's own; it does not share state with any
    other policy run. That's the entire point: True Oracle has its own
    λ trajectory determined by ITS OWN choices. The scenario is the
    same one all policies face for this seed, so the Oracle's
    upper-bound is the upper-bound *for this scenario*.

    Args:
        scenario: optional within-experiment market scenario. Defaults to
                  Stationary identity (preserves M3.D semantics).
        recorder: optional. If provided, writes one ``LogRecord`` per round
                  in the same schema as run_one_seed (so oracle and policy
                  logs are directly comparable).
    """
    if scenario is None:
        scenario = StationaryScenario()

    seeds = SeedSource(seed)
    sampler_rng = seeds.derive(f"loop/{cfg.run_id}/sampler").rng
    version_rng = seeds.derive(f"loop/{cfg.run_id}/version").rng
    sampler = WorkloadSampler(tasks=tasks, rng=sampler_rng)

    provider_specs = {p.provider_id: p for p in cfg.providers}
    arm_counts: dict[ProviderId, int] = {pid: 0 for pid in provider_specs}
    failure_count = 0
    total_charged = 0.0
    cum_pa_reward = 0.0
    bankruptcy_round: int | None = None

    for round_idx in range(cfg.num_rounds):
        # 1. Pick task.
        task = sampler.next()

        # 2. Affordable arms (scenario-aware prices).
        affordable: list[ProviderId] = [
            pid
            for pid, spec in provider_specs.items()
            if wallet.affordable(
                scenario.effective_price(round_idx, pid, spec.base_price_usdc)
            )
        ]
        if not affordable:
            bankruptcy_round = round_idx
            break

        # 3. Deterministic version pick (same RNG path as run_one_seed).
        sample_versions = store.versions(task.task_id, affordable[0])
        version = _pick_version(version_rng, sample_versions)

        # 4. Peek at every affordable arm's outcome (scenario-transformed)
        # and compute PA-reward.
        lambda_t = wallet.get_lambda()
        best_arm: ProviderId | None = None
        best_pa = float("-inf")
        best_record: PregenRecord | None = None
        best_reward = None
        for arm in affordable:
            rec = store.get(task.task_id, arm, version)
            rec = scenario.transform_record(round_idx, rec)
            r = reward_calc.compute(
                quality=rec.quality_score,
                cost_usdc=rec.cost_usdc,
                failure_flag=rec.failure_flag,
                lambda_t=lambda_t,
            )
            if r.payment_aware_reward > best_pa:
                best_pa = r.payment_aware_reward
                best_arm = arm
                best_record = rec
                best_reward = r

        assert best_arm is not None
        assert best_record is not None
        assert best_reward is not None

        # 5. Charge + accumulate.
        wallet.record_spend(best_record.cost_usdc)
        total_charged += best_record.cost_usdc
        arm_counts[best_arm] += 1
        if best_record.failure_flag:
            failure_count += 1
        cum_pa_reward += best_pa

        # 6. Log (optional).
        if recorder is not None:
            snapshot = wallet.snapshot()
            context = encoder.encode(task, {
                "remaining_fraction": snapshot.get("remaining_fraction", 1.0),
                "lambda_t": snapshot.get("lambda_t", 1.0),
            })
            log_rec = LogRecord(
                run_id=cfg.run_id,
                seed=seed,
                scenario=cfg.scenario.name,
                round=round_idx,
                task_id=task.task_id,
                task_type=task.task_type,
                context=context,
                chosen_arm=best_arm,
                affordable_arms=tuple(affordable),
                charged_cost_usdc=best_record.cost_usdc,
                latency_s=best_record.latency_s,
                quality=best_record.quality_score.q,
                failure_flag=best_record.failure_flag,
                failure_code=best_record.failure_code,
                utility=best_reward.utility,
                payment_aware_reward=best_reward.payment_aware_reward,
                lambda_t=best_reward.lambda_t,
                budget_remaining_usdc=snapshot["remaining_usdc"],
            )
            recorder.write(log_rec)

    return OracleRunStats(
        rounds_completed=cfg.num_rounds if bankruptcy_round is None else bankruptcy_round,
        total_charged_usdc=total_charged,
        bankruptcy_round=bankruptcy_round,
        arm_counts=arm_counts,
        failure_count=failure_count,
        cum_pa_reward=cum_pa_reward,
    )


__all__ = ["OracleRunStats", "run_true_oracle_seed"]
