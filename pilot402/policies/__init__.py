"""Policy implementations for 402Pilot.

Each policy satisfies the ``Policy`` Protocol from
``pilot402.core.interfaces``: a ``select`` method that picks one provider
from the affordable set given a context vector, and an ``update`` method
that ingests post-call utility.

Policies in the repo:

* ``random.RandomPolicy``           — uniform-random baseline; no learning.
* ``fixed.AlwaysX``                 — pin a specific provider; useful for upper /
                                      lower bounds (Always-P-premium, Always-P-cheap).
* ``rule.BudgetRule``               — hand-written budget threshold heuristic
                                      (Frugal-style static cascade under the
                                      §3 admissible contract).
* ``oracle.OraclePolicy``           — hindsight-optimal upper bound.
* ``contextual_dsts.ContextualDSTSPolicy``
                                    — DS-TS (Qi et al. 2023) extended to task
                                      buckets; drift-aware, no wallet pressure,
                                      no cost posterior.
* ``contextual_bts.ContextualBTSPolicy``
                                    — BTS (Xia et al. 2015) extended to
                                      Gaussian Q/C posteriors and task buckets;
                                      learns cost but no discount.
* ``lincbwk.LinCBwKPolicy``         — LinCBwK-style admissible adaptation
                                      (Agrawal & Devanur 2016); per-(arm, bucket)
                                      ridge regression on UCB(r) − μ·LCB(c) with
                                      dual μ update.
* ``pm_greedy.PMGreedyPolicy``      — Price-Metadata Greedy threshold cascade;
                                      single-pass online adaptation of the
                                      FrugalGPT cascade idea.
* ``sw_ts.SWTSPolicy``              — Sliding-window Thompson Sampling
                                      (Trovò et al. 2020); non-contextual,
                                      drift via window forgetting.
* ``padct.PADCTPolicy``             — PA-DCT (this paper's bandit algorithm).
"""

from __future__ import annotations

from pilot402.policies.contextual_bts import ContextualBTSPolicy
from pilot402.policies.contextual_dsts import ContextualDSTSPolicy
from pilot402.policies.fixed import (
    FixedPolicy,
    always_cheapest,
    always_mid,
    always_premium,
)
from pilot402.policies.lincbwk import LinCBwKPolicy
from pilot402.policies.padct import PADCTPolicy
from pilot402.policies.pm_greedy import PMGreedyPolicy
from pilot402.policies.posterior import GaussianPosterior
from pilot402.policies.random import RandomPolicy
from pilot402.policies.rule import BudgetRulePolicy
from pilot402.policies.sw_ts import SWTSPolicy

__all__ = [
    "BudgetRulePolicy",
    "ContextualBTSPolicy",
    "ContextualDSTSPolicy",
    "FixedPolicy",
    "GaussianPosterior",
    "LinCBwKPolicy",
    "PADCTPolicy",
    "PMGreedyPolicy",
    "RandomPolicy",
    "SWTSPolicy",
    "always_cheapest",
    "always_mid",
    "always_premium",
]
