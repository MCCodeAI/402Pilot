"""Per-round task sampler for the bandit replay loop.

The ``WorkloadSampler`` draws one ``Task`` per round from a fixed pool with
replacement. The sampling is driven by an explicit ``numpy.random.Generator``
so a per-seed run is fully deterministic — the same (seed, round_idx) pair
always yields the same task across machines.

Design choice: uniform sampling from the concatenated task pool. The natural
mix ratios across task types come out close to:

    T1 (HumanEval) :  164 / 823 ≈ 19.9%
    T2 (HotpotQA) :  220 / 823 ≈ 26.7%
    T3a (TriviaQA):  219 / 823 ≈ 26.6%
    T3b (OpenWeb) :  220 / 823 ≈ 26.7%

If a future experiment requires a different mix (e.g. forcing 25/25/25/25
or skewing toward T3b), pass a ``mix`` dict to ``WorkloadSampler``: tasks
are then bucketed by ``task_type`` and a two-step draw (type → task) is
used instead of the flat uniform default.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from numpy.random import Generator

from pilot402.core import Task, TaskType


@dataclass
class WorkloadSampler:
    """Uniform-with-replacement task sampler.

    Args:
        tasks: the full task pool, typically the output of
            ``pilot402.pregen.tasks.load_all_tasks``.
        rng: a ``numpy.random.Generator`` derived from the per-seed
            ``SeedSource`` so two runs with the same seed produce the
            same task sequence.
        mix: optional ``{TaskType: weight}`` to override flat-uniform
            sampling. Weights need not sum to 1 — they are normalized
            internally. ``None`` means "uniform over the flat pool".
    """

    tasks: list[Task]
    rng: Generator
    mix: Mapping[TaskType, float] | None = None
    _by_type: dict[TaskType, list[Task]] = field(init=False, default_factory=dict)
    _types: list[TaskType] = field(init=False, default_factory=list)
    _weights: list[float] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        if not self.tasks:
            raise ValueError("WorkloadSampler requires at least one task.")
        if self.mix is not None:
            for tt in self.mix:
                if tt not in (
                    TaskType.T1_CODING,
                    TaskType.T2_MULTIHOP_QA,
                    TaskType.T3A_WEBSEARCH_CLOSED,
                    TaskType.T3B_WEBSEARCH_OPEN,
                ):
                    raise ValueError(f"Unknown task type in mix: {tt}")
            for task in self.tasks:
                self._by_type.setdefault(task.task_type, []).append(task)
            present = sorted(self._by_type.keys(), key=lambda t: t.value)
            for tt in self.mix:
                if tt not in self._by_type:
                    raise ValueError(
                        f"mix names task type {tt!r} but no such tasks "
                        f"in pool; loaded types: {[t.value for t in present]}"
                    )
            self._types = list(self.mix.keys())
            total = float(sum(self.mix.values()))
            if total <= 0:
                raise ValueError("mix weights must sum to a positive value.")
            self._weights = [self.mix[tt] / total for tt in self._types]

    def next(self) -> Task:
        """Draw one Task. Two-step (type → task) if ``mix`` is set,
        flat-uniform over the entire pool otherwise."""

        if self.mix is None:
            idx = int(self.rng.integers(0, len(self.tasks)))
            return self.tasks[idx]
        # Two-step: pick a task type from the mix, then pick a task within it.
        type_idx = int(self.rng.choice(len(self._types), p=self._weights))
        chosen_type = self._types[type_idx]
        bucket = self._by_type[chosen_type]
        task_idx = int(self.rng.integers(0, len(bucket)))
        return bucket[task_idx]


__all__ = ["WorkloadSampler"]
