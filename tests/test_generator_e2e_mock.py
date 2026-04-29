"""End-to-end test for ``pilot402.pregen.run_pregen``.

Drives the orchestrator with mock backends through the full path:
load tasks (from fixtures) → pick provider → generate → score →
write JSONL → reload via ``JsonlPregenStore`` → assert round-trip.

This is the closest thing we have to "what Tier 1 thin pregen will do",
minus the actual API calls.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from pilot402.core import (
    BudgetConfig,
    ExperimentConfig,
    FailureCode,
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
from pilot402.eval import CachedJudgeBackend, MockJudgeClient
from pilot402.pregen import JsonlPregenStore, run_pregen
from pilot402.pregen.providers import MockLlmBackend

FIXTURE_TASKS = Path(__file__).parent / "fixtures" / "tasks"


def _make_cfg(seed: int = 42) -> ExperimentConfig:
    return ExperimentConfig(
        run_id="test_e2e",
        seed=seed,
        num_rounds=10,
        num_seeds=1,
        providers=(
            ProviderSpec(
                provider_id=ProviderId.P_CHEAP,
                model_name="qwen3-8b",
                base_price_usdc=0.0005,
                tier="cheap",
            ),
            ProviderSpec(
                provider_id=ProviderId.P_MID,
                model_name="gpt-5.4-mini",
                base_price_usdc=0.002,
                tier="mid",
            ),
            ProviderSpec(
                provider_id=ProviderId.P_PREMIUM,
                model_name="gpt-5.4",
                base_price_usdc=0.02,
                tier="premium",
            ),
            ProviderSpec(
                provider_id=ProviderId.P_ADV,
                model_name="gpt-5.4-mini",
                base_price_usdc=0.002,
                tier="mid",
            ),
            ProviderSpec(
                provider_id=ProviderId.P_FLAKY,
                model_name="gpt-5.4-mini",
                base_price_usdc=0.002,
                tier="mid",
            ),
        ),
        scenario=ScenarioConfig(name=ScenarioId.S1_STATIONARY),
        budget=BudgetConfig(
            total_usdc=1.0, lambda_0=1.0, alpha=1.0, target_burn_rate=0.01
        ),
        reward=RewardConfig(mu=0.05, nu=0.5),
        policy=PolicyConfig(name="padcts"),
        paths=PathConfig(),
        x402=X402Settings(),
        llm_keys=LlmKeysSettings(),
        judge=JudgeSettings(),
    )


@pytest.fixture
def runtime(tmp_path: Path) -> tuple[ExperimentConfig, Path, Path]:
    task_dir = tmp_path / "tasks"
    pregen_dir = tmp_path / "pregen"
    # Copy only the triviaqa fixture to keep the test fast and predictable —
    # T3a is the cleanest path (deterministic EM/F1, no judge or subprocess).
    task_dir.mkdir()
    shutil.copy(FIXTURE_TASKS / "triviaqa.jsonl", task_dir / "triviaqa.jsonl")
    return _make_cfg(), task_dir, pregen_dir


def _all_provider_mocks() -> dict[ProviderId, MockLlmBackend]:
    return {pid: MockLlmBackend() for pid in ProviderId}


def _judge(tmp_path: Path) -> CachedJudgeBackend:
    return CachedJudgeBackend(
        client=MockJudgeClient(),
        cache_path=tmp_path / "judge.jsonl",
        model_id="mock-judge",
    )


def test_dry_run_returns_planned_cell_count(
    runtime: tuple[ExperimentConfig, Path, Path], tmp_path: Path
) -> None:
    cfg, task_dir, pregen_dir = runtime
    n = run_pregen(
        cfg,
        backends=dict(_all_provider_mocks()),
        judge=_judge(tmp_path),
        task_cache_dir=task_dir,
        pregen_out_dir=pregen_dir,
        limits={"humaneval": 0, "hotpotqa": 0, "triviaqa": 2, "openweb": 0},
        version_count=2,
        dry_run=True,
    )
    # 5 providers × 2 tasks × 2 versions = 20 cells.
    assert n == 20
    # Dry run must not write any files.
    assert not pregen_dir.exists() or not any(pregen_dir.iterdir())


def test_e2e_writes_loadable_jsonl(
    runtime: tuple[ExperimentConfig, Path, Path], tmp_path: Path
) -> None:
    cfg, task_dir, pregen_dir = runtime
    n = run_pregen(
        cfg,
        backends=dict(_all_provider_mocks()),
        judge=_judge(tmp_path),
        task_cache_dir=task_dir,
        pregen_out_dir=pregen_dir,
        limits={"humaneval": 0, "hotpotqa": 0, "triviaqa": 2, "openweb": 0},
        version_count=2,
    )
    assert n == 20

    # Output should split per (provider × task_type).
    jsonl_files = sorted(pregen_dir.glob("*.jsonl"))
    assert len(jsonl_files) == 5  # one per provider; one task type only

    # Reload and verify the index covers all (task, provider) pairs we ran.
    store = JsonlPregenStore(pregen_dir)
    assert len(store) == 20
    for pid in ProviderId:
        # Each (provider, task) has versions 0 and 1.
        assert store.versions("trivia/test_001", pid) == (0, 1)
        assert store.versions("trivia/test_002", pid) == (0, 1)


def test_p_flaky_version_0_records_billed_timeout(
    runtime: tuple[ExperimentConfig, Path, Path], tmp_path: Path
) -> None:
    cfg, task_dir, pregen_dir = runtime
    run_pregen(
        cfg,
        backends={pid: MockLlmBackend() for pid in ProviderId},
        judge=_judge(tmp_path),
        task_cache_dir=task_dir,
        pregen_out_dir=pregen_dir,
        limits={"humaneval": 0, "hotpotqa": 0, "triviaqa": 2, "openweb": 0},
        version_count=5,
    )
    store = JsonlPregenStore(pregen_dir)
    # Version 0 of P-flaky must be a billed timeout per ADVERSARIAL_VERSIONS.
    rec = store.get("trivia/test_001", ProviderId.P_FLAKY, version=0)
    assert rec.failure_flag is True
    assert rec.failure_code is FailureCode.TIMEOUT
    assert rec.cost_usdc == 0.002
    assert rec.response == ""
    assert rec.quality_score.q == 0.0

    # Versions 1-4 must NOT be timeouts.
    for v in (1, 2, 3, 4):
        rec = store.get("trivia/test_001", ProviderId.P_FLAKY, version=v)
        assert rec.failure_flag is False


def test_run_is_deterministic_for_fixed_seed(
    runtime: tuple[ExperimentConfig, Path, Path], tmp_path: Path
) -> None:
    cfg, task_dir, _ = runtime

    pregen_dir_a = tmp_path / "pregen_a"
    pregen_dir_b = tmp_path / "pregen_b"
    for out in (pregen_dir_a, pregen_dir_b):
        run_pregen(
            cfg,
            backends={pid: MockLlmBackend() for pid in ProviderId},
            judge=_judge(tmp_path / out.name),
            task_cache_dir=task_dir,
            pregen_out_dir=out,
            limits={"humaneval": 0, "hotpotqa": 0, "triviaqa": 1, "openweb": 0},
            version_count=2,
        )
    a_files = sorted(p.name for p in pregen_dir_a.glob("*.jsonl"))
    b_files = sorted(p.name for p in pregen_dir_b.glob("*.jsonl"))
    assert a_files == b_files
    # Compare every record except generated_at (a real wall-clock timestamp).
    for name in a_files:
        recs_a = (pregen_dir_a / name).read_text(encoding="utf-8").splitlines()
        recs_b = (pregen_dir_b / name).read_text(encoding="utf-8").splitlines()
        assert len(recs_a) == len(recs_b)
        for line_a, line_b in zip(recs_a, recs_b, strict=True):
            import json

            ra = json.loads(line_a)
            rb = json.loads(line_b)
            ra.pop("generated_at", None)
            rb.pop("generated_at", None)
            assert ra == rb


def test_missing_backend_for_subset_raises(
    runtime: tuple[ExperimentConfig, Path, Path], tmp_path: Path
) -> None:
    cfg, task_dir, pregen_dir = runtime
    with pytest.raises(KeyError):
        run_pregen(
            cfg,
            backends={ProviderId.P_CHEAP: MockLlmBackend()},  # missing the rest
            judge=_judge(tmp_path),
            task_cache_dir=task_dir,
            pregen_out_dir=pregen_dir,
            limits={"humaneval": 0, "hotpotqa": 0, "triviaqa": 1, "openweb": 0},
            version_count=1,
        )


def test_version_count_zero_rejected(
    runtime: tuple[ExperimentConfig, Path, Path], tmp_path: Path
) -> None:
    cfg, task_dir, pregen_dir = runtime
    with pytest.raises(ValueError):
        run_pregen(
            cfg,
            backends={pid: MockLlmBackend() for pid in ProviderId},
            judge=_judge(tmp_path),
            task_cache_dir=task_dir,
            pregen_out_dir=pregen_dir,
            limits={"humaneval": 0, "hotpotqa": 0, "triviaqa": 1, "openweb": 0},
            version_count=0,
        )
