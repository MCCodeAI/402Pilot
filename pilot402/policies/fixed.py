"""FixedPolicy — pin a specific provider, every round.

Three named factories the paper compares against:

* ``always_cheapest()``   — pick P-cheap. Lower bound on quality, upper
                            bound on rounds-survived per fixed budget.
* ``always_mid()``        — pick P-mid. The "default that's good enough"
                            heuristic; cheap-tier failure rate isn't a
                            problem because mid is reliable.
* ``always_premium()``    — pick P-premium. Pays maximum cost for maximum
                            quality; with the paper budget, exhausts the
                            wallet near round ~5,000.

Edge case: if the target provider isn't in the affordable set (only
possible if the budget is between two providers' prices), fall back to
``affordable_arms[0]``. In practice this shouldn't trigger — the loop's
bankruptcy check fires first if the target isn't affordable AND the
budget is below other providers too.
"""

from __future__ import annotations

from dataclasses import dataclass

from pilot402.core import ProviderId
from pilot402.core.interfaces import ContextVector


@dataclass(frozen=True)
class FixedPolicy:
    """Always pick the configured target provider."""

    target: ProviderId

    def select(
        self,
        context: ContextVector,  # noqa: ARG002 — fixed policy ignores context
        affordable_arms: tuple[ProviderId, ...],
    ) -> ProviderId:
        if not affordable_arms:
            raise ValueError(
                "FixedPolicy received an empty affordable set; the loop "
                "should detect bankruptcy before invoking the policy."
            )
        if self.target in affordable_arms:
            return self.target
        # Edge case: target not affordable. Pick the first affordable
        # arm to keep the run progressing; the bandit will still bankrupt
        # naturally as the wallet drains.
        return affordable_arms[0]

    def update(
        self,
        context: ContextVector,  # noqa: ARG002
        arm: ProviderId,  # noqa: ARG002
        utility: float,  # noqa: ARG002
        observed_cost: float,  # noqa: ARG002
    ) -> None:
        return None


def always_cheapest() -> FixedPolicy:
    """Always-P-cheap baseline."""
    return FixedPolicy(target=ProviderId.P_CHEAP)


def always_mid() -> FixedPolicy:
    """Always-P-mid baseline."""
    return FixedPolicy(target=ProviderId.P_MID)


def always_premium() -> FixedPolicy:
    """Always-P-premium baseline."""
    return FixedPolicy(target=ProviderId.P_PREMIUM)


__all__ = ["FixedPolicy", "always_cheapest", "always_mid", "always_premium"]
