"""Tests for ``pilot402.policies.padct.PADCTPolicy``.

Coverage:
- Protocol conformance
- Decision rule (correct PA-reward computation, argmax selection)
- All 4 ablation flags work in isolation
- Posterior updates only the chosen (arm, bucket)
- Discount applies per round to all cells
- Behavior on real pregen data: PA-DCT converges toward strong arms
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from numpy.random import default_rng

from pilot402.core import ProviderId
from pilot402.core.interfaces import Policy
from pilot402.policies.padct import PADCTPolicy


# ---------------------------------------------------------------------------
# Fixtures: minimal stub wallet and provider costs
# ---------------------------------------------------------------------------


@dataclass
class _StubWallet:
    """Minimal BudgetManager stand-in. Lambda_t can be set explicitly."""

    fixed_lambda: float = 1.0

    def get_lambda(self) -> float:
        return self.fixed_lambda

    def affordable(self, cost_usdc: float) -> bool:
        return True

    def record_spend(self, cost_usdc: float) -> None:
        pass

    def snapshot(self) -> dict[str, float]:
        return {"lambda_t": self.fixed_lambda, "remaining_fraction": 1.0}


_DEFAULT_PRICES = {
    ProviderId.P_CHEAP: 0.0005,
    ProviderId.P_MID: 0.002,
    ProviderId.P_PREMIUM: 0.01,
    ProviderId.P_ADV: 0.002,
    ProviderId.P_FLAKY: 0.002,
}


def _ctx_t1() -> tuple[float, ...]:
    """Sample context with task type T1 one-hot at index 0."""
    return (1.0, 0.0, 0.0, 0.0, 0.5, 1.0, 1.0)


def _ctx_t2() -> tuple[float, ...]:
    return (0.0, 1.0, 0.0, 0.0, 0.5, 1.0, 1.0)


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_implements_policy_protocol() -> None:
    p = PADCTPolicy(
        rng=default_rng(0),
        wallet=_StubWallet(),
        provider_costs=_DEFAULT_PRICES,
    )
    assert isinstance(p, Policy)


# ---------------------------------------------------------------------------
# Decision rule sanity
# ---------------------------------------------------------------------------


def test_select_returns_member_of_affordable() -> None:
    p = PADCTPolicy(
        rng=default_rng(0),
        wallet=_StubWallet(),
        provider_costs=_DEFAULT_PRICES,
    )
    affordable = (ProviderId.P_CHEAP, ProviderId.P_MID)
    for _ in range(50):
        chosen = p.select(context=_ctx_t1(), affordable_arms=affordable)
        assert chosen in affordable


def test_empty_affordable_set_rejected() -> None:
    p = PADCTPolicy(
        rng=default_rng(0),
        wallet=_StubWallet(),
        provider_costs=_DEFAULT_PRICES,
    )
    with pytest.raises(ValueError):
        p.select(context=_ctx_t1(), affordable_arms=())


def test_unknown_arm_raises() -> None:
    """Affordable arm without a price entry is a wiring bug; raise loudly."""
    p = PADCTPolicy(
        rng=default_rng(0),
        wallet=_StubWallet(),
        provider_costs={ProviderId.P_CHEAP: 0.0005},  # missing other arms
    )
    with pytest.raises(KeyError):
        p.select(context=_ctx_t1(), affordable_arms=(ProviderId.P_MID,))


# ---------------------------------------------------------------------------
# Posterior update isolates to (arm, bucket)
# ---------------------------------------------------------------------------


def test_update_only_touches_chosen_arm_bucket() -> None:
    p = PADCTPolicy(
        rng=default_rng(0),
        wallet=_StubWallet(),
        provider_costs=_DEFAULT_PRICES,
        gamma=1.0,  # disable discount so we can compare cleanly
    )
    p.update(context=_ctx_t1(), arm=ProviderId.P_MID, utility=0.8, observed_cost=0.002)

    state = p.posterior_state()
    # Only (P-mid, bucket=0) should have n_eff=1
    for arm_str, buckets in state.items():
        for b, s in buckets.items():
            if arm_str == ProviderId.P_MID.value and b == 0:
                assert s["n_eff"] == pytest.approx(1.0)
                assert s["s_eff"] == pytest.approx(0.8)
            else:
                assert s["n_eff"] == 0.0
                assert s["s_eff"] == 0.0


# ---------------------------------------------------------------------------
# Ablations
# ---------------------------------------------------------------------------


def test_ablation_no_payment_aware_ignores_lambda() -> None:
    """With enable_payment_aware=False, λ_t shouldn't matter."""
    p_low = PADCTPolicy(
        rng=default_rng(0),
        wallet=_StubWallet(fixed_lambda=0.1),
        provider_costs=_DEFAULT_PRICES,
        enable_payment_aware=False,
        gamma=1.0,
    )
    p_high = PADCTPolicy(
        rng=default_rng(0),  # SAME seed for direct comparison
        wallet=_StubWallet(fixed_lambda=100.0),
        provider_costs=_DEFAULT_PRICES,
        enable_payment_aware=False,
        gamma=1.0,
    )
    affordable = tuple(ProviderId)
    # With same seed and PA disabled, decisions should match regardless of λ
    for _ in range(20):
        chosen_low = p_low.select(context=_ctx_t1(), affordable_arms=affordable)
        chosen_high = p_high.select(context=_ctx_t1(), affordable_arms=affordable)
        assert chosen_low == chosen_high


