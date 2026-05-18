# Annotated Walkthrough — PA-DCT at Round 2000 of S3 (seed 0)

This document explains **every** symbol, term, and formula that appears in the
PA-DCT decision-time math, using one concrete round (round 2000 of seed 0 in
the S3 sweep) as the running example. Read this whenever you need to refresh
the algorithm's concepts.

---

## 0. Glossary of terms (in the order they appear)

### Scenario / experiment-level

| Term | Meaning |
|---|---|
| **Round** | One full decision cycle: pick a task, choose a provider, pay, observe quality, update. We run 10000 rounds per seed. |
| **Seed** | A fixed random seed (we use seeds 0 through 29). Same seed → bit-identical run. We average across 30 seeds for statistical confidence. |
| **PregenRecord** | A frozen `(task, provider, version) → (quality, cost, latency, failure_flag)` row stored on disk in `data/pregen/*.jsonl`. The runtime replays these records instead of calling LLMs live. |
| **Scenario** | A function that transforms the market mid-experiment. S1 = identity (stationary). S2 = forces P-mid timeouts during rounds 3000-5500. **S3** = drops P-premium price from $0.01 to $0.002 starting at round 1000. |
| **Workload sampler** | Picks a `task_id` uniformly at random each round. Sampler is seeded so all policies see the **same task sequence** for a given seed. |

### Provider / cost terms

| Term | Meaning |
|---|---|
| **Arm** | A "provider" in bandit terminology. We have 5 arms: P-cheap, P-mid, P-premium, P-adv, P-flaky. |
| **Affordable arms** | Subset of arms whose price ≤ remaining wallet balance. Computed each round. |
| **base_price_usdc** | The provider's spec price (e.g., $0.002 for P-mid). Used as the prior mean for the cost posterior. |
| **observed_cost** | The actual $ charged this round, AFTER the scenario transformation. In S3 post-shock, `observed_cost` for premium = $0.002, even though `base_price_usdc` is still $0.01. |
| **max_provider_cost** | A constant ($0.01) used to **normalize** cost so that c̃ ∈ [0, 1]. Without it, c values from $0.0005 to $0.01 would have wildly different scales relative to quality (which is in [0, 1]). |
| **c̃ (c-tilde, "normalized cost")** | `c̃ = clip(observed_cost / max_provider_cost, 0, 1)`. Dimensionless number in [0, 1] used in the PA reward formula. |

### Budget / wallet terms

| Term | Meaning |
|---|---|
| **Wallet** | Tracks `total_usdc` (budget cap, $50) and `_spent` (running total). Every round, after the LLM call, the wallet records the spend. |
| **target_burn_rate** | The fraction of total budget we'd ideally spend per round to last exactly the planned 10000 rounds. We set it to 1e-4 (= 1/10000), so target spend = $50 × 1e-4 = $0.005/round. |
| **actual_burn_rate** | What we're actually spending: `actual_burn_rate = (spent / total_budget) / rounds_elapsed`. Updated each round. |
| **burn_excess** | A normalized deviation: `burn_excess = (actual − target) / target`. Negative = under-spending (cheap), positive = over-spending (cost pressure). |
| **α (alpha)** | A sensitivity hyperparameter, default α=2.0. Controls how aggressively λ responds to burn_excess. Higher α = sharper response. |
| **λ_0 (lambda zero)** | The baseline λ when burn_excess=0. Default λ_0=1.0 — interpreted as "neutral budget pressure". |
| **λ_t (lambda at time t)** | The current cost-penalty multiplier: `λ_t = λ_0 × exp(α × burn_excess)`. Read each round from the wallet. **Unbounded** in principle (can be 0 to ∞), but capped numerically. |
| **λ_norm (lambda normalized)** | Sigmoid-normalized version: `λ_norm = λ_t / (1 + λ_t)`. Bounded in (0, 1). Used in the PA reward formula. As λ_t → 0, λ_norm → 0; as λ_t → ∞, λ_norm → 1. |

### Quality / utility terms

