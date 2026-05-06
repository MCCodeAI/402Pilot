"""Policy implementations for 402Pilot.

Each policy satisfies the ``Policy`` Protocol from
``pilot402.core.interfaces``: a ``select`` method that picks one provider
from the affordable set given a context vector, and an ``update`` method
that ingests post-call utility.

Order of arrival (PLAN.md §5):

* ``random.RandomPolicy``   — uniform-random baseline; no learning.
* ``fixed.AlwaysX``         — pin a specific provider; useful for upper /
                              lower bounds (Always-P-premium, Always-P-cheap).
* ``rule.BudgetRule``       — hand-written budget threshold heuristic.
* ``oracle.OraclePolicy``   — hindsight-optimal upper bound.
* ``ts.ThompsonSampling``   — vanilla TS, no discount, no λ.
* ``dts.DiscountedTS``      — adds γ-discount.
* ``padct.PADCTPolicy``     — PA-DCT (this paper's bandit algorithm).
"""

from __future__ import annotations

from pilot402.policies.fixed import (
    FixedPolicy,
    always_cheapest,
    always_mid,
    always_premium,
)
from pilot402.policies.padct import PADCTPolicy
from pilot402.policies.posterior import GaussianPosterior
from pilot402.policies.random import RandomPolicy
from pilot402.policies.rule import BudgetRulePolicy

__all__ = [
    "BudgetRulePolicy",
    "FixedPolicy",
    "GaussianPosterior",
    "PADCTPolicy",
    "RandomPolicy",
    "always_cheapest",
    "always_mid",
    "always_premium",
]
