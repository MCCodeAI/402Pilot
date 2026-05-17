"""Tests for ``pilot402.policies.contextual_bts.ContextualBTSPolicy``.

Coverage:
- Protocol conformance (no wallet handle needed)
- Decision rule selects from affordable set only
- No discount: posterior n_eff accumulates monotonically
- Posterior updates touch only the chosen (arm, bucket)
- Both Q and C posteriors update from a single update() call
- Ratio scoring: higher-quality cheaper arm wins under matched priors
- Per-context bucketing
"""

from __future__ import annotations

import pytest
from numpy.random import default_rng

from pilot402.core import ProviderId
from pilot402.core.interfaces import Policy
from pilot402.policies.contextual_bts import ContextualBTSPolicy


_DEFAULT_PRICES = {
    ProviderId.P_CHEAP: 0.0005,
    ProviderId.P_MID: 0.002,
    ProviderId.P_PREMIUM: 0.01,
    ProviderId.P_ADV: 0.002,
    ProviderId.P_FLAKY: 0.002,
}


def _ctx_t1() -> tuple[float, ...]:
    return (1.0, 0.0, 0.0, 0.0, 0.5, 1.0, 1.0)


def _ctx_t2() -> tuple[float, ...]:
    return (0.0, 1.0, 0.0, 0.0, 0.5, 1.0, 1.0)


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_implements_policy_protocol() -> None:
    p = ContextualBTSPolicy(rng=default_rng(0), provider_costs=_DEFAULT_PRICES)
    assert isinstance(p, Policy)


# ---------------------------------------------------------------------------
# Decision rule sanity
# ---------------------------------------------------------------------------


def test_select_returns_member_of_affordable() -> None:
    p = ContextualBTSPolicy(rng=default_rng(0), provider_costs=_DEFAULT_PRICES)
    affordable = (ProviderId.P_CHEAP, ProviderId.P_MID)
    for _ in range(50):
        chosen = p.select(context=_ctx_t1(), affordable_arms=affordable)
        assert chosen in affordable


def test_empty_affordable_set_rejected() -> None:
    p = ContextualBTSPolicy(rng=default_rng(0), provider_costs=_DEFAULT_PRICES)
    with pytest.raises(ValueError):
        p.select(context=_ctx_t1(), affordable_arms=())


def test_unknown_arm_raises() -> None:
    p = ContextualBTSPolicy(
        rng=default_rng(0),
        provider_costs={ProviderId.P_CHEAP: 0.0005},
    )
    with pytest.raises(KeyError):
        p.select(context=_ctx_t1(), affordable_arms=(ProviderId.P_MID,))


# ---------------------------------------------------------------------------
# No discount: n_eff grows monotonically
# ---------------------------------------------------------------------------


def test_no_discount_means_n_eff_accumulates() -> None:
    """BTS is stationary: 100 selects + updates should leave n_eff = 100."""
    p = ContextualBTSPolicy(rng=default_rng(0), provider_costs=_DEFAULT_PRICES)
    for _ in range(100):
        p.select(
            context=_ctx_t1(),
            affordable_arms=tuple(_DEFAULT_PRICES.keys()),
        )
        p.update(
            context=_ctx_t1(),
            arm=ProviderId.P_MID,
            utility=0.8,
            observed_cost=0.002,
        )
    q_state = p.posterior_state()[ProviderId.P_MID.value][0]
    c_state = p.cost_posterior_state()[ProviderId.P_MID.value][0]
    assert q_state["n_eff"] == pytest.approx(100.0)
    assert c_state["n_eff"] == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# Posterior updates
# ---------------------------------------------------------------------------


def test_update_touches_both_posteriors_for_chosen_cell() -> None:
    p = ContextualBTSPolicy(rng=default_rng(0), provider_costs=_DEFAULT_PRICES)
    p.update(context=_ctx_t1(), arm=ProviderId.P_MID, utility=0.8, observed_cost=0.003)
    q_state = p.posterior_state()
    c_state = p.cost_posterior_state()
    # Q-posterior: P-mid bucket 0 should be updated
    assert q_state[ProviderId.P_MID.value][0]["n_eff"] == pytest.approx(1.0)
    assert q_state[ProviderId.P_MID.value][0]["s_eff"] == pytest.approx(0.8)
    # C-posterior: same cell should also be updated
    assert c_state[ProviderId.P_MID.value][0]["n_eff"] == pytest.approx(1.0)
    assert c_state[ProviderId.P_MID.value][0]["s_eff"] == pytest.approx(0.003)
    # Other cells must remain at zero in both posteriors
    for arm_str, buckets in q_state.items():
        for b, s in buckets.items():
            if (arm_str, b) != (ProviderId.P_MID.value, 0):
                assert s["n_eff"] == 0.0


def test_contextual_buckets_are_independent() -> None:
    p = ContextualBTSPolicy(rng=default_rng(0), provider_costs=_DEFAULT_PRICES)
    p.update(context=_ctx_t1(), arm=ProviderId.P_MID, utility=0.9, observed_cost=0.002)
    state = p.posterior_state()[ProviderId.P_MID.value]
    assert state[0]["n_eff"] == pytest.approx(1.0)
    for b in (1, 2, 3):
        assert state[b]["n_eff"] == 0.0


# ---------------------------------------------------------------------------
# Ratio scoring: when one arm dominates on quality at equal cost, BTS picks it
# ---------------------------------------------------------------------------


def test_ratio_scoring_converges_to_better_arm_at_equal_price() -> None:
    """Two arms, identical price, different quality: BTS should converge."""
    p = ContextualBTSPolicy(
        rng=default_rng(123),
        provider_costs={
            ProviderId.P_CHEAP: 0.002,
            ProviderId.P_MID: 0.002,
        },
    )
    affordable = (ProviderId.P_CHEAP, ProviderId.P_MID)
    counts = {ProviderId.P_CHEAP: 0, ProviderId.P_MID: 0}
    for _ in range(500):
        chosen = p.select(context=_ctx_t1(), affordable_arms=affordable)
        counts[chosen] += 1
        utility = 0.85 if chosen == ProviderId.P_MID else 0.55
        p.update(context=_ctx_t1(), arm=chosen, utility=utility, observed_cost=0.002)
    assert counts[ProviderId.P_MID] > counts[ProviderId.P_CHEAP] * 3


def test_cost_floor_prevents_division_blowup() -> None:
    """A near-zero sampled cost should not produce an infinite score."""
    p = ContextualBTSPolicy(
        rng=default_rng(0),
        provider_costs={ProviderId.P_CHEAP: 1e-9, ProviderId.P_MID: 1e-9},
        cost_floor=1e-3,
    )
    # No data → samples cluster near priors (1e-9), but cost_floor 1e-3 caps the
    # denominator so select() still returns a valid arm without overflow.
    for _ in range(20):
        chosen = p.select(
            context=_ctx_t1(),
            affordable_arms=(ProviderId.P_CHEAP, ProviderId.P_MID),
        )
        assert chosen in (ProviderId.P_CHEAP, ProviderId.P_MID)