| Term | Meaning |
|---|---|
| **q (quality)** | Score in [0, 1] from the evaluator (judge or EM/F1 metric). 1.0 = perfect answer; 0 = wrong / no answer. |
| **f (failure_flag)** | Binary {0, 1}. 1 if the LLM call failed (timeout, schema error, etc.). |
| **ν (nu, failure penalty)** | Hyperparameter ν=0.5 (locked). Cost of a failure in utility units. |
| **utility u** | `u = q − ν × f`. The "intrinsic" reward we observe from a call. ν=0.5 means a failure costs half a unit of quality (so utility ∈ [-0.5, +1]). |
| **PA reward** | Payment-aware reward: `PA = (1 − λ_norm) × u − λ_norm × c̃`. Used at decision time AND for paper-reported cumulative reward (cum_PA). Bounded in (-1, +1). |

### Bayesian posterior terms

| Term | Meaning |
|---|---|
| **Posterior** | A probability distribution over the unknown parameter (here: the true mean utility or true cost of an arm). It's updated as we observe data. |
| **Prior** | Our initial belief BEFORE any data. We use prior `μ ~ N(μ₀, σ₀²)`. |
| **μ₀ (mu zero, prior_mean)** | The center of our prior. For q-posterior we use 0.5 (neutral). For c-posterior we use the spec price (e.g., $0.002 for mid — "the spec is roughly right"). |
| **σ₀² (sigma-zero squared, prior_var)** | Variance of the prior. Larger = less certain initially. q uses 1.0 (broad — initial exploration). c uses 1e-4 (= max_cost², so prior std ≈ max_cost — fairly broad in $ terms but tight relative to plausibilities). |
| **σ² (sigma squared, noise_var)** | Variance of the **observation noise**. Each observation is `obs = true_value + noise` where `noise ~ N(0, σ²)`. q uses 0.09 (judge scores have natural noise). c uses 1e-6 (cost in our replay is essentially deterministic, so observation noise is tiny). |
| **N(μ, σ²)** | Normal (Gaussian) distribution with mean μ and variance σ². |
| **Sufficient statistics** | Summary numbers that capture all information needed to compute the posterior. For our Normal-Normal model: n_eff and s_eff. |
| **n_eff (effective sample size)** | A *weighted* count of observations. With γ-discount, recent observations weight more than old ones (full weight 1.0 → decays each round by γ). After many discounts, n_eff is smaller than the raw count of observations. |
| **s_eff (effective weighted sum)** | The discounted sum of observed values: `s_eff = Σ γ^(age of observation) × observation`. |
| **Conjugate prior** | A prior whose family is preserved after updating. Normal prior + Normal likelihood → Normal posterior. This makes math closed-form (no integrals to numerically compute). |
| **Posterior precision** | `1/σ²_post = 1/σ₀² + n_eff/σ²`. "Information" — high precision means tight posterior. |
| **Posterior variance** | `σ²_post = 1 / posterior_precision`. As n_eff grows, σ²_post shrinks → tighter belief. |
| **Posterior mean** | `μ_post = σ²_post × (μ₀/σ₀² + s_eff/σ²)`. A weighted average of prior_mean and observed mean, weighted by their respective precisions. As n_eff → ∞, μ_post → s_eff/n_eff (the observed mean). |

### Discount / non-stationarity terms

| Term | Meaning |
|---|---|
| **γ (gamma, discount factor)** | Number in (0, 1] applied multiplicatively to n_eff and s_eff each round. Default γ=0.999. γ<1 lets old observations decay so the algorithm can adapt to changes. |
| **Half-life** | Number of rounds for an observation's weight to drop to 50%: `half-life = ln(2) / (1 − γ)`. With γ=0.999, half-life ≈ 693 rounds. |
| **Effective memory** | At steady state, n_eff settles at roughly `1/(1 − γ)` for an arm pulled every round. With γ=0.999, that's ~1000 effective samples. |

### Thompson Sampling terms

