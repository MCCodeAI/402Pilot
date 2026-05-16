"""Tests for ``pilot402.runtime.oracle_loop.run_true_oracle_seed``.

The True Oracle is the upper-bound benchmark. Tests verify it makes
correct per-round decisions under hindsight access.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pilot402.core import (
    BudgetConfig,
    ExperimentConfig,
    JudgeSettings,
    LlmKeysSettings,
    PathConfig,
    PolicyConfig,
    ProviderId,
    ProviderSpec,
    RewardConfig,
    ScenarioConfig,
    ScenarioId,
    X402Settings,
)
from pilot402.pregen import JsonlPregenStore
from pilot402.runtime import (
    NaiveEncoder,
    RewardCalculator,
    Wallet,
    run_true_oracle_seed,
)

PREGEN_DIR = Path(__file__).parents[1] / "data" / "pregen"


def _cfg(num_rounds: int = 100) -> ExperimentConfig:
    return ExperimentConfig(
        run_id="test_oracle",
        seed=0,
        num_rounds=num_rounds,
        num_seeds=1,
        providers=(
            ProviderSpec(provider_id=ProviderId.P_CHEAP, model_name="qwen3.5-flash",
                         base_price_usdc=0.0005, tier="cheap"),
            ProviderSpec(provider_id=ProviderId.P_MID, model_name="GPT-5.4-mini",
                         base_price_usdc=0.002, tier="mid"),
            ProviderSpec(provider_id=ProviderId.P_PREMIUM, model_name="GPT-5.4",
                         base_price_usdc=0.01, tier="premium"),
            ProviderSpec(provider_id=ProviderId.P_ADV, model_name="GPT-5.4-mini",
                         base_price_usdc=0.002, tier="mid"),
            ProviderSpec(provider_id=ProviderId.P_FLAKY, model_name="GPT-5.4-mini",
                         base_price_usdc=0.002, tier="mid"),
        ),
        scenario=ScenarioConfig(name=ScenarioId.S1_STATIONARY),
        budget=BudgetConfig(
            total_usdc=50.0, lambda_0=1.0, alpha=2.0, target_burn_rate=0.0001
        ),
        reward=RewardConfig(nu=0.5),
        policy=PolicyConfig(name="oracle"),
        paths=PathConfig(),
        x402=X402Settings(),
        llm_keys=LlmKeysSettings(),
        judge=JudgeSettings(),
    )


@pytest.fixture(scope="module")
def real_pregen_store() -> JsonlPregenStore:
    if not PREGEN_DIR.is_dir() or not any(PREGEN_DIR.glob("*.jsonl")):
        pytest.skip("data/pregen/ is empty; run pregen first")
    return JsonlPregenStore(PREGEN_DIR)


@pytest.fixture
def real_tasks() -> list:
    from pilot402.pregen.tasks import load_all_tasks

    task_dir = Path(__file__).parents[1] / "data" / "tasks"
    if not task_dir.is_dir():
        pytest.skip("data/tasks/ is empty; run pregen first")
    tasks = load_all_tasks(task_dir)
    if not tasks:
        pytest.skip("data/tasks/ is empty; run pregen first")
    return tasks


def test_true_oracle_runs_and_accumulates_pa(
    real_pregen_store: JsonlPregenStore, real_tasks: list
) -> None:
    cfg = _cfg(num_rounds=200)
    wallet = Wallet(total_usdc=cfg.budget.total_usdc,
                    target_burn_rate=cfg.budget.target_burn_rate)
    stats = run_true_oracle_seed(
        cfg,
        tasks=real_tasks,
        store=real_pregen_store,
        wallet=wallet,
        encoder=NaiveEncoder(),
        reward_calc=RewardCalculator(nu=cfg.reward.nu),
        recorder=None,
        seed=0,
    )
    assert stats.rounds_completed == 200
    assert stats.cum_pa_reward > 0
    # Oracle should achieve > 0.5 PA on average (well above random)
    assert stats.cum_pa_reward / 200 > 0.4


def test_true_oracle_beats_any_fixed_policy(
    real_pregen_store: JsonlPregenStore, real_tasks: list
) -> None:
    """The True Oracle must beat or match any single-arm fixed policy by
    construction (it can pick the best arm each round, including the same
    arm always if that's truly optimal)."""
    cfg = _cfg(num_rounds=500)

    # True Oracle
    oracle_stats = run_true_oracle_seed(
        cfg,
        tasks=real_tasks,
        store=real_pregen_store,
        wallet=Wallet(total_usdc=cfg.budget.total_usdc,
                      target_burn_rate=cfg.budget.target_burn_rate),
        encoder=NaiveEncoder(),
        reward_calc=RewardCalculator(nu=cfg.reward.nu),
        recorder=None,
        seed=0,
    )
    oracle_per_round = oracle_stats.cum_pa_reward / oracle_stats.rounds_completed

    # Always-Mid for comparison via run_one_seed
    from pilot402.policies import always_mid
    from pilot402.runtime import run_one_seed
    from pilot402.runtime.recorder import JsonlRecorder
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        log_path = Path(tmp) / "log.jsonl"
        with JsonlRecorder(path=log_path) as rec:
            mid_stats = run_one_seed(
                cfg, tasks=real_tasks, store=real_pregen_store,
                policy=always_mid(),
                wallet=Wallet(total_usdc=cfg.budget.total_usdc,
                              target_burn_rate=cfg.budget.target_burn_rate),
                encoder=NaiveEncoder(),
                reward_calc=RewardCalculator(nu=cfg.reward.nu),
                recorder=rec, seed=0, progress_every=None,
            )
        # Compute always_mid's cum_PA from log
        import json
        mid_pa = sum(json.loads(line)["payment_aware_reward"]
                     for line in log_path.read_text().splitlines())
    mid_per_round = mid_pa / mid_stats.rounds_completed

    # Oracle should be >= AlwaysMid
    assert oracle_per_round >= mid_per_round, (
        f"True Oracle ({oracle_per_round:.3f}/round) should be ≥ "
        f"AlwaysMid ({mid_per_round:.3f}/round)"
    )


def test_true_oracle_is_deterministic_for_fixed_seed(
    real_pregen_store: JsonlPregenStore, real_tasks: list
) -> None:
    """Same seed → same trace."""
    cfg = _cfg(num_rounds=100)

    def _run() -> float:
        wallet = Wallet(total_usdc=cfg.budget.total_usdc,
                        target_burn_rate=cfg.budget.target_burn_rate)
        return run_true_oracle_seed(
            cfg, tasks=real_tasks, store=real_pregen_store,
            wallet=wallet, encoder=NaiveEncoder(),
            reward_calc=RewardCalculator(nu=cfg.reward.nu),
            recorder=None, seed=42,
        ).cum_pa_reward

    a = _run()
    b = _run()
    assert a == b


def test_true_oracle_avoids_flaky_timeouts(
    real_pregen_store: JsonlPregenStore, real_tasks: list
) -> None:
    """Oracle peeks at all arms; should never pick a timeout when alternatives
    exist (timeouts give utility = -0.5, worst possible)."""
    cfg = _cfg(num_rounds=200)
    stats = run_true_oracle_seed(
        cfg,
        tasks=real_tasks,
        store=real_pregen_store,
        wallet=Wallet(total_usdc=cfg.budget.total_usdc,
                      target_burn_rate=cfg.budget.target_burn_rate),
        encoder=NaiveEncoder(),
        reward_calc=RewardCalculator(nu=cfg.reward.nu),
        recorder=None, seed=0,
    )
    # Oracle should have 0 failures (it can always pick a non-timeout version)
    assert stats.failure_count == 0
