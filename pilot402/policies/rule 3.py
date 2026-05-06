"""BudgetRulePolicy — hand-written threshold heuristic.

Picks a provider tier based on the wallet's remaining-budget fraction:

    remaining_fraction > high_threshold  → P-premium
    remaining_fraction > low_threshold   → P-mid
    else                                 → P-cheap

This is the kind of rule a developer would hard-code if they didn't know
about bandit algorithms — "spend lavishly while you can, save toward the
end". It serves as a smarter-than-random but non-learning baseline; PA-DCT
should beat it precisely because the budget thresholds are blind to per-task
quality differences (e.g. P-cheap is fine on T2 but terrible on T3a, but
the rule is identical regardless).

Edge case: when the chosen tier isn't in the affordable set (unusual; only
happens if budget is between two providers' prices), we fall back to the
most-expensive affordable arm — preserves the spirit of "use what you can
afford" rather than refusing to act.
"""

from __future__ import annotations

from dataclasses import dataclass

from pilot402.core import ProviderId
from pilot402.core.interfaces import BudgetManager, ContextVector


@dataclass
class BudgetRulePolicy:
    """Threshold heuristic on remaining-budget fraction.

    Args:
        wallet:          Read-only handle for ``snapshot()`` access. The
                         policy queries ``remaining_fraction`` per round.
        high_threshold:  Above this fraction, pick P-premium. Default 0.5.
        low_threshold:   Above this fraction (and below high), pick P-mid.
                         Below this, pick P-cheap. Default 0.2.
        provider_prices: ``{ProviderId: base_price_usdc}`` so the fallback
                         path can pick the most-expensive affordable arm.
                         If omitted, fallback uses ``affordable_arms[0]``.
    """

    wallet: BudgetManager
    high_threshold: float = 0.5
    low_threshold: float = 0.2
    provider_prices: dict[ProviderId, float] | None = None

    def __post_init__(self) -> None:
        if not (0.0 < self.low_threshold < self.high_threshold < 1.0):
            raise ValueError(
                f"thresholds must satisfy 0 < low < high < 1; got "
                f"low={self.low_threshold}, high={self.high_threshold}"
            )

    def _pick_tier(self) -> ProviderId:
        snap = self.wallet.snapshot()
        frac = snap.get("remaining_fraction", 1.0)
        if frac > self.high_threshold:
            return ProviderId.P_PREMIUM
        if frac > self.low_threshold:
            return ProviderId.P_MID
        return ProviderId.P_CHEAP

    def _fallback(self, affordable_arms: tuple[ProviderId, ...]) -> ProviderId:
        if self.provider_prices is None:
            return affordable_arms[0]
        # Pick the most expensive affordable arm.
        ranked = sorted(
            affordable_arms,
            key=lambda p: self.provider_prices.get(p, 0.0),
            reverse=True,
        )
        return ranked[0]

    def select(
        self,
        context: ContextVector,  # noqa: ARG002 — rule reads wallet, not context
        affordable_arms: tuple[ProviderId, ...],
    ) -> ProviderId:
        if not affordable_arms:
            raise ValueError(
                "BudgetRulePolicy received an empty affordable set."
            )
        target = self._pick_tier()
        if target in affordable_arms:
            return target
        return self._fallback(affordable_arms)

    def update(
        self,
        context: ContextVector,  # noqa: ARG002
        arm: ProviderId,  # noqa: ARG002
        utility: float,  # noqa: ARG002
        observed_cost: float,  # noqa: ARG002
    ) -> None:
        """No-op. BudgetRulePolicy doesn't learn from observations."""
        return None


__all__ = ["BudgetRulePolicy"]