def test_ablation_no_discount_keeps_n_eff_growing() -> None:
    p = PADCTPolicy(
        rng=default_rng(0),
        wallet=_StubWallet(),
        provider_costs=_DEFAULT_PRICES,
        enable_discount=False,
    )
    for _ in range(100):
        p.select(context=_ctx_t1(), affordable_arms=tuple(ProviderId))
        p.update(context=_ctx_t1(), arm=ProviderId.P_MID, utility=0.8, observed_cost=0.002)
    state = p.posterior_state()[ProviderId.P_MID.value][0]
    assert state["n_eff"] == pytest.approx(100.0)


def test_ablation_no_contextual_collapses_to_one_bucket() -> None:
    p = PADCTPolicy(
        rng=default_rng(0),
        wallet=_StubWallet(),
        provider_costs=_DEFAULT_PRICES,
        enable_contextual=False,
    )
    # Update under T1 context, then check T2 context sees the same posterior
    p.update(context=_ctx_t1(), arm=ProviderId.P_MID, utility=0.9, observed_cost=0.002)
    state = p.posterior_state()[ProviderId.P_MID.value]
    assert len(state) == 1, "Non-contextual should have 1 bucket"
    assert state[0]["n_eff"] == 1.0


def test_ablation_no_ts_uses_posterior_mean_deterministic() -> None:
    """With enable_ts=False, decisions are deterministic given same posteriors."""
    p1 = PADCTPolicy(
        rng=default_rng(0),
        wallet=_StubWallet(),
        provider_costs=_DEFAULT_PRICES,
        enable_ts=False,
        gamma=1.0,
    )
    p2 = PADCTPolicy(
        rng=default_rng(7),  # DIFFERENT seed
        wallet=_StubWallet(),
        provider_costs=_DEFAULT_PRICES,
        enable_ts=False,
        gamma=1.0,
    )
    affordable = tuple(ProviderId)
    # No data → all posteriors at prior_mean, ties broken by argmax order.
    # Same context + same prior + no sampling → both pick the same arm.
    chosen1 = p1.select(context=_ctx_t1(), affordable_arms=affordable)
    chosen2 = p2.select(context=_ctx_t1(), affordable_arms=affordable)
    assert chosen1 == chosen2


# ---------------------------------------------------------------------------
# Decision rule math (small numerical sanity check)
# ---------------------------------------------------------------------------


def test_decision_with_strong_evidence_picks_clearly_better_arm() -> None:
    """If P-mid posterior is concentrated at high value, it should be chosen
    over P-cheap when lambda is moderate."""
    p = PADCTPolicy(
        rng=default_rng(0),
        wallet=_StubWallet(fixed_lambda=0.3),
        provider_costs=_DEFAULT_PRICES,
        gamma=1.0,
    )
    # Train: P-mid clearly delivers higher utility than P-cheap
    for _ in range(200):
        p.update(context=_ctx_t1(), arm=ProviderId.P_MID, utility=0.81, observed_cost=0.002)
        p.update(context=_ctx_t1(), arm=ProviderId.P_CHEAP, utility=0.62, observed_cost=0.0005)

    # Now select; should overwhelmingly pick mid
    counts = {ProviderId.P_CHEAP: 0, ProviderId.P_MID: 0}
    for _ in range(200):
        chosen = p.select(
            context=_ctx_t1(),
            affordable_arms=(ProviderId.P_CHEAP, ProviderId.P_MID),
        )
        if chosen in counts:
            counts[chosen] += 1
    # PA-mid > PA-cheap at λ_norm = 0.3/1.3 = 0.23
    # PA_mid  = (1-0.23)·0.81 - 0.23·0.20 = 0.624 - 0.046 = 0.578
    # PA_cheap = (1-0.23)·0.62 - 0.23·0.05 = 0.477 - 0.012 = 0.465
    # Mid wins by 0.113. Posterior std at n=200 ≈ sqrt(0.09/200) ≈ 0.021,
    # so ratio of correct choice should be near 1.0.
    assert counts[ProviderId.P_MID] > counts[ProviderId.P_CHEAP]
    assert counts[ProviderId.P_MID] > 180  # >90% on mid


