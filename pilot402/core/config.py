"""Typed configuration for 402Pilot.

Two sources are merged into a single ``ExperimentConfig``:

1. **Environment** (``.env`` / ``os.environ``) — secrets and host-specific
   endpoints (LLM API keys, Anvil RPC URL, x402 wallet, judge identity).
   Loaded via ``pydantic-settings``.
2. **YAML** (``experiments/<name>.yaml``) — experiment shape (rounds,
   providers, scenario, budget, reward weights, policy choice). Each
   experiment YAML is the only source of truth for that run.

This module is the *only* place in the package that reads ``os.environ``.
All other modules receive a parsed ``ExperimentConfig`` and never touch the
environment directly. (See ``code_structure.md``: ``pilot402/core/config.py``.)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from pilot402.core.types import ProviderId, ProviderSpec, ScenarioId

# ---------------------------------------------------------------------------
# Environment-sourced settings (read from .env via pydantic-settings)
# ---------------------------------------------------------------------------


class X402Settings(BaseSettings):
    """Local Anvil devnet + x402 wallet settings.

    Defaults point at the local Anvil fork used by the integration witness.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    anvil_rpc_url: str = Field(default="http://127.0.0.1:8545", alias="ANVIL_RPC_URL")
    anvil_chain_id: int = Field(default=31337, alias="ANVIL_CHAIN_ID")
    x402_wallet_private_key: str = Field(default="", alias="X402_WALLET_PRIVATE_KEY")
    x402_facilitator_url: str = Field(
        default="http://127.0.0.1:4021",
        alias="X402_FACILITATOR_URL",
    )


class LlmKeysSettings(BaseSettings):
    """LLM provider keys, used only during pregen (Phase 1)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    qwen_api_key: str = Field(default="", alias="QWEN_API_KEY")
    judge_api_key: str = Field(default="", alias="JUDGE_API_KEY")


class JudgeSettings(BaseSettings):
    """LLM-as-judge backend identity. Logged as provenance per call.

    ``judge_provider`` selects the wire protocol; the credential always
    comes from ``LlmKeysSettings.judge_api_key`` (env: ``JUDGE_API_KEY``)
    regardless of which gateway is used.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    judge_model: str = Field(default="claude-sonnet-4.6", alias="JUDGE_MODEL")
    judge_seed: int = Field(default=0, alias="JUDGE_SEED")
    judge_provider: str = Field(default="anthropic", alias="JUDGE_PROVIDER")
    judge_base_url: str = Field(default="", alias="JUDGE_BASE_URL")


# ---------------------------------------------------------------------------
# YAML-sourced sub-configs
# ---------------------------------------------------------------------------


class BudgetConfig(BaseModel):
    """Budget manager parameters (system_design §2.2)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    total_usdc: float = Field(gt=0.0, description="Total wallet B for the run.")
    lambda_0: float = Field(ge=0.0, description="Baseline λ when burn rate is on target.")
    alpha: float = Field(ge=0.0, description="Sensitivity of λ to burn-rate excess.")
    target_burn_rate: float = Field(
        gt=0.0,
        description="Target spend per round; budget pressure rises above this.",
    )


class RewardConfig(BaseModel):
    """Reward calculator weights.

    ``nu`` is fixed across the paper experiments. ``lambda_t`` is dynamic and
    lives in ``BudgetConfig``. Latency is logged separately and is not part of
    the reported reward.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    nu: float = Field(ge=0.0, description="Failure penalty weight (constant).")


class PolicyConfig(BaseModel):
    """Selector policy choice + free-form kwargs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(description="Policy registry key (e.g. 'padct', 'always_premium').")
    kwargs: dict[str, Any] = Field(default_factory=dict)


class ScenarioConfig(BaseModel):
    """Within-experiment market scenario."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: ScenarioId
    kwargs: dict[str, Any] = Field(default_factory=dict)


class PathConfig(BaseModel):
    """Filesystem layout. All paths are interpreted relative to the repo root."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pregen_dir: Path = Path("data/pregen")
    tasks_dir: Path = Path("data/tasks")
    results_dir: Path = Path("results")


# ---------------------------------------------------------------------------
# Top-level experiment config
# ---------------------------------------------------------------------------


class ExperimentConfig(BaseModel):
    """Frozen, fully-resolved experiment configuration.

    A copy of this object is serialized to ``results/<run_id>/config.yaml``
    at the start of every run so the configuration is recoverable post-hoc.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    seed: int
    num_rounds: int = Field(gt=0)
    num_seeds: int = Field(gt=0)

    providers: tuple[ProviderSpec, ...]
    scenario: ScenarioConfig
    budget: BudgetConfig
    reward: RewardConfig
    policy: PolicyConfig
    paths: PathConfig = PathConfig()

    # Environment-sourced sub-objects (populated by ``load_config``).
    x402: X402Settings
    llm_keys: LlmKeysSettings
    judge: JudgeSettings

    @field_validator("providers")
    @classmethod
    def _providers_are_unique(
        cls,
        providers: tuple[ProviderSpec, ...],
    ) -> tuple[ProviderSpec, ...]:
        ids = [p.provider_id for p in providers]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate provider_id in providers list.")
        return providers

    def provider(self, provider_id: ProviderId) -> ProviderSpec:
        """Look up a provider by id; raises KeyError if absent."""
        for spec in self.providers:
            if spec.provider_id == provider_id:
                return spec
        raise KeyError(f"Provider {provider_id!r} not in config.")


# ---------------------------------------------------------------------------
# YAML loader — the only public entry point
# ---------------------------------------------------------------------------


def load_config(yaml_path: str | Path) -> ExperimentConfig:
    """Load an experiment YAML and merge in environment-sourced settings.

    The YAML must specify the experiment shape (run_id, seed, num_rounds,
    num_seeds, providers, scenario, budget, reward, policy). Environment
    settings (x402, llm_keys, judge) are filled from ``.env`` / ``os.environ``
    and never appear in the YAML.

    Raises:
        FileNotFoundError: if ``yaml_path`` does not exist.
        pydantic.ValidationError: on schema mismatch.
    """

    path = Path(yaml_path)
    if not path.is_file():
        raise FileNotFoundError(f"Experiment config not found: {path}")

    with path.open("r", encoding="utf-8") as fh:
        raw: dict[str, Any] = yaml.safe_load(fh) or {}

    # Defensive: forbid env-sourced keys from sneaking into the YAML.
    for forbidden in ("x402", "llm_keys", "judge"):
        if forbidden in raw:
            raise ValueError(
                f"Key {forbidden!r} must not appear in experiment YAML; "
                f"it is sourced from the environment."
            )

    return ExperimentConfig(
        **raw,
        x402=X402Settings(),
        llm_keys=LlmKeysSettings(),
        judge=JudgeSettings(),
    )


__all__ = [
    "BudgetConfig",
    "ExperimentConfig",
    "JudgeSettings",
    "LlmKeysSettings",
    "PathConfig",
    "PolicyConfig",
    "RewardConfig",
    "ScenarioConfig",
    "X402Settings",
    "load_config",
]
