# M3.F: Dual-Posterior PA-DCT — Design Rationale & Math

**Date locked**: 2026-05-05
**Status**: Implementation complete; 30-seed sweep validated; ready for paper write-up

---

## 1. The bug we found

### Symptom

After M3.E (scenario implementation), the 30-seed sweep showed:

| Scenario | PA-DCT PA | AlwaysMid PA | Δ |
|---|---|---|---|
| S1 (stationary) | 5509 ± 56 | 5831 ± 29 | -322 (PA-DCT pays exploration cost — expected) |
| S2 (mid outage) | 5129 ± 79 | 5069 ± 37 | **+60** (PA-DCT reverses Mid via failure detection ✓) |
| S3 (premium ×0.4 at round 3000) | 5584 ± 57 | 5831 ± 29 | -247 (no adaptation visible) |

We then ran multiple S3 design variants:
- Path AB: tier compression 1:3:5 → PA-DCT premium share **didn't move** (4% pre vs 4% post)
- Path Z: 1:2:5 → same
- Premium Promo (premium=mid throughout): same — premium share stuck at 4%

The pattern: **PA-DCT as designed in M3.D does not respond to cost-only signals at all**.

### Root cause

Reading `pilot402/policies/padct.py` (pre-M3.F):

```python
# In select():
for arm in affordable_arms:
    sampled_u = self._value_for_arm(arm, bucket)  # samples from Q-posterior
    cost = self.provider_costs.get(arm)            # ← READS FROM STATIC DICT
    c_norm = min(cost / self.max_provider_cost, 1.0)
    pa = (1.0 - lambda_norm) * sampled_u - lambda_norm * c_norm
```

`self.provider_costs` is constructed once at policy init and never updated. When a scenario changes the effective price (via `scenario.effective_price`), the wallet sees the new price and the pregen record's `cost_usdc` reflects the new price — **but PA-DCT still uses the old spec value at decision time**.

### Why this is a real bug, not a feature

The paper's title is "Payment-Aware DCTS". A payment-aware algorithm that ignores price changes contradicts its name. The user's question identified the issue: in real markets prices change (surge pricing, promos, tier-wide repricing). Hardcoding the spec violates the algorithm's premise.

---

## 2. Design choice: factored q + c posteriors (vs joint PA posterior)

### Two architectures considered

**Architecture A — Posterior over PA-reward directly**
- Update: each round observe `PA = (1-λ)q − λc̃`
- Sample: TS-sample PA values per arm, pick max
- **Problem**: λ is dynamic per round. Each round's PA observation is at a different λ, so they can't be combined cleanly into a single posterior.

**Architecture B — Factored: separate posteriors over q and c** (CHOSEN)
- Update: observe q and c separately each round; update each posterior
- Sample: TS-sample q̂ and ĉ independently per arm
- Combine at decision time using current λ_norm: `PA = (1-λ_n)q̂ − λ_n c̃`
- Cleanly separates intrinsic provider properties (q, c) from the budget-pressure shaping (λ)

Architecture B is correct because:
1. q and c have independent observation noise structures
2. Discount γ can be applied independently if their non-stationary timescales differ (we keep both at γ=0.999 for now, but the design allows γ_q ≠ γ_c)
3. Theoretically grounded — Bayesian inference over the underlying parameters, not the shaped reward

### Hyperparameters

| Param | q-posterior | c-posterior | Rationale |
|---|---|---|---|
| `prior_mean` | 0.5 | spec.base_price_usdc | Prior centered at spec; first observations dominate |
| `prior_var` | 1.0 | 1e-4 | c-prior tighter (we trust spec roughly) but order-of-magnitude flexibility |
| `noise_var` | 0.09 | 1e-6 | c noise much smaller because in our replay setup cost is deterministic given (arm, scenario, round); real-world deployments would set this larger for genuine cost stochasticity |
| `γ` | 0.999 | 0.999 | Half-life ≈693 rounds. Same for both — empirically S1 stays calibrated, S2/S3 adapt within ~1500 rounds |

### Why c_noise_var=1e-6 specifically

In our replay, observed_cost == record.cost_usdc (after scenario transform). It's deterministic. So setting σ² very small is correct — observations should dominate the prior almost immediately. With σ²=1e-6 and one observation:
- precision_post = 1/1e-4 + 1/1e-6 = 10⁴ + 10⁶ = 1.01×10⁶
- σ²_post = 9.9×10⁻⁷
- After 1 observation, posterior std ≈ $0.001 — already collapsed near observation.

If we set c_noise_var larger (e.g., 0.01), the posterior would be artificially wide → TS sampling produces noisy ĉ → spurious decisions when costs are actually stable. Empirically tested in initial debugging: PA=5070 (8% degradation) with σ²=0.01 vs PA=5512 (matches vanilla) with σ²=1e-6.

---

## 3. Implementation

### Code structure