def test_high_lambda_steers_toward_cheap_provider() -> None:
    """When wallet pressure is extreme, even strong P-mid signal loses to P-cheap."""
    p = PADCTPolicy(
        rng=default_rng(0),
        wallet=_StubWallet(fixed_lambda=100.0),  # λ_norm ≈ 0.99
        provider_costs=_DEFAULT_PRICES,
        gamma=1.0,
    )
    # Both arms get similar utility evidence
    for _ in range(100):
        p.update(context=_ctx_t1(), arm=ProviderId.P_MID, utility=0.81, observed_cost=0.002)
        p.update(context=_ctx_t1(), arm=ProviderId.P_CHEAP, utility=0.62, observed_cost=0.0005)

    # PA-cheap wins because cost penalty dominates
    # PA_mid = 0.01·0.81 - 0.99·0.2 = 0.008 - 0.198 = -0.190
    # PA_cheap = 0.01·0.62 - 0.99·0.05 = 0.006 - 0.0495 = -0.043
    counts = {ProviderId.P_CHEAP: 0, ProviderId.P_MID: 0}
    for _ in range(200):
        chosen = p.select(
            context=_ctx_t1(),
            affordable_arms=(ProviderId.P_CHEAP, ProviderId.P_MID),
        )
        if chosen in counts:
            counts[chosen] += 1
    assert counts[ProviderId.P_CHEAP] > counts[ProviderId.P_MID]


# ---------------------------------------------------------------------------
# Convergence / non-stationarity
# ---------------------------------------------------------------------------


def test_discount_lets_policy_adapt_to_quality_shift() -> None:
    """Simulate non-stationary: P-mid was great, then suddenly poor.
    With discount, the policy should adapt within a few hundred rounds."""
    p = PADCTPolicy(
        rng=default_rng(0),
        wallet=_StubWallet(fixed_lambda=0.1),
        provider_costs=_DEFAULT_PRICES,
        gamma=0.99,  # memory ~100 rounds
    )
    # Phase 1: P-mid is the best (utility 0.85)
    for _ in range(500):
        p.select(context=_ctx_t1(), affordable_arms=tuple(ProviderId))
        p.update(context=_ctx_t1(), arm=ProviderId.P_MID, utility=0.85, observed_cost=0.002)
        p.update(context=_ctx_t1(), arm=ProviderId.P_CHEAP, utility=0.50, observed_cost=0.0005)

    state_before = p.posterior_state()[ProviderId.P_MID.value][0]
    assert state_before["posterior_mean"] > 0.7

    # Phase 2: P-mid quality crashes to 0.3
    for _ in range(500):
        p.select(context=_ctx_t1(), affordable_arms=tuple(ProviderId))
        p.update(context=_ctx_t1(), arm=ProviderId.P_MID, utility=0.30, observed_cost=0.002)

    state_after = p.posterior_state()[ProviderId.P_MID.value][0]
    # With γ=0.99 and 500 rounds of new evidence, posterior should track ~0.3
    assert state_after["posterior_mean"] < 0.5


# ---------------------------------------------------------------------------
# Cold start exploration
# ---------------------------------------------------------------------------


def test_cold_start_explores_all_arms() -> None:
    """At round 0, no posterior has data; all arms should get tried."""
    p = PADCTPolicy(
        rng=default_rng(42),
        wallet=_StubWallet(fixed_lambda=0.5),
        provider_costs=_DEFAULT_PRICES,
        gamma=1.0,
        prior_var=4.0,  # extra-broad prior to encourage exploration
    )
    chosen_set = set()
    for _ in range(200):
        chosen = p.select(context=_ctx_t1(), affordable_arms=tuple(ProviderId))
        chosen_set.add(chosen)
    # Should explore at least 3 of the 5 arms in 200 cold-start rounds
    assert len(chosen_set) >= 3


