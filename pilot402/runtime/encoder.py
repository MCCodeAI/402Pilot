"""NaiveEncoder — minimal context-feature implementation of ``Encoder``.

The bandit policy needs a fixed-dimensional context vector at decision
time. ``NaiveEncoder`` packs the most-relevant scalar features into a
7-dim vector, in this order:

    index  feature                       range
    -----  ---------------------------   ------------
      0    is_T1   (1 if task is T1)     {0, 1}
      1    is_T2                         {0, 1}
      2    is_T3a                        {0, 1}
      3    is_T3b                        {0, 1}
      4    task.difficulty               [0, 1]
      5    budget_remaining_fraction     [0, 1]
      6    lambda_t (clipped at 5.0)     [0, 5]

Why these features:

* The four task-type one-hots let the policy learn per-task-type quality
  estimates (P-cheap is great on T2 but weak on T3a, etc).
* ``difficulty`` is the per-task signal (length-derived heuristic from
  the loader); useful within a task type.
* ``budget_remaining_fraction`` and ``lambda_t`` give the policy a sense
  of budget pressure without forcing it to recompute λ-dynamics itself.

This is intentionally simple. Sophisticated context (recent provider
performance EWMAs, response-length statistics) lives in a future
``ContextfulEncoder`` swap-in.
"""

from __future__ import annotations

from dataclasses import dataclass

from pilot402.core.interfaces import ContextVector, EncoderState
from pilot402.core.types import Task, TaskType

_TASK_TYPE_ORDER: tuple[TaskType, ...] = (
    TaskType.T1_CODING,
    TaskType.T2_MULTIHOP_QA,
    TaskType.T3A_WEBSEARCH_CLOSED,
    TaskType.T3B_WEBSEARCH_OPEN,
)


@dataclass(frozen=True)
class NaiveEncoder:
    """Stateless 7-dim feature encoder.

    Args:
        lambda_clip: upper bound on ``lambda_t`` before clipping. Default 5.0.
                     This keeps λ feature on a similar scale to the others
                     even during severe overspend (e.g. λ=50 from a runaway
                     burn rate).
    """

    lambda_clip: float = 5.0

    @property
    def feature_dim(self) -> int:
        return 7

    def encode(self, task: Task, state: EncoderState) -> ContextVector:
        """Pack (task, runtime_state) into a fixed-dim context vector.

        ``state`` keys consumed (others ignored — forward-compatible):

        * ``"remaining_fraction"`` — float in [0, 1]; 1.0 if not provided.
        * ``"lambda_t"``           — float ≥ 0; 1.0 if not provided.
        """

        type_onehot = tuple(1.0 if task.task_type is t else 0.0 for t in _TASK_TYPE_ORDER)
        remaining_fraction = float(state.get("remaining_fraction", 1.0))
        lambda_t = float(state.get("lambda_t", 1.0))
        lambda_feature = max(0.0, min(lambda_t, self.lambda_clip))
        return (
            *type_onehot,
            float(task.difficulty),
            remaining_fraction,
            lambda_feature,
        )


__all__ = ["NaiveEncoder"]
