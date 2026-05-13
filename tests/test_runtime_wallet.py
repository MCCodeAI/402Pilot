"""Tests for ``pilot402.runtime.wallet.Wallet``."""

from __future__ import annotations

import math

import pytest

from pilot402.core.interfaces import BudgetManager
from pilot402.runtime.wallet import Wallet


def test_implements_budget_manager_protocol() -> None:
    w = Wallet(total_usdc=10.0)
    assert isinstance(w, BudgetManager)


def test_initial_state() -> None:
    w = Wallet(total_usdc=10.0, lambda_0=1.5)
    assert w.spent == 0.0
    assert w.remaining == 10.0
    assert w.rounds == 0
    assert w.get_lambda() == 1.5  # No rounds yet → λ_0
    assert w.affordable(5.0)
    assert not w.affordable(11.0)


def test_record_spend_advances_state() -> None:
    w = Wallet(total_usdc=10.0)
    w.record_spend(0.5)
    assert w.spent == 0.5
    assert w.remaining == 9.5
    assert w.rounds == 1


def test_record_spend_zero_is_valid() -> None:
    w = Wallet(total_usdc=10.0)
    w.record_spend(0.0)
    assert w.rounds == 1
    assert w.spent == 0.0


def test_record_spend_negative_rejected() -> None:
    w = Wallet(total_usdc=10.0)
    with pytest.raises(ValueError):
        w.record_spend(-0.5)


def test_lambda_at_target_burn_rate_equals_lambda_0() -> None:
    """If actual burn rate matches target exactly, λ should equal λ_0."""
    w = Wallet(total_usdc=100.0, lambda_0=1.0, alpha=2.0, target_burn_rate=0.01)
    # target_burn_rate = 0.01 means $1 spent per 100 rounds → $0.01 / round.
    # 10 rounds spending $0.01 each = $0.10 total = burn rate 0.001 / round = 0.01 of total / round? wait.
    # actual_rate = (spent / total) / rounds = (0.10 / 100) / 10 = 0.0001
    # That's not 0.01. Let me redo.
    # To match target_burn_rate=0.01, we need actual_rate = (spent / total) / rounds = 0.01.
    # If spent=0.10 and rounds=10, then (0.10/100)/10 = 0.0001 — way below target. λ should be < λ_0.
    # To exactly match: spent/total = 0.01 * rounds, so for rounds=10, spent=10, i.e. burn $1/round.
    for _ in range(10):
        w.record_spend(1.0)  # $1 per round, 10 rounds → spent $10 of $100 budget
    # actual_rate = (10/100)/10 = 0.01 = target_burn_rate → burn_dev=0 → λ=λ_0
    assert w.get_lambda() == pytest.approx(1.0, rel=1e-9)


def test_lambda_rises_when_overspending() -> None:
    """Burn rate above target → λ rises exponentially."""
    w = Wallet(total_usdc=100.0, lambda_0=1.0, alpha=2.0, target_burn_rate=0.01)
    for _ in range(10):
        w.record_spend(2.0)  # $2 per round, double the target
    # actual_rate = (20/100)/10 = 0.02; target = 0.01; burn_dev = 1.0
    # λ = λ_0 * exp(α * burn_dev) = 1.0 * exp(2.0) ≈ 7.389
    assert w.get_lambda() == pytest.approx(math.exp(2.0), rel=1e-9)


def test_lambda_falls_when_underspending() -> None:
    """Burn rate below target → λ shrinks exponentially."""
    w = Wallet(total_usdc=100.0, lambda_0=1.0, alpha=2.0, target_burn_rate=0.01)
    for _ in range(10):
        w.record_spend(0.5)  # $0.50 per round, half the target
    # actual_rate = (5/100)/10 = 0.005; burn_dev = -0.5; λ = exp(-1) ≈ 0.368
    assert w.get_lambda() == pytest.approx(math.exp(-1.0), rel=1e-9)


def test_affordable_blocks_when_overspent() -> None:
    w = Wallet(total_usdc=10.0)
    w.record_spend(9.5)
    assert w.affordable(0.5)  # exactly to the limit
    assert not w.affordable(0.51)  # over the limit


def test_affordable_negative_rejected() -> None:
    w = Wallet(total_usdc=10.0)
    with pytest.raises(ValueError):
        w.affordable(-1.0)


def test_snapshot_includes_all_fields() -> None:
    w = Wallet(total_usdc=10.0, lambda_0=1.0, alpha=2.0, target_burn_rate=0.01)
    w.record_spend(0.10)
    snap = w.snapshot()
    assert snap["total_usdc"] == 10.0
    assert snap["spent_usdc"] == 0.10
    assert snap["remaining_usdc"] == pytest.approx(9.90)
    assert snap["remaining_fraction"] == pytest.approx(0.99)
    assert snap["rounds_elapsed"] == 1.0
    assert snap["lambda_t"] > 0


def test_invalid_construction() -> None:
    with pytest.raises(ValueError):
        Wallet(total_usdc=0.0)
    with pytest.raises(ValueError):
        Wallet(total_usdc=10.0, lambda_0=-0.1)
    # lambda_0 = 0 is degenerate (λ_t stays 0 → λ_norm stays 0 →
    # PA-DCT reduces to pure quality maximization).
    with pytest.raises(ValueError):
        Wallet(total_usdc=10.0, lambda_0=0.0)
    with pytest.raises(ValueError):
        Wallet(total_usdc=10.0, alpha=-1.0)
    with pytest.raises(ValueError):
        Wallet(total_usdc=10.0, target_burn_rate=0.0)
    with pytest.raises(ValueError):
        Wallet(total_usdc=10.0, target_burn_rate=1.5)
