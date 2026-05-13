"""Wallet — concrete implementation of the ``BudgetManager`` Protocol.

The wallet tracks total budget and cumulative spend. Once per round it is
told how much was charged (``record_spend``); the policy queries
``get_lambda()`` between rounds to incorporate budget pressure into the
arm-selection reward.

λ-dynamics (system_design §2.2, PLAN §3.5):

    λ_t = λ_0 · exp(α · burn_dev_t)
    burn_dev_t = (actual_burn_rate_t − target_burn_rate) / target_burn_rate

``burn_dev_t`` is **signed**: negative when under-spending, zero when
on the linear burn plan, positive when over-spending. This matches the
paper's symbol $b_{\text{dev}, t}$ (§Problem Formulation).

where:

    actual_burn_rate_t = spent_t / (round_t × budget_per_round_target)
    budget_per_round_target = total_budget × target_burn_rate / total_budget
                            = target_burn_rate per round (fraction of total)

Concretely, for ``main.yaml`` defaults (total_budget = $50, target_burn_rate
= 0.0001, num_rounds = 10000), the wallet expects spend = $0.005 / round
(= 1/10000 of total per round, the rate at which the budget would last
exactly the full run). Always-Mid spends $0.002 / round (≈ 40% of target,
**raw λ_t ≈ 0.6**). Always-Premium spends $0.01 / round (2× target →
burn_dev = +1.0 → **raw λ_t ≈ 7.4**).

This module returns the **raw** λ_t. The downstream reward calculator
sigmoid-normalizes it into ``λ_norm = λ_t / (1+λ_t) ∈ (0, 1)`` for use as
a bounded decision weight; see ``pilot402/runtime/reward.py``. The two
quantities are semantically distinct — λ_t describes wallet pressure, λ_norm
describes reward weighting — and both are tracked separately in plots/logs.

Edge case: at round 0 (no spend yet, no rounds elapsed) we return λ_0
unchanged. Same for any time the rolling window has not gathered enough
data to compute a stable rate.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class Wallet:
    """In-memory budget tracker with PA-DCT λ-dynamics.

    Args:
        total_usdc:        starting budget. Once spend ≥ this, ``affordable()``
                           returns False for any positive cost.
        lambda_0:          baseline cost-penalty multiplier. PLAN default = 1.0.
        alpha:             sensitivity of λ to burn-rate deviation. Higher α
                           = sharper response. PLAN default = 2.0.
        target_burn_rate:  desired fraction of total budget to spend per round.
                           Must lie in (0, 1]. With 10,000 rounds and a budget
                           that should "last the run", target_burn_rate ≈ 1/10000
                           = 1e-4. ``main.yaml`` uses 0.01 as a stress-test
                           setting that implies "burn the wallet in ~100 rounds
                           if you always pick premium".
    """

    total_usdc: float
    lambda_0: float = 1.0
    alpha: float = 2.0
    target_burn_rate: float = 0.0001
    _spent: float = field(default=0.0, init=False)
    _rounds: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        if self.total_usdc <= 0:
            raise ValueError(f"total_usdc must be > 0, got {self.total_usdc}")
        if self.lambda_0 <= 0:
            # lambda_0 = 0 is degenerate: λ_t stays 0 forever, so
            # λ_norm = 0/1 = 0, so PA-reward = utility always (cost never
            # penalized regardless of overspending). The bandit becomes a
            # plain quality-maximizer, defeating the "Payment-Aware" half
            # of PA-DCT.
            raise ValueError("lambda_0 must be strictly positive.")
        if self.alpha < 0:
            raise ValueError("alpha must be non-negative.")
        if not (0 < self.target_burn_rate <= 1.0):
            raise ValueError(
                f"target_burn_rate must lie in (0, 1], got {self.target_burn_rate}"
            )

    # ------------------------------------------------------------------
    # BudgetManager Protocol
    # ------------------------------------------------------------------

    def get_lambda(self) -> float:
        """Current cost-penalty multiplier.

        Returns ``lambda_0`` until at least one round has elapsed. After
        that, scales by ``exp(alpha * burn_dev)`` where ``burn_dev`` is
        the signed normalized deviation from the target burn rate
        (negative = under-spending, positive = over-spending).
        """

        if self._rounds == 0:
            return self.lambda_0
        actual_rate = (self._spent / self.total_usdc) / self._rounds
        burn_dev = (actual_rate - self.target_burn_rate) / self.target_burn_rate
        # Cap exponent to avoid float overflow on pathological streaks.
        capped = max(min(self.alpha * burn_dev, 50.0), -50.0)
        return self.lambda_0 * math.exp(capped)

    def affordable(self, cost_usdc: float) -> bool:
        if cost_usdc < 0:
            raise ValueError(f"cost_usdc must be non-negative, got {cost_usdc}")
        return self._spent + cost_usdc <= self.total_usdc

    def record_spend(self, cost_usdc: float) -> None:
        """Commit a charged amount and advance the round counter by one.

        ``cost_usdc`` may be 0 (e.g. a budget block round where no payment
        attempt was made). It must be non-negative; a negative value is a
        bug, not a refund. The round counter advances regardless of cost
        so that burn-rate normalization is per-round, not per-paid-round.
        """

        if cost_usdc < 0:
            raise ValueError(f"cost_usdc must be non-negative, got {cost_usdc}")
        self._spent += cost_usdc
        self._rounds += 1

    def snapshot(self) -> dict[str, float]:
        return {
            "total_usdc": self.total_usdc,
            "spent_usdc": self._spent,
            "remaining_usdc": self.total_usdc - self._spent,
            "remaining_fraction": (self.total_usdc - self._spent) / self.total_usdc,
            "rounds_elapsed": float(self._rounds),
            "lambda_t": self.get_lambda(),
        }

    # ------------------------------------------------------------------
    # Convenience accessors (not part of the Protocol)
    # ------------------------------------------------------------------

    @property
    def remaining(self) -> float:
        return self.total_usdc - self._spent

    @property
    def spent(self) -> float:
        return self._spent

    @property
    def rounds(self) -> int:
        return self._rounds


__all__ = ["Wallet"]
