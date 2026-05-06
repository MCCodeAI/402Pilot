"""Tests for ``pilot402.policies.random.RandomPolicy``."""

from __future__ import annotations

from collections import Counter

import pytest
from numpy.random import default_rng

from pilot402.core import ProviderId
from pilot402.core.interfaces import Policy
from pilot402.policies.random import RandomPolicy


def test_implements_policy_protocol() -> None:
    p = RandomPolicy(rng=default_rng(0))
    assert isinstance(p, Policy)


def test_select_returns_member_of_affordable() -> None:
    p = RandomPolicy(rng=default_rng(0))
    affordable = (ProviderId.P_CHEAP, ProviderId.P_MID)
    for _ in range(50):
        chosen = p.select(context=(0.0,), affordable_arms=affordable)
        assert chosen in affordable


def test_select_is_uniform_over_affordable() -> None:
    p = RandomPolicy(rng=default_rng(42))
    affordable = tuple(ProviderId)
    counts = Counter(
        p.select(context=(0.0,), affordable_arms=affordable) for _ in range(5000)
    )
    # 5 arms × 5000 draws ≈ 1000 each; tolerate ±20%.
    for arm in ProviderId:
        assert 800 < counts[arm] < 1200, f"arm {arm} undersampled: {counts}"


def test_empty_affordable_set_rejected() -> None:
    p = RandomPolicy(rng=default_rng(0))
    with pytest.raises(ValueError):
        p.select(context=(0.0,), affordable_arms=())


def test_update_is_noop_and_returns_none() -> None:
    p = RandomPolicy(rng=default_rng(0))
    assert p.update(context=(0.0,), arm=ProviderId.P_MID, utility=0.5, observed_cost=0.002) is None


def test_deterministic_for_fixed_seed() -> None:
    seq_a = []
    p = RandomPolicy(rng=default_rng(7))
    affordable = tuple(ProviderId)
    for _ in range(20):
        seq_a.append(p.select(context=(0.0,), affordable_arms=affordable))
    seq_b = []
    p = RandomPolicy(rng=default_rng(7))
    for _ in range(20):
        seq_b.append(p.select(context=(0.0,), affordable_arms=affordable))
    assert seq_a == seq_b
