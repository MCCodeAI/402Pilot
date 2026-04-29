"""Tests for ``pilot402.core.config``.

These verify that:

* The placeholder ``experiments/main.yaml`` parses cleanly (the schema
  contract for every downstream YAML).
* Invalid YAMLs raise ``ValidationError`` rather than silently passing.
* Env-sourced keys cannot leak into the YAML.
* The loader is the single point of ``os.environ`` access (asserted by
  importing ``config.py`` and grepping its source for ``os.environ``).
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from pydantic import ValidationError

from pilot402.core import (
    ExperimentConfig,
    ProviderId,
    ScenarioId,
    load_config,
)
from pilot402.core import config as config_mod

FIXTURES = Path(__file__).parent / "fixtures"


def test_main_yaml_placeholder_loads(repo_root: Path) -> None:
    cfg = load_config(repo_root / "experiments" / "main.yaml")
    assert isinstance(cfg, ExperimentConfig)
    assert cfg.num_rounds == 10000
    assert cfg.num_seeds == 30
    assert cfg.scenario.name == ScenarioId.S1_STATIONARY
    ids = {p.provider_id for p in cfg.providers}
    assert ids == {
        ProviderId.P_CHEAP,
        ProviderId.P_MID,
        ProviderId.P_PREMIUM,
        ProviderId.P_ADV,
        ProviderId.P_FLAKY,
    }


def test_provider_lookup_by_id(repo_root: Path) -> None:
    cfg = load_config(repo_root / "experiments" / "main.yaml")
    spec = cfg.provider(ProviderId.P_PREMIUM)
    assert spec.model_name == "GPT-5.4"
    assert spec.base_price_usdc > 0


def test_provider_lookup_missing_raises(repo_root: Path) -> None:
    cfg = load_config(repo_root / "experiments" / "main.yaml")
    with pytest.raises(KeyError):
        # A valid enum value that's just not in this config — manufacture one
        # by removing P-flaky in a sub-config; here we just test the path with
        # a mocked absent provider via reconstruction.
        cfg2 = cfg.model_copy(update={"providers": tuple(p for p in cfg.providers if p.provider_id != ProviderId.P_PREMIUM)})
        cfg2.provider(ProviderId.P_PREMIUM)


def test_invalid_scenario_name_rejected() -> None:
    with pytest.raises(ValidationError):
        load_config(FIXTURES / "bad_scenario.yaml")


def test_duplicate_providers_rejected() -> None:
    with pytest.raises(ValidationError):
        load_config(FIXTURES / "duplicate_providers.yaml")


def test_env_keys_in_yaml_rejected() -> None:
    """``x402``, ``llm_keys``, and ``judge`` come from ``.env``, never from YAML."""
    with pytest.raises(ValueError, match="must not appear in experiment YAML"):
        load_config(FIXTURES / "with_env_key.yaml")


def test_missing_yaml_raises_filenotfound(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "does_not_exist.yaml")


def test_config_is_frozen(repo_root: Path) -> None:
    cfg = load_config(repo_root / "experiments" / "main.yaml")
    with pytest.raises(ValidationError):
        cfg.run_id = "mutated"  # type: ignore[misc]


def test_config_yaml_roundtrip(repo_root: Path) -> None:
    """Serialize → load back. Catches accidental non-JSON-able values."""
    cfg = load_config(repo_root / "experiments" / "main.yaml")
    payload = cfg.model_dump_json()
    rehydrated = ExperimentConfig.model_validate_json(payload)
    assert rehydrated == cfg


def test_config_module_is_only_environ_consumer() -> None:
    """Cross-cutting contract: ``os.environ`` must appear only inside
    ``pilot402.core.config`` (and even there, only via ``pydantic-settings``).

    This test scans the package source files and asserts the rule. As soon
    as any other module reaches into the environment, this turns red.
    """
    package_root = Path(inspect.getfile(config_mod)).parent.parent  # pilot402/
    offenders: list[Path] = []
    for py in package_root.rglob("*.py"):
        if py.name == "config.py" and py.parent.name == "core":
            continue
        text = py.read_text(encoding="utf-8")
        if "os.environ" in text or "os.getenv" in text:
            offenders.append(py)
    assert not offenders, f"os.environ access found outside core/config.py: {offenders}"
