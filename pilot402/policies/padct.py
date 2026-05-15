"""PA-DCT — Payment-Aware Discounted Contextual Thompson Sampling.

The paper's headline algorithm. Combines four components, each separately
ablatable:

1. **Payment-aware (P)**:
   At decision time, the cost penalty `λ_norm·c̃_a` is subtracted from the
   utility-maximization. λ_norm = λ_t/(1+λ_t) is read from the wallet on
   each call, where λ_t = exp(α·burn_dev) reflects current budget pressure.

   **Critical: c̃_a is sampled from a Bayesian cost posterior, not from a
   static spec dict.** PA-DCT maintains separate posteriors over quality
   AND cost per (arm, bucket). When the market changes the price of an
   arm, the cost posterior tracks the change via fresh observations and
   the same discount γ that handles quality drift. This is what makes
   the algorithm "payment-aware" beyond the name: the payment dimension
   is a *learned* signal, not a hard-wired constant.

2. **Discounted (D)**:
   Per-round multiplicative discount γ < 1 on every (arm, bucket) cell's
   sufficient statistics — applied to BOTH quality and cost posteriors.
   Lets the bandit forget stale observations and adapt to non-stationary
   providers in either dimension (S2: P-flaky timeout spike, S3:
   P-premium price shock).

3. **Contextual (C)**:
   Separate posterior per (arm, context_bucket) where the bucket is the
   task type. The bandit can learn that P-cheap is decent on T2 multi-hop
   but weak on T3a TriviaQA, while P-mid is uniform across types.

4. **Thompson sampling (TS)**:
   Each round, sample from BOTH the quality and cost posteriors per
   (arm, bucket) and pick the arm with highest sampled PA-reward. Natural
   exploration-exploitation tradeoff via posterior uncertainty in both
   dimensions.

Decision rule per round:

    For each affordable arm a:
        q_a ~ Q-Posterior_{a, current_bucket}.sample()
        c_a ~ C-Posterior_{a, current_bucket}.sample()       ← NEW
        c̃_a = clip(c_a / max_provider_cost, 0, 1)
        PA_a = (1 − λ_norm) · q_a − λ_norm · c̃_a
    chosen = argmax_a PA_a

Posterior update (only the chosen arm's bucket):

    Q-Posterior_{chosen, bucket}.update(observed_utility)
    C-Posterior_{chosen, bucket}.update(observed_cost)        ← NEW

Discount (every (arm, bucket) cell, every round, on both posteriors):

    Q-Posterior.discount() and C-Posterior.discount() applied before sampling.

The policy is updated with **utility** (q − ν·f) for the q-posterior
(intrinsic provider quality, regardless of current λ_norm) and with the
**raw observed cost** for the c-posterior (so learning is independent of
the cost-normalization choice). (system_design §2.6.)

## Ablation flags

- ``enable_payment_aware = False``: forces λ_norm = 0 → ranks arms by
  pure sampled utility. Tests the value of cost-awareness.
- ``enable_discount = False``: forces γ = 1 → vanilla Thompson Sampling
  with no decay. Tests the value of non-stationary adaptation.
- ``enable_contextual = False``: collapses to a single posterior per arm
  (n_buckets=1). Tests the value of context (task-type) bucketing.
- ``enable_ts = False``: replaces sampling with posterior_mean.
  Tests the value of stochastic exploration vs greedy exploitation.

The full PA-DCT has all flags True (default).

## Default γ = 0.999

Half-life ≈ ln(2)/(1−γ) = 693 rounds. Chosen so:
- Long enough to accumulate stable estimates within a 10,000-round run
- Short enough to detect and react to mid-run shocks (S2 outage at
  rounds 3000-5500, S3 price shock at round 1000+) within the shock
  windows.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from numpy.random import Generator

from pilot402.core import ProviderId
from pilot402.core.interfaces import BudgetManager, ContextVector
from pilot402.policies.posterior import GaussianPosterior


def _default_context_to_bucket(context: ContextVector) -> int:
    """Default bucket extractor for ``NaiveEncoder``: argmax of first 4 dims.

    Assumes the encoder packs task-type one-hot in positions 0..3 (T1, T2,
    T3a, T3b in this order). If a future encoder uses a different layout,
    pass a custom ``context_to_bucket`` to ``PADCTPolicy``.
    """

    return max(range(4), key=lambda i: context[i] if i < len(context) else float("-inf"))


@dataclass
class PADCTPolicy:
    """Payment-Aware Discounted Contextual Thompson Sampling.

    Args:
        rng:                 NumPy ``Generator`` for stochastic decisions.
        wallet:              ``BudgetManager`` to query λ_t from.
        provider_costs:      ``{ProviderId: cost_usdc}`` — used as the *prior
                             mean* for each arm's cost posterior. After
                             observations roll in, the posterior tracks the
                             actual market price; the spec value is just the
                             starting belief. Arms not in this dict get no
                             posterior; selecting them raises KeyError.
        max_provider_cost:   denominator for cost normalization.  Default
                             $0.01 (matches RewardCalculator's default and the
                             current calibrated max).
        n_buckets:           number of context buckets. 4 = task types (T1, T2,
                             T3a, T3b). Set to 1 for contextual ablation.
        context_to_bucket:   maps ContextVector → bucket index ∈ [0, n_buckets).
                             Default: argmax of first 4 dims (NaiveEncoder layout).

        prior_mean / prior_var / noise_var:
                             quality posterior hyperparameters; see
                             ``GaussianPosterior``.

        c_prior_var:         cost posterior prior variance. Default 1e-4
                             (= ``max_provider_cost²`` in $² units, so prior
                             std ≈ max_provider_cost). Wide enough to allow
                             the spec value to be wrong by an order of
                             magnitude; first observation dominates.
        c_noise_var:         cost observation noise. Default 1e-6 — much
                             smaller than the prior because cost is
                             essentially deterministic given the provider /
                             scenario in our replay setup. Real-world
                             deployments with variable pricing should set
                             this larger to account for genuine cost
                             stochasticity.

        gamma:               discount factor applied to the QUALITY posterior.
                             Default 0.999 → half-life ≈ 693 rounds.
                             Quality shifts (provider regressions) tend to
                             be slow / persistent in real LLM markets, so
                             the q-posterior can afford a long memory.
        gamma_cost:          discount factor applied to the COST posterior.
                             Default 0.999 → half-life ≈ 693 rounds, same
                             as the quality posterior. Splitting the two
                             rates is supported (set gamma_cost < gamma to
                             give cost a faster reaction) but in our
                             calibrated experiments both dimensions adapt
                             cleanly at 0.999.

        enable_payment_aware: if False, PA-reward = sampled utility only
                              (force λ_norm = 0).
        enable_discount:      if False, γ = 1 (no decay, vanilla TS).
        enable_contextual:    if False, single posterior per arm (collapse buckets).
        enable_ts:            if False, use posterior_mean instead of sampling
                              (greedy / Bayesian-greedy variant).
        enable_cost_posterior: if False, use the static ``provider_costs`` dict
                              at decision time (vanilla pre-M3.F behavior) and
                              skip cost-posterior updates. This is the M3.F
                              ablation: empirically demonstrates that cost
                              posteriors are necessary for adapting to price
                              shocks.
    """

    rng: Generator
    wallet: BudgetManager
    provider_costs: dict[ProviderId, float]
    max_provider_cost: float = 0.01
    n_buckets: int = 4
    context_to_bucket: Callable[[ContextVector], int] = field(
        default=_default_context_to_bucket
    )
    prior_mean: float = 0.5
    prior_var: float = 1.0
    noise_var: float = 0.09
    c_prior_var: float = 1e-4
    c_noise_var: float = 1e-6
    gamma: float = 0.999
    gamma_cost: float = 0.999
    enable_payment_aware: bool = True
    enable_discount: bool = True
    enable_contextual: bool = True
    enable_ts: bool = True
    enable_cost_posterior: bool = True
    # Posterior tables: posteriors[arm][bucket]
    _q_posteriors: dict[ProviderId, list[GaussianPosterior]] = field(init=False)
    _c_posteriors: dict[ProviderId, list[GaussianPosterior]] = field(init=False)

    def __post_init__(self) -> None:
        if self.max_provider_cost <= 0:
            raise ValueError("max_provider_cost must be > 0")
        if self.n_buckets < 1:
            raise ValueError("n_buckets must be >= 1")
        # Effective hyperparameters honoring ablation flags
        effective_gamma_q = self.gamma if self.enable_discount else 1.0
        effective_gamma_c = self.gamma_cost if self.enable_discount else 1.0
        effective_buckets = self.n_buckets if self.enable_contextual else 1
        # Build q posteriors and c posteriors per (arm, bucket).
        # Only arms listed in provider_costs get posteriors — unlisted arms
        # cause select()/update() to KeyError at lookup time, which is the
        # right behavior for catching wiring mistakes.
        self._q_posteriors = {}
        self._c_posteriors = {}
        for arm, spec_cost in self.provider_costs.items():
            self._q_posteriors[arm] = [
                GaussianPosterior(
                    prior_mean=self.prior_mean,
                    prior_var=self.prior_var,
                    noise_var=self.noise_var,
                    gamma=effective_gamma_q,
                )
                for _ in range(effective_buckets)
            ]
            # Cost prior mean is the spec price — initial belief that prices
            # match the spec, but a few observations will dominate.
            # Cost uses its own (typically faster) discount.
            self._c_posteriors[arm] = [
                GaussianPosterior(
                    prior_mean=spec_cost,
                    prior_var=self.c_prior_var,
                    noise_var=self.c_noise_var,
                    gamma=effective_gamma_c,
                )
                for _ in range(effective_buckets)
            ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _bucket_for(self, context: ContextVector) -> int:
        """Resolve context → bucket index, honoring `enable_contextual`."""
        if not self.enable_contextual:
            return 0
        b = self.context_to_bucket(context)
        return b % len(self._q_posteriors[next(iter(self._q_posteriors))])

    def _discount_all(self) -> None:
        """Apply per-round discount to every (arm, bucket) posterior — both q and c.

        The discount is a no-op when ``enable_discount=False`` (γ=1).
        Cost posterior is skipped entirely when ``enable_cost_posterior=False``
        (ablation: cost dimension is treated as static).
        """
        for posts in self._q_posteriors.values():
            for p in posts:
                p.discount()
        if self.enable_cost_posterior:
            for posts in self._c_posteriors.values():
                for p in posts:
                    p.discount()

    def _q_value_for_arm(self, arm: ProviderId, bucket: int) -> float:
        """Sample (or take posterior mean) of utility for an arm."""
        post = self._q_posteriors[arm][bucket]
        if self.enable_ts:
            return post.sample(self.rng)
        return post.posterior_mean

    def _c_value_for_arm(self, arm: ProviderId, bucket: int) -> float:
        """Sample (or take posterior mean) of cost for an arm.

        Returned in raw $/call units (NOT normalized). Caller normalizes
        with max_provider_cost and clips to [0, 1].

        ABLATION: when ``enable_cost_posterior=False``, returns the static
        spec price directly (recovering the vanilla pre-M3.F behavior — cost
        is "known" and never updated, so the policy is blind to price shocks).
        """
        if not self.enable_cost_posterior:
            return self.provider_costs[arm]
        post = self._c_posteriors[arm][bucket]
        if self.enable_ts:
            return post.sample(self.rng)
        return post.posterior_mean

    def _lambda_norm(self) -> float:
        """Read wallet's λ_t and convert to λ_norm.

        Returns 0.0 (pure utility) when payment-aware ablation is off.
        """
        if not self.enable_payment_aware:
            return 0.0
        lambda_t = self.wallet.get_lambda()
        if lambda_t < 0:
            raise RuntimeError(f"wallet returned negative lambda_t: {lambda_t}")
        return lambda_t / (1.0 + lambda_t)

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
                "PADCTPolicy received an empty affordable set; the loop "
                "should detect bankruptcy before invoking the policy."
            )

        # 1. Per-round discount (applies to all (arm, bucket) cells in both
        #    q and c posteriors).
        self._discount_all()

        # 2. Determine bucket from context.
        bucket = self._bucket_for(context)

        # 3. Read budget pressure.
        lambda_norm = self._lambda_norm()

        # 4. Score each affordable arm via PA-reward = (1-λ_n)·q̂ - λ_n·c̃̂,
        #    where both q̂ and c̃̂ are sampled (or posterior-mean) values.
        best_arm: ProviderId | None = None
        best_score = float("-inf")
        for arm in affordable_arms:
            if arm not in self._q_posteriors:
                raise KeyError(
                    f"provider_costs missing entry for {arm.value!r}; "
                    f"have {list(self.provider_costs)}"
                )
            sampled_q = self._q_value_for_arm(arm, bucket)
            sampled_c_raw = self._c_value_for_arm(arm, bucket)
            # Clip into the c̃ ∈ [0, 1] range. Gaussian sampling can produce
            # values outside [0, max_provider_cost]; the clipping is a sample-
            # space adjustment only — the underlying posterior still sees the
            # raw numerical observations from update().
            c_norm = max(0.0, min(sampled_c_raw / self.max_provider_cost, 1.0))
            pa = (1.0 - lambda_norm) * sampled_q - lambda_norm * c_norm
            if pa > best_score:
                best_score = pa
                best_arm = arm

        assert best_arm is not None  # always reachable: affordable non-empty
        return best_arm

    def update(
        self,
        context: ContextVector,
        arm: ProviderId,
        utility: float,
        observed_cost: float,
    ) -> None:
        """Add observations to BOTH the (arm, bucket) q and c posteriors.

        Args:
            context:        feature vector → bucket (via context_to_bucket).
            arm:            which provider was actually paid for this round.
            utility:        observed quality minus failure penalty
                            (q − ν·f). Tracks intrinsic provider quality.
            observed_cost:  raw $/call charged this round (post any
                            scenario transformation). Drives the cost
                            posterior; lets the bandit detect price shocks
                            the same way it detects quality shocks.

        Note: discount() was already applied in select() at the start of
        this round; we just append the new observations here.
        """
        if arm not in self._q_posteriors:
            raise KeyError(
                f"PADCTPolicy.update called with unknown arm {arm.value!r}; "
                f"have {list(self.provider_costs)}"
            )
        bucket = self._bucket_for(context)
        self._q_posteriors[arm][bucket].update(utility)
        # Skip cost posterior update under the M3.F ablation. The c-posterior
        # state stays at its prior, recovering the vanilla pre-M3.F decision
        # rule (cost is read from the static spec dict).
        if self.enable_cost_posterior:
            self._c_posteriors[arm][bucket].update(observed_cost)

    # ------------------------------------------------------------------
    # Diagnostics (not part of the Protocol; useful for analysis)
    # ------------------------------------------------------------------

    def posterior_state(self) -> dict[str, dict[int, dict[str, float]]]:
        """Snapshot of all q-posteriors for offline analysis (back-compat).

        Returns the quality posteriors only, keyed by arm.value → bucket →
        {n_eff, s_eff, posterior_mean, posterior_var}. Use
        ``cost_posterior_state()`` for the cost posteriors.
        """
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
        """Snapshot of all cost posteriors for offline analysis."""
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


__all__ = ["PADCTPolicy"]
