"""Main bandit replay loop (single-seed orchestration).

Per round:

1. ``WorkloadSampler.next()`` → ``Task``.
2. Compute affordable provider set against ``Wallet.affordable``,
   using ``scenario.effective_price`` to source per-round prices.
3. ``Encoder.encode(task, state)`` → context vector.
4. ``Policy.select(context, affordable)`` → chosen arm.
5. Pick a deterministic version for this (round, arm, task) and
   ``PregenStore.get(...)`` → ``PregenRecord``, then route through
   ``scenario.transform_record`` (S2 may force timeouts; S3 may
   scale cost).
6. ``RewardCalculator.compute(...)`` → ``Reward``.
7. ``Policy.update(context, arm, utility, observed_cost)``.
8. ``Wallet.record_spend(charged_cost)``.
9. ``Recorder.write(LogRecord)``.

Bankruptcy: if no provider is affordable, the loop exits early and the
remaining rounds are simply not logged. This is the contract — we do not
synthesize "you did nothing" rounds.

Scenario injection (M3.E): the optional ``scenario`` argument owns the
two transforms that turn the calibrated stationary market (S1) into a
non-stationary one (S2 outage, S3 price shock). When omitted we default
to ``StationaryScenario`` so legacy tests keep their old semantics.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field

from numpy.random import Generator, default_rng

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
    Policy,
    PregenStore,
    Recorder,
)
from pilot402.runtime.reward import RewardCalculator
from pilot402.runtime.sampler import WorkloadSampler
from pilot402.scenarios import Scenario, StationaryScenario


@dataclass
class LoopRunStats:
    """Lightweight summary returned from ``run_one_seed``.

    Useful for unit tests and the pipeline driver to assert on without
    parsing the JSONL log.
    """

    rounds_completed: int
    total_charged_usdc: float
    bankruptcy_round: int | None = None  # None = ran the full plan
    arm_counts: dict[ProviderId, int] = field(default_factory=dict)
    failure_count: int = 0


def _pick_version(
    rng: Generator,
    available_versions: tuple[int, ...],
) -> int:
    """Uniform random pick of a stored version.

    M3.A is intentionally simple: replay one of the 5 stored runs of the
    chosen (provider, task) pair. M3.B's Scenario object will override
    this for non-stationary settings.
    """

    if not available_versions:
        raise ValueError(
            "No versions available for the (task, provider) pair; the "
            "pregen dataset is incomplete."
        )
    idx = int(rng.integers(0, len(available_versions)))
    return available_versions[idx]


def run_one_seed(
    cfg: ExperimentConfig,
    *,
    tasks: list[Task],
    store: PregenStore,
    policy: Policy,
    wallet: BudgetManager,
    encoder: Encoder,
    reward_calc: RewardCalculator,
    recorder: Recorder,
    seed: int,
    scenario: Scenario | None = None,
    progress_every: int | None = 1000,
) -> LoopRunStats:
    """Run one (policy × scenario × seed) trace through ``cfg.num_rounds``.

    Determinism: the per-round RNG is derived from ``seed`` via
    ``SeedSource(seed)``. The ``policy`` and ``wallet`` should already be
    initialized for this seed by the caller; we don't re-create them here
    to keep the loop testable with mocked components.

    Args:
        scenario: optional within-experiment market scenario. When omitted,
            we default to a stationary identity, preserving M3.A behavior.
        progress_every: print a progress line to stderr every N rounds.
            ``None`` disables progress output (for tests / dry runs).

    Returns:
        ``LoopRunStats`` summary; the bulk of the data goes through the
        recorder into JSONL on disk.
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
    bankruptcy_round: int | None = None

    for round_idx in range(cfg.num_rounds):
        # 1. Pick a task.
        task = sampler.next()

        # 2. Determine affordable arms (scenario-aware prices).
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
        affordable_tuple = tuple(affordable)

        # 3. Encode context.
        snapshot = wallet.snapshot()
        encoder_state = {
            "remaining_fraction": snapshot.get("remaining_fraction", 1.0),
            "lambda_t": snapshot.get("lambda_t", 1.0),
        }
        context = encoder.encode(task, encoder_state)

        # 4. Pick an arm.
        chosen_arm = policy.select(context, affordable_tuple)
        if chosen_arm not in affordable_tuple:
            raise RuntimeError(
                f"Policy returned arm {chosen_arm!r} not in affordable set "
                f"{[a.value for a in affordable_tuple]} at round {round_idx}."
            )

        # 5. Look up the cached LLM outcome (scenario may rewrite it).
        versions = store.versions(task.task_id, chosen_arm)
        version = _pick_version(version_rng, versions)
        record: PregenRecord = store.get(task.task_id, chosen_arm, version)
        record = scenario.transform_record(round_idx, record)

        # 6. Compute reward. latency_s is logged below but not used in the
        # reward formula (the latency penalty was retired 2026-05-02; see
        # pilot402.runtime.reward module docstring).
        lambda_t = wallet.get_lambda()
        reward = reward_calc.compute(
            quality=record.quality_score,
            cost_usdc=record.cost_usdc,
            failure_flag=record.failure_flag,
            lambda_t=lambda_t,
        )

        # 7. Update policy with utility (NOT payment-aware reward) AND
        # the observed cost. PA-DCT uses the cost signal to maintain a
        # dual-posterior over (q, c); other policies ignore it.
        policy.update(
            context, chosen_arm, reward.utility, record.cost_usdc
        )

        # 8. Charge wallet.
        wallet.record_spend(record.cost_usdc)
        total_charged += record.cost_usdc
        arm_counts[chosen_arm] += 1
        if record.failure_flag:
            failure_count += 1

        # 9. Log.
        log_rec = LogRecord(
            run_id=cfg.run_id,
            seed=seed,
            scenario=cfg.scenario.name,
            round=round_idx,
            task_id=task.task_id,
            task_type=task.task_type,
            context=context,
            chosen_arm=chosen_arm,
            affordable_arms=affordable_tuple,
            charged_cost_usdc=record.cost_usdc,
            latency_s=record.latency_s,
            quality=record.quality_score.q,
            failure_flag=record.failure_flag,
            failure_code=record.failure_code,
            utility=reward.utility,
            payment_aware_reward=reward.payment_aware_reward,
            lambda_t=reward.lambda_t,
            budget_remaining_usdc=wallet.snapshot()["remaining_usdc"],
        )
        recorder.write(log_rec)

        if progress_every and (round_idx + 1) % progress_every == 0:
            print(
                f"[seed={seed}] round {round_idx + 1}/{cfg.num_rounds} "
                f"spent=${total_charged:.4f} λ={lambda_t:.3f} "
                f"failures={failure_count}",
                file=sys.stderr,
                flush=True,
            )

    return LoopRunStats(
        rounds_completed=cfg.num_rounds if bankruptcy_round is None else bankruptcy_round,
        total_charged_usdc=total_charged,
        bankruptcy_round=bankruptcy_round,
        arm_counts=arm_counts,
        failure_count=failure_count,
    )


__all__ = ["LoopRunStats", "run_one_seed"]
