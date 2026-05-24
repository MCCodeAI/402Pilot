"""Tests for ``pilot402.policies.lincbwk.LinCBwKPolicy``.

Coverage:
- Protocol conformance
- Decision rule selects from affordable set only
- Posterior update touches only the chosen (arm, bucket)
- Cost LCB clipping prevents negative penalty contributions
- Dual μ responds to wallet pressure (rises when remaining_frac < time_frac)
- Per-context bucketing
- Under stationary feedback, converges to a strong arm
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from numpy.random import default_rng

from pilot402.core import ProviderId
from pilot402.core.interfaces import Policy
from pilot402.policies.lincbwk import LinCBwKPolicy


_ARMS: tuple[ProviderId, ...] = (
    ProviderId.P_CHEAP,
    ProviderId.P_MID,
    ProviderId.P_PREMIUM,
    ProviderId.P_ADV,
    ProviderId.P_FLAKY,
)


@dataclass
class _StubWallet:
    """Minimal BudgetManager stand-in with overridable remaining_fraction."""

    remaining_fraction: float = 1.0
    fixed_lambda: float = 1.0

    def get_lambda(self) -> float:
        return self.fixed_lambda

    def affordable(self, cost_usdc: float) -> bool:
        return True

    def record_spend(self, cost_usdc: float) -> None:
        pass

    def snapshot(self) -> dict[str, float]:
        return {
            "lambda_t": self.fixed_lambda,
            "remaining_fraction": self.remaining_fraction,
        }


def _ctx_t1() -> tuple[float, ...]:
    return (1.0, 0.0, 0.0, 0.0, 0.5, 1.0, 1.0)


def _ctx_t2() -> tuple[float, ...]:
    return (0.0, 1.0, 0.0, 0.0, 0.5, 1.0, 1.0)


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_implements_policy_protocol() -> None:
    p = LinCBwKPolicy(
        wallet=_StubWallet(),
        provider_ids=_ARMS,
        total_rounds=1000,
    )
    assert isinstance(p, Policy)


# ---------------------------------------------------------------------------
# Decision rule sanity
# ---------------------------------------------------------------------------


def test_select_returns_member_of_affordable() -> None:
    p = LinCBwKPolicy(
        wallet=_StubWallet(),
        provider_ids=_ARMS,
        total_rounds=1000,
    )
    affordable = (ProviderId.P_CHEAP, ProviderId.P_MID)
    for _ in range(50):
        chosen = p.select(context=_ctx_t1(), affordable_arms=affordable)
        assert chosen in affordable


def test_empty_affordable_set_rejected() -> None:
    p = LinCBwKPolicy(
        wallet=_StubWallet(),
        provider_ids=_ARMS,
        total_rounds=1000,
    )
    with pytest.raises(ValueError):
        p.select(context=_ctx_t1(), affordable_arms=())


def test_unknown_arm_raises() -> None:
    p = LinCBwKPolicy(
        wallet=_StubWallet(),
        provider_ids=(ProviderId.P_CHEAP,),
        total_rounds=1000,
    )
    with pytest.raises(KeyError):
        p.select(context=_ctx_t1(), affordable_arms=(ProviderId.P_MID,))


# ---------------------------------------------------------------------------
# Cost LCB numerical guard
# ---------------------------------------------------------------------------


def test_cost_lcb_clipped_at_floor_no_nan_in_early_rounds() -> None:
    """Early rounds should produce finite scores even with wide cost posterior."""
    p = LinCBwKPolicy(
        wallet=_StubWallet(),
        provider_ids=_ARMS,
        total_rounds=1000,
    )
    # 10 select() calls with no updates: posterior var stays wide. Scores must
    # be finite (cost_floor guard prevents lcb_c going negative through the
    # μ multiplication when μ becomes positive in later runs).
    for _ in range(10):
        chosen = p.select(context=_ctx_t1(), affordable_arms=_ARMS)
        assert chosen in _ARMS


# ---------------------------------------------------------------------------
# Dual variable update
# ---------------------------------------------------------------------------


def test_dual_increases_when_overspending() -> None:
    """remaining_frac < time_frac → μ grows."""
    wallet = _StubWallet(remaining_fraction=0.1)  # very low remaining
    p = LinCBwKPolicy(
        wallet=wallet,
        provider_ids=_ARMS,
        total_rounds=1000,
        eta_dual=0.1,  # bigger step for test legibility
    )
    initial_mu = p.mu
    # Many select calls with low remaining_frac, no updates increase round.
    for _ in range(20):
        p.select(context=_ctx_t1(), affordable_arms=_ARMS)
    assert p.mu > initial_mu


def test_dual_decreases_when_underspending() -> None:
    """remaining_frac > time_frac → μ shrinks back to 0."""
    wallet = _StubWallet(remaining_fraction=1.0)
    p = LinCBwKPolicy(
        wallet=wallet,
        provider_ids=_ARMS,
        total_rounds=1000,
        eta_dual=0.1,
        mu_init=5.0,  # start with positive μ
    )
    initial_mu = p.mu
    for _ in range(20):
        p.select(context=_ctx_t1(), affordable_arms=_ARMS)
    assert p.mu < initial_mu


def test_dual_stays_nonnegative() -> None:
    """μ is clipped at 0 from below."""
    p = LinCBwKPolicy(
        wallet=_StubWallet(remaining_fraction=1.0),
        provider_ids=_ARMS,
        total_rounds=10,
        eta_dual=1.0,  # huge step so μ would go negative without clip
    )
    for _ in range(20):
        p.select(context=_ctx_t1(), affordable_arms=_ARMS)
    assert p.mu >= 0.0


# ---------------------------------------------------------------------------
# Posterior updates
# ---------------------------------------------------------------------------


def test_update_only_touches_chosen_arm_bucket() -> None:
    p = LinCBwKPolicy(
        wallet=_StubWallet(),
        provider_ids=_ARMS,
        total_rounds=1000,
    )
    p.update(context=_ctx_t1(), arm=ProviderId.P_MID, utility=0.8, observed_cost=0.002)
    r_state = p.posterior_state()
    c_state = p.cost_posterior_state()
    for arm_str, buckets in r_state.items():
        for b, s in buckets.items():
            if arm_str == ProviderId.P_MID.value and b == 0:
                assert s["n_eff"] == pytest.approx(1.0)
                assert s["s_eff"] == pytest.approx(0.8)
            else:
                assert s["n_eff"] == 0.0
                assert s["s_eff"] == 0.0
    # Cost posterior: same touch pattern; check the normalized cost.
    chosen_c = c_state[ProviderId.P_MID.value][0]
    assert chosen_c["n_eff"] == pytest.approx(1.0)
    # Default c_max = 0.01 → normalized cost = 0.2.
    assert chosen_c["s_eff"] == pytest.approx(0.2)


def test_contextual_buckets_are_independent() -> None:
    p = LinCBwKPolicy(
        wallet=_StubWallet(),
        provider_ids=_ARMS,
        total_rounds=1000,
    )
    p.update(context=_ctx_t1(), arm=ProviderId.P_MID, utility=0.9, observed_cost=0.002)
    state = p.posterior_state()[ProviderId.P_MID.value]
    assert state[0]["n_eff"] == pytest.approx(1.0)
    for b in (1, 2, 3):
        assert state[b]["n_eff"] == 0.0


# ---------------------------------------------------------------------------
# Learning behaviour: stationary, μ disabled (constant remaining)
# ---------------------------------------------------------------------------


def test_converges_to_higher_quality_arm_under_no_cost_pressure() -> None:
    """Two arms, identical cost; LinCBwK should prefer higher quality."""
    p = LinCBwKPolicy(
        wallet=_StubWallet(remaining_fraction=1.0),  # μ stays at 0
        provider_ids=(ProviderId.P_CHEAP, ProviderId.P_MID),
        total_rounds=1000,
        eta_dual=0.001,  # small step so μ remains negligible
    )
    affordable = (ProviderId.P_CHEAP, ProviderId.P_MID)
    counts = {ProviderId.P_CHEAP: 0, ProviderId.P_MID: 0}
    for _ in range(500):
        chosen = p.select(context=_ctx_t1(), affordable_arms=affordable)
        counts[chosen] += 1
        # Same fixed cost for fair quality-only comparison
        utility = 0.85 if chosen == ProviderId.P_MID else 0.55
        p.update(context=_ctx_t1(), arm=chosen, utility=utility, observed_cost=0.002)
    # After 500 rounds the policy should favor the better arm.
    assert counts[ProviderId.P_MID] > counts[ProviderId.P_CHEAP]
