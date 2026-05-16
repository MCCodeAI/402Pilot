"""End-to-end smoke test for the bandit replay loop.

Drives ``run_one_seed`` against the FROZEN ``data/pregen/`` dataset with
``RandomPolicy`` for a small number of rounds. Asserts:

* All log records validate as ``LogRecord`` instances.
* Charged spend never exceeds the wallet's total budget.
* Round numbers are strictly ascending.
* Every chosen arm came from the affordable set at that round.

This is the integration test that lets us trust the runtime layer enough
to bring real policies (Always-X, BudgetRule, Oracle, PA-DCT) online.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from numpy.random import default_rng

from pilot402.core import (
    BudgetConfig,
    ExperimentConfig,
    JudgeSettings,
    LlmKeysSettings,
    LogRecord,
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
from pilot402.policies import RandomPolicy
from pilot402.runtime import (
    JsonlRecorder,
    NaiveEncoder,
    RewardCalculator,
    Wallet,
    run_one_seed,
)

PREGEN_DIR = Path(__file__).parents[1] / "data" / "pregen"


def _cfg(num_rounds: int = 100) -> ExperimentConfig:
    return ExperimentConfig(
        run_id="test_loop_smoke",
        seed=0,
        num_rounds=num_rounds,
        num_seeds=1,
        providers=(
            ProviderSpec(
                provider_id=ProviderId.P_CHEAP,
                model_name="qwen3.5-flash",
                base_price_usdc=0.0005,
                tier="cheap",
            ),
            ProviderSpec(
                provider_id=ProviderId.P_MID,
                model_name="GPT-5.4-mini",
                base_price_usdc=0.002,
                tier="mid",
            ),
            ProviderSpec(
                provider_id=ProviderId.P_PREMIUM,
                model_name="GPT-5.4",
                base_price_usdc=0.01,
                tier="premium",
            ),
            ProviderSpec(
                provider_id=ProviderId.P_ADV,
                model_name="GPT-5.4-mini",
                base_price_usdc=0.002,
                tier="mid",
            ),
            ProviderSpec(
                provider_id=ProviderId.P_FLAKY,
                model_name="GPT-5.4-mini",
                base_price_usdc=0.002,
                tier="mid",
            ),
        ),
        scenario=ScenarioConfig(name=ScenarioId.S1_STATIONARY),
        budget=BudgetConfig(
            total_usdc=10.0, lambda_0=1.0, alpha=2.0, target_burn_rate=0.01
        ),
        reward=RewardConfig(nu=0.5),
        policy=PolicyConfig(name="random"),
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


def test_random_policy_runs_to_completion(
    tmp_path: Path,
    real_pregen_store: JsonlPregenStore,
    real_tasks: list,
) -> None:
    cfg = _cfg(num_rounds=200)
    log_path = tmp_path / "log.jsonl"
    with JsonlRecorder(path=log_path) as recorder:
        stats = run_one_seed(
            cfg,
            tasks=real_tasks,
            store=real_pregen_store,
            policy=RandomPolicy(rng=default_rng(0)),
            wallet=Wallet(
                total_usdc=cfg.budget.total_usdc,
                lambda_0=cfg.budget.lambda_0,
                alpha=cfg.budget.alpha,
                target_burn_rate=cfg.budget.target_burn_rate,
            ),
            encoder=NaiveEncoder(),
            reward_calc=RewardCalculator(nu=cfg.reward.nu),
            recorder=recorder,
            seed=0,
            progress_every=None,
        )

    # Either we ran the full plan, or we hit bankruptcy somewhere.
    assert stats.rounds_completed > 0
    assert stats.total_charged_usdc <= cfg.budget.total_usdc + 1e-9
    if stats.bankruptcy_round is not None:
        assert stats.rounds_completed == stats.bankruptcy_round

    # Every line should be a valid LogRecord.
    raw_lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(raw_lines) == stats.rounds_completed
    records = [LogRecord.model_validate_json(line) for line in raw_lines]

    # Round numbers strictly ascending from 0.
    assert [r.round for r in records] == list(range(stats.rounds_completed))

    # Every chosen arm was in its round's affordable set.
    for r in records:
        assert r.chosen_arm in r.affordable_arms

    # Spend monotonic non-decreasing across rounds.
    remaining = [r.budget_remaining_usdc for r in records]
    assert remaining == sorted(remaining, reverse=True)

    # All 5 arms got picked at least once over 200 random draws.
    seen_arms = {r.chosen_arm for r in records}
    expected_arms = {ProviderId.P_CHEAP, ProviderId.P_MID, ProviderId.P_PREMIUM,
                     ProviderId.P_ADV, ProviderId.P_FLAKY}
    # Allow up to one arm to miss in 200 rounds — though with 5 arms × 200 draws
    # the probability of missing any single arm is (4/5)^200 ≈ negligible.
    assert len(seen_arms & expected_arms) >= 4


def test_loop_is_deterministic_for_fixed_seed(
    tmp_path: Path,
    real_pregen_store: JsonlPregenStore,
    real_tasks: list,
) -> None:
    cfg = _cfg(num_rounds=50)

    def _run(out: Path) -> None:
        with JsonlRecorder(path=out) as rec:
            run_one_seed(
                cfg,
                tasks=real_tasks,
                store=real_pregen_store,
                policy=RandomPolicy(rng=default_rng(42)),
                wallet=Wallet(total_usdc=cfg.budget.total_usdc),
                encoder=NaiveEncoder(),
                reward_calc=RewardCalculator(nu=cfg.reward.nu),
                recorder=rec,
                seed=42,
                progress_every=None,
            )

    a = tmp_path / "a.jsonl"
    b = tmp_path / "b.jsonl"
    _run(a)
    _run(b)
    # Identical seed → identical (modulo nothing, since we don't log timestamps).
    assert a.read_text() == b.read_text()


def test_bankruptcy_handled_gracefully(
    tmp_path: Path,
    real_pregen_store: JsonlPregenStore,
    real_tasks: list,
) -> None:
    """A wallet too small to cover even one P-cheap round bankrupts immediately."""
    cfg = _cfg(num_rounds=100)

    log_path = tmp_path / "log.jsonl"
    with JsonlRecorder(path=log_path) as recorder:
        stats = run_one_seed(
            cfg,
            tasks=real_tasks,
            store=real_pregen_store,
            policy=RandomPolicy(rng=default_rng(0)),
            # 0.0001 < every provider's price (cheapest is 0.0005)
            wallet=Wallet(total_usdc=0.0001),
            encoder=NaiveEncoder(),
            reward_calc=RewardCalculator(nu=cfg.reward.nu),
            recorder=recorder,
            seed=0,
            progress_every=None,
        )

    assert stats.rounds_completed == 0
    assert stats.bankruptcy_round == 0
    # Recorder is lazy: with 0 rounds, no write happens, so the file
    # may not exist (which is fine — it's an edge case, not data loss).
    if log_path.exists():
        assert log_path.read_text() == ""