```python
@dataclass
class PADCTPolicy:
    rng: Generator
    wallet: BudgetManager
    provider_costs: dict[ProviderId, float]   # NOW: prior mean for c-posterior
    max_provider_cost: float = 0.01
    prior_mean: float = 0.5                   # q
    prior_var: float = 1.0                    # q
    noise_var: float = 0.09                   # q
    c_prior_var: float = 1e-4                 # NEW
    c_noise_var: float = 1e-6                 # NEW
    gamma: float = 0.999                      # for q
    gamma_cost: float = 0.999                 # NEW (independent control if desired)
    enable_payment_aware: bool = True
    enable_discount: bool = True
    enable_contextual: bool = True
    enable_ts: bool = True
    _q_posteriors: dict[ProviderId, list[GaussianPosterior]]
    _c_posteriors: dict[ProviderId, list[GaussianPosterior]]   # NEW
```

### Decision rule per round

```python
def select(self, context, affordable_arms):
    # 1. Discount BOTH q and c posteriors
    self._discount_all()  # iterates both _q_posteriors and _c_posteriors

    bucket = self._bucket_for(context)
    lambda_norm = self._lambda_norm()

    best_arm, best_score = None, -inf
    for arm in affordable_arms:
        # 2. Sample BOTH q and c independently
        q_sample = self._q_value_for_arm(arm, bucket)        # TS draw or post mean
        c_sample_raw = self._c_value_for_arm(arm, bucket)    # in $/call units
        c_norm = max(0, min(c_sample_raw / max_provider_cost, 1.0))

        pa = (1 - lambda_norm) * q_sample - lambda_norm * c_norm
        if pa > best_score:
            best_score, best_arm = pa, arm
    return best_arm
```

### Update rule

```python
def update(self, context, arm, utility, observed_cost):
    bucket = self._bucket_for(context)
    self._q_posteriors[arm][bucket].update(utility)
    self._c_posteriors[arm][bucket].update(observed_cost)   # NEW
```

### Policy Protocol change

`pilot402/core/interfaces.py`:

```python
def update(
    self,
    context: ContextVector,
    arm: ProviderId,
    utility: float,
    observed_cost: float,   # NEW required param
) -> None:
    ...
```

All 5 implementations (PADCTPolicy, RandomPolicy, FixedPolicy, BudgetRulePolicy) updated. Non-learning policies just ignore `observed_cost`.

`pilot402/runtime/loop.py` change:

```python
# Before:
policy.update(context, chosen_arm, reward.utility)

# After:
policy.update(context, chosen_arm, reward.utility, record.cost_usdc)
# record was already scenario-transformed earlier in the loop, so cost_usdc
# reflects the actual market price, not the spec
```

---

## 4. Math walkthrough — round 2000 of S3 (verified empirically)

To verify the design is sound, walk through one round on real data (seed 0, S3).

### Setup
- S3: `PremiumDropScenario(shock_round=1000, price_multiplier=0.2)`
- Pre-shock 0-999: cheap=$0.0005, mid=$0.002, premium=$0.01
- Post-shock 1000+: premium=$0.002 (= mid price)
- Budget=$50, target_burn_rate=1e-4 (target spend $0.005/round)

### Wallet state at round 2000 (verified from log)

```
spent  = $3.79                                  (empirical from log)
actual_burn_rate = ($3.79 / $50) / 2000 = 3.79e-5
target_burn_rate = 1e-4
burn_excess = (3.79e-5 − 1e-4) / 1e-4 = −0.621
λ_t = exp(α·burn_excess) = exp(2 × −0.621) = exp(−1.242) ≈ 0.289
λ_norm = λ_t / (1 + λ_t) = 0.289 / 1.289 ≈ 0.224
```

Log records `λ_t = 0.2891` at round 1999 ✓ matches.

### Posterior states for T3b at round 2000

T3b is 25% of workload → 506 T3b rounds in [0, 2000].

Empirical pick counts on T3b by round 2000 (from log):
- P-mid: 223  /  P-premium: 204  /  P-adv: 54  /  P-cheap: 22  /  P-flaky: 3
- Premium pre-shock: 24, post-shock: 180

#### C-posterior of premium on T3b

Effective n with γ=0.999 decay:
- 24 pre-shock obs at $0.01, average age ~1500 → weight γ^1500 ≈ 0.223 each → 5.4
- 180 post-shock obs at $0.002, average age ~500 → weight γ^500 ≈ 0.607 each → 109.3
- **n_eff_total ≈ 114.6**

s_eff = 5.4 × $0.01 + 109.3 × $0.002 = $0.0540 + $0.2186 = **$0.2726**

Apply Normal-Normal posterior formula with prior μ₀=$0.01, σ₀²=1e-4, σ²=1e-6:

```
precision_post = 1/σ₀² + n_eff/σ² = 10⁴ + 114.6/1e-6 = 1.146×10⁸
σ²_post       = 1 / 1.146e8 = 8.7e-9
σ_post        ≈ $9.3×10⁻⁵  (very tight)

μ_post = σ²_post × (μ₀/σ₀² + s_eff/σ²)
       = 8.7e-9 × (100 + 272600)
       ≈ $0.00237
```

**C-posterior_premium_T3b:** mean ≈ **$0.00237**, std ≈ $0.0001

Already 81% of the way from prior $0.01 to true $0.002 — fast adaptation due to positive feedback (each new pick provides another observation).

