"""Tests for ``pilot402.policies.sw_ts.SWTSPolicy``.

Coverage:
- Protocol conformance
- Decision rule selects from affordable set only
- Sliding window forgets old samples
- ``observed_cost`` ignored (SW-TS is reward-only)
- Context is ignored (per-arm posterior, no per-bucket structure)
- Under stationary feedback, converges to a higher-reward arm
"""

from __future__ import annotations

import pytest
from numpy.random import default_rng

from pilot402.core import ProviderId
from pilot402.core.interfaces import Policy
from pilot402.policies.sw_ts import SWTSPolicy


_ARMS: tuple[ProviderId, ...] = (
    ProviderId.P_CHEAP,
    ProviderId.P_MID,
    ProviderId.P_PREMIUM,
    ProviderId.P_ADV,
    ProviderId.P_FLAKY,
)


def _ctx_t1() -> tuple[float, ...]:
    return (1.0, 0.0, 0.0, 0.0, 0.5, 1.0, 1.0)


def _ctx_t2() -> tuple[float, ...]:
    return (0.0, 1.0, 0.0, 0.0, 0.5, 1.0, 1.0)


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_implements_policy_protocol() -> None:
    p = SWTSPolicy(rng=default_rng(0), provider_ids=_ARMS)
    assert isinstance(p, Policy)


# ---------------------------------------------------------------------------
# Decision rule sanity
# ---------------------------------------------------------------------------


def test_select_returns_member_of_affordable() -> None:
    p = SWTSPolicy(rng=default_rng(0), provider_ids=_ARMS)
    affordable = (ProviderId.P_CHEAP, ProviderId.P_MID)
    for _ in range(50):
        chosen = p.select(context=_ctx_t1(), affordable_arms=affordable)
        assert chosen in affordable


def test_empty_affordable_set_rejected() -> None:
    p = SWTSPolicy(rng=default_rng(0), provider_ids=_ARMS)
    with pytest.raises(ValueError):
        p.select(context=_ctx_t1(), affordable_arms=())


def test_unknown_arm_raises() -> None:
    p = SWTSPolicy(rng=default_rng(0), provider_ids=(ProviderId.P_CHEAP,))
    with pytest.raises(KeyError):
        p.select(context=_ctx_t1(), affordable_arms=(ProviderId.P_MID,))


# ---------------------------------------------------------------------------
# Observed-cost / context independence
# ---------------------------------------------------------------------------


def test_observed_cost_is_ignored() -> None:
    """SW-TS does not learn cost; observed_cost must not affect the policy."""
    p1 = SWTSPolicy(rng=default_rng(0), provider_ids=_ARMS)
    p2 = SWTSPolicy(rng=default_rng(0), provider_ids=_ARMS)
    p1.update(context=_ctx_t1(), arm=ProviderId.P_MID, utility=0.8, observed_cost=0.001)
    p2.update(context=_ctx_t1(), arm=ProviderId.P_MID, utility=0.8, observed_cost=999.0)
    assert p1.posterior_state() == p2.posterior_state()


def test_context_is_ignored() -> None:
    """SW-TS posterior must not depend on context (non-contextual)."""
    p1 = SWTSPolicy(rng=default_rng(0), provider_ids=_ARMS)
    p2 = SWTSPolicy(rng=default_rng(0), provider_ids=_ARMS)
    p1.update(context=_ctx_t1(), arm=ProviderId.P_MID, utility=0.8, observed_cost=0.001)
    p2.update(context=_ctx_t2(), arm=ProviderId.P_MID, utility=0.8, observed_cost=0.001)
    assert p1.posterior_state() == p2.posterior_state()


# ---------------------------------------------------------------------------
# Sliding window
# ---------------------------------------------------------------------------


def test_sliding_window_forgets_old_samples() -> None:
    p = SWTSPolicy(rng=default_rng(0), provider_ids=_ARMS, window=3)
    # Fill the window with three high observations of P_MID (global rounds 1,2,3).
    for _ in range(3):
        p.update(context=_ctx_t1(), arm=ProviderId.P_MID, utility=1.0, observed_cost=0.002)
    state = p.posterior_state()[ProviderId.P_MID.value]
    assert state["n_samples"] == 3
    high_mean = state["posterior_mean"]

    # Push three low observations (global rounds 4,5,6). Round-1..3 entries
    # fall outside the W=3 window at global_round=6 (cutoff=3, pruned).
    for _ in range(3):
        p.update(context=_ctx_t1(), arm=ProviderId.P_MID, utility=0.0, observed_cost=0.002)
    state = p.posterior_state()[ProviderId.P_MID.value]
    assert state["n_samples"] == 3
    assert state["posterior_mean"] < high_mean


def test_unselected_arm_drains_to_prior_after_W_global_rounds() -> None:
    """Wall-clock semantics: an arm that is not pulled for W+1 rounds
    reverts to its prior even though its deque still holds the old entry.
    """
    p = SWTSPolicy(rng=default_rng(0), provider_ids=_ARMS, window=5)
    # One observation on P_MID at global round 1 with very high utility.
    p.update(context=_ctx_t1(), arm=ProviderId.P_MID, utility=1.0, observed_cost=0.002)
    state = p.posterior_state()[ProviderId.P_MID.value]
    high_mean = state["posterior_mean"]
    assert state["n_samples"] == 1
    assert high_mean > p.prior_mean  # one high obs pulls mean above prior

    # Now push P_CHEAP observations for W+5 = 10 rounds. P_MID gets stale.
    for _ in range(10):
        p.update(context=_ctx_t1(), arm=ProviderId.P_CHEAP, utility=0.5, observed_cost=0.0005)

    # P_MID's old observation (round 1) is now older than W=5 from round 11
    # → cutoff = 11 - 5 = 6, round_idx 1 ≤ 6 → pruned. P_MID reverts to prior.
    state = p.posterior_state()[ProviderId.P_MID.value]
    assert state["n_samples"] == 0
    assert state["posterior_mean"] == pytest.approx(p.prior_mean)


# ---------------------------------------------------------------------------
# Learning behaviour
# ---------------------------------------------------------------------------


def test_converges_to_higher_quality_arm() -> None:
    """Two arms with different reward; SW-TS should converge."""
    p = SWTSPolicy(
        rng=default_rng(123),
        provider_ids=(ProviderId.P_CHEAP, ProviderId.P_MID),
        window=500,
    )
    affordable = (ProviderId.P_CHEAP, ProviderId.P_MID)
    counts = {ProviderId.P_CHEAP: 0, ProviderId.P_MID: 0}
    for _ in range(500):
        chosen = p.select(context=_ctx_t1(), affordable_arms=affordable)
        counts[chosen] += 1
        utility = 0.85 if chosen == ProviderId.P_MID else 0.55
        p.update(context=_ctx_t1(), arm=chosen, utility=utility, observed_cost=0.002)
    assert counts[ProviderId.P_MID] > counts[ProviderId.P_CHEAP] * 3
