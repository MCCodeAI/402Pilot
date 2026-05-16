"""Composite quality evaluator for the four benchmark task types."""

from __future__ import annotations

from dataclasses import dataclass

from pilot402.core import EvaluatorBackend, QualityScore, Task, TaskType
from pilot402.eval.judge_backend import JudgeBackend
from pilot402.eval.metric_backend import max_em_f1, pass_at_1


def backend_for(task_type: TaskType) -> EvaluatorBackend:
    if task_type is TaskType.T1_CODING:
        return EvaluatorBackend.PASS_AT_1
    if task_type in (TaskType.T2_MULTIHOP_QA, TaskType.T3A_WEBSEARCH_CLOSED):
        return EvaluatorBackend.EM_F1
    if task_type is TaskType.T3B_WEBSEARCH_OPEN:
        return EvaluatorBackend.JUDGE
    raise ValueError(f"Unknown task type: {task_type!r}")


@dataclass(frozen=True)
class CompositeEvaluator:
    """Dispatch scoring to deterministic metrics or the cached judge."""

    judge: JudgeBackend

    def score(self, task: Task, response: str) -> QualityScore:
        backend = backend_for(task.task_type)
        if backend is EvaluatorBackend.PASS_AT_1:
            return QualityScore(q=pass_at_1(task, response), backend=backend)
        if backend is EvaluatorBackend.EM_F1:
            return QualityScore(q=max_em_f1(response, task.gold_answer), backend=backend)
        return self.judge.score(task.prompt, response)


__all__ = ["CompositeEvaluator", "backend_for"]

