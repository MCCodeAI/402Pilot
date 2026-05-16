"""Shared typed schemas for 402Pilot.

The runtime, pregen pipeline, and analysis scripts exchange only these
Pydantic models and enums. Keeping the wire values stable matters because
JSONL fixtures and result logs are replayed across paper revisions.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProviderId(str, Enum):
    P_CHEAP = "P-cheap"
    P_MID = "P-mid"
    P_PREMIUM = "P-premium"
    P_ADV = "P-adv"
    P_FLAKY = "P-flaky"


class TaskType(str, Enum):
    T1_CODING = "T1"
    T2_MULTIHOP_QA = "T2"
    T3A_WEBSEARCH_CLOSED = "T3a"
    T3B_WEBSEARCH_OPEN = "T3b"


class ScenarioId(str, Enum):
    S1_STATIONARY = "S1"
    S2_DEGRADATION = "S2"
    S3_PRICE_SHOCK = "S3"


class FailureCode(str, Enum):
    NONE = "none"
    TIMEOUT = "timeout"
    PAYMENT_FAILURE = "payment_failure"


class EvaluatorBackend(str, Enum):
    PASS_AT_1 = "pass_at_1"
    EM_F1 = "em_f1"
    JUDGE = "judge"


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ProviderSpec(_FrozenModel):
    provider_id: ProviderId
    model_name: str
    base_price_usdc: float = Field(ge=0.0)
    tier: str


class Task(_FrozenModel):
    task_id: str
    task_type: TaskType
    prompt: str
    gold_answer: str
    difficulty: float = Field(ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class QualityScore(_FrozenModel):
    q: float = Field(ge=0.0, le=1.0)
    backend: EvaluatorBackend
    judge_model_id: str | None = None
    judge_seed: int | None = None


class Reward(_FrozenModel):
    utility: float
    payment_aware_reward: float
    lambda_t: float = Field(ge=0.0)
    mu: float = 0.0
    nu: float = Field(ge=0.0)


class PregenRecord(_FrozenModel):
    schema_version: int = 2
    task_id: str
    task_type: TaskType
    provider_id: ProviderId
    version: int = Field(ge=0)
    response: str
    cost_usdc: float = Field(ge=0.0)
    latency_s: float = Field(ge=0.0)
    failure_flag: bool
    failure_code: FailureCode = FailureCode.NONE
    quality_score: QualityScore
    generated_at: datetime
    temperature: float

    @field_validator("failure_code")
    @classmethod
    def _failure_code_matches_flag(cls, code: FailureCode, info):  # noqa: ANN001
        failure_flag = info.data.get("failure_flag")
        if failure_flag is False and code is not FailureCode.NONE:
            raise ValueError("failure_code must be 'none' when failure_flag is false")
        return code


class LogRecord(_FrozenModel):
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
    failure_code: FailureCode = FailureCode.NONE
    utility: float
    payment_aware_reward: float
    lambda_t: float = Field(ge=0.0)
    budget_remaining_usdc: float = Field(ge=0.0)


class ProviderQuote(_FrozenModel):
    provider_id: ProviderId
    price_usdc: float = Field(ge=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PaymentReceipt(_FrozenModel):
    provider_id: ProviderId
    amount_usdc: float = Field(ge=0.0)
    tx_id: str | None = None
    accepted: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class Outcome(_FrozenModel):
    provider_id: ProviderId
    response: str
    cost_usdc: float = Field(ge=0.0)
    latency_s: float = Field(ge=0.0)
    failure_flag: bool
    failure_code: FailureCode = FailureCode.NONE
    quality_score: QualityScore | None = None
    receipt: PaymentReceipt | None = None


__all__ = [
    "EvaluatorBackend",
    "FailureCode",
    "LogRecord",
    "Outcome",
    "PaymentReceipt",
    "PregenRecord",
    "ProviderId",
    "ProviderQuote",
    "ProviderSpec",
    "QualityScore",
    "Reward",
    "ScenarioId",
    "Task",
    "TaskType",
]