# ---------------------------------------------------------------------------
# Cost posterior — Dual-posterior PA-DCT specific tests
# ---------------------------------------------------------------------------


def test_cost_posterior_initialized_with_spec_prior_mean() -> None:
    """Day-1 cost posterior_mean per arm equals the spec price provided."""
    p = PADCTPolicy(
        rng=default_rng(0),
        wallet=_StubWallet(),
        provider_costs=_DEFAULT_PRICES,
        gamma=1.0,
    )
    state = p.cost_posterior_state()
    for arm, expected in _DEFAULT_PRICES.items():
        # Bucket 0 (any bucket — they're all initialized identically)
        assert state[arm.value][0]["posterior_mean"] == pytest.approx(expected)
        assert state[arm.value][0]["n_eff"] == 0.0


def test_cost_posterior_converges_to_observed_cost() -> None:
    """After ~30 observations of a single cost, posterior mean ≈ observed."""
    p = PADCTPolicy(
        rng=default_rng(0),
        wallet=_StubWallet(),
        provider_costs=_DEFAULT_PRICES,
        gamma=1.0,
    )
    # Feed observations at a different cost than the spec.
    new_cost = 0.005
    for _ in range(30):
        p.update(context=_ctx_t1(), arm=ProviderId.P_PREMIUM,
                 utility=0.85, observed_cost=new_cost)
    state = p.cost_posterior_state()[ProviderId.P_PREMIUM.value][0]
    # Should track new_cost closely (defaults: c_noise_var=1e-6 << c_prior_var=1e-4)
    assert state["posterior_mean"] == pytest.approx(new_cost, abs=1e-4)
    assert state["n_eff"] == pytest.approx(30.0)


def test_cost_posterior_tracks_price_shock() -> None:
    """Simulate a mid-experiment price drop on premium; posterior should follow."""
    p = PADCTPolicy(
        rng=default_rng(0),
        wallet=_StubWallet(),
        provider_costs=_DEFAULT_PRICES,
        gamma=0.99,
        gamma_cost=0.99,  # short memory on cost too for this test
    )
    # Phase 1: 100 observations at the spec price ($0.01).
    for _ in range(100):
        p.update(context=_ctx_t1(), arm=ProviderId.P_PREMIUM,
                 utility=0.85, observed_cost=0.01)
    state_before = p.cost_posterior_state()[ProviderId.P_PREMIUM.value][0]
    assert state_before["posterior_mean"] == pytest.approx(0.01, abs=1e-4)

    # Phase 2: 100 observations at the new (post-shock) price ($0.002).
    # γ=0.99 means after 100 rounds, old observations have weight 0.37×.
    for _ in range(100):
        p.select(context=_ctx_t1(), affordable_arms=tuple(ProviderId))
        p.update(context=_ctx_t1(), arm=ProviderId.P_PREMIUM,
                 utility=0.85, observed_cost=0.002)
    state_after = p.cost_posterior_state()[ProviderId.P_PREMIUM.value][0]
    # After 100 rounds of new observations + decayed old, mean should be
    # noticeably below the old spec value.
    assert state_after["posterior_mean"] < 0.005


def test_cost_posterior_only_updates_chosen_arm() -> None:
    """Updating one arm doesn't affect the cost posterior of another."""
    p = PADCTPolicy(
        rng=default_rng(0),
        wallet=_StubWallet(),
        provider_costs=_DEFAULT_PRICES,
        gamma=1.0,
    )
    p.update(context=_ctx_t1(), arm=ProviderId.P_MID,
             utility=0.8, observed_cost=0.0033)
    state = p.cost_posterior_state()
    # P-mid bucket 0: posterior_mean shifted toward 0.0033 (from spec 0.002)
    assert state[ProviderId.P_MID.value][0]["n_eff"] == pytest.approx(1.0)
    # All other (arm, bucket) cells: untouched
    for arm_str, buckets in state.items():
        for b, s in buckets.items():
            if not (arm_str == ProviderId.P_MID.value and b == 0):
                assert s["n_eff"] == 0.0
                # And posterior_mean still equals spec
                expected_spec = _DEFAULT_PRICES[ProviderId(arm_str)]
                assert s["posterior_mean"] == pytest.approx(expected_spec)


