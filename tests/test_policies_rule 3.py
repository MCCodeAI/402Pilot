"""Tests for ``pilot402.policies.rule.BudgetRulePolicy``."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from pilot402.core import ProviderId
from pilot402.core.interfaces import Policy
from pilot402.policies.rule import BudgetRulePolicy


@dataclass
class _StubWallet:
    """Minimal BudgetManager stand-in for tests."""

    fraction: float = 1.0
    _lambda: float = 1.0
    _state: dict[str, float] = field(default_factory=dict)

    def get_lambda(self) -> float:
        return self._lambda

    def affordable(self, cost_usdc: float) -> bool:  # noqa: ARG002
        return True

    def record_spend(self, cost_usdc: float) -> None:  # noqa: ARG002
        pass

    def snapshot(self) -> dict[str, float]:
        return {"remaining_fraction": self.fraction, "lambda_t": self._lambda}


def test_implements_policy_protocol() -> None:
    p = BudgetRulePolicy(wallet=_StubWallet())
    assert isinstance(p, Policy)


def test_high_remaining_picks_premium() -> None:
    p = BudgetRulePolicy(wallet=_StubWallet(fraction=0.8))
    affordable = (ProviderId.P_CHEAP, ProviderId.P_MID, ProviderId.P_PREMIUM)
    assert p.select(context=(0.0,), affordable_arms=affordable) == ProviderId.P_PREMIUM


def test_mid_remaining_picks_mid() -> None:
    p = BudgetRulePolicy(wallet=_StubWallet(fraction=0.35))
    affordable = (ProviderId.P_CHEAP, ProviderId.P_MID, ProviderId.P_PREMIUM)
    assert p.select(context=(0.0,), affordable_arms=affordable) == ProviderId.P_MID


def test_low_remaining_picks_cheap() -> None:
    p = BudgetRulePolicy(wallet=_StubWallet(fraction=0.05))
    affordable = (ProviderId.P_CHEAP, ProviderId.P_MID, ProviderId.P_PREMIUM)
    assert p.select(context=(0.0,), affordable_arms=affordable) == ProviderId.P_CHEAP


def test_threshold_boundary_at_high_inclusive_above() -> None:
    """Above threshold → premium; exactly at threshold → mid (>, not >=)."""
    above = BudgetRulePolicy(wallet=_StubWallet(fraction=0.51))
    at_or_below = BudgetRulePolicy(wallet=_StubWallet(fraction=0.50))
    affordable = (ProviderId.P_CHEAP, ProviderId.P_MID, ProviderId.P_PREMIUM)
    assert above.select(context=(0.0,), affordable_arms=affordable) == ProviderId.P_PREMIUM
    assert at_or_below.select(context=(0.0,), affordable_arms=affordable) == ProviderId.P_MID


def test_target_unaffordable_falls_back_with_prices() -> None:
    # High remaining → wants premium; but premium not affordable.
    # With prices supplied, fallback to most expensive affordable.
    prices = {
        ProviderId.P_CHEAP: 0.0005,
        ProviderId.P_MID: 0.002,
        ProviderId.P_PREMIUM: 0.02,
    }
    p = BudgetRulePolicy(wallet=_StubWallet(fraction=0.8), provider_prices=prices)
    affordable = (ProviderId.P_CHEAP, ProviderId.P_MID)  # premium missing
    assert p.select(context=(0.0,), affordable_arms=affordable) == ProviderId.P_MID


def test_target_unaffordable_falls_back_without_prices() -> None:
    p = BudgetRulePolicy(wallet=_StubWallet(fraction=0.8))
    affordable = (ProviderId.P_CHEAP,)  # only cheap; premium not there
    assert p.select(context=(0.0,), affordable_arms=affordable) == ProviderId.P_CHEAP


def test_invalid_thresholds_rejected() -> None:
    with pytest.raises(ValueError):
        BudgetRulePolicy(wallet=_StubWallet(), low_threshold=0.5, high_threshold=0.3)
    with pytest.raises(ValueError):
        BudgetRulePolicy(wallet=_StubWallet(), low_threshold=-0.1)
    with pytest.raises(ValueError):
        BudgetRulePolicy(wallet=_StubWallet(), high_threshold=1.5)


def test_empty_affordable_set_rejected() -> None:
    p = BudgetRulePolicy(wallet=_StubWallet())
    with pytest.raises(ValueError):
        p.select(context=(0.0,), affordable_arms=())


def test_update_is_noop() -> None:
    p = BudgetRulePolicy(wallet=_StubWallet())
    assert p.update(context=(0.0,), arm=ProviderId.P_MID, utility=0.5, observed_cost=0.002) is None
