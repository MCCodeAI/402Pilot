"""Contextual DS-TS — Discounted Thompson Sampling extended to task buckets.

Adapted from Qi et al. 2023 (DS-TS) for head-to-head comparison against
PA-DCT in 402Pilot-Bench. The published DS-TS is a single-posterior-per-arm
algorithm; we extend it to per-(arm, bucket) posteriors so that the
comparison isolates "what does PA-DCT add beyond drift-tracking?" rather
than confounding drift-tracking with context heterogeneity.

Algorithmic essence preserved from published DS-TS:

* Per-arm reward posterior under a Normal-Normal Bayesian model
* Multiplicative per-round discount on sufficient statistics (γ < 1)
* Thompson sample one value of expected utility per affordable arm
* Greedy argmax over sampled values

What DS-TS does NOT have (and we faithfully omit here):

* No wallet-pressure scaling — the policy does not read λ_t. The
  affordable-set mask supplied by ``run_one_seed`` is the only budget
  signal the algorithm sees.
* No cost posterior — the price of each arm is treated as a pre-known
  property of the environment, not a learned quantity. Realized charges
  pass through ``update`` and are ignored.

This baseline is therefore expected to over-spend on premium arms in
stationary or reliability-shock regimes (no wallet pressure), bankrupting
the wallet in S1/S2. Under the S3 price promotion, the same quality-greedy
behaviour can actually exploit premium's high quality once the price drop
keeps the policy solvent; however, because it ignores realized cost in the
scoring rule, it still pays inefficiently and exhibits worse ROI and
PA-gap/$T$ than wallet-aware policies. It is included to test whether
drift-tracking alone, without payment-aware scoring and without learned
realized cost, is sufficient on 402Pilot-Bench.

Hyperparameter alignment with PA-DCT:

The Q-posterior priors (``prior_mean``, ``prior_var``, ``noise_var``) and
the discount γ default to the same values as PA-DCT so that the only
algorithmic differences in the head-to-head comparison are the omitted
wallet-pressure and cost-posterior mechanisms. The dataclass defaults
match ``PADCTPolicy``.
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
class ContextualDSTSPolicy:
    """Discounted Thompson Sampling with per-(arm, bucket) Q-posterior.

    Args:
        rng:                NumPy ``Generator`` for stochastic decisions.
        provider_ids:       Iterable of provider IDs the policy will see.
                            Used to pre-allocate posterior tables; selecting
                            an unlisted arm raises ``KeyError`` (same
                            failure mode as PA-DCT).
        n_buckets:          Number of context buckets. 4 = task types
                            (T1, T2, T3a, T3b).
        context_to_bucket:  Maps ``ContextVector`` → bucket index ∈ [0, n_buckets).
                            Default matches PA-DCT (argmax of first 4 dims).
        prior_mean:         μ₀ for Q-posterior. Default 0.5 (matches PA-DCT).
        prior_var:          σ₀² for Q-posterior. Default 1.0 (matches PA-DCT).
        noise_var:          σ² for Q-posterior. Default 0.09 (matches PA-DCT).
        gamma:              γ ∈ (0, 1] discount per round. Default 0.999
                            (matches PA-DCT's q-posterior discount).

    Implementation note: this policy does NOT take a ``wallet`` handle.
    The affordable-set filter is applied by the runtime loop, and the
    policy itself is wallet-blind — that is the published DS-TS contract.
    """

    rng: Generator
    provider_ids: tuple[ProviderId, ...]
    n_buckets: int = 4
    context_to_bucket: Callable[[ContextVector], int] = field(
        default=_default_context_to_bucket
    )
    prior_mean: float = 0.5
    prior_var: float = 1.0
    noise_var: float = 0.09
    gamma: float = 0.999

    _q_posteriors: dict[ProviderId, list[GaussianPosterior]] = field(init=False)

    def __post_init__(self) -> None:
        if self.n_buckets < 1:
            raise ValueError(f"n_buckets must be >= 1, got {self.n_buckets}")
        if not (0 < self.gamma <= 1):
            raise ValueError(f"gamma must be in (0, 1], got {self.gamma}")
        # Pre-allocate one posterior per (arm, bucket) cell.
        self._q_posteriors = {
            arm: [
                GaussianPosterior(
                    prior_mean=self.prior_mean,
                    prior_var=self.prior_var,
                    noise_var=self.noise_var,
                    gamma=self.gamma,
                )
                for _ in range(self.n_buckets)
            ]
            for arm in self.provider_ids
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _bucket_for(self, context: ContextVector) -> int:
        b = self.context_to_bucket(context)
        return b % self.n_buckets

    def _discount_all(self) -> None:
        """Per-round multiplicative discount on every (arm, bucket) cell."""
        for posts in self._q_posteriors.values():
            for p in posts:
                p.discount()

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
                "ContextualDSTSPolicy received an empty affordable set; the "
                "loop should detect bankruptcy before invoking the policy."
            )

        # 1. Per-round discount over all (arm, bucket) cells (the algorithm
        #    forgets at wall-clock rate, not pull-conditional).
        self._discount_all()

        # 2. Determine bucket from context.
        bucket = self._bucket_for(context)

        # 3. Thompson-sample one utility value per affordable arm and pick
        #    the argmax. No cost term, no λ_t — this is DS-TS.
        best_arm: ProviderId | None = None
        best_score = float("-inf")
        for arm in affordable_arms:
            if arm not in self._q_posteriors:
                raise KeyError(
                    f"ContextualDSTSPolicy: unknown arm {arm.value!r}; "
                    f"provider_ids has {[a.value for a in self.provider_ids]}"
                )
            sampled_q = self._q_posteriors[arm][bucket].sample(self.rng)
            if sampled_q > best_score:
                best_score = sampled_q
                best_arm = arm

        assert best_arm is not None  # affordable set is non-empty
        return best_arm

    def update(
        self,
        context: ContextVector,
        arm: ProviderId,
        utility: float,
        observed_cost: float,  # noqa: ARG002 — DS-TS does not learn cost
    ) -> None:
        """Update only the chosen (arm, bucket)'s Q-posterior with utility.

        Note: ``observed_cost`` is ignored. The runtime loop passes it to
        every policy uniformly, but DS-TS by construction does not model
        cost as a learned signal.
        """
        if arm not in self._q_posteriors:
            raise KeyError(
                f"ContextualDSTSPolicy.update: unknown arm {arm.value!r}; "
                f"provider_ids has {[a.value for a in self.provider_ids]}"
            )
        bucket = self._bucket_for(context)
        self._q_posteriors[arm][bucket].update(utility)

    # ------------------------------------------------------------------
    # Diagnostics (parallels PADCTPolicy.posterior_state for analysis)
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


__all__ = ["ContextualDSTSPolicy"]