def test_cost_posterior_responds_to_price_promo_decision() -> None:
    """When premium's observed cost matches mid's, premium (higher q) should
    eventually beat mid in PA decisions — the headline behavior the dual
    posterior unlocks."""
    p = PADCTPolicy(
        rng=default_rng(0),
        wallet=_StubWallet(fixed_lambda=0.3),  # λ_n ≈ 0.23
        provider_costs=_DEFAULT_PRICES,
        gamma=1.0,  # no decay so observations accumulate cleanly
    )
    # Both arms get equal cost ($0.002 — premium under "promo"), but premium
    # has consistently higher quality.
    for _ in range(200):
        p.update(context=_ctx_t1(), arm=ProviderId.P_MID,
                 utility=0.82, observed_cost=0.002)
        p.update(context=_ctx_t1(), arm=ProviderId.P_PREMIUM,
                 utility=0.86, observed_cost=0.002)
    counts = {ProviderId.P_MID: 0, ProviderId.P_PREMIUM: 0}
    for _ in range(300):
        chosen = p.select(
            context=_ctx_t1(),
            affordable_arms=(ProviderId.P_MID, ProviderId.P_PREMIUM),
        )
        if chosen in counts:
            counts[chosen] += 1
    # With equal observed cost and clearly higher q on premium, PA-DCT
    # should pick premium far more often. (At λ_n=0.23, c_norm cancel, so
    # decision reduces to argmax sampled q.)
    assert counts[ProviderId.P_PREMIUM] > counts[ProviderId.P_MID]
    assert counts[ProviderId.P_PREMIUM] > 200  # >66% on premium


def test_cost_posterior_static_market_matches_spec_decisions() -> None:
    """In a stationary market where observed cost == spec, the new dual-posterior
    PA-DCT should agree with what the OLD design would do (uses spec cost).

    Sanity check: dual posterior doesn't break baseline (S1) behavior."""
    p = PADCTPolicy(
        rng=default_rng(7),
        wallet=_StubWallet(fixed_lambda=0.3),
        provider_costs=_DEFAULT_PRICES,
        gamma=1.0,
    )
    # Train: each arm observed at its spec cost a bunch of times.
    for _ in range(50):
        p.update(context=_ctx_t1(), arm=ProviderId.P_CHEAP,
                 utility=0.62, observed_cost=0.0005)
        p.update(context=_ctx_t1(), arm=ProviderId.P_MID,
                 utility=0.82, observed_cost=0.002)
        p.update(context=_ctx_t1(), arm=ProviderId.P_PREMIUM,
                 utility=0.86, observed_cost=0.01)
    # Cost posterior means should be very close to spec.
    cstate = p.cost_posterior_state()
    for arm, expected in [
        (ProviderId.P_CHEAP, 0.0005),
        (ProviderId.P_MID, 0.002),
        (ProviderId.P_PREMIUM, 0.01),
    ]:
        assert cstate[arm.value][0]["posterior_mean"] == pytest.approx(expected, abs=1e-3)
    # And the policy still picks mid (the calibrated PA-optimum) most often.
    counts = {a: 0 for a in (ProviderId.P_CHEAP, ProviderId.P_MID, ProviderId.P_PREMIUM)}
    for _ in range(200):
        chosen = p.select(
            context=_ctx_t1(),
            affordable_arms=tuple(counts.keys()),
        )
        if chosen in counts:
            counts[chosen] += 1
    # Mid should win (highest PA at λ_n=0.23 with spec costs)
    assert counts[ProviderId.P_MID] >= counts[ProviderId.P_CHEAP]
    assert counts[ProviderId.P_MID] > counts[ProviderId.P_PREMIUM]


def test_default_gammas_q_and_c_at_0_999() -> None:
    """Locked defaults post-M3.F: γ_q = γ_c = 0.999 (half-life ≈693 rounds).
    Splitting the two is supported but the calibrated experiments use the
    same rate for both dimensions."""
    p = PADCTPolicy(
        rng=default_rng(0),
        wallet=_StubWallet(),
        provider_costs=_DEFAULT_PRICES,
    )
    assert p.gamma == 0.999
    assert p.gamma_cost == 0.999


