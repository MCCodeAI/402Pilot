"""RandomPolicy — uniform-random baseline.

Picks one provider uniformly at random from the affordable set each round.
Ignores the context vector and the post-call utility; ``update`` is a no-op.

Used as:

* a smoke-test bandit for the runtime loop (does the orchestration plumb
  end-to-end before any real algorithm shows up?), and
* a sanity baseline in the paper's results table — any non-trivial policy
  must beat random.
"""

from __future__ import annotations

from dataclasses import dataclass

from numpy.random import Generator

from pilot402.core import ProviderId
from pilot402.core.interfaces import ContextVector


@dataclass
class RandomPolicy:
    """Stateless uniform-random arm picker.

    Args:
        rng: ``numpy.random.Generator``; the loop derives this from the
             per-seed ``SeedSource`` so two runs at the same seed get the
             same sequence of arm picks.
    """

    rng: Generator

    def select(
        self,
        context: ContextVector,  # noqa: ARG002 — random ignores context
        affordable_arms: tuple[ProviderId, ...],
    ) -> ProviderId:
        if not affordable_arms:
            raise ValueError(
                "RandomPolicy received an empty affordable set; the loop "
                "should detect bankruptcy before invoking the policy."
            )
        idx = int(self.rng.integers(0, len(affordable_arms)))
        return affordable_arms[idx]

    def update(
        self,
        context: ContextVector,  # noqa: ARG002
        arm: ProviderId,  # noqa: ARG002
        utility: float,  # noqa: ARG002
        observed_cost: float,  # noqa: ARG002
    ) -> None:
        """No-op. RandomPolicy does not learn."""
        return None


__all__ = ["RandomPolicy"]
