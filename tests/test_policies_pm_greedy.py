"""Tests for ``pilot402.policies.pm_greedy.PMGreedyPolicy``.

Coverage:
- Protocol conformance
- Decision rule selects from affordable set only
- Cascade rule (cheapest above τ, fallback argmax q̂)
- Tie-break: cheapest first, then higher q̂ within tied price
- Optimistic init: first round picks cheapest affordable arm
- Listed price callable is read per select(), enabling S3-style shocks
- Sliding window forgets old observations
"""

from __future__ import annotations

import pytest

from pilot402.core import ProviderId
from pilot402.core.interfaces import Policy
from pilot402.policies.pm_greedy import PMGreedyPolicy


_ARMS: tuple[ProviderId, ...] = (
    ProviderId.P_CHEAP,
    ProviderId.P_MID,
    ProviderId.P_PREMIUM,
    ProviderId.P_ADV,
    ProviderId.P_FLAKY,
)


_STATIC_PRICES = {
    ProviderId.P_CHEAP: 0.0005,
    ProviderId.P_MID: 0.002,
    ProviderId.P_PREMIUM: 0.01,
    ProviderId.P_ADV: 0.002,
    ProviderId.P_FLAKY: 0.002,
}


def _static_price_fn(round_idx: int, pid: ProviderId) -> float:
    return _STATIC_PRICES[pid]


def _ctx_t1() -> tuple[float, ...]:
    return (1.0, 0.0, 0.0, 0.0, 0.5, 1.0, 1.0)


def _ctx_t2() -> tuple[float, ...]:
    return (0.0, 1.0, 0.0, 0.0, 0.5, 1.0, 1.0)


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_implements_policy_protocol() -> None:
    p = PMGreedyPolicy(
        listed_price_fn=_static_price_fn,
        provider_ids=_ARMS,
    )
    assert isinstance(p, Policy)


# ---------------------------------------------------------------------------
# Decision rule sanity
# ---------------------------------------------------------------------------


def test_select_returns_member_of_affordable() -> None:
    p = PMGreedyPolicy(listed_price_fn=_static_price_fn, provider_ids=_ARMS)
    affordable = (ProviderId.P_CHEAP, ProviderId.P_MID)
    for _ in range(50):
        chosen = p.select(context=_ctx_t1(), affordable_arms=affordable)
        assert chosen in affordable


def test_empty_affordable_set_rejected() -> None:
    p = PMGreedyPolicy(listed_price_fn=_static_price_fn, provider_ids=_ARMS)
    with pytest.raises(ValueError):
        p.select(context=_ctx_t1(), affordable_arms=())


def test_unknown_arm_raises() -> None:
    p = PMGreedyPolicy(
        listed_price_fn=_static_price_fn,
        provider_ids=(ProviderId.P_CHEAP,),
    )
    with pytest.raises(KeyError):
        p.select(context=_ctx_t1(), affordable_arms=(ProviderId.P_MID,))


# ---------------------------------------------------------------------------
# Cascade rule
# ---------------------------------------------------------------------------


def test_optimistic_init_picks_cheapest_first() -> None:
    """All arms start at q̂=1.0 ≥ τ → rule picks the lowest listed price."""
    p = PMGreedyPolicy(listed_price_fn=_static_price_fn, provider_ids=_ARMS)
    chosen = p.select(context=_ctx_t1(), affordable_arms=_ARMS)
    assert chosen == ProviderId.P_CHEAP


def test_fallback_to_argmax_q_when_all_below_threshold() -> None:
    """If every q̂ < τ, return the arm with the highest q̂."""
    p = PMGreedyPolicy(
        listed_price_fn=_static_price_fn,
        provider_ids=_ARMS,
        threshold=0.9,  # very high
        q_init=0.0,    # no optimism so cells start below τ
    )
    # Seed P-mid with q=0.6 obs; P-cheap stays at q̂=0 (no samples).
    p.update(context=_ctx_t1(), arm=ProviderId.P_MID, utility=0.6, observed_cost=0.002)
    chosen = p.select(context=_ctx_t1(), affordable_arms=(ProviderId.P_CHEAP, ProviderId.P_MID))
    # Both below 0.9 → fallback. P-mid has higher q̂.
    assert chosen == ProviderId.P_MID


