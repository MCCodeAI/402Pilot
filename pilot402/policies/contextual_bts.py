r"""Contextual BTS — Budgeted Thompson Sampling extended to task buckets.

Adapted from Xia et al. 2015 (BTS for budgeted multi-armed bandits with
random costs) for head-to-head comparison against PA-DCT in 402Pilot-Bench.
The published BTS is a single-posterior-per-arm algorithm with Bernoulli
reward and cost; we make two adaptations to fit the 402Pilot setup:

* **Continuous Gaussian Q and C posteriors** — utility and realized cost in
  402Pilot-Bench are continuous, so we replace Beta-Bernoulli posteriors
  with the same Normal-Normal Bayesian model PA-DCT uses for fairness.

* **Per-(arm, bucket) posteriors** — published BTS is non-contextual, but
  comparing against PA-DCT requires the same context resolution to
  isolate "what does PA-DCT add beyond stationary cost-posterior learning?"
  rather than confounding cost-learning with context heterogeneity.

Algorithmic essence preserved from published BTS:

* Bayesian posterior over realized cost, learned from receipts
* No discount — stationary cost assumption (γ = 1 on both posteriors)
* Reward-to-cost ratio scoring: ``argmax_a sample(Q[a, k]) / sample(C[a, k])``
* No wallet-pressure scaling — wallet enters only through the
  affordable-set mask, as in published BTS

What BTS does NOT have (and we faithfully omit here):

* No discount mechanism — old observations never fade. Under a price
  shock (S3) or reliability shock (S2), the cost/quality posteriors
  remain anchored on pre-shock evidence and adapt slowly through
  accumulated post-shock samples.
* No explicit λ_t coupling — selection uses the raw r/c ratio in
  per-call $/utility units, not the wallet-pressure-scaled trade-off
  ``(1−λ̃)r − λ̃c̃`` that PA-DCT uses.

Hyperparameter alignment with PA-DCT:

The Q-posterior priors (``prior_mean``, ``prior_var``, ``noise_var``)
and the C-posterior priors (``c_prior_var``, ``c_noise_var``) default to
the same values as PA-DCT so that the only algorithmic differences in
the head-to-head comparison are (i) γ = 1 (no discount), (ii) ratio
scoring instead of wallet-aware weighted scoring. The cost prior mean
comes from each arm's spec price, matching PA-DCT.

Ratio scoring detail: when the sampled cost is below ``cost_floor``
(positive, defaults to 1e-6 USD), the ratio defaults to dividing by the
floor so the score remains finite. This is a Gaussian-adaptation artifact:
unlike Xia 2015's Beta-Bernoulli BTS, our Gaussian C-posterior has
non-negligible negative-sample probability in early rounds. With the
default ``c_prior_var = 1e-4`` (std $\approx 0.01$ USD) and provider spec
costs in $[0.0005, 0.01]$, the prior phase produces negative samples about
$16\%$--$48\%$ of the time depending on the arm; the floor prevents these
from producing inflated ratios. After a handful of observations the
likelihood (``c_noise_var = 1e-6``) shrinks the posterior std to
$\sim 10^{-3}$, and negative samples drop to a few percent or less.
The asymptotic ``argmax_a r/c'' behaviour is set by the realized cost
spread across providers and is unaffected by the floor; the floor only
affects which arms get exploration weight in the first $\sim 10$--$30$
rounds.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from numpy.random import Generator

from pilot402.core import ProviderId
from pilot402.core.interfaces import ContextVector
from pilot402.policies.posterior import GaussianPosterior


def _default_context_to_bucket(context: ContextVector) -> int:
    """Default bucket extractor for ``NaiveEncoder``: argmax of first 4 dims.

    Matches ``pilot402.policies.padct._default_context_to_bucket`` so the
    bucket index is identical to PA-DCT for the same context.
    """

    return max(range(4), key=lambda i: context[i] if i < len(context) else float("-inf"))


@dataclass
class ContextualBTSPolicy:
    """Budgeted Thompson Sampling with per-(arm, bucket) Q and C posteriors.

    Args:
        rng:                NumPy ``Generator`` for stochastic decisions.
        provider_costs:     ``{ProviderId: spec_cost_usdc}`` — used as the
                            cost posterior's prior mean (one entry per arm).
                            Arms not in this dict get no posterior; selecting
                            them raises ``KeyError``. Same wiring as PA-DCT's
                            ``provider_costs``.
        n_buckets:          Number of context buckets. 4 = task types
                            (T1, T2, T3a, T3b).
        context_to_bucket:  Maps ``ContextVector`` → bucket index ∈ [0, n_buckets).
                            Default matches PA-DCT.
        prior_mean:         μ₀ for Q-posterior. Default 0.5 (matches PA-DCT).
        prior_var:          σ₀² for Q-posterior. Default 1.0 (matches PA-DCT).
        noise_var:          σ² for Q-posterior. Default 0.09 (matches PA-DCT).
        c_prior_var:        σ₀² for C-posterior. Default 1e-4 (matches PA-DCT).
        c_noise_var:        σ² for C-posterior. Default 1e-6 (matches PA-DCT).
        cost_floor:         Lower bound for the denominator of the ratio
                            score, in $/call. Default 1e-6. Sampled cost
                            below this value is clipped up to avoid
                            division by ~0.

    Implementation note: this policy does NOT take a ``wallet`` handle.
    The affordable-set filter is applied by the runtime loop, and the
    policy itself is wallet-blind — that is the published BTS contract.
    """

    rng: Generator
    provider_costs: dict[ProviderId, float]
    n_buckets: int = 4
    context_to_bucket: Callable[[ContextVector], int] = field(
        default=_default_context_to_bucket
    )
    prior_mean: float = 0.5
    prior_var: float = 1.0
    noise_var: float = 0.09
    c_prior_var: float = 1e-4
    c_noise_var: float = 1e-6
    cost_floor: float = 1e-6

    _q_posteriors: dict[ProviderId, list[GaussianPosterior]] = field(init=False)
    _c_posteriors: dict[ProviderId, list[GaussianPosterior]] = field(init=False)

    def __post_init__(self) -> None:
        if self.n_buckets < 1:
            raise ValueError(f"n_buckets must be >= 1, got {self.n_buckets}")
        if self.cost_floor <= 0:
            raise ValueError(f"cost_floor must be > 0, got {self.cost_floor}")
        # BTS = no discount → γ = 1 on both posteriors.
        self._q_posteriors = {}
        self._c_posteriors = {}
        for arm, spec_cost in self.provider_costs.items():
            self._q_posteriors[arm] = [
                GaussianPosterior(
                    prior_mean=self.prior_mean,
                    prior_var=self.prior_var,
                    noise_var=self.noise_var,
                    gamma=1.0,
                )
                for _ in range(self.n_buckets)
            ]
            self._c_posteriors[arm] = [
                GaussianPosterior(
                    prior_mean=spec_cost,
                    prior_var=self.c_prior_var,
                    noise_var=self.c_noise_var,
                    gamma=1.0,
                )
                for _ in range(self.n_buckets)
            ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _bucket_for(self, context: ContextVector) -> int:
        b = self.context_to_bucket(context)
        return b % self.n_buckets

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
                "ContextualBTSPolicy received an empty affordable set; the "
                "loop should detect bankruptcy before invoking the policy."
            )

        # NB: no discount step — BTS treats the world as stationary.

        bucket = self._bucket_for(context)

        best_arm: ProviderId | None = None
        best_score = float("-inf")
        for arm in affordable_arms:
            if arm not in self._q_posteriors:
                raise KeyError(
                    f"ContextualBTSPolicy: unknown arm {arm.value!r}; "
                    f"provider_costs has {list(self.provider_costs)}"
                )
            sampled_q = self._q_posteriors[arm][bucket].sample(self.rng)
            sampled_c = self._c_posteriors[arm][bucket].sample(self.rng)
            denom = max(sampled_c, self.cost_floor)
            score = sampled_q / denom
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
        """Update both Q and C posteriors on the chosen (arm, bucket) cell.

        Both posteriors are stationary (γ=1), so updates accumulate
        forever; BTS's intended failure mode under non-stationarity is
        slow adaptation to post-shock evidence, not forgetting pre-shock
        evidence.
        """
        if arm not in self._q_posteriors:
            raise KeyError(
                f"ContextualBTSPolicy.update: unknown arm {arm.value!r}; "
                f"provider_costs has {list(self.provider_costs)}"
            )
        bucket = self._bucket_for(context)
        self._q_posteriors[arm][bucket].update(utility)
        self._c_posteriors[arm][bucket].update(observed_cost)

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def posterior_state(self) -> dict[str, dict[int, dict[str, float]]]:
        """Snapshot of all Q-posteriors, keyed by ``arm.value → bucket → stats``."""
        out: dict[str, dict[int, dict[str, float]]] = {}
        for arm, posts in self._q_posteriors.items():
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
        """Snapshot of all C-posteriors, keyed by ``arm.value → bucket → stats``."""
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


__all__ = ["ContextualBTSPolicy"]
