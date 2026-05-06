"""Tests for ``pilot402.runtime.reward.RewardCalculator``.

Reward formula (calibrated 2026-05-02):

    utility   = q − ν·f                                ∈ [-ν, +1]
    λ_norm    = λ_t / (1 + λ_t)                        ∈ (0, 1)
    PA_reward = (1 − λ_norm) · utility − λ_norm · c̃    ∈ [-1, +1]

Latency was retired (was μ·l̃); failure penalty kept (P-flaky's distinct
identity hinges on it; see module docstring + reward_design_rationale.md).
"""

from __future__ import annotations

import pytest

from pilot402.core.types import EvaluatorBackend, QualityScore
from pilot402.runtime.reward import RewardCalculator, quality_from_q


# ---------------------------------------------------------------------------
# Shape and bounds
# ---------------------------------------------------------------------------


def test_pa_reward_bounded_in_unit_interval() -> None:
    """For any (q ∈ [0,1], cost ≤ max, λ ≥ 0), PA_reward ∈ [-1, +1]."""
    rc = RewardCalculator(nu=0.5, max_provider_cost_usdc=0.01)
    for q in [0.0, 0.3, 0.7, 1.0]:
        for cost in [0.0, 0.005, 0.01]:
            for fail in [False, True]:
                for lambda_t in [0.0, 0.5, 1.0, 7.4, 1000.0]:
                    out = rc.compute(
                        quality=q,
                        cost_usdc=cost,
                        failure_flag=fail,
                        lambda_t=lambda_t,
                    )
                    assert -1.0 - 1e-9 <= out.payment_aware_reward <= 1.0 + 1e-9, (
                        f"PA out of [-1, 1]: {out.payment_aware_reward} at "
                        f"q={q} cost={cost} fail={fail} λ={lambda_t}"
                    )


def test_utility_q_minus_nu_f() -> None:
    """utility = q - ν·f, no latency term."""
    rc = RewardCalculator(nu=0.5)
    success = rc.compute(quality=quality_from_q(0.8), cost_usdc=0.0,
                         failure_flag=False, lambda_t=0.0)
    fail = rc.compute(quality=quality_from_q(0.8), cost_usdc=0.0,
                      failure_flag=True, lambda_t=0.0)
    assert success.utility == pytest.approx(0.8)
    assert fail.utility == pytest.approx(0.8 - 0.5)


def test_failure_with_zero_quality_gives_minus_nu() -> None:
    """A real timeout: q=0 (no scorable response) AND f=1.
    Combined utility = 0 − 0.5 = −0.5."""
    rc = RewardCalculator(nu=0.5)
    out = rc.compute(quality=0.0, cost_usdc=0.002, failure_flag=True, lambda_t=0.0)
    assert out.utility == pytest.approx(-0.5)


# ---------------------------------------------------------------------------
# λ_norm convex combination behavior
# ---------------------------------------------------------------------------


def test_lambda_zero_means_pure_utility() -> None:
    """λ=0 → λ_norm=0 → PA_reward = utility (no cost weight)."""
    rc = RewardCalculator(nu=0.5)
    out = rc.compute(quality=0.7, cost_usdc=0.01, failure_flag=False, lambda_t=0.0)
    assert out.payment_aware_reward == pytest.approx(out.utility)
    assert out.payment_aware_reward == pytest.approx(0.7)


def test_lambda_huge_means_pure_negative_cost() -> None:
    """λ→∞ → λ_norm→1 → PA_reward → -c̃."""
    rc = RewardCalculator(nu=0.5)
    out = rc.compute(quality=0.7, cost_usdc=0.01, failure_flag=False,
                     lambda_t=1e9)
    # λ_norm = 1e9 / (1 + 1e9) ≈ 1
    # PA = (1 − 1)·0.7 − 1·1.0 = -1.0
    assert out.payment_aware_reward == pytest.approx(-1.0, abs=1e-6)


def test_lambda_one_gives_equal_weight() -> None:
    """λ=1 → λ_norm=0.5 → equal weights on utility and -c̃."""
    rc = RewardCalculator(nu=0.5)
    out = rc.compute(quality=0.8, cost_usdc=0.005, failure_flag=False, lambda_t=1.0)
    # utility = 0.8, c̃ = 0.5 (since cost/max = 0.005/0.01)
    # λ_norm = 1/2 = 0.5
    # PA = 0.5·0.8 - 0.5·0.5 = 0.40 - 0.25 = 0.15
    assert out.payment_aware_reward == pytest.approx(0.15)


