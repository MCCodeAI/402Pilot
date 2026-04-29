"""Per-task-type composite evaluator.

Two modes (system_design §2.5, code_structure ``eval/composite.py``):

* ``score(task, response)`` — used at pregen time. Dispatches by
  ``task.task_type`` to the right backend and returns a fresh
  ``QualityScore``.
* ``lookup(task_id, provider_id, version)`` — used at experiment time.
  Returns the cached score from the bound ``PregenStore``. Bandit loops
  MUST go through this path; calling ``score`` during a run is a bug.

The class implements the ``Evaluator`` Protocol from
``pilot402.core.interfaces``.
"""

from __future__ import annotations

from dataclasses import dataclass

from pilot402.core import (
    EvaluatorBackend,
    PregenStore,
    ProviderId,
    QualityScore,
    Task,
    TaskType,
)
from pilot402.eval.judge_backend import JudgeBackend
from pilot402.eval.metric_backend import max_em_f1, pass_at_1


def backend_for(task_type: TaskType) -> EvaluatorBackend:
    """Return the evaluator backend that natively scores ``task_type``.

    Used by the pregen orchestrator to construct a zero-quality
    ``QualityScore`` for failed calls without invoking the real scorer
    (``pass_at_1`` would error on an empty response, ``em_f1`` would error
    without a gold answer for T3b, the judge would burn a billed call to
    score an empty string).
    """

    if task_type is TaskType.T1_CODING:
        return EvaluatorBackend.PASS_AT_1
    if task_type in (TaskType.T2_MULTIHOP_QA, TaskType.T3A_WEBSEARCH_CLOSED):
        return EvaluatorBackend.EM_F1
    if task_type is TaskType.T3B_WEBSEARCH_OPEN:
        return EvaluatorBackend.JUDGE
    raise ValueError(f"Unknown task type: {task_type}")


@dataclass
class CompositeEvaluator:
    """Dispatches scoring by ``task.task_type`` and serves cached lookups."""

    judge: JudgeBackend
    pregen_store: PregenStore | None = None

    def score(self, task: Task, response: str) -> QualityScore:
        if task.task_type is TaskType.T1_CODING:
            q = pass_at_1(task, response)
            return QualityScore(q=q, backend=EvaluatorBackend.PASS_AT_1)

        if task.task_type in (
            TaskType.T2_MULTIHOP_QA,
            TaskType.T3A_WEBSEARCH_CLOSED,
        ):
            if task.gold_answer is None:
                raise ValueError(
                    f"Task {task.task_id} has type {task.task_type} but "
                    f"no gold_answer; cannot score with EM/F1."
                )
            q = max_em_f1(response, task.gold_answer)
            return QualityScore(q=q, backend=EvaluatorBackend.EM_F1)

        if task.task_type is TaskType.T3B_WEBSEARCH_OPEN:
            return self.judge.score(question=task.prompt, response=response)

        raise ValueError(f"Unknown task type: {task.task_type}")

    def lookup(
        self,
        task_id: str,
        provider_id: ProviderId,
        version: int,
    ) -> QualityScore:
        """Return the cached pregen quality score.

        Raises ``RuntimeError`` if no ``pregen_store`` was bound — calling
        ``lookup`` on a pregen-time evaluator is a wiring mistake.
        """

        if self.pregen_store is None:
            raise RuntimeError(
                "CompositeEvaluator.lookup requires a bound PregenStore. "
                "If you are running pregen, call score() instead."
            )
        record = self.pregen_store.get(task_id, provider_id, version)
        return record.quality_score
