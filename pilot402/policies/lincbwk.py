r"""LinCBwK-style admissible adaptation — Linear Contextual Bandits with Knapsack.

This policy is an admissible adaptation of the Linear Contextual Bandits
with Knapsack family (Agrawal & Devanur 2016) under the 402Pilot
chosen-arm, receipt-feedback contract (§3 of the paper). It is included
as the canonical "cost-aware contextual bandit" baseline requested by
reviewers; we do not claim it is a complete reproduction of the original
theoretical algorithm.

What we adapt from the LinCBwK family
-------------------------------------
* **Per-arm linear reward and cost estimators on a context vector**,
  which in our setting is a 4-dim one-hot indicator of the task bucket
  (T1 / T2 / T3a / T3b). With one-hot context, the full ridge regression
  ``θ_a = (X^T X + λI)^{-1} X^T y`` collapses to per-(arm, bucket)
  scalar sufficient statistics, which we maintain as ``GaussianPosterior``
  instances with ``gamma=1`` (no discount — matches the LinCBwK assumption
  of stationary linear regression).
* **Knapsack constraint via a dual penalty.** Each round, the score
  ``ucb_r(a, b) − μ · lcb_c(a, b)`` is computed over affordable arms,
  where ``μ`` is a dual variable that grows when the wallet is draining
  faster than time elapses and shrinks otherwise (gradient-style update
  with locked step ``η = 0.01``).
* **Affordable-set mask.** Same mask the runtime loop already supplies;
  ``μ`` provides additional soft-pressure beyond the hard affordable
  cutoff so the policy can prefer cheaper arms before exhausting the
  wallet.

What we do NOT take from the original LinCBwK paper
---------------------------------------------------
* No log-T confidence radius derivation, no problem-dependent regret
  guarantees. ``β`` is a single locked scalar.
* No primal-dual mirror descent over the full LP; we use a much simpler
  consumption-rate gradient that is sufficient for empirical comparison
  on a single-resource budget.
* No drift mechanism. Both posteriors are stationary (``γ = 1``); this
  is intentional, because the role of LinCBwK in the experimental design
  is to show what "budget + context, no drift" accomplishes on its own.

Cost numerical guard
--------------------
The cost lower-confidence-bound ``lcb_c = posterior_mean_c − β · σ_c`` can
be negative in early rounds (the prior + sparse data leave wide error
bars). A negative ``lcb_c`` would invert the sign of the dual penalty —
the score would *reward* a high-uncertainty arm for its uncertainty
in the cost direction, which is the opposite of the intended
"discourage-expensive-arms" effect. We clip ``lcb_c`` at
``cost_floor = 1e-6`` for the same reason ``ContextualBTSPolicy`` clips
its sampled cost: numerical guard, not a substantive design choice. The
asymptotic ``μ · θ_c`` ranking across arms is set by the realized cost
spread and is unaffected by the floor.

Cost normalization
------------------
We maintain the cost posterior on ``c̃ = c / c_max`` (where
``c_max = 0.01`` matches ``PADCTPolicy.max_provider_cost``), so that
``θ_c`` and ``σ_c`` live on the same numerical scale as ``θ_r`` (both
roughly in ``[0, 1]``). Without normalization, raw USD costs in
``[0.0005, 0.01]`` would keep ``θ_c − β · σ_c`` pinned at the floor for
~10⁵ rounds, effectively disabling the cost dimension throughout our
10k-round runs.

Cold-start behaviour
--------------------
There is no forced warm-start. With ``prior_mean = 0.5``,
``prior_var = 0.09``, all arms begin tied at
``ucb_r = 0.5 + β · √0.09 = 0.8``; deterministic tie-break by iteration
order over ``affordable_arms`` resolves the first pull. Subsequent
exploration is driven by the UCB uncertainty term over (arm, bucket)
cells with low ``n_eff``. We make no theoretical guarantee that this
produces uniform exploration; the empirical allocation is reported in
the diagnostics.

Prior configuration and relation to PA-DCT
------------------------------------------
The Q-posterior prior mean (``prior_mean = 0.5``) and likelihood
variance (``noise_var = 0.09``) match PA-DCT's defaults. The Q-prior
**variance** is **not** matched: LinCBwK-Adapt. uses
``prior_var_r = 0.09`` (equal to ``noise_var``, the standard
ridge-regression-style choice that anchors the posterior with one
pseudo-observation of weight equal to a real observation), whereas
PA-DCT uses ``prior_var = 1.0`` (effectively flat — the data quickly
dominate the prior). The C-posterior uses the same
``prior_var_c = 0.09`` for symmetry with the reward side; PA-DCT's
cost posterior uses a much tighter ``c_prior_var = 1e-4`` because it
is initialized at the *known listed price* of each provider, whereas
LinCBwK-Adapt. — being a generic LinCBwK adaptation — does not seed
the cost posterior from listed prices.

The algorithmic differences in the comparison are therefore:
(i) UCB scoring instead of Thompson sampling, (ii) explicit dual
penalty ``μ · lcb_c`` instead of wallet-pressure-scaled
``(1 − λ̃) r − λ̃ c̃``, (iii) no discount on either posterior, and
(iv) ridge-style Q-prior (var = noise_var) versus PA-DCT's flat
Q-prior. These are deliberate locked configurations, not omissions;
the paper text §6 should refer to the Thompson-style Bayesian
baselines (DS-TS, BTS) — not LinCBwK-Adapt. — when claiming
PA-DCT-prior parity.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field

from pilot402.core import ProviderId
from pilot402.core.interfaces import BudgetManager, ContextVector
from pilot402.policies.posterior import GaussianPosterior


def _default_context_to_bucket(context: ContextVector) -> int:
    """Default bucket extractor for ``NaiveEncoder``: argmax of first 4 dims.

    Matches ``pilot402.policies.padct._default_context_to_bucket`` so the
    bucket index is identical to PA-DCT for the same context.
    """

    return max(range(4), key=lambda i: context[i] if i < len(context) else float("-inf"))


@dataclass
class LinCBwKPolicy:
    """Linear Contextual Bandits with Knapsack — admissible adaptation.

    Args:
        wallet:             Budget manager; the policy reads
                            ``wallet.snapshot()["remaining_fraction"]`` to
                            update the dual variable ``μ``.
        provider_ids:       Iterable of provider IDs the policy will see.
                            Used to pre-allocate per-(arm, bucket) posteriors.
        total_rounds:       ``T`` (= ``cfg.num_rounds``). Used to compute
                            the time-fraction reference for the dual update.
        n_buckets:          Number of context buckets. 4 = task types.
        context_to_bucket:  Maps ``ContextVector`` → bucket index ∈ [0, n_buckets).
        prior_mean_r:       μ₀ for reward posterior. Default 0.5
                            (matches PA-DCT Q-posterior).
        prior_var_r:        σ₀² for reward posterior. Default 0.09.
        noise_var_r:        σ² for reward posterior. Default 0.09.
        prior_mean_c:       μ₀ for cost posterior (on normalized cost
                            ``c̃ = c / c_max``). Default 0.5.
        prior_var_c:        σ₀² for cost posterior. Default 0.09.
        noise_var_c:        σ² for cost posterior. Default 0.09.
        c_max:              Cost normalization constant in USD/call.
                            Default 0.01 (matches PA-DCT).
        beta:               UCB / LCB exploration coefficient.
                            Default 1.0. **Locked for the main table;**
                            ``β ∈ {0.5, 2.0}`` reported in Appendix D as
                            robustness sweep.
        eta_dual:           Dual update step. Default 0.01.
        mu_init:            Initial dual variable. Default 0.0.
        mu_max:             Upper bound on ``μ``. Default 100.0.
        cost_floor:         Lower bound for ``lcb_c`` in the score.
                            Default 1e-6. Numerical guard.
    """

    wallet: BudgetManager
    provider_ids: tuple[ProviderId, ...]
    total_rounds: int
    n_buckets: int = 4
    context_to_bucket: Callable[[ContextVector], int] = field(
        default=_default_context_to_bucket
    )
    prior_mean_r: float = 0.5
    prior_var_r: float = 0.09
    noise_var_r: float = 0.09
    prior_mean_c: float = 0.5
    prior_var_c: float = 0.09
    noise_var_c: float = 0.09
    c_max: float = 0.01
    beta: float = 1.0
    eta_dual: float = 0.01
    mu_init: float = 0.0
    mu_max: float = 100.0
    cost_floor: float = 1e-6

    _r_posteriors: dict[ProviderId, list[GaussianPosterior]] = field(init=False)
    _c_posteriors: dict[ProviderId, list[GaussianPosterior]] = field(init=False)
    _mu: float = field(init=False)
    _round: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        if self.n_buckets < 1:
            raise ValueError(f"n_buckets must be >= 1, got {self.n_buckets}")
        if self.total_rounds < 1:
            raise ValueError(f"total_rounds must be >= 1, got {self.total_rounds}")
        if self.beta <= 0:
            raise ValueError(f"beta must be > 0, got {self.beta}")
        if self.eta_dual <= 0:
            raise ValueError(f"eta_dual must be > 0, got {self.eta_dual}")
        if self.mu_max < 0:
            raise ValueError(f"mu_max must be >= 0, got {self.mu_max}")
        if self.cost_floor <= 0:
            raise ValueError(f"cost_floor must be > 0, got {self.cost_floor}")
        if self.c_max <= 0:
            raise ValueError(f"c_max must be > 0, got {self.c_max}")

        # Per-(arm, bucket) posteriors. gamma=1 → no discount (stationary
        # linear regression, faithful to the LinCBwK family contract).
        self._r_posteriors = {
            arm: [
                GaussianPosterior(
                    prior_mean=self.prior_mean_r,
                    prior_var=self.prior_var_r,
                    noise_var=self.noise_var_r,
                    gamma=1.0,
                )
                for _ in range(self.n_buckets)
            ]
            for arm in self.provider_ids
        }
        self._c_posteriors = {
            arm: [
                GaussianPosterior(
                    prior_mean=self.prior_mean_c,
                    prior_var=self.prior_var_c,
                    noise_var=self.noise_var_c,
                    gamma=1.0,
                )
                for _ in range(self.n_buckets)
            ]
            for arm in self.provider_ids
        }
        self._mu = float(self.mu_init)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _bucket_for(self, context: ContextVector) -> int:
        b = self.context_to_bucket(context)
        return b % self.n_buckets

    def _update_dual(self) -> None:
        """Consumption-rate gradient update for ``μ``.

        ``μ`` increases when remaining-budget-fraction drops below
        remaining-time-fraction (the wallet is draining faster than the
        run is elapsing) and decreases otherwise. Locked step ``η_dual``.
        """
        snap = self.wallet.snapshot()
        remaining_frac = snap.get("remaining_fraction", 1.0)
        elapsed_frac = self._round / max(1, self.total_rounds)
        time_remaining_frac = 1.0 - elapsed_frac
        if remaining_frac < time_remaining_frac:
            # Spending too fast → tighten cost penalty.
            self._mu = min(self.mu_max, self._mu + self.eta_dual)
        else:
            # Spending slower than schedule → loosen.
            self._mu = max(0.0, self._mu - self.eta_dual)

    # ------------------------------------------------------------------
    # Policy Protocol
    # ------------------------------------------------------------------

    def select(
        self,
        context: ContextVector,
        affordable_arms: tuple[ProviderId, ...],
    ) -> ProviderId:
        if not affordable_arms:
            raise ValueError(
                "LinCBwKPolicy received an empty affordable set; the "
                "loop should detect bankruptcy before invoking the policy."
            )

        # 1. Dual update (consumption-rate gradient).
        self._update_dual()

        # 2. UCB on reward, LCB on cost (clipped at cost_floor).
        bucket = self._bucket_for(context)
        best_arm: ProviderId | None = None
        best_score = float("-inf")
        for arm in affordable_arms:
            if arm not in self._r_posteriors:
                raise KeyError(
                    f"LinCBwKPolicy: unknown arm {arm.value!r}; "
                    f"provider_ids has {[a.value for a in self.provider_ids]}"
                )
            r_post = self._r_posteriors[arm][bucket]
            c_post = self._c_posteriors[arm][bucket]
            sigma_r = math.sqrt(r_post.posterior_var)
            sigma_c = math.sqrt(c_post.posterior_var)
            ucb_r = r_post.posterior_mean + self.beta * sigma_r
            lcb_c = max(self.cost_floor, c_post.posterior_mean - self.beta * sigma_c)
            score = ucb_r - self._mu * lcb_c
            if score > best_score:
                best_score = score
                best_arm = arm

        assert best_arm is not None  # affordable set is non-empty
        return best_arm

    def update(
        self,
        context: ContextVector,
        arm: ProviderId,
        utility: float,
        observed_cost: float,
    ) -> None:
        """Update reward and (normalized) cost posteriors for the chosen
        (arm, bucket) cell.
        """
        if arm not in self._r_posteriors:
            raise KeyError(
                f"LinCBwKPolicy.update: unknown arm {arm.value!r}; "
                f"provider_ids has {[a.value for a in self.provider_ids]}"
            )
        bucket = self._bucket_for(context)
        self._r_posteriors[arm][bucket].update(utility)
        # Normalize cost to [0, 1] scale before posterior update.
        normalized_cost = observed_cost / self.c_max
        self._c_posteriors[arm][bucket].update(normalized_cost)
        self._round += 1

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    @property
    def mu(self) -> float:
        """Current dual variable (read-only)."""
        return self._mu

    def posterior_state(self) -> dict[str, dict[int, dict[str, float]]]:
        """Snapshot of reward posteriors, keyed by ``arm.value → bucket → stats``."""
        out: dict[str, dict[int, dict[str, float]]] = {}
        for arm, posts in self._r_posteriors.items():
            out[arm.value] = {
                b: {
                    "n_eff": p.n_eff,
                    "s_eff": p.s_eff,
                    "posterior_mean": p.posterior_mean,
                    "posterior_var": p.posterior_var,
                }
                for b, p in enumerate(posts)
            }
        return out

    def cost_posterior_state(self) -> dict[str, dict[int, dict[str, float]]]:
        """Snapshot of cost posteriors (on normalized scale c̃ = c / c_max)."""
        out: dict[str, dict[int, dict[str, float]]] = {}
        for arm, posts in self._c_posteriors.items():
            out[arm.value] = {
                b: {
                    "n_eff": p.n_eff,
                    "s_eff": p.s_eff,
                    "posterior_mean": p.posterior_mean,
                    "posterior_var": p.posterior_var,
                }
                for b, p in enumerate(posts)
            }
        return out


__all__ = ["LinCBwKPolicy"]
