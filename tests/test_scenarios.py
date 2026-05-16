"""Tests for ``pilot402.scenarios``.

Three layers:

1. **Unit** — each scenario class in isolation (transform shapes, idempotence,
   targeting, parameter validation).
2. **Factory** — ``build_scenario`` dispatches correctly and the scenario RNG
   is deterministic across re-instantiations of the same master seed.
3. **Integration** — wired into the runtime loop and the True Oracle, the
   scenarios produce the expected behavioral signatures (S2 outage hurts
   AlwaysMid; S3 premium drop makes premium affordable; Oracle adapts).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from numpy.random import default_rng

from pilot402.core import (
    BudgetConfig,
    EvaluatorBackend,
    ExperimentConfig,
    FailureCode,
    JudgeSettings,
    LlmKeysSettings,
    LogRecord,
    PathConfig,
    PolicyConfig,
    PregenRecord,
    ProviderId,
    ProviderSpec,
    QualityScore,
    RewardConfig,
    ScenarioConfig,
    ScenarioId,
    X402Settings,
)
from pilot402.pregen import JsonlPregenStore
from pilot402.runtime import (
    JsonlRecorder,
    NaiveEncoder,
    RewardCalculator,
    Wallet,
    run_one_seed,
    run_true_oracle_seed,
)
from pilot402.scenarios import (
    MidOutageScenario,
    PremiumDropScenario,
    Scenario,
    StationaryScenario,
    build_scenario,
)
from datetime import datetime, timezone

PREGEN_DIR = Path(__file__).parents[1] / "data" / "pregen"
TASKS_DIR = Path(__file__).parents[1] / "data" / "tasks"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_record(
    *,
    provider_id: ProviderId,
    cost: float = 0.002,
    q: float = 0.7,
    failure: bool = False,
    code: FailureCode = FailureCode.NONE,
) -> PregenRecord:
    """Hand-rolled PregenRecord for unit tests (avoid touching disk)."""
    return PregenRecord(
        task_id="task_unit",
        task_type="T2",
        provider_id=provider_id,
        version=0,
        response="x",
        cost_usdc=cost,
        latency_s=0.5,
        failure_flag=failure,
        failure_code=code,
        quality_score=QualityScore(q=q, backend=EvaluatorBackend.JUDGE),
        generated_at=datetime(2026, 5, 3, tzinfo=timezone.utc),
        temperature=0.0,
    )


def _cfg_for_integration(num_rounds: int, scenario_id: ScenarioId) -> ExperimentConfig:
    return ExperimentConfig(
        run_id=f"test_scenario_{scenario_id.value}",
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
        scenario=ScenarioConfig(name=scenario_id),
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


@pytest.fixture(scope="module")
def real_tasks() -> list:
    from pilot402.pregen.tasks import load_all_tasks
    if not TASKS_DIR.is_dir():
        pytest.skip("data/tasks/ is empty; run pregen first")
    tasks = load_all_tasks(TASKS_DIR)
    if not tasks:
        pytest.skip("data/tasks/ is empty; run pregen first")
    return tasks


# ---------------------------------------------------------------------------
# Unit — Stationary
# ---------------------------------------------------------------------------


class TestStationary:
    def test_is_subclass_of_scenario(self) -> None:
        assert issubclass(StationaryScenario, Scenario)
        assert StationaryScenario.name == ScenarioId.S1_STATIONARY

    def test_effective_price_identity(self) -> None:
        s = StationaryScenario()
        for round_idx in (0, 1000, 9999):
            for pid in ProviderId:
                assert s.effective_price(round_idx, pid, 0.01) == 0.01
                assert s.effective_price(round_idx, pid, 0.0005) == 0.0005

    def test_transform_record_identity(self) -> None:
        s = StationaryScenario()
        rec = _make_record(provider_id=ProviderId.P_MID)
        for round_idx in (0, 5000, 9999):
            assert s.transform_record(round_idx, rec) is rec


# ---------------------------------------------------------------------------
# Unit — Mid Outage (S2)
# ---------------------------------------------------------------------------


class TestMidOutage:
    def test_construction_validates(self) -> None:
        rng = default_rng(0)
        with pytest.raises(ValueError):
            MidOutageScenario(rng=rng, outage_start=-1)
        rng = default_rng(0)
        with pytest.raises(ValueError):
            MidOutageScenario(rng=rng, outage_start=100, outage_end=100)
        rng = default_rng(0)
        with pytest.raises(ValueError):
            MidOutageScenario(rng=rng, outage_failure_rate=1.5)

    def test_pre_shock_identity(self) -> None:
        s = MidOutageScenario(rng=default_rng(0))
        rec = _make_record(provider_id=ProviderId.P_MID)
        for round_idx in (0, 1500, s.outage_start - 1):
            out = s.transform_record(round_idx, rec)
            assert out is rec  # no copy — identity

    def test_post_recovery_identity(self) -> None:
        s = MidOutageScenario(rng=default_rng(0))
        rec = _make_record(provider_id=ProviderId.P_MID)
        for round_idx in (s.outage_end, s.outage_end + 100, 9999):
            out = s.transform_record(round_idx, rec)
            assert out is rec

    def test_only_targets_mid(self) -> None:
        s = MidOutageScenario(rng=default_rng(0))
        # Even during outage window, non-Mid records pass through.
        for pid in (ProviderId.P_CHEAP, ProviderId.P_PREMIUM,
                    ProviderId.P_ADV, ProviderId.P_FLAKY):
            rec = _make_record(provider_id=pid)
            for round_idx in (s.outage_start, s.outage_start + 500,
                              s.outage_end - 1):
                out = s.transform_record(round_idx, rec)
                assert out is rec, f"{pid} should be untouched even in outage"

    def test_effective_price_unchanged(self) -> None:
        """S2 only changes failure_flag, not price."""
        s = MidOutageScenario(rng=default_rng(0))
        for round_idx in (0, s.outage_start, 9999):
            assert s.effective_price(round_idx, ProviderId.P_MID, 0.002) == 0.002

    def test_outage_failure_rate_within_bounds(self) -> None:
        """Over 2500 rounds at 30% rate, flip count should be ≈ 750."""
        s = MidOutageScenario(rng=default_rng(0))
        n_flipped = sum(1 for r in range(s.outage_start, s.outage_end)
                        if s.is_outage_round(r))
        n_total = s.outage_end - s.outage_start
        rate = n_flipped / n_total
        # Binomial(2500, 0.30): mean=750, std≈22.9 → 5σ window = [635, 865]
        assert 0.25 < rate < 0.35, (
            f"Empirical rate {rate:.3f} not in 5σ band of nominal 0.30"
        )

    def test_synthetic_timeout_shape(self) -> None:
        """A flipped record must look like a P-flaky timeout."""
        s = MidOutageScenario(rng=default_rng(0))
        rec = _make_record(provider_id=ProviderId.P_MID, q=0.85,
                           cost=0.002, failure=False, code=FailureCode.NONE)
        # Find an outage round that flips.
        flip_round = next(r for r in range(s.outage_start, s.outage_end)
                          if s.is_outage_round(r))
        out = s.transform_record(flip_round, rec)
        assert out is not rec
        assert out.failure_flag is True
        assert out.failure_code == FailureCode.TIMEOUT
        assert out.quality_score.q == 0.0
        # Cost preserved (provider charges even on timeout, mirroring P-flaky).
        assert out.cost_usdc == 0.002
        # Untouched fields stay.
        assert out.task_id == rec.task_id
        assert out.provider_id == rec.provider_id
        assert out.latency_s == rec.latency_s

    def test_idempotent_for_repeated_round(self) -> None:
        """Oracle peek queries the same round multiple times. Outcome must stick."""
        s = MidOutageScenario(rng=default_rng(0))
        rec = _make_record(provider_id=ProviderId.P_MID)
        flip_round = next(r for r in range(s.outage_start, s.outage_end)
                          if s.is_outage_round(r))
        a = s.transform_record(flip_round, rec)
        b = s.transform_record(flip_round, rec)
        c = s.transform_record(flip_round, rec)
        # All three flipped, all three identical in content.
        assert a.failure_flag and b.failure_flag and c.failure_flag

    def test_determinism_across_construction(self) -> None:
        """Same RNG seed → identical flip pattern."""
        s1 = MidOutageScenario(rng=default_rng(123))
        s2 = MidOutageScenario(rng=default_rng(123))
        for r in range(s1.outage_start, s1.outage_end):
            assert s1.is_outage_round(r) == s2.is_outage_round(r)


# ---------------------------------------------------------------------------
# Unit — Premium Drop (S3)
# ---------------------------------------------------------------------------


class TestPremiumDrop:
    def test_construction_validates(self) -> None:
        with pytest.raises(ValueError):
            PremiumDropScenario(shock_round=-1)
        with pytest.raises(ValueError):
            PremiumDropScenario(price_multiplier=0.0)
        with pytest.raises(ValueError):
            PremiumDropScenario(price_multiplier=-0.5)

    def test_pre_shock_identity(self) -> None:
        s = PremiumDropScenario()
        for round_idx in (0, s.shock_round // 2, s.shock_round - 1):
            assert s.effective_price(round_idx, ProviderId.P_PREMIUM, 0.01) == 0.01
            rec = _make_record(provider_id=ProviderId.P_PREMIUM, cost=0.01)
            assert s.transform_record(round_idx, rec) is rec

    def test_post_shock_premium_only(self) -> None:
        s = PremiumDropScenario()
        for pid in ProviderId:
            spec_price = 0.01 if pid == ProviderId.P_PREMIUM else 0.002
            for round_idx in (s.shock_round, s.shock_round + 1000, 9999):
                out_price = s.effective_price(round_idx, pid, spec_price)
                if pid == ProviderId.P_PREMIUM:
                    assert out_price == pytest.approx(spec_price * s.price_multiplier)
                else:
                    assert out_price == spec_price

    def test_post_shock_record_cost_scales(self) -> None:
        s = PremiumDropScenario()
        rec = _make_record(provider_id=ProviderId.P_PREMIUM, cost=0.01)
        out = s.transform_record(s.shock_round, rec)
        assert out is not rec
        assert out.cost_usdc == pytest.approx(0.01 * s.price_multiplier)
        # Quality, failure unchanged.
        assert out.quality_score.q == rec.quality_score.q
        assert out.failure_flag == rec.failure_flag

    def test_post_shock_other_providers_unchanged(self) -> None:
        s = PremiumDropScenario()
        for pid in (ProviderId.P_CHEAP, ProviderId.P_MID,
                    ProviderId.P_ADV, ProviderId.P_FLAKY):
            rec = _make_record(provider_id=pid, cost=0.002)
            out = s.transform_record(s.shock_round + 100, rec)
            assert out is rec  # identity for non-premium

    def test_price_and_record_use_same_multiplier(self) -> None:
        """Critical invariant: affordability check and charge must agree."""
        s = PremiumDropScenario()
        rec = _make_record(provider_id=ProviderId.P_PREMIUM, cost=0.01)
        round_idx = s.shock_round + 500
        eff = s.effective_price(round_idx, ProviderId.P_PREMIUM, 0.01)
        out = s.transform_record(round_idx, rec)
        assert eff == pytest.approx(out.cost_usdc)


# ---------------------------------------------------------------------------
# Factory — build_scenario
# ---------------------------------------------------------------------------


class TestBuildScenario:
    def test_dispatches_s1(self) -> None:
        cfg = ScenarioConfig(name=ScenarioId.S1_STATIONARY)
        s = build_scenario(cfg, master_seed=0)
        assert isinstance(s, StationaryScenario)

    def test_dispatches_s2_with_kwargs(self) -> None:
        cfg = ScenarioConfig(
            name=ScenarioId.S2_DEGRADATION,
            kwargs={"outage_start": 100, "outage_end": 200,
                    "outage_failure_rate": 0.5},
        )
        s = build_scenario(cfg, master_seed=0)
        assert isinstance(s, MidOutageScenario)
        assert s.outage_start == 100
        assert s.outage_end == 200
        assert s.outage_failure_rate == 0.5

    def test_dispatches_s3_with_kwargs(self) -> None:
        cfg = ScenarioConfig(
            name=ScenarioId.S3_PRICE_SHOCK,
            kwargs={"shock_round": 500, "price_multiplier": 0.25},
        )
        s = build_scenario(cfg, master_seed=0)
        assert isinstance(s, PremiumDropScenario)
        assert s.shock_round == 500
        assert s.price_multiplier == 0.25

    def test_s2_deterministic_for_same_seed(self) -> None:
        cfg = ScenarioConfig(name=ScenarioId.S2_DEGRADATION)
        a = build_scenario(cfg, master_seed=42)
        b = build_scenario(cfg, master_seed=42)
        assert isinstance(a, MidOutageScenario)
        assert isinstance(b, MidOutageScenario)
        for r in range(a.outage_start, a.outage_end):
            assert a.is_outage_round(r) == b.is_outage_round(r)

    def test_s2_differs_across_seeds(self) -> None:
        """Different master seeds should yield different outage patterns."""
        cfg = ScenarioConfig(name=ScenarioId.S2_DEGRADATION)
        a = build_scenario(cfg, master_seed=0)
        b = build_scenario(cfg, master_seed=1)
        assert isinstance(a, MidOutageScenario)
        assert isinstance(b, MidOutageScenario)
        diffs = sum(
            1 for r in range(a.outage_start, a.outage_end)
            if a.is_outage_round(r) != b.is_outage_round(r)
        )
        # At p=0.30 vs p=0.30 with independent draws, expected disagreements
        # ≈ 2 * 0.3 * 0.7 = 0.42 of rounds → ≥ 25% almost surely.
        assert diffs > 0.25 * (a.outage_end - a.outage_start)

    def test_s2_invariant_to_run_id(self) -> None:
        """Scenario RNG keyed on scenario_name only — fairness across policies."""
        cfg = ScenarioConfig(name=ScenarioId.S2_DEGRADATION)
        # Construct twice for the same master seed; flip patterns must match.
        # (run_id would only enter via SeedSource.derive in build_scenario;
        # since we don't take run_id there, this is structurally enforced —
        # this test pins the contract.)
        a = build_scenario(cfg, master_seed=7)
        b = build_scenario(cfg, master_seed=7)
        assert isinstance(a, MidOutageScenario)
        assert isinstance(b, MidOutageScenario)
        for r in range(a.outage_start, a.outage_end):
            assert a.is_outage_round(r) == b.is_outage_round(r)

    def test_unknown_scenario_raises(self) -> None:
        # Build a config with a hand-crafted unknown id by monkeying around
        # the enum — we can't easily synthesize a new ScenarioId, so just
        # patch the call site.
        class _Fake:
            name = "S99"  # not a ScenarioId member
        with pytest.raises(ValueError):
            build_scenario(_Fake(), master_seed=0)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Integration — runtime loop with scenarios
# ---------------------------------------------------------------------------


class TestLoopIntegration:
    def test_s1_loop_matches_no_scenario(
        self, real_pregen_store: JsonlPregenStore, real_tasks: list, tmp_path: Path
    ) -> None:
        """Passing StationaryScenario explicitly == omitting scenario."""
        from pilot402.policies import always_mid

        cfg = _cfg_for_integration(num_rounds=200, scenario_id=ScenarioId.S1_STATIONARY)

        def _run(scenario) -> Path:
            log = tmp_path / f"log_{scenario.__class__.__name__}.jsonl"
            with JsonlRecorder(path=log) as rec:
                run_one_seed(
                    cfg,
                    tasks=real_tasks,
                    store=real_pregen_store,
                    policy=always_mid(),
                    wallet=Wallet(total_usdc=cfg.budget.total_usdc,
                                  target_burn_rate=cfg.budget.target_burn_rate),
                    encoder=NaiveEncoder(),
                    reward_calc=RewardCalculator(nu=cfg.reward.nu),
                    recorder=rec, seed=0, scenario=scenario,
                    progress_every=None,
                )
            return log

        a = _run(StationaryScenario())
        b_log = tmp_path / "log_no_scenario.jsonl"
        with JsonlRecorder(path=b_log) as rec:
            run_one_seed(
                cfg,
                tasks=real_tasks,
                store=real_pregen_store,
                policy=always_mid(),
                wallet=Wallet(total_usdc=cfg.budget.total_usdc,
                              target_burn_rate=cfg.budget.target_burn_rate),
                encoder=NaiveEncoder(),
                reward_calc=RewardCalculator(nu=cfg.reward.nu),
                recorder=rec, seed=0, scenario=None,
                progress_every=None,
            )
        assert a.read_text() == b_log.read_text()

    def test_s2_loop_alwaysmid_eats_failures(
        self, real_pregen_store: JsonlPregenStore, real_tasks: list, tmp_path: Path
    ) -> None:
        """AlwaysMid in S2 must accumulate failures during the outage window
        (Mid baseline failure rate is 0%, so any failures are scenario-driven)."""
        from pilot402.policies import always_mid

        cfg = _cfg_for_integration(num_rounds=4000, scenario_id=ScenarioId.S2_DEGRADATION)
        scenario = build_scenario(cfg.scenario, master_seed=0)
        log_path = tmp_path / "log.jsonl"
        with JsonlRecorder(path=log_path) as rec:
            stats = run_one_seed(
                cfg,
                tasks=real_tasks,
                store=real_pregen_store,
                policy=always_mid(),
                wallet=Wallet(total_usdc=cfg.budget.total_usdc,
                              target_burn_rate=cfg.budget.target_burn_rate),
                encoder=NaiveEncoder(),
                reward_calc=RewardCalculator(nu=cfg.reward.nu),
                recorder=rec, seed=0, scenario=scenario,
                progress_every=None,
            )

        # Outage window is rounds 3000-5500. We ran 4000 rounds → 1000 in window.
        # At 30% failure rate, expect ~300 ± 30 failures.
        # AlwaysMid picks Mid every round, so window failures ≈ scenario flips.
        assert stats.failure_count > 200
        assert stats.failure_count < 400

    def test_s2_loop_no_failures_outside_window(
        self, real_pregen_store: JsonlPregenStore, real_tasks: list, tmp_path: Path
    ) -> None:
        """Run AlwaysMid for 2999 rounds (just before outage). Mid has 0%
        natural failure rate, so failure_count should be 0."""
        from pilot402.policies import always_mid

        cfg = _cfg_for_integration(num_rounds=2999, scenario_id=ScenarioId.S2_DEGRADATION)
        scenario = build_scenario(cfg.scenario, master_seed=0)
        with JsonlRecorder(path=tmp_path / "log.jsonl") as rec:
            stats = run_one_seed(
                cfg, tasks=real_tasks, store=real_pregen_store,
                policy=always_mid(),
                wallet=Wallet(total_usdc=cfg.budget.total_usdc,
                              target_burn_rate=cfg.budget.target_burn_rate),
                encoder=NaiveEncoder(),
                reward_calc=RewardCalculator(nu=cfg.reward.nu),
                recorder=rec, seed=0, scenario=scenario,
                progress_every=None,
            )
        assert stats.failure_count == 0

    def test_s3_loop_premium_charged_at_discount(
        self, real_pregen_store: JsonlPregenStore, real_tasks: list, tmp_path: Path
    ) -> None:
        """Run AlwaysPremium across the shock. After shock, charged costs
        for premium must drop by the multiplier."""
        from pilot402.policies import always_premium

        cfg = _cfg_for_integration(num_rounds=4000, scenario_id=ScenarioId.S3_PRICE_SHOCK)
        scenario = build_scenario(cfg.scenario, master_seed=0)
        log_path = tmp_path / "log.jsonl"
        with JsonlRecorder(path=log_path) as rec:
            run_one_seed(
                cfg, tasks=real_tasks, store=real_pregen_store,
                policy=always_premium(),
                wallet=Wallet(total_usdc=cfg.budget.total_usdc,
                              target_burn_rate=cfg.budget.target_burn_rate),
                encoder=NaiveEncoder(),
                reward_calc=RewardCalculator(nu=cfg.reward.nu),
                recorder=rec, seed=0, scenario=scenario,
                progress_every=None,
            )

        records = [LogRecord.model_validate_json(line) for line
                   in log_path.read_text().splitlines()]
        pre_shock = [r for r in records if r.round < scenario.shock_round
                     and r.chosen_arm == ProviderId.P_PREMIUM]
        post_shock = [r for r in records if r.round >= scenario.shock_round
                      and r.chosen_arm == ProviderId.P_PREMIUM]
        assert pre_shock, "expected some pre-shock premium charges"
        assert post_shock, "expected some post-shock premium charges"
        # Pre-shock cost should center on $0.01; post-shock on $0.002.
        assert all(abs(r.charged_cost_usdc - 0.01) < 1e-9 for r in pre_shock)
        assert all(abs(r.charged_cost_usdc - 0.002) < 1e-9 for r in post_shock)


# ---------------------------------------------------------------------------
# Integration — True Oracle with scenarios
# ---------------------------------------------------------------------------


class TestOracleWithScenarios:
    def test_oracle_avoids_mid_during_s2_outage(
        self, real_pregen_store: JsonlPregenStore, real_tasks: list, tmp_path: Path
    ) -> None:
        """Oracle has hindsight; it should never pick Mid on a forced-timeout
        round when alternatives exist."""
        cfg = _cfg_for_integration(num_rounds=4000, scenario_id=ScenarioId.S2_DEGRADATION)
        scenario = build_scenario(cfg.scenario, master_seed=0)
        log_path = tmp_path / "log.jsonl"
        with JsonlRecorder(path=log_path) as rec:
            stats = run_true_oracle_seed(
                cfg, tasks=real_tasks, store=real_pregen_store,
                wallet=Wallet(total_usdc=cfg.budget.total_usdc,
                              target_burn_rate=cfg.budget.target_burn_rate),
                encoder=NaiveEncoder(),
                reward_calc=RewardCalculator(nu=cfg.reward.nu),
                recorder=rec, seed=0, scenario=scenario,
            )

        # Oracle's failure_count should be 0 — even in an outage, it picks
        # a non-failing arm if any exists. (P-flaky may still fail, but the
        # Oracle will avoid it; everything else is no-failure under S1+S2.)
        assert stats.failure_count == 0

    def test_oracle_s3_pulls_more_premium_post_shock(
        self, real_pregen_store: JsonlPregenStore, real_tasks: list, tmp_path: Path
    ) -> None:
        """In S3, Premium becomes attractive post-shock; Oracle's premium-share
        in the post-shock window should exceed its pre-shock share."""
        cfg = _cfg_for_integration(num_rounds=4000, scenario_id=ScenarioId.S3_PRICE_SHOCK)
        scenario = build_scenario(cfg.scenario, master_seed=0)
        log_path = tmp_path / "log.jsonl"
        with JsonlRecorder(path=log_path) as rec:
            run_true_oracle_seed(
                cfg, tasks=real_tasks, store=real_pregen_store,
                wallet=Wallet(total_usdc=cfg.budget.total_usdc,
                              target_burn_rate=cfg.budget.target_burn_rate),
                encoder=NaiveEncoder(),
                reward_calc=RewardCalculator(nu=cfg.reward.nu),
                recorder=rec, seed=0, scenario=scenario,
            )

        records = [LogRecord.model_validate_json(line) for line
                   in log_path.read_text().splitlines()]
        pre = [r for r in records if r.round < scenario.shock_round]
        post = [r for r in records if r.round >= scenario.shock_round]
        assert pre and post
        pre_premium = sum(1 for r in pre if r.chosen_arm == ProviderId.P_PREMIUM)
        post_premium = sum(1 for r in post if r.chosen_arm == ProviderId.P_PREMIUM)
        pre_rate = pre_premium / len(pre)
        post_rate = post_premium / len(post)
        assert post_rate > pre_rate, (
            f"Oracle pre-shock premium share {pre_rate:.2%} should be < "
            f"post-shock {post_rate:.2%}"
        )

    def test_oracle_beats_alwaysmid_in_s2(
        self, real_pregen_store: JsonlPregenStore, real_tasks: list, tmp_path: Path
    ) -> None:
        """In S2, AlwaysMid eats failures; Oracle dodges them. Oracle's PA-reward
        per round must exceed AlwaysMid's by a clear margin."""
        from pilot402.policies import always_mid

        cfg = _cfg_for_integration(num_rounds=4000, scenario_id=ScenarioId.S2_DEGRADATION)
        scenario = build_scenario(cfg.scenario, master_seed=0)

        # Oracle
        oracle_stats = run_true_oracle_seed(
            cfg, tasks=real_tasks, store=real_pregen_store,
            wallet=Wallet(total_usdc=cfg.budget.total_usdc,
                          target_burn_rate=cfg.budget.target_burn_rate),
            encoder=NaiveEncoder(),
            reward_calc=RewardCalculator(nu=cfg.reward.nu),
            recorder=None, seed=0, scenario=scenario,
        )
        oracle_per_round = oracle_stats.cum_pa_reward / oracle_stats.rounds_completed

        # AlwaysMid (need fresh scenario — flips are a one-time roll, not
        # consumed; safe to reuse, but rebuild for hygiene).
        scenario_b = build_scenario(cfg.scenario, master_seed=0)
        log_path = tmp_path / "mid.jsonl"
        with JsonlRecorder(path=log_path) as rec:
            mid_stats = run_one_seed(
                cfg, tasks=real_tasks, store=real_pregen_store,
                policy=always_mid(),
                wallet=Wallet(total_usdc=cfg.budget.total_usdc,
                              target_burn_rate=cfg.budget.target_burn_rate),
                encoder=NaiveEncoder(),
                reward_calc=RewardCalculator(nu=cfg.reward.nu),
                recorder=rec, seed=0, scenario=scenario_b,
                progress_every=None,
            )
        import json
        mid_pa = sum(json.loads(line)["payment_aware_reward"]
                     for line in log_path.read_text().splitlines())
        mid_per_round = mid_pa / mid_stats.rounds_completed

        assert oracle_per_round > mid_per_round, (
            f"Oracle ({oracle_per_round:.3f}) should beat AlwaysMid "
            f"({mid_per_round:.3f}) in S2 outage"
        )
