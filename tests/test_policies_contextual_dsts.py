"""Tests for ``pilot402.policies.contextual_dsts.ContextualDSTSPolicy``.

Coverage:
- Protocol conformance (no wallet handle needed)
- Decision rule selects from affordable set only
- Discount applies per round to all (arm, bucket) cells
- Posterior update touches only the chosen (arm, bucket)
- ``observed_cost`` argument is ignored (DS-TS does not learn cost)
- Per-context bucketing (T1 vs T2 use different posteriors)
"""

from __future__ import annotations

import pytest
from numpy.random import default_rng

from pilot402.core import ProviderId
from pilot402.core.interfaces import Policy
from pilot402.policies.contextual_dsts import ContextualDSTSPolicy


_ARMS: tuple[ProviderId, ...] = (
    ProviderId.P_CHEAP,
    ProviderId.P_MID,
    ProviderId.P_PREMIUM,
    ProviderId.P_ADV,
    ProviderId.P_FLAKY,
)


def _ctx_t1() -> tuple[float, ...]:
    """Sample context with task type T1 one-hot at index 0."""
    return (1.0, 0.0, 0.0, 0.0, 0.5, 1.0, 1.0)


def _ctx_t2() -> tuple[float, ...]:
    return (0.0, 1.0, 0.0, 0.0, 0.5, 1.0, 1.0)


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_implements_policy_protocol() -> None:
    p = ContextualDSTSPolicy(rng=default_rng(0), provider_ids=_ARMS)
    assert isinstance(p, Policy)


# ---------------------------------------------------------------------------
# Decision rule sanity
# ---------------------------------------------------------------------------


def test_select_returns_member_of_affordable() -> None:
    p = ContextualDSTSPolicy(rng=default_rng(0), provider_ids=_ARMS)
    affordable = (ProviderId.P_CHEAP, ProviderId.P_MID)
    for _ in range(50):
        chosen = p.select(context=_ctx_t1(), affordable_arms=affordable)
        assert chosen in affordable


def test_empty_affordable_set_rejected() -> None:
    p = ContextualDSTSPolicy(rng=default_rng(0), provider_ids=_ARMS)
    with pytest.raises(ValueError):
        p.select(context=_ctx_t1(), affordable_arms=())


def test_unknown_arm_raises() -> None:
    p = ContextualDSTSPolicy(rng=default_rng(0), provider_ids=(ProviderId.P_CHEAP,))
    with pytest.raises(KeyError):
        p.select(context=_ctx_t1(), affordable_arms=(ProviderId.P_MID,))


# ---------------------------------------------------------------------------
# Posterior updates
# ---------------------------------------------------------------------------


def test_update_only_touches_chosen_arm_bucket() -> None:
    p = ContextualDSTSPolicy(rng=default_rng(0), provider_ids=_ARMS, gamma=1.0)
    p.update(context=_ctx_t1(), arm=ProviderId.P_MID, utility=0.8, observed_cost=0.002)
    state = p.posterior_state()
    for arm_str, buckets in state.items():
        for b, s in buckets.items():
            if arm_str == ProviderId.P_MID.value and b == 0:
                assert s["n_eff"] == pytest.approx(1.0)
                assert s["s_eff"] == pytest.approx(0.8)
            else:
                assert s["n_eff"] == 0.0
                assert s["s_eff"] == 0.0


def test_observed_cost_is_ignored() -> None:
    """DS-TS does not learn cost: observed_cost must not affect the policy."""
    p1 = ContextualDSTSPolicy(rng=default_rng(0), provider_ids=_ARMS, gamma=1.0)
    p2 = ContextualDSTSPolicy(rng=default_rng(0), provider_ids=_ARMS, gamma=1.0)
    p1.update(context=_ctx_t1(), arm=ProviderId.P_MID, utility=0.8, observed_cost=0.001)
    p2.update(context=_ctx_t1(), arm=ProviderId.P_MID, utility=0.8, observed_cost=999.0)
    assert p1.posterior_state() == p2.posterior_state()


# ---------------------------------------------------------------------------
# Discount and contextual bucketing
# ---------------------------------------------------------------------------


def test_discount_applies_to_all_cells_per_round() -> None:
    p = ContextualDSTSPolicy(rng=default_rng(0), provider_ids=_ARMS, gamma=0.5)
    # Seed P-mid bucket 0 with one observation
    p.update(context=_ctx_t1(), arm=ProviderId.P_MID, utility=0.8, observed_cost=0.002)
    # One select() applies discount once; then update is fresh on chosen cell.
    p.select(context=_ctx_t1(), affordable_arms=(ProviderId.P_MID,))
    state = p.posterior_state()[ProviderId.P_MID.value][0]
    # After discount: n_eff = 0.5 * 1 = 0.5, then no update yet since this
    # call just discounted in select.
    assert state["n_eff"] == pytest.approx(0.5)
    assert state["s_eff"] == pytest.approx(0.4)


def test_contextual_buckets_are_independent() -> None:
    """An observation in T1 must not bleed into T2's posterior."""
    p = ContextualDSTSPolicy(rng=default_rng(0), provider_ids=_ARMS, gamma=1.0)
    p.update(context=_ctx_t1(), arm=ProviderId.P_MID, utility=0.9, observed_cost=0.002)
    state = p.posterior_state()[ProviderId.P_MID.value]
    assert state[0]["n_eff"] == pytest.approx(1.0)
    # Buckets 1, 2, 3 must remain at zero
    for b in (1, 2, 3):
        assert state[b]["n_eff"] == 0.0


# ---------------------------------------------------------------------------
# Learning: under stationary feedback the policy should converge
# ---------------------------------------------------------------------------


def test_converges_to_best_arm_when_quality_differs() -> None:
    """Two arms, identical price, different quality; DS-TS should learn."""
    p = ContextualDSTSPolicy(
        rng=default_rng(123),
        provider_ids=(ProviderId.P_CHEAP, ProviderId.P_MID),
        gamma=1.0,
    )
    affordable = (ProviderId.P_CHEAP, ProviderId.P_MID)
    counts = {ProviderId.P_CHEAP: 0, ProviderId.P_MID: 0}
    for _ in range(500):
        chosen = p.select(context=_ctx_t1(), affordable_arms=affordable)
        counts[chosen] += 1
        # P-mid is better
        utility = 0.85 if chosen == ProviderId.P_MID else 0.55
        p.update(context=_ctx_t1(), arm=chosen, utility=utility, observed_cost=0.002)
    # After 500 rounds the policy should heavily favor the better arm.
    assert counts[ProviderId.P_MID] > counts[ProviderId.P_CHEAP] * 3