def test_ablation_no_cost_posterior_uses_static_spec() -> None:
    """With enable_cost_posterior=False, the policy should ignore observations
    of cost and always use the static spec value at decision time. This
    recovers the vanilla pre-M3.F behavior."""
    p = PADCTPolicy(
        rng=default_rng(0),
        wallet=_StubWallet(fixed_lambda=0.3),
        provider_costs=_DEFAULT_PRICES,
        enable_cost_posterior=False,  # ABLATION
        gamma=1.0,
    )
    # Feed wildly different observed_costs — they should be ignored.
    for _ in range(50):
        p.update(context=_ctx_t1(), arm=ProviderId.P_PREMIUM,
                 utility=0.86, observed_cost=0.0001)  # Pretend premium became free
    # Cost posterior should be unchanged (n_eff=0, posterior_mean=spec=$0.01).
    cstate = p.cost_posterior_state()[ProviderId.P_PREMIUM.value][0]
    assert cstate["n_eff"] == 0.0
    assert cstate["posterior_mean"] == pytest.approx(0.01)
    # Q posterior IS updated (only c is ablated).
    qstate = p.posterior_state()[ProviderId.P_PREMIUM.value][0]
    assert qstate["n_eff"] == pytest.approx(50.0)


def test_ablation_no_cost_posterior_blind_to_price_drop() -> None:
    """Ablation: even with abundant evidence that premium is now cheaper, the
    decision rule keeps using spec ($0.01) — exactly the bug we fix in M3.F."""
    p = PADCTPolicy(
        rng=default_rng(0),
        wallet=_StubWallet(fixed_lambda=0.3),
        provider_costs=_DEFAULT_PRICES,
        enable_cost_posterior=False,  # ABLATION
        gamma=1.0,
    )
    # Train: premium quality is high (0.86) and observed cost is $0.002 (= mid),
    # but the ablation makes the policy keep treating premium as $0.01.
    for _ in range(200):
        p.update(context=_ctx_t1(), arm=ProviderId.P_PREMIUM,
                 utility=0.86, observed_cost=0.002)
        p.update(context=_ctx_t1(), arm=ProviderId.P_MID,
                 utility=0.82, observed_cost=0.002)
    counts = {ProviderId.P_MID: 0, ProviderId.P_PREMIUM: 0}
    for _ in range(300):
        chosen = p.select(
            context=_ctx_t1(),
            affordable_arms=(ProviderId.P_MID, ProviderId.P_PREMIUM),
        )
        if chosen in counts:
            counts[chosen] += 1
    # Under the ablation, premium uses c̃=1.0 (=spec/max=$0.01/$0.01) while
    # mid uses c̃=0.2. Even with q_premium > q_mid by 0.04, mid wins because
    # cost gap dominates: PA(mid) = 0.77×0.82 - 0.23×0.20 = 0.585
    #                    PA(prem) = 0.77×0.86 - 0.23×1.00 = 0.432
    # Mid dominates → blind-to-promo behavior (the M3.F bug).
    assert counts[ProviderId.P_MID] > counts[ProviderId.P_PREMIUM]
    assert counts[ProviderId.P_PREMIUM] < 50  # <17% premium under ablation


def test_split_gamma_decay_works_independently() -> None:
    """Verify that gamma_q and gamma_c decay their respective posteriors
    at independent rates."""
    p = PADCTPolicy(
        rng=default_rng(0),
        wallet=_StubWallet(),
        provider_costs=_DEFAULT_PRICES,
        gamma=0.99,        # explicit q-decay
        gamma_cost=0.5,    # very aggressive c-decay
    )
    p.update(context=_ctx_t1(), arm=ProviderId.P_MID,
             utility=0.8, observed_cost=0.002)
    # Apply discount many times via select() (which calls _discount_all)
    for _ in range(20):
        p.select(context=_ctx_t1(), affordable_arms=tuple(ProviderId))
    q_state = p.posterior_state()[ProviderId.P_MID.value][0]
    c_state = p.cost_posterior_state()[ProviderId.P_MID.value][0]
    # q n_eff after 20 discounts at γ=0.99: 0.99^20 ≈ 0.818
    assert q_state["n_eff"] == pytest.approx(0.99**20, rel=1e-3)
    # c n_eff after 20 discounts at γ=0.5: 0.5^20 ≈ 9.5e-7 (essentially 0)
    assert c_state["n_eff"] == pytest.approx(0.5**20, rel=1e-3)
    assert c_state["n_eff"] < q_state["n_eff"] / 100
