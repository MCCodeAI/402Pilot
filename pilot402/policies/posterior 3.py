"""Gaussian-conjugate posterior with multiplicative discount.

Mathematical core of PA-DCT. Maintains discounted sufficient statistics
for a Normal-Normal model:

    Prior:        μ ~ N(μ₀, σ₀²)
    Likelihood:   utility | μ ~ N(μ, σ²)        (σ² fixed, known)
    Posterior:    μ ~ N(μ_n, σ_n²)
        precision_n = 1/σ₀² + n_eff/σ²
        σ_n²        = 1 / precision_n
        μ_n         = σ_n² · (μ₀/σ₀² + S_eff/σ²)

where ``n_eff`` and ``S_eff`` are the *discounted* effective sample size
and weighted sum of observations:

    n_eff_t = γ · n_eff_{t-1} + 1{arm pulled this round}
    S_eff_t = γ · S_eff_{t-1} + utility · 1{arm pulled this round}

Discount γ ∈ (0, 1) shrinks old observations exponentially; γ = 1 recovers
vanilla TS (no discount).

Why Gaussian: utility ∈ [-ν, +1] is continuous and roughly unimodal per
provider in our experimental data. Beta-Bernoulli would mis-fit (only
binary outcomes). Gamma-Gaussian (unknown variance) is more general but
the extra hyperparameter buys little for our setup; we estimate noise
variance σ² empirically from the calibration data and pin it.

Why multiplicative discount on sufficient stats: standard form for
non-stationary contextual bandits (Garivier & Moulines 2008). Equivalent
to "weighted least squares with exponential window."
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from numpy.random import Generator


@dataclass
class GaussianPosterior:
    """Discounted Normal-Normal sufficient statistics.

    All fields are init-time hyperparameters except n_eff / s_eff which
    are mutable state.

    Args:
        prior_mean:  μ₀ — prior on the latent expected utility.
        prior_var:   σ₀² — prior variance. Larger → more initial exploration.
        noise_var:   σ² — observation noise (likelihood variance). Fixed.
        gamma:       γ — discount factor per ``discount()`` call. γ=1 disables.
    """

    prior_mean: float = 0.5
    prior_var: float = 1.0
    noise_var: float = 0.09
    gamma: float = 0.999
    n_eff: float = field(default=0.0, init=False)
    s_eff: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        if self.prior_var <= 0:
            raise ValueError(f"prior_var must be > 0, got {self.prior_var}")
        if self.noise_var <= 0:
            raise ValueError(f"noise_var must be > 0, got {self.noise_var}")
        if not (0 < self.gamma <= 1):
            raise ValueError(f"gamma must be in (0, 1], got {self.gamma}")

    # ------------------------------------------------------------------
    # Updates
    # ------------------------------------------------------------------

    def discount(self) -> None:
        """Apply per-round multiplicative discount to sufficient stats.

        Called once per round before any select() / update() in PA-DCT,
        BEFORE observing any new data this round. The discount applies
        regardless of whether this arm/context was pulled — non-stationarity
        is wall-clock, not pull-conditional.
        """

        self.n_eff *= self.gamma
        self.s_eff *= self.gamma

    def update(self, utility: float) -> None:
        """Add a new observation to the posterior.

        Should be called AFTER discount() in the same round, and only for
        the arm/context that was actually pulled.
        """

        self.n_eff += 1.0
        self.s_eff += utility

    # ------------------------------------------------------------------
    # Posterior queries
    # ------------------------------------------------------------------

    @property
    def posterior_precision(self) -> float:
        """1/σ_n² = 1/σ₀² + n_eff/σ²  (always > 0 since both terms ≥ 0)."""

        return 1.0 / self.prior_var + self.n_eff / self.noise_var

    @property
    def posterior_var(self) -> float:
        return 1.0 / self.posterior_precision

    @property
    def posterior_mean(self) -> float:
        """μ_n = σ_n² · (μ₀/σ₀² + S_eff/σ²).

        Reduces to prior_mean when n_eff=0; converges to S_eff/n_eff
        (sample mean) as n_eff → ∞.
        """

        return self.posterior_var * (
            self.prior_mean / self.prior_var + self.s_eff / self.noise_var
        )

    def sample(self, rng: Generator) -> float:
        """Thompson-sample one value of μ from the posterior."""

        return float(rng.normal(loc=self.posterior_mean, scale=math.sqrt(self.posterior_var)))


__all__ = ["GaussianPosterior"]