def test_tie_break_within_equal_price_uses_higher_q_hat() -> None:
    """Among arms at the same listed price above τ, prefer higher q̂."""
    # Set up: feed P-MID with q=1.0, P-ADV with q=0.6 (both $0.002, both above τ=0.7).
    p = PMGreedyPolicy(
        listed_price_fn=_static_price_fn,
        provider_ids=_ARMS,
        threshold=0.5,
        q_init=0.0,
    )
    for _ in range(5):
        p.update(context=_ctx_t1(), arm=ProviderId.P_MID, utility=1.0, observed_cost=0.002)
        p.update(context=_ctx_t1(), arm=ProviderId.P_ADV, utility=0.6, observed_cost=0.002)
    chosen = p.select(
        context=_ctx_t1(),
        affordable_arms=(ProviderId.P_MID, ProviderId.P_ADV),
    )
    assert chosen == ProviderId.P_MID


# ---------------------------------------------------------------------------
# Listed-price callable freshness (S3-style shock simulation)
# ---------------------------------------------------------------------------


def test_listed_price_callable_is_read_per_round() -> None:
    """Switching the price of an arm mid-run should change selection.

    Simulates the S3 mechanic: at round 1000 P-premium's listed price drops to
    P-mid's; the cascade rule should now consider P-premium at the same tier.
    """
    shock_round = 5
    base = dict(_STATIC_PRICES)

    def shock_price(round_idx: int, pid: ProviderId) -> float:
        if round_idx >= shock_round and pid == ProviderId.P_PREMIUM:
            return 0.002  # post-shock price
        return base[pid]

    p = PMGreedyPolicy(
        listed_price_fn=shock_price,
        provider_ids=_ARMS,
        threshold=0.5,
        q_init=1.0,
    )
    affordable = (ProviderId.P_MID, ProviderId.P_PREMIUM)

    # Before the shock, premium is more expensive → P-mid wins.
    chosen = p.select(context=_ctx_t1(), affordable_arms=affordable)
    p.update(context=_ctx_t1(), arm=chosen, utility=0.8, observed_cost=0.002)
    assert chosen == ProviderId.P_MID

    # Advance round counter to past the shock.
    while p._round < shock_round:
        chosen = p.select(context=_ctx_t1(), affordable_arms=affordable)
        p.update(context=_ctx_t1(), arm=chosen, utility=0.8, observed_cost=0.002)

    # Now both prices equal; tie-break uses higher q̂. P-premium has optimistic
    # q̂=1.0 (never sampled) vs P-mid's accumulated samples around 0.8.
    chosen_post = p.select(context=_ctx_t1(), affordable_arms=affordable)
    assert chosen_post == ProviderId.P_PREMIUM


# ---------------------------------------------------------------------------
# Sliding window
# ---------------------------------------------------------------------------


def test_sliding_window_forgets_old_samples() -> None:
    """When the window fills, the oldest observation should be dropped."""
    p = PMGreedyPolicy(
        listed_price_fn=_static_price_fn,
        provider_ids=_ARMS,
        window=3,
    )
    # Fill the window with three high observations.
    for _ in range(3):
        p.update(context=_ctx_t1(), arm=ProviderId.P_MID, utility=1.0, observed_cost=0.002)
    high_q = p.quality_estimates()[ProviderId.P_MID.value][0]["q_hat"]
    assert high_q == pytest.approx(1.0)

    # Push three low observations; window now holds only the low ones.
    for _ in range(3):
        p.update(context=_ctx_t1(), arm=ProviderId.P_MID, utility=0.0, observed_cost=0.002)
    low_q = p.quality_estimates()[ProviderId.P_MID.value][0]["q_hat"]
    assert low_q == pytest.approx(0.0)


def test_contextual_buckets_are_independent() -> None:
    p = PMGreedyPolicy(listed_price_fn=_static_price_fn, provider_ids=_ARMS)
    p.update(context=_ctx_t1(), arm=ProviderId.P_MID, utility=0.9, observed_cost=0.002)
    est = p.quality_estimates()[ProviderId.P_MID.value]
    assert est[0]["n_samples"] == 1
    for b in (1, 2, 3):
        assert est[b]["n_samples"] == 0
