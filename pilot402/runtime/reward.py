"""Reward calculator for utility and payment-aware reward.

Reward formula:

    utility   = q − ν·f                                 ∈  [-ν, +1]
    λ_norm    = λ_t / (1 + λ_t)                         ∈  (0, 1)
    PA_reward = (1 − λ_norm) · utility − λ_norm · c̃     ∈  [-1, +1]

Two reward channels are computed per round:

* **Utility** ``u_t = q_t − ν·f_t``. This is what the policy posterior is
  updated with, intentionally λ-free so the posterior tracks intrinsic
  provider quality. (Without this separation, the policy would re-learn
  the same provider differently as the wallet drains, defeating the point
  of having a posterior at all.)

* **Payment-aware reward** ``r_t = (1−λ_norm)·u_t − λ_norm·c̃_t``.
  This is the ranking criterion the policy uses at decision time (via
  Thompson Sampling) and the quantity reported in the regret bound. λ_t
  comes from ``BudgetManager.get_lambda()`` and is mapped to a sigmoid-shape
  weight λ_norm ∈ (0, 1) so the reward is bounded in [-1, +1].

Design choices:

1. **No latency term.** The benchmark scenarios manipulate service quality,
   failures, and realized cost, but not latency. Latency is logged for future
   analysis and is intentionally not part of the reported reward.

2. **Failure as a distinct utility term, not just q=0.** When P-flaky times
   out, q = 0 already (no answer to score). One could argue ν·f double-counts
   the same event. We keep ν·f because:
   - P-flaky models unreliable services that share
     cost + base model + prompt with P-mid; failure is the *only* observable
     dimension distinguishing them.
   - In real systems, a timeout has structural costs beyond q=0 — it forces
     retry, breaks the agent's call chain, increases wallclock latency for
     the user. ν·f abstracts these without modeling retry explicitly.
   - It cleanly separates "service unavailable" (f=1, q=0) from "service
     gave a wrong answer" (f=0, q=0). Both lower expected reward but at
     different magnitudes; the bandit can learn the distinction.

   We treat (q, f) as a single composite "utility" because they evaluate
   the *same axis* — task delivery — at two extremes. Failure is the
   limiting case of zero quality plus an additional structural cost
   (encoded by ν). Bundling them into utility, then sigmoid-normalizing
   utility-vs-cost, keeps the formula's two-tier structure clean:
   intrinsic value (utility) × budget weighting (λ_norm).

3. **Sigmoid normalization of cost penalty.** The convex-combination form
       PA_reward = (1−λ_norm)·utility − λ_norm·c̃
   with λ_norm = λ/(1+λ) = sigmoid(log λ) keeps reward in [-1, +1] and
   has a clean interpretation: λ_norm is the *fraction of decision weight*
   given to cost (vs. utility). Low λ → "I'm not over-spending, weigh
   utility heavily"; high λ → "I'm overspending, weigh cost heavily".

Cost normalizer ``c̃_t = c_t / max_provider_cost`` puts cost on [0, 1]
matching utility's range. The paper configuration uses P-premium's listed
$0.01 price as the denominator.
"""

from __future__ import annotations

from dataclasses import dataclass

from pilot402.core.types import EvaluatorBackend, QualityScore, Reward


@dataclass(frozen=True)
class RewardCalculator:
    """Stateless reward computation with sigmoid-bounded PA term.

    Hyperparameter ``nu`` is fixed across a run and is not tuned per provider.
    The cost normalizer is fixed as part of the reward definition because it
    affects both decision-time scoring and PA-gap values.

    Args:
        nu:               weight on the boolean failure flag. Default 0.5.
                          A failure deducts ν from utility; combined with
                          q=0 (a failed call has no scorable response), the
                          total utility on a failure round is −ν.
        max_provider_cost_usdc: denominator for cost normalization. Default
                          $0.01, matching P-premium's listed paper price.
    """

    nu: float = 0.5
    max_provider_cost_usdc: float = 0.01

    def __post_init__(self) -> None:
        if self.nu < 0:
            raise ValueError("nu must be non-negative.")
        if self.max_provider_cost_usdc <= 0:
            raise ValueError("max_provider_cost_usdc must be > 0.")

    def compute(
        self,
        *,
        quality: QualityScore | float,
        cost_usdc: float,
        failure_flag: bool,
        lambda_t: float,
    ) -> Reward:
        """Compute both utility (λ-free) and payment-aware reward.

        ``quality`` may be either a ``QualityScore`` (recommended) or a raw
        float; the float path is convenient for unit tests and policies
        that only care about ``q``.

        Note: ``latency_s`` is intentionally NOT a parameter — see the
        module docstring for why we dropped the latency term. The
        ``PregenRecord`` still carries latency_s for logging and possible
        future use, but the reward calculator no longer consumes it.
        """

        if lambda_t < 0:
            raise ValueError(f"lambda_t must be non-negative, got {lambda_t}")
        if cost_usdc < 0:
            raise ValueError(f"cost_usdc must be non-negative, got {cost_usdc}")

        q = quality.q if isinstance(quality, QualityScore) else float(quality)
        if not (0.0 <= q <= 1.0):
            raise ValueError(f"quality must be in [0, 1], got {q}")

        c_norm = min(cost_usdc / self.max_provider_cost_usdc, 1.0)
        f = 1.0 if failure_flag else 0.0

        # Utility: intrinsic value of this provider × task outcome.
        # On failure: q=0 by construction (no scorable response) AND ν·f=ν,
        # so utility = -ν. Both terms move in the same direction (downward)
        # because they reflect the same axis at its extreme.
        utility = q - self.nu * f

        # Sigmoid-normalize λ to (0, 1) for a bounded convex combination.
        # λ/(1+λ) = sigmoid(log λ); the wallet returns λ = exp(α·burn_dev),
        # so this is sigmoid(α·burn_dev) without recomputing burn_dev
        # in this module.
        lambda_norm = lambda_t / (1.0 + lambda_t)

        # PA_reward ∈ [-1, +1]. Pure utility when no budget pressure
        # (λ_norm → 0); pure -cost when wallet is stretched (λ_norm → 1).
        payment_aware_reward = (1.0 - lambda_norm) * utility - lambda_norm * c_norm

        return Reward(
            utility=utility,
            payment_aware_reward=payment_aware_reward,
            lambda_t=lambda_t,
            mu=0.0,  # latency weight retired; field preserved for schema stability
            nu=self.nu,
        )


# Sentinel so unit tests can quickly construct a QualityScore without
# importing EvaluatorBackend just to satisfy a Protocol check.
def quality_from_q(q: float, *, backend: EvaluatorBackend = EvaluatorBackend.EM_F1) -> QualityScore:
    """Lightweight QualityScore factory for tests and ad-hoc reward queries."""
    return QualityScore(q=q, backend=backend)


__all__ = ["RewardCalculator", "quality_from_q"]
