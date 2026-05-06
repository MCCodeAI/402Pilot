"""Tests for ``pilot402.policies.fixed``."""

from __future__ import annotations

import pytest

from pilot402.core import ProviderId
from pilot402.core.interfaces import Policy
from pilot402.policies.fixed import (
    FixedPolicy,
    always_cheapest,
    always_mid,
    always_premium,
)


def test_implements_policy_protocol() -> None:
    p = FixedPolicy(target=ProviderId.P_MID)
    assert isinstance(p, Policy)


def test_picks_target_when_affordable() -> None:
    p = FixedPolicy(target=ProviderId.P_PREMIUM)
    affordable = (ProviderId.P_CHEAP, ProviderId.P_MID, ProviderId.P_PREMIUM)
    for _ in range(10):
        assert p.select(context=(0.0,), affordable_arms=affordable) == ProviderId.P_PREMIUM


def test_falls_back_when_target_not_affordable() -> None:
    p = FixedPolicy(target=ProviderId.P_PREMIUM)
    # Premium not available; cheap is the only one.
    affordable = (ProviderId.P_CHEAP,)
    chosen = p.select(context=(0.0,), affordable_arms=affordable)
    assert chosen == ProviderId.P_CHEAP


def test_empty_affordable_set_rejected() -> None:
    p = FixedPolicy(target=ProviderId.P_MID)
    with pytest.raises(ValueError):
        p.select(context=(0.0,), affordable_arms=())


def test_update_is_noop() -> None:
    p = FixedPolicy(target=ProviderId.P_MID)
    assert p.update(context=(0.0,), arm=ProviderId.P_MID, utility=0.5, observed_cost=0.002) is None


def test_named_factories_match_targets() -> None:
    assert always_cheapest().target is ProviderId.P_CHEAP
    assert always_mid().target is ProviderId.P_MID
    assert always_premium().target is ProviderId.P_PREMIUM


def test_factories_satisfy_protocol() -> None:
    for factory in (always_cheapest, always_mid, always_premium):
        assert isinstance(factory(), Policy)
