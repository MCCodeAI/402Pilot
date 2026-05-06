"""Quality scoring for 402Pilot-Bench.

Two surfaces:

* ``score(task, response) -> QualityScore`` — used at pregen time, calls
  the underlying metric backend or LLM-as-judge.
* ``lookup(task_id, provider_id, version) -> QualityScore`` — used at
  experiment time, returns the cached pregen score from the
  ``PregenStore``.

A bandit loop never calls ``score``; if ``lookup`` raises, that is a
missing-record bug, not a fallback trigger.
"""

from pilot402.eval.composite import CompositeEvaluator, backend_for
from pilot402.eval.judge_backend import (
    AnthropicJudgeClient,
    CachedJudgeBackend,
    JudgeBackend,
    JudgeClient,
    JudgeRequest,
    MockJudgeClient,
    OpenRouterJudgeClient,
)
from pilot402.eval.metric_backend import (
    em_score,
    f1_score,
    max_em_f1,
    pass_at_1,
)

__all__ = [
    "AnthropicJudgeClient",
    "CachedJudgeBackend",
    "CompositeEvaluator",
    "JudgeBackend",
    "JudgeClient",
    "JudgeRequest",
    "MockJudgeClient",
    "OpenRouterJudgeClient",
    "backend_for",
    "em_score",
    "f1_score",
    "max_em_f1",
    "pass_at_1",
]
