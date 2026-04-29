"""CLI smoke tests for ``scripts.prepare_tasks`` and ``scripts.run_pregen``.

We exercise the argument parsing and ``--dry-run`` paths without invoking
any LLM. The real-call path is exercised manually during Tier 1 thin
pregen and not in CI.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

from scripts import prepare_tasks
from scripts import run_pregen as run_pregen_cli

FIXTURE_TASKS = Path(__file__).parent / "fixtures" / "tasks"


def test_prepare_tasks_reads_existing_caches(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cache = tmp_path / "tasks"
    cache.mkdir()
    for name in ("humaneval", "hotpotqa", "triviaqa", "openweb"):
        shutil.copy(FIXTURE_TASKS / f"{name}.jsonl", cache / f"{name}.jsonl")

    rc = prepare_tasks.main(["--cache-dir", str(cache)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "DONE: 8 tasks" in out  # 4 sources × 2 tasks per fixture


def test_prepare_tasks_subset(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cache = tmp_path / "tasks"
    cache.mkdir()
    shutil.copy(FIXTURE_TASKS / "humaneval.jsonl", cache / "humaneval.jsonl")

    rc = prepare_tasks.main(
        ["--cache-dir", str(cache), "--sources", "humaneval"]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "DONE: 2 tasks" in out


def test_prepare_tasks_bad_limits_format() -> None:
    with pytest.raises(SystemExit):
        prepare_tasks.main(["--limits", "no_equals_sign"])


def test_run_pregen_dry_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Dry-run path must work without any API keys present and must not
    write any files."""

    config_path = tmp_path / "exp.yaml"
    config_path.write_text(
        Path("experiments/main.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    rc = run_pregen_cli.main(
        [
            str(config_path),
            "--providers",
            "P-cheap",
            "--limits",
            "humaneval=0",
            "hotpotqa=0",
            "triviaqa=0",
            "openweb=0",
            "--version-count",
            "1",
            "--dry-run",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert out.startswith("PLAN:")


def test_run_pregen_bad_limits_format(tmp_path: Path) -> None:
    config_path = tmp_path / "exp.yaml"
    config_path.write_text(
        Path("experiments/main.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    with pytest.raises(SystemExit):
        run_pregen_cli.main([str(config_path), "--limits", "bogus"])


def test_run_pregen_module_importable() -> None:
    """The script must be importable as a module so `python -m scripts.run_pregen`
    works. (No assertion needed; reaching this point is the assertion.)"""
    assert run_pregen_cli is not None
    assert "scripts" in sys.modules
