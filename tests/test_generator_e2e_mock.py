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
from pilot402.pregen.providers import MockLlmBackend, RecordingMockBackend

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
                base_price_usdc=0.01,
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
        reward=RewardConfig(nu=0.5),
        policy=PolicyConfig(name="padct"),
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


def test_p_flaky_versions_0_and_1_record_billed_timeouts(
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
    # Versions 0 AND 1 of P-flaky must be billed timeouts per ADVERSARIAL_VERSIONS
    # (calibrated 40% failure rate: 2 of 5 versions).
    for v in (0, 1):
        rec = store.get("trivia/test_001", ProviderId.P_FLAKY, version=v)
        assert rec.failure_flag is True, f"v={v} should be timeout"
        assert rec.failure_code is FailureCode.TIMEOUT
        assert rec.cost_usdc == 0.002
        assert rec.response == ""
        assert rec.quality_score.q == 0.0

    # Versions 2-4 must NOT be timeouts.
    for v in (2, 3, 4):
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


def test_resume_skips_existing_cells(
    runtime: tuple[ExperimentConfig, Path, Path], tmp_path: Path
) -> None:
    """Re-running with resume=True must NOT issue any new LLM calls when all
    cells are already on disk. This is the contract that lets a 4-hour run
    survive Ctrl+C and resume cleanly."""

    cfg, task_dir, pregen_dir = runtime

    # First run: complete all 10 cells (5 providers × 1 task × 2 versions).
    first_backends = {pid: RecordingMockBackend() for pid in ProviderId}
    n_first = run_pregen(
        cfg,
        backends=dict(first_backends),
        judge=_judge(tmp_path / "judge1"),
        task_cache_dir=task_dir,
        pregen_out_dir=pregen_dir,
        limits={"humaneval": 0, "hotpotqa": 0, "triviaqa": 1, "openweb": 0},
        version_count=2,
    )
    assert n_first == 10
    # P-flaky versions 0 AND 1 force billed timeouts WITHOUT calling the backend
    # (40% failure rate). With version_count=2, BOTH P-flaky cells are timeouts,
    # so we expect 8 actual LLM calls (10 cells minus the 2 P-flaky timeouts).
    total_first_calls = sum(len(b.calls) for b in first_backends.values())
    assert total_first_calls == 8

    # Second run with resume=True: every cell is already present → 0 new
    # records written and 0 LLM calls issued.
    second_backends = {pid: RecordingMockBackend() for pid in ProviderId}
    n_second = run_pregen(
        cfg,
        backends=dict(second_backends),
        judge=_judge(tmp_path / "judge2"),
        task_cache_dir=task_dir,
        pregen_out_dir=pregen_dir,
        limits={"humaneval": 0, "hotpotqa": 0, "triviaqa": 1, "openweb": 0},
        version_count=2,
        resume=True,
    )
    assert n_second == 0, "resume should skip every cell when all are on disk"
    total_second_calls = sum(len(b.calls) for b in second_backends.values())
    assert total_second_calls == 0, "resume must NOT call the LLM"

    # The on-disk store still has exactly 10 records (no duplicates).
    store = JsonlPregenStore(pregen_dir)
    assert len(store) == 10


def test_resume_completes_partial_run(
    runtime: tuple[ExperimentConfig, Path, Path], tmp_path: Path
) -> None:
    """Simulate an interrupted run by manually pre-populating SOME records,
    then resume should fill in only the missing ones."""

    cfg, task_dir, pregen_dir = runtime

    # First, write only ProviderId.P_CHEAP records to disk by running with
    # a provider_subset of just P-cheap.
    partial_backends = {pid: RecordingMockBackend() for pid in ProviderId}
    n_partial = run_pregen(
        cfg,
        backends=dict(partial_backends),
        judge=_judge(tmp_path / "judge_partial"),
        task_cache_dir=task_dir,
        pregen_out_dir=pregen_dir,
        limits={"humaneval": 0, "hotpotqa": 0, "triviaqa": 1, "openweb": 0},
        version_count=2,
        provider_subset=(ProviderId.P_CHEAP,),
    )
    assert n_partial == 2  # 1 task × 2 versions
    # Only P-cheap was called.
    assert len(partial_backends[ProviderId.P_CHEAP].calls) == 2
    for pid in ProviderId:
        if pid is ProviderId.P_CHEAP:
            continue
        assert len(partial_backends[pid].calls) == 0

    # Now resume with the FULL provider set. Should run only the 8 missing
    # cells (4 providers × 1 task × 2 versions; P-flaky versions 0 AND 1 take
    # the forced-timeout path with no LLM call, so 6 LLM calls expected).
    resume_backends = {pid: RecordingMockBackend() for pid in ProviderId}
    n_resume = run_pregen(
        cfg,
        backends=dict(resume_backends),
        judge=_judge(tmp_path / "judge_resume"),
        task_cache_dir=task_dir,
        pregen_out_dir=pregen_dir,
        limits={"humaneval": 0, "hotpotqa": 0, "triviaqa": 1, "openweb": 0},
        version_count=2,
        resume=True,
    )
    assert n_resume == 8
    # P-cheap must NOT be re-called.
    assert len(resume_backends[ProviderId.P_CHEAP].calls) == 0
    # Final store has all 10 cells.
    store = JsonlPregenStore(pregen_dir)
    assert len(store) == 10


def test_resume_tolerates_corrupted_last_line(
    runtime: tuple[ExperimentConfig, Path, Path], tmp_path: Path
) -> None:
    """A truncated final line (write killed mid-record) is the realistic
    crash mode. resume should skip it and rerun that one cell."""

    cfg, task_dir, pregen_dir = runtime

    # Complete a real run first to get clean records.
    run_pregen(
        cfg,
        backends={pid: MockLlmBackend() for pid in ProviderId},
        judge=_judge(tmp_path / "judge_init"),
        task_cache_dir=task_dir,
        pregen_out_dir=pregen_dir,
        limits={"humaneval": 0, "hotpotqa": 0, "triviaqa": 1, "openweb": 0},
        version_count=2,
        provider_subset=(ProviderId.P_CHEAP,),
    )

    # Corrupt the file: append a partial JSON line as if the writer was
    # killed mid-record.
    cheap_jsonl = pregen_dir / f"{ProviderId.P_CHEAP.value}__T3a.jsonl"
    with cheap_jsonl.open("a", encoding="utf-8") as fh:
        fh.write('{"task_id": "trivia/test_999", "task_type": "T3a", "provid')

    # Resume with the same provider subset must NOT crash on the bad line.
    backends = {pid: RecordingMockBackend() for pid in ProviderId}
    n = run_pregen(
        cfg,
        backends=dict(backends),
        judge=_judge(tmp_path / "judge_after"),
        task_cache_dir=task_dir,
        pregen_out_dir=pregen_dir,
        limits={"humaneval": 0, "hotpotqa": 0, "triviaqa": 1, "openweb": 0},
        version_count=2,
        provider_subset=(ProviderId.P_CHEAP,),
        resume=True,
    )
    # All 2 cells already on disk, partial line ignored — 0 new work.
    assert n == 0
    assert len(backends[ProviderId.P_CHEAP].calls) == 0