| Term | Meaning |
|---|---|
| **Thompson Sampling (TS)** | A bandit strategy: instead of using the posterior **mean** to choose, draw a sample θ̂ ~ posterior(arm) for each arm and pick `argmax θ̂`. The randomness automatically balances exploration (rare arms with wide posterior get occasionally high samples) and exploitation (well-explored arms with narrow posteriors are sampled near their mean). |
| **Posterior sample** | One random draw from the posterior distribution: `θ̂ ~ N(μ_post, σ²_post)`. |
| **Contextual bucket** | A discretized version of the context. Our context is the task type (T1/T2/T3a/T3b), so we have 4 buckets. Each (arm, bucket) pair has its own posterior. |

---

## 1. Setup — what scenario we're in

We're running **S3**, defined as `PremiumDropScenario(shock_round=1000, price_multiplier=0.2)`.

| Round | What changes |
|---|---|
| 0 to 999 | Original calibrated market: cheap=$0.0005, mid=$0.002, premium=$0.01 |
| 1000 onward | Premium price is multiplied by 0.2: premium=$0.002 (= mid price). Other arms unchanged. |

We zoom in on **seed=0, round=2000** (so we're 1000 rounds into the post-shock period).

The task drawn for this round happens to be a **T3b** task (open-ended websearch). We will work through what PA-DCT does for this single decision.

---

## 2. Wallet state at round 2000

We need to know the *current* λ_norm to compute PA-reward.

### Step 2a — read empirical spent

From `results/scenario_sweep_s3promo/padct/seed_00.jsonl`, summing
`charged_cost_usdc` over rounds 0..1999:

```
spent = $3.79
```

### Step 2b — compute actual burn rate

```
actual_burn_rate = (spent / total_budget) / rounds_elapsed
                 = ($3.79 / $50) / 2000
                 = 0.0758 / 2000
                 = 3.79 × 10⁻⁵
```

**Term reminder**: `actual_burn_rate` = "what fraction of the total budget am I burning per round, on average so far".

### Step 2c — compute burn excess

```
burn_excess = (actual_burn_rate − target_burn_rate) / target_burn_rate
            = (3.79e-5 − 1e-4) / 1e-4
            = (-6.21e-5) / (1e-4)
            = −0.621
```

**Interpretation**: PA-DCT is currently spending about 38% of the target rate (= 1 + (-0.62)) — i.e., **under-spending**. The negative burn_excess will produce a small λ.

### Step 2d — compute λ_t

```
λ_t = λ_0 × exp(α × burn_excess)
    = 1.0 × exp(2.0 × −0.621)
    = exp(−1.242)
    ≈ 0.289
```

**Term reminder**: `exp(x)` is the natural exponential function `e^x` where e ≈ 2.71828. So `exp(-1.242)` means `e^(-1.242) ≈ 1 / 3.46 ≈ 0.289`.

**Sanity check**: log line at round 1999 contains `"lambda_t": 0.2891`. ✓ Matches.

### Step 2e — convert to λ_norm

```
λ_norm = λ_t / (1 + λ_t)
       = 0.289 / 1.289
       ≈ 0.224
```

**Why this transformation**: λ_t can range from 0 to ∞, but we want a bounded weight in (0, 1) for the PA formula. The transformation `x / (1+x)` is the **sigmoid** (σ(x) = 1/(1+e^-x) is what most people mean; here we use a similar bounded squashing function). At λ_t=1 (neutral), λ_norm=0.5. As λ_t→0, λ_norm→0 (no cost penalty). As λ_t→∞, λ_norm→1 (cost dominates).

**Read this number**: λ_norm = 0.224 means the PA formula will weight (1 − 0.224) = 0.776 on quality and 0.224 on cost. **Quality matters ~3.5× more than cost right now**, because we've been under-spending.

---

## 3. Posterior state at round 2000

PA-DCT maintains separate posteriors per (arm, task_type). At round 2000, on **T3b**, we look up the posteriors for each of the 5 arms.

### 3a — How many T3b observations have we collected per arm?

Empirically (counting from the log):

| Arm | T3b picks pre-shock (rounds 0-999) | T3b picks post-shock (1000-1999) | Total by round 2000 |
|---|---|---|---|
| P-cheap | ~11 | ~11 | 22 |
| P-mid | ~110 | ~113 | 223 |
| **P-premium** | **24** | **180** ⭐ | **204** |
| P-adv | ~26 | ~28 | 54 |
| P-flaky | ~2 | ~1 | 3 |

**The big number is premium: 180 post-shock picks.** This is the positive feedback at work — once PA-DCT started observing the cheaper price, premium became attractive in PA terms, so it got picked more, generating more observations.

### 3b — Computing n_eff for premium-on-T3b

Each observation contributes weight `γ^(rounds elapsed since the observation)`:
- An observation made at round 50 has weight `γ^(2000−50) = γ^1950 ≈ 0.999^1950 ≈ 0.142`
- An observation made at round 1990 has weight `γ^10 ≈ 0.990`

For 24 pre-shock obs (average age ~1500 rounds at time of round 2000):
```
weighted contribution ≈ 24 × γ^1500 ≈ 24 × 0.999^1500 ≈ 24 × 0.223 ≈ 5.4
```

For 180 post-shock obs (average age ~500):
```
weighted contribution ≈ 180 × γ^500 ≈ 180 × 0.999^500 ≈ 180 × 0.607 ≈ 109.3
```

Total:
```
n_eff(premium, T3b) ≈ 5.4 + 109.3 = 114.7
```

**Reminder**: `n_eff` is NOT just a count — it's the *effective* count after γ-decay. 204 raw observations contribute 114.7 effective samples to the posterior because old ones are partially "forgotten".

### 3c — Computing s_eff for the cost posterior

`s_eff = Σ (weight × observed_cost)`:

```
Pre-shock: 5.4 × $0.01 = $0.0540   (premium cost was $0.01 then)
Post-shock: 109.3 × $0.002 = $0.2186   (premium cost is $0.002 now)
s_eff = $0.0540 + $0.2186 = $0.2726
```

### 3d — Computing posterior_var (cost posterior, premium on T3b)

Using the Normal-Normal conjugate posterior formula:

```
posterior_precision = 1/σ₀² + n_eff/σ²
                    = 1/(c_prior_var) + n_eff/(c_noise_var)
                    = 1/1e-4 + 114.7/1e-6
                    = 10⁴ + 1.147 × 10⁸
                    ≈ 1.147 × 10⁸    ← data swamps the prior
posterior_var = 1 / 1.147e8
              = 8.72 × 10⁻⁹
posterior_std = √8.72e-9
              ≈ 9.34 × 10⁻⁵        (very tight: $0.0001-ish)
```

**Read this number**: the posterior on premium's cost is centered at some value with std about $0.0001 — meaning we're very sure of where the true cost is.

### 3e — Computing posterior_mean (cost posterior, premium on T3b)

```
posterior_mean = posterior_var × (μ₀/σ₀² + s_eff/σ²)
              = 8.72e-9 × ($0.01/1e-4 + $0.2726/1e-6)
              = 8.72e-9 × (100 + 272600)
              = 8.72e-9 × 272700
              ≈ $0.00237
```

**Read this number**: PA-DCT believes premium currently costs about **$0.00237** — close to but slightly above the true post-shock price of $0.002. The difference comes from old (decayed but not gone) pre-shock observations of $0.01 that still have some weight.

### 3f — Same calculation for q-posterior of premium on T3b

n_eff is the same (114.7) — q and c are observed together each time we pick this arm.

```
posterior_precision_q = 1/(prior_var) + n_eff/(noise_var)
                      = 1/1.0 + 114.7/0.09
                      = 1 + 1274
                      = 1275
posterior_var_q = 1/1275 ≈ 0.000784
posterior_std_q = √0.000784 ≈ 0.028   (tight: about ±0.028)
```

The s_eff for q is approximately `n_eff × q_true = 114.7 × 0.91 ≈ 104.4`
(empirically q for premium on T3b ≈ 0.91, the true mean).

```
posterior_mean_q = 0.000784 × (0.5/1.0 + 104.4/0.09)
                = 0.000784 × (0.5 + 1160)
                = 0.000784 × 1160.5
                ≈ 0.910
```

So q-posterior on premium-T3b ≈ N(0.910, 0.028²).

### 3g — Comparable computation for mid (T3b)

| Term | mid on T3b at round 2000 | premium on T3b at round 2000 |
|---|---|---|
| total picks | 223 | 204 |
| n_eff (γ-decayed) | ~96.5 | ~114.7 |
| q post mean | ~0.836 (true T3b mid mean) | ~0.910 |
| q post std | ~0.030 | ~0.028 |
| c post mean | $0.002 (very tight) | **$0.00237** |
| c post std | very tight | $0.0001 |

---

## 4. Decision rule at round 2000

### 4a — Sample one q and one c value per arm

Using the `numpy.random.Generator` seeded for this run:

```python
q̂_premium = rng.normal(0.910, 0.028)        # one possible draw: 0.93
ĉ_premium = rng.normal(0.00237, 0.0001)     # one possible draw: 0.00240
q̂_mid     = rng.normal(0.836, 0.030)        # one possible draw: 0.84
ĉ_mid     = rng.normal(0.00200, ~0.00001)   # one possible draw: 0.00200
```

**Term reminder**: `rng.normal(mu, sigma)` returns one sample from N(mu, sigma²).
The "hat" notation `q̂` (q-hat) means "a sampled estimate of q" — distinguish
from the true q.

### 4b — Normalize cost into c̃

```
c̃_premium = clip(ĉ_premium / max_provider_cost, 0, 1)
          = clip(0.00240 / 0.01, 0, 1)
          = clip(0.240, 0, 1)
          = 0.240
c̃_mid     = clip(0.00200 / 0.01, 0, 1) = 0.200
```

`clip(x, 0, 1)` enforces `x ∈ [0, 1]` (sets x to 0 if negative, to 1 if larger
than 1; otherwise leaves it). Needed because Gaussian samples can theoretically
go outside the realistic cost range.

### 4c — Compute PA-reward per arm

Recall: `PA = (1 − λ_norm) × q̂ − λ_norm × c̃`. With λ_norm = 0.224:

```
PA(premium) = 0.776 × 0.93 − 0.224 × 0.240
            = 0.722 − 0.054
            = 0.668

PA(mid) = 0.776 × 0.84 − 0.224 × 0.200
        = 0.652 − 0.045
        = 0.607
```

### 4d — Pick argmax

Premium has the higher PA (0.668 > 0.607), so PA-DCT chooses **P-premium**.

**Term reminder**: `argmax` = "argument that maximizes" — returns the *index*
(here, the *arm*) that produces the maximum value, not the value itself.

---

## 5. Update rule at round 2000

After the decision, the runtime executes:
1. `wallet.affordable(...)` (already checked above — premium IS affordable at $0.002)
2. Look up the PregenRecord for (this task_id, premium, sampled version)
3. Apply scenario transformation: scenario sets `record.cost_usdc = $0.002` (the post-shock price)
4. Compute `utility = q − ν × f`. For this record: q ≈ 0.91, f = 0 (no failure), so utility ≈ 0.91.
5. Charge wallet: `wallet.record_spend($0.002)`. Now spent goes from $3.79 to $3.792.
6. Call `policy.update(context, P-premium, utility=0.91, observed_cost=0.002)`:

```python
# Inside PADCTPolicy.update:
bucket = T3b_index   # since this round's task was T3b

# Update q-posterior for (premium, T3b):
self._q_posteriors[P-premium][T3b].update(0.91)
# Internally: n_eff += 1, s_eff += 0.91
# n_eff: 114.7 → 115.7
# s_eff: 104.4 → 105.3
# new posterior_mean ≈ 0.910 (essentially unchanged — the observation was at the mean)

# Update c-posterior for (premium, T3b):
self._c_posteriors[P-premium][T3b].update(0.002)
# Internally: n_eff += 1, s_eff += 0.002
# n_eff: 114.7 → 115.7
# s_eff: $0.2726 → $0.2746
# new posterior_mean: $0.2746 / 115.7 (data dominant) ≈ $0.00237
# (slightly drifts toward $0.002 because new obs is at $0.002; with this many
#  samples, individual observations move the mean by ~0.001× their gap)
```

**Note**: the discount γ was already applied at the START of this round, before sampling. So the n_eff values shown above (114.7) are already post-discount. After update, n_eff = 115.7 (γ has not been applied AGAIN).

At the start of round 2001, the discount applies again before any decision:
```
n_eff[premium][T3b] = γ × 115.7 = 0.999 × 115.7 = 115.58
s_eff[premium][T3b] = γ × $0.2746 = $0.27432
```

And the cycle continues.

---

## 6. Why this leads to migration (the positive feedback loop)

Step-by-step:

1. **Round 1000**: shock fires. From here on, when premium is picked, observed_cost is $0.002 instead of $0.01. The c-posterior for premium starts seeing low observations.

2. **Rounds 1000-1100**: PA-DCT occasionally picks premium (at the rate it was picking premium pre-shock, ~5%). Each pick provides a fresh $0.002 observation. The c-posterior mean starts dropping below $0.01.

3. **As c-posterior drops**: the PA reward formula `PA = (1-λ_n)·q̂ − λ_n·c̃` becomes more favorable to premium because c̃ is shrinking. With q_premium genuinely > q_mid (especially on T3b), premium starts to win the argmax more often.

4. **Premium pick rate increases**: more observations come in faster, the c-posterior tightens around $0.002, and PA reward for premium becomes consistently higher.

5. **Equilibrium**: premium pick rate stabilizes at the level where the *expected PA gap* between premium and mid is balanced against the TS-sampling noise. Empirically: ~66% by round 10000 on T3b.

This is **classical Bayesian online learning** — what TS does naturally — except now applied to the cost dimension as well as quality. The bug pre-M3.F was that cost was hardcoded, so this learning loop never engaged for cost.

---

## 7. What if you want to verify this yourself

Re-run the seed and pull diagnostics:

```bash
python -m scripts.run_s3_promo --num-seeds 1
```

Then in Python:

```python
import json
from pathlib import Path
records = [json.loads(line) for line in
           Path("results/scenario_sweep_s3promo/padct/seed_00.jsonl")
           .read_text().splitlines()]
print(f"spent at round 2000: ${sum(r['charged_cost_usdc'] for r in records[:2000]):.4f}")
print(f"premium picks on T3b by round 2000: "
      f"{sum(1 for r in records[:2000] if r['task_type']=='T3b' and r['chosen_arm']=='P-premium')}")
print(f"λ_t at round 1999 (logged): {records[1999]['lambda_t']:.4f}")
```

Expected output (matches our derivation above):
```
spent at round 2000: $3.7945
premium picks on T3b by round 2000: 204
λ_t at round 1999 (logged): 0.2891
```

---

## 8. Summary in one paragraph

At round 2000 of S3, PA-DCT has been under-spending (3.79/10 of target) so
λ_norm = 0.224 (cost penalty is weak). Among the 5 arms, premium-on-T3b has a
posterior over quality centered at 0.910 ± 0.028 and a posterior over cost
centered at $0.00237 ± $0.0001 (close to the true post-shock price $0.002).
Drawing a TS sample of `q̂_premium ≈ 0.93` and `ĉ_premium ≈ $0.0024`, the PA
reward formula `(1-λ_n)·q̂ - λ_n·c̃` evaluates to 0.668 for premium versus 0.607
for mid, so premium wins. After observing the actual outcome (q ≈ 0.91, cost
$0.002), both posteriors update slightly tighter, and the cost-posterior mean
drifts a tiny bit closer to $0.002. This adaptation, repeated every round,
takes premium's share on T3b from ~5% pre-shock to ~66% by round 10000.

---

## 9. Cross-references

- Algorithm code: `pilot402/policies/padct.py`
- Posterior class: `pilot402/policies/posterior.py`
- Reward formula: `pilot402/runtime/reward.py`
- Wallet / λ-dynamics: `pilot402/runtime/wallet.py`
- Scenario hooks: `pilot402/scenarios.py` (PremiumDropScenario)
- Tests for dual posterior: `tests/test_policies_padct.py` (7 new in M3.F)
- M3.F design rationale: `logs/m3f_dual_posterior_design.md`
- M3.F empirical results: `logs/m3f_results.md`