def test_pa_negative_when_failure_and_high_lambda() -> None:
    """Failure (-0.5 utility) + tight budget (high λ) → strongly negative PA."""
    rc = RewardCalculator(nu=0.5)
    out = rc.compute(quality=0.0, cost_usdc=0.002, failure_flag=True, lambda_t=7.4)
    # utility = -0.5; λ_norm = 7.4/8.4 ≈ 0.881; c̃ = 0.2
    # PA = 0.119·(-0.5) − 0.881·0.2 = -0.060 − 0.176 = -0.236
    assert out.payment_aware_reward == pytest.approx(-0.236, abs=1e-3)


# ---------------------------------------------------------------------------
# Provider profile sanity (matches calibration story)
# ---------------------------------------------------------------------------


def test_premium_at_typical_lambda() -> None:
    """Premium (q=0.86, c̃=1.0) at λ=7.4 (always_premium burn)."""
    rc = RewardCalculator(nu=0.5)
    out = rc.compute(quality=0.86, cost_usdc=0.01, failure_flag=False, lambda_t=7.4)
    # utility=0.86, λ_norm=0.881, c̃=1.0
    # PA = 0.119·0.86 - 0.881·1.0 = 0.102 - 0.881 = -0.779
    assert out.payment_aware_reward == pytest.approx(-0.779, abs=1e-3)


def test_mid_at_typical_lambda() -> None:
    """Mid (q=0.81, c̃=0.2) at λ=0.30 (always_mid burn)."""
    rc = RewardCalculator(nu=0.5)
    out = rc.compute(quality=0.81, cost_usdc=0.002, failure_flag=False, lambda_t=0.30)
    # utility=0.81, λ_norm=0.30/1.30=0.231, c̃=0.2
    # PA = 0.769·0.81 - 0.231·0.2 = 0.623 - 0.046 = 0.577
    assert out.payment_aware_reward == pytest.approx(0.577, abs=1e-3)


def test_cheap_at_low_lambda() -> None:
    """Cheap (q=0.62, c̃=0.05) at λ=0.17 (always_cheap burn)."""
    rc = RewardCalculator(nu=0.5)
    out = rc.compute(quality=0.62, cost_usdc=0.0005, failure_flag=False, lambda_t=0.17)
    # utility=0.62, λ_norm=0.17/1.17=0.145, c̃=0.05
    # PA = 0.855·0.62 - 0.145·0.05 = 0.530 - 0.007 = 0.523
    assert out.payment_aware_reward == pytest.approx(0.523, abs=1e-3)


# ---------------------------------------------------------------------------
# Input handling
# ---------------------------------------------------------------------------


def test_quality_score_or_float_accepted() -> None:
    rc = RewardCalculator(nu=0.5)
    via_float = rc.compute(quality=0.7, cost_usdc=0.0, failure_flag=False, lambda_t=0.0)
    via_qs = rc.compute(
        quality=QualityScore(q=0.7, backend=EvaluatorBackend.EM_F1),
        cost_usdc=0.0, failure_flag=False, lambda_t=0.0,
    )
    assert via_float.utility == via_qs.utility


def test_quality_outside_unit_interval_rejected() -> None:
    rc = RewardCalculator(nu=0.5)
    with pytest.raises(ValueError):
        rc.compute(quality=1.5, cost_usdc=0.0, failure_flag=False, lambda_t=0.0)


def test_negative_inputs_rejected() -> None:
    rc = RewardCalculator(nu=0.5)
    with pytest.raises(ValueError):
        rc.compute(quality=0.5, cost_usdc=-0.001, failure_flag=False, lambda_t=0.0)
    with pytest.raises(ValueError):
        rc.compute(quality=0.5, cost_usdc=0.0, failure_flag=False, lambda_t=-0.5)


def test_nu_must_be_non_negative() -> None:
    with pytest.raises(ValueError):
        RewardCalculator(nu=-0.1)


def test_max_provider_cost_must_be_positive() -> None:
    with pytest.raises(ValueError):
        RewardCalculator(nu=0.5, max_provider_cost_usdc=0.0)


def test_cost_above_max_clipped_to_one() -> None:
    """If a future provider exceeds max_provider_cost_usdc, c̃ caps at 1.0."""
    rc = RewardCalculator(nu=0.5, max_provider_cost_usdc=0.01)
    out = rc.compute(quality=1.0, cost_usdc=0.05, failure_flag=False, lambda_t=1e9)
    # c̃ should cap at 1.0 → λ_norm→1 → PA → -1
    assert out.payment_aware_reward == pytest.approx(-1.0, abs=1e-6)


def test_reward_object_has_legacy_mu_field_zero() -> None:
    """Schema stability: Reward.mu still exists (=0) so older log readers
    don't break, even though the latency term was retired."""
    rc = RewardCalculator(nu=0.5)
    out = rc.compute(quality=0.7, cost_usdc=0.0, failure_flag=False, lambda_t=0.0)
    assert out.mu == 0.0
    assert out.nu == 0.5
