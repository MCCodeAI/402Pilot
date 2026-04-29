"""Cross-module data types for 402Pilot.

These are the *only* shapes that flow between modules. Every type is frozen
(immutable) so that a value passed to one module cannot be mutated by another.

Two of these types are also the on-disk wire format and must be treated as
schema-stable:

* ``PregenRecord`` — one JSONL line in ``data/pregen/`` (Phase 1 output).
* ``LogRecord``    — one JSONL line in ``results/<run_id>/log.jsonl``.

Both carry ``schema_version`` so future migrations can be performed without
invalidating historical artifacts.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TaskType(str, Enum):
    """The three task families plus the web-search sub-types (system_design §2.5)."""

    T1_CODING = "T1"
    T2_MULTIHOP_QA = "T2"
    T3A_WEBSEARCH_CLOSED = "T3a"
    T3B_WEBSEARCH_OPEN = "T3b"


class ProviderId(str, Enum):
    """The K=5 providers locked in PLAN §3.5."""

    P_CHEAP = "P-cheap"
    P_MID = "P-mid"
    P_PREMIUM = "P-premium"
    P_ADV = "P-adv"
    P_FLAKY = "P-flaky"


class ScenarioId(str, Enum):
    """Within-experiment market scenarios (PLAN §3.2)."""

    S1_STATIONARY = "S1"
    S2_DEGRADATION = "S2"
    S3_PRICE_SHOCK = "S3"


class FailureCode(str, Enum):
    """Normalized failure codes returned by the payment executor (system_design §2.4)."""

    NONE = "none"
    TIMEOUT = "timeout"
    PAYMENT_FAILURE = "payment_failure"
    SCHEMA_INVALID = "schema_invalid"
    BUDGET_BLOCK = "budget_block"


class EvaluatorBackend(str, Enum):
    """Quality scoring backends (system_design §2.5)."""

    EM_F1 = "em_f1"
    PASS_AT_1 = "pass_at_1"
    JUDGE = "judge"


# ---------------------------------------------------------------------------
# In-memory types (not on-disk wire format)
# ---------------------------------------------------------------------------


class Task(BaseModel):
    """A single task descriptor presented to the agent in one round."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str
    task_type: TaskType
    prompt: str
    gold_answer: str | None = None
    difficulty: float = Field(ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderSpec(BaseModel):
    """Static provider metadata. Behavior is driven by the pregen dataset."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider_id: ProviderId
    model_name: str
    base_price_usdc: float = Field(gt=0.0)
    tier: str  # "cheap" / "mid" / "premium" — used for sanity checks, not selection


class Decision(BaseModel):
    """Output of the Service Selector for a single round."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    round: int = Field(ge=0)
    task_id: str
    context: tuple[float, ...]
    chosen_arm: ProviderId
    affordable_arms: tuple[ProviderId, ...]


class Outcome(BaseModel):
    """Result of executing a paid call through ``PaymentExecutor`` (system_design §2.4)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    response: str
    charged_cost_usdc: float = Field(ge=0.0)
    latency_s: float = Field(ge=0.0)
    failure_flag: bool
    failure_code: FailureCode
    attempt_count: int = Field(ge=1)


class QualityScore(BaseModel):
    """Output of the Evaluator for a single (task, response) pair."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    q: float = Field(ge=0.0, le=1.0)
    backend: EvaluatorBackend
    judge_model_id: str | None = None
    judge_seed: int | None = None


class Reward(BaseModel):
    """Output of the Reward Calculator (system_design §2.6).

    The policy posterior is updated with ``utility``; ``payment_aware_reward``
    is logged and used for regret accounting.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    utility: float
    payment_aware_reward: float
    lambda_t: float = Field(ge=0.0)
    mu: float = Field(ge=0.0)
    nu: float = Field(ge=0.0)


# ---------------------------------------------------------------------------
# On-disk wire-format types (schema-stable; bump schema_version on changes)
# ---------------------------------------------------------------------------


class PregenRecord(BaseModel):
    """One row of the pregen dataset (``data/pregen/*.jsonl``).

    Generated once in Phase 1 by ``pilot402.pregen``. Read at experiment time
    by ``env/`` and ``eval/`` via the ``PregenStore`` and ``Evaluator``
    interfaces. See ``docs/dataset_schema.md`` for the canonical schema spec.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = 1
    task_id: str
    task_type: TaskType
    provider_id: ProviderId
    version: int = Field(ge=0)
    response: str
    cost_usdc: float = Field(ge=0.0)
    latency_s: float = Field(ge=0.0)
    failure_flag: bool
    failure_code: FailureCode
    quality_score: QualityScore
    generated_at: datetime


class LogRecord(BaseModel):
    """One row of an experiment run log (``results/<run_id>/log.jsonl``).

    Single source of truth for the analysis pipeline. Bump ``schema_version``
    when adding or removing fields.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = 1
    run_id: str
    seed: int
    scenario: ScenarioId
    round: int = Field(ge=0)
    task_id: str
    task_type: TaskType
    context: tuple[float, ...]
    chosen_arm: ProviderId
    affordable_arms: tuple[ProviderId, ...]
    charged_cost_usdc: float = Field(ge=0.0)
    latency_s: float = Field(ge=0.0)
    quality: float = Field(ge=0.0, le=1.0)
    failure_flag: bool
    failure_code: FailureCode
    utility: float
    payment_aware_reward: float
    lambda_t: float = Field(ge=0.0)
    budget_remaining_usdc: float


__all__ = [
    "Decision",
    "EvaluatorBackend",
    "FailureCode",
    "LogRecord",
    "Outcome",
    "PregenRecord",
    "ProviderId",
    "ProviderSpec",
    "QualityScore",
    "Reward",
    "ScenarioId",
    "Task",
    "TaskType",
]