#### Q-posterior of premium on T3b

Same n_eff ≈ 114.6 (q and c update together).

```
precision_post_q = 1/1.0 + 114.6/0.09 = 1274
σ_post_q = √(1/1274) ≈ 0.028

s_eff_q ≈ 114.6 × 0.91 (true mean) = 104.3
μ_post_q = (0.5/1.0 + 104.3/0.09) / 1274 ≈ 0.910
```

**Q-posterior_premium_T3b:** mean ≈ **0.910**, std ≈ 0.028

### One TS sample at round 2000

```
q̂_premium ~ N(0.910, 0.028²)  →  example: 0.93
ĉ_premium ~ N(0.00237, 0.0001²) →  example: 0.00240
q̂_mid    ~ N(0.836, 0.030²)  →  example: 0.84
ĉ_mid    ~ N(0.00200, tight)  →  example: 0.00200

c̃_premium = 0.00240 / 0.01 = 0.240
c̃_mid    = 0.00200 / 0.01 = 0.200

PA(premium) = 0.776 × 0.93 − 0.224 × 0.240 = 0.722 − 0.054 = 0.668
PA(mid)    = 0.776 × 0.84 − 0.224 × 0.200 = 0.652 − 0.045 = 0.607
```

Premium wins by 0.061 PA per round.

### After choosing premium

```
LLM call returns (q=0.91, observed_cost=$0.002)
Q-post[premium][T3b]: n_eff=115.6, μ_post stable at 0.910
C-post[premium][T3b]: n_eff=115.6, μ_post drifts further toward $0.002
```

Each future premium pick on T3b further tightens C-posterior at $0.002, making PA(premium) even more stable above PA(mid). Positive feedback → 60% premium share by round 10000.

---

## 5. Tests added (M3.F.3)

`tests/test_policies_padct.py` — 7 new dual-posterior tests:

| Test | What it verifies |
|---|---|
| `test_cost_posterior_initialized_with_spec_prior_mean` | Day-1 cost prior_mean = spec.base_price |
| `test_cost_posterior_converges_to_observed_cost` | After 30 obs at new cost, posterior tracks new cost (within 1e-4) |
| `test_cost_posterior_tracks_price_shock` | Mid-experiment price drop → posterior follows |
| `test_cost_posterior_only_updates_chosen_arm` | Updating arm A doesn't touch arm B's c-posterior |
| `test_cost_posterior_responds_to_price_promo_decision` | Equal cost + higher q → premium chosen >66% |
| `test_cost_posterior_static_market_matches_spec_decisions` | Stationary calibration unchanged |
| `test_default_gammas_q_and_c_at_0_999` | Locks γ_q = γ_c = 0.999 default |
| `test_split_gamma_decay_works_independently` | γ_q and γ_c can decay at different rates if set |

All 21 PA-DCT tests pass; full suite 279/279 pass.

---

## 6. What we did NOT change

| Locked component | Status |
|---|---|
| Reward formula `(1-λ_n)·utility − λ_n·c̃` | Unchanged ✓ |
| GaussianPosterior class | Unchanged (general enough for both q and c) ✓ |
| Wallet / λ-dynamics | Unchanged ✓ |
| Pregen data | Unchanged ✓ |
| Scenarios (S1, S2, S3) | Unchanged interface; only S3 design parameters tuned |
| All 5 fixed-policy baselines | Only signature change in update() — behavior identical ✓ |
| Oracle (no policy update) | Unchanged ✓ |

---

## 7. Empirical validation summary

See `logs/m3f_results.md` for full 30-seed × 3-scenario × 6-policy results. Headlines:

| Scenario | PA-DCT reverses AlwaysMid? | Component tested |
|---|---|---|
| **S1** (stationary) | No (pays 5.5% exploration cost) | baseline equivalence |
| **S2** (mid outage) | **+79 PA, t=4.90, p<0.001** ✓ | Q-posterior (D + C) |
| **S3** (premium=mid promo at 1000) | **+80 PA, t=7.50, p<0.0001** ✓ | **C-posterior** (the M3.F contribution) |

Premium share trajectory in S3: ~5% pre-shock → **66% post-shock** (visible adaptation curve, the paper's centerpiece figure).

---

## 8. Future work / paper extensions

1. **Real-world deployment with stochastic costs**: increase `c_noise_var` to reflect genuine pricing variability (e.g., per-token billing variations).
2. **Split γ_q ≠ γ_c**: implementation supports it; future scenarios may motivate (e.g., "model quality is months-stable but prices change weekly").
3. **Per-task contextual features**: current bucket is task type; finer features (task difficulty, length) could close more of the gap to Oracle.
4. **Ablation: enable_cost_posterior flag**: not currently a flag (cost posterior is core), but for the paper an ablation could disable it (revert to static dict) and show S3 reverts to no-adaptation behavior.

---

**Sign-off**: M3.F dual-posterior PA-DCT is the version of record for the paper. The bug discovery and fix is itself a paper contribution: vanilla payment-aware bandits are cost-blind despite the name; we propose dual posteriors as the principled fix.
