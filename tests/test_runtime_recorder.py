"""Tests for ``pilot402.runtime.recorder.JsonlRecorder``."""

from __future__ import annotations

from pathlib import Path

import pytest

from pilot402.core import FailureCode, LogRecord, ProviderId, ScenarioId, TaskType
from pilot402.core.interfaces import Recorder
from pilot402.runtime.recorder import JsonlRecorder


def _record(round_idx: int = 0) -> LogRecord:
    return LogRecord(
        run_id="r1",
        seed=0,
        scenario=ScenarioId.S1_STATIONARY,
        round=round_idx,
        task_id=f"t/{round_idx}",
        task_type=TaskType.T1_CODING,
        context=(1.0, 0.0, 0.0, 0.0, 0.5, 1.0, 1.0),
        chosen_arm=ProviderId.P_MID,
        affordable_arms=tuple(ProviderId),
        charged_cost_usdc=0.002,
        latency_s=0.5,
        quality=0.8,
        failure_flag=False,
        failure_code=FailureCode.NONE,
        utility=0.78,
        payment_aware_reward=0.65,
        lambda_t=1.0,
        budget_remaining_usdc=9.998,
    )


def test_implements_recorder_protocol(tmp_path: Path) -> None:
    rec = JsonlRecorder(path=tmp_path / "log.jsonl")
    assert isinstance(rec, Recorder)


def test_write_creates_file_lazily(tmp_path: Path) -> None:
    out = tmp_path / "subdir" / "log.jsonl"
    rec = JsonlRecorder(path=out)
    assert not out.exists(), "file should not be created until first write"
    rec.write(_record())
    assert out.exists()
    rec.close()


def test_round_trip_serialization(tmp_path: Path) -> None:
    out = tmp_path / "log.jsonl"
    with JsonlRecorder(path=out) as rec:
        for i in range(5):
            rec.write(_record(round_idx=i))

    lines = [LogRecord.model_validate_json(line) for line in out.read_text().splitlines()]
    assert len(lines) == 5
    assert [r.round for r in lines] == [0, 1, 2, 3, 4]
    assert lines[2].chosen_arm is ProviderId.P_MID


def test_close_is_idempotent(tmp_path: Path) -> None:
    rec = JsonlRecorder(path=tmp_path / "log.jsonl")
    rec.write(_record())
    rec.close()
    rec.close()  # second close should not raise


def test_writing_after_close_raises(tmp_path: Path) -> None:
    rec = JsonlRecorder(path=tmp_path / "log.jsonl")
    rec.write(_record())
    rec.close()
    with pytest.raises(RuntimeError):
        rec.write(_record())


def test_append_preserves_existing_records(tmp_path: Path) -> None:
    """Two recorders writing to the same path append, not overwrite."""
    out = tmp_path / "log.jsonl"
    with JsonlRecorder(path=out) as rec:
        rec.write(_record(0))
    with JsonlRecorder(path=out) as rec:
        rec.write(_record(1))
    lines = out.read_text().splitlines()
    assert len(lines) == 2
