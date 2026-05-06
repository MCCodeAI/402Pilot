"""Tests for ``pilot402.policies.posterior.GaussianPosterior``."""

from __future__ import annotations

import math

import pytest
from numpy.random import default_rng

from pilot402.policies.posterior import GaussianPosterior


# ---------------------------------------------------------------------------
# Construction & validation
# ---------------------------------------------------------------------------


def test_initial_state_is_prior() -> None:
    p = GaussianPosterior(prior_mean=0.5, prior_var=1.0, noise_var=0.09)
    assert p.n_eff == 0.0
    assert p.s_eff == 0.0
    # No data → posterior = prior
    assert p.posterior_mean == pytest.approx(0.5)
    assert p.posterior_var == pytest.approx(1.0)


def test_invalid_construction() -> None:
    with pytest.raises(ValueError):
        GaussianPosterior(prior_var=0.0)
    with pytest.raises(ValueError):
        GaussianPosterior(prior_var=-1.0)
    with pytest.raises(ValueError):
        GaussianPosterior(noise_var=0.0)
    with pytest.raises(ValueError):
        GaussianPosterior(gamma=0.0)
    with pytest.raises(ValueError):
        GaussianPosterior(gamma=1.5)


# ---------------------------------------------------------------------------
# Bayesian update math
# ---------------------------------------------------------------------------


def test_single_observation_shrinks_variance() -> None:
    """One observation should reduce posterior variance below prior."""
    p = GaussianPosterior(prior_mean=0.5, prior_var=1.0, noise_var=0.09)
    p.update(0.7)
    # Precision: 1/1 + 1/0.09 = 1 + 11.11 = 12.11
    # Var: 1/12.11 ≈ 0.0826
    expected_var = 1.0 / (1.0 / 1.0 + 1.0 / 0.09)
    assert p.posterior_var == pytest.approx(expected_var)
    assert p.posterior_var < 1.0


def test_posterior_mean_weighted_average() -> None:
    """μ_post is a precision-weighted average of prior and data."""
    p = GaussianPosterior(prior_mean=0.0, prior_var=1.0, noise_var=1.0)
    # σ² = 1, σ₀² = 1: each contributes equally with one data point.
    p.update(2.0)
    # Posterior precision = 1 + 1 = 2 → var = 0.5
    # Posterior mean = 0.5 * (0/1 + 2/1) = 1.0
    assert p.posterior_var == pytest.approx(0.5)
    assert p.posterior_mean == pytest.approx(1.0)


def test_many_observations_converge_to_sample_mean() -> None:
    """As n → ∞, posterior_mean → empirical mean."""
    p = GaussianPosterior(prior_mean=0.0, prior_var=1.0, noise_var=0.09)
    target = 0.7
    for _ in range(1000):
        p.update(target)
    # With n=1000 and σ²=0.09, precision dominated by data: ≈ 1 + 11111 = 11112
    # Mean: ≈ (1/11112) * (0 + 1000 * 0.7 / 0.09) = (1/11112) * 7777.7 ≈ 0.7
    assert p.posterior_mean == pytest.approx(target, abs=1e-3)
    assert p.posterior_var < 1e-3


def test_no_discount_when_gamma_one() -> None:
    """γ=1 is vanilla TS (no decay)."""
    p = GaussianPosterior(gamma=1.0)
    p.update(0.5)
    p.update(0.5)
    p.update(0.5)
    p.discount()
    p.discount()
    p.discount()
    # n_eff should still be 3
    assert p.n_eff == pytest.approx(3.0)


def test_discount_reduces_n_eff_geometrically() -> None:
    p = GaussianPosterior(gamma=0.9)
    p.update(1.0)
    p.update(1.0)
    # n_eff = 2, s_eff = 2
    p.discount()
    # n_eff = 1.8, s_eff = 1.8
    assert p.n_eff == pytest.approx(1.8)
    assert p.s_eff == pytest.approx(1.8)
    p.discount()
    # n_eff = 1.62
    assert p.n_eff == pytest.approx(1.62)


def test_steady_state_n_eff_equals_one_over_one_minus_gamma() -> None:
    """If we update every round and discount every round, n_eff converges
    to 1/(1−γ). This is the 'effective memory window'."""
    gamma = 0.99
    p = GaussianPosterior(gamma=gamma)
    for _ in range(2000):
        p.discount()
        p.update(0.5)
    # Steady state: n_eff = 1/(1-γ) = 100
    assert p.n_eff == pytest.approx(1.0 / (1.0 - gamma), rel=0.01)


# ---------------------------------------------------------------------------
# Thompson sampling
# ---------------------------------------------------------------------------


def test_sample_around_posterior_mean() -> None:
    """Many samples should average to posterior_mean."""
    p = GaussianPosterior(prior_mean=0.5, prior_var=1.0, noise_var=0.09)
    for _ in range(200):
        p.update(0.7)
    rng = default_rng(0)
    samples = [p.sample(rng) for _ in range(2000)]
    sample_mean = sum(samples) / len(samples)
    # Posterior std ≈ sqrt(0.09 / 200) ≈ 0.021
    # SE of sample mean ≈ 0.021 / sqrt(2000) ≈ 0.0005
    assert abs(sample_mean - p.posterior_mean) < 0.005


def test_sample_variance_matches_posterior_variance() -> None:
    """Sample empirical variance should match posterior_var."""
    p = GaussianPosterior(prior_mean=0.0, prior_var=1.0, noise_var=1.0)
    for _ in range(10):
        p.update(1.0)
    rng = default_rng(7)
    samples = [p.sample(rng) for _ in range(10000)]
    n = len(samples)
    mean = sum(samples) / n
    emp_var = sum((s - mean) ** 2 for s in samples) / n
    assert emp_var == pytest.approx(p.posterior_var, rel=0.05)


def test_zero_n_eff_samples_from_prior() -> None:
    """No data → samples ~ N(prior_mean, prior_var)."""
    p = GaussianPosterior(prior_mean=2.0, prior_var=4.0)
    rng = default_rng(42)
    samples = [p.sample(rng) for _ in range(5000)]
    sample_mean = sum(samples) / len(samples)
    # SE ≈ 2/sqrt(5000) ≈ 0.028
    assert abs(sample_mean - 2.0) < 0.1


# ---------------------------------------------------------------------------
# Discount + update interaction (the actual PA-DCT lifecycle)
# ---------------------------------------------------------------------------


def test_pa_dcts_lifecycle_per_round() -> None:
    """Simulate a 100-round lifecycle: discount each round, sometimes update.

    Verify n_eff stays bounded by 1/(1-γ) and posterior tracks recent data.
    """
    gamma = 0.95
    p = GaussianPosterior(gamma=gamma)
    rng = default_rng(0)

    # Round 0-49: utility = 0.3
    for _ in range(50):
        p.discount()
        p.update(0.3)

    posterior_at_50 = p.posterior_mean
    assert posterior_at_50 == pytest.approx(0.3, abs=0.05)

    # Round 50-99: utility shifts to 0.8 (non-stationary)
    for _ in range(50):
        p.discount()
        p.update(0.8)

    posterior_at_100 = p.posterior_mean
    # Should have shifted toward 0.8, but old 0.3 observations still drag
    # With γ=0.95, memory ≈ 20 rounds, so by round 100 the 0.3 observations
    # from round 0-49 are heavily discounted (γ^50 ≈ 0.077).
    assert posterior_at_100 > 0.7  # mostly forgot the 0.3
    # n_eff should be at most 1/(1-γ) = 20
    assert p.n_eff < 1.0 / (1.0 - gamma) + 0.1
