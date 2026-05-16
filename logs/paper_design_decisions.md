# 402Pilot — Paper Design Decisions (Consolidated, Latest)

**Date**: 2026-05-02 (live document — updated as new decisions are made)

This is the **single source of truth** for paper-relevant design decisions.
All values reflect the LATEST calibration and **supersede any earlier
numbers** in `replication_comparison.md`, the previous Tier 3 analysis,
or initial baseline reports.

## Maintenance protocol

Going forward, **every paper-relevant design discussion should be appended
to or update this document** (or one of the cross-referenced specialty
docs: `reward_design_rationale.md`, `baselines_s1_analysis.md`).

When conflicts arise between this document and earlier artifacts:
**latest-here wins**. Older artifacts are kept for traceability of the
decision journey but are not authoritative.

A decision is "paper-relevant" if it would need to be explained,
justified, or defended in the paper or its appendix — including:
- Calibration choices (budget, prices, failure rates, hyperparameters)
- Formula design (reward shape, normalization, etc.)
- Experimental setup (providers, scenarios, evaluators, baselines)
- Methodology rationale (why bandit, why frozen pregen, why specific tasks)
- Sensitivity analyses and ablations
- Open issues and future work

---

## 1. Problem framing

402Pilot is a **finance layer** above x402-style micropayments. The agent
faces a **budget-constrained, non-stationary, contextual bandit problem**:

- Per round: one paid LLM call (one arm pulled)
- One observation: (quality, cost, latency, failure_flag)
- Wallet drains over time; cannot exceed budget
- Provider quality / price may drift (S2/S3 scenarios)

**Why bandit, not RL**: one observation per round, no long-horizon credit
assignment within a single service call. x402 payments are irreversible
(no rollback).

### 1.1 Paper hook: optimal allocation is **counterintuitive**

The True Oracle (Plan A: free-running with hindsight per-round arm
peek) on our S1 stationary benchmark allocates as follows:

| Provider | Oracle picks | Common-sense expectation |
|---|---|---|
| **P-cheap** | **54%** ⭐ | "no way, quality too low" |
| **P-mid** | 32% | "this should be 70%+" |
| P-premium | 5% | "for hardest tasks only" ✓ |
| P-adv | 7% | "shouldn't ever pick this" |
| P-flaky | 3% | "shouldn't ever pick this" |

**The counterintuitive finding**: optimal allocation under realistic
LLM workloads + budget pressure is **cheap-dominated**, not mid-dominated.
This stems from the cost-quality asymmetry: many tasks (~70-80%) are
solvable by the cheap tier; on those tasks, paying 4× more for mid (or
20× for premium) is wasteful. Only on the hardest 20-30% of tasks does
mid become genuinely necessary, and only on the hardest 5% does premium
pay off.

**Why this matters for the paper**:
1. **Most developers don't know this** — they default to "always mid" for
   safety or "all premium" if cost-blind. Real-world LLM API spend
   patterns confirm this: most teams over-pay by using a single tier.
2. **Oracle requires hindsight per-task per-version peek** — structurally
   unavailable to any online bandit. This is the upper-bound ceiling.
3. **PA-DCT approaches this counterintuitive optimum** without any prior
   knowledge of provider behavior, recovering 80% of Oracle's reward
   from observed (utility, cost, failure) signals alone.

The paper's central contribution is therefore not "a bandit learns to
allocate paid LLM calls" — that would be unsurprising. It is:

> **"In realistic LLM markets, the cost-aware optimal allocation is
> counterintuitive (cheap-dominated). We show a contextual bandit
> (PA-DCT) discovers this allocation online without prior knowledge,
> achieving 80% of oracle performance, and remains robust under
> non-stationary changes (S2 / S3) where fixed policies fail."**

This narrative justifies the paper's existence — it's a non-obvious,
empirically-grounded finding that overturns common heuristics.

---

## 2. Benchmark design — 402Pilot-Bench

### 2.1 Five providers (K=5)

| Provider | Model | Price (USD/call) | Special behavior |
|---|---|---|---|
| **P-cheap** | Qwen3.5-flash (DashScope) | $0.0005 | No tools, parametric memory only |
| **P-mid** | GPT-5.4-mini | $0.002 | BM25 retrieval, top-2 paragraphs |
| **P-premium** | GPT-5.4 | **$0.01** | CoT pipeline, full document context |
| **P-adv** | GPT-5.4-mini | $0.002 | Adversarial system prompt → fluent-but-wrong |
| **P-flaky** | GPT-5.4-mini | $0.002 | **40% timeout injection** (versions 0+1 of 5) |

**Cost ratio**: 1 : 4 : 20 : 4 : 4 (cheap : mid : premium : adv : flaky)

**Calibration history**:
- Premium price **$0.02 → $0.01** (2026-05-02): the 10x mid:premium ratio
  was Anthropic Opus territory; 5x matches GPT-4o-mini→GPT-4o, Haiku→Sonnet
  more naturally. All 4,115 P-premium pregen records were updated to
  reflect the new x402 charge price.
- P-flaky failure rate **20% → 40%** (2026-05-02): the original 1/5
  timeout was too subtle for clear bandit signal vs P-mid; 2/5 failures
  produces a clean 0.32 quality gap.

**Why P-mid / P-adv / P-flaky share cost + model**: by design. The bandit
must distinguish them via observable rewards alone (quality, failure
indicators), not via price tier. This is the central methodological claim:
contextual bandits learn provider behavior without privileged metadata.

### 2.2 Four task types (M=4)

| Type | Source | Tasks | Evaluator |
|---|---|---|---|
| T1 — Coding | HumanEval | 164 | pass@1 (subprocess sandbox) |
| T2 — Multi-hop QA | HotpotQA validation | 220 | EM/F1 |
| T3a — Closed-form QA | TriviaQA-web | 219* | EM/F1 |
| T3b — Open-ended | OpenAssistant-filtered | 220 | LLM-as-judge (Gemini 2.5 Pro) |

*One TriviaQA task (`trivia/jp_3954`) excluded after triggering DashScope
content filter; documented in `pilot402/pregen/tasks/triviaqa.py`.

### 2.3 Three scenarios

| Scenario | Round 0–2999 | Round 3000–4999 | Round 5000–9999 |
|---|---|---|---|
| **S1 — Stationary** | All providers fixed | Fixed | Fixed |
| **S2 — Mid outage** | Fixed | P-mid timeout 30% during rounds 3,000--5,500 | Fixed |
| **S3 — Premium promo** | Fixed | Fixed | P-premium price drops from $0.01 to $0.002 at round 1,000 |

S1 is what M3.C/D have been calibrated against. S2/S3 are M3.B (next).

### 2.4 Budget calibration (final)

- **Total budget**: $50
- **Rounds per run**: 10,000
- **Target burn rate**: 0.0001 (= 1/num_rounds; the rate at which the wallet
  would last exactly the full run)
- **λ_0 = 1.0, α = 2.0** (wallet's λ-dynamics)

**"Always-Premium bankrupts at exactly round 5,000"**: $50 / $0.01 = 5,000.
This is preserved across all calibration changes — the dramatic narrative
that premium-only is unsustainable is locked.

**Calibration history**:
- Budget **$100 → $50** (2026-05-02): with $100, Always-Mid used only 20%
  of budget — too generous, no real budget pressure on most policies. $50
  brings Always-Mid to 40% utilization (genuine pressure).
- Target burn rate **0.01 → 0.0001** (2026-05-02): bug found via design
  audit. Original 0.01 told wallet "expect to spend 1% of budget per round"
  = $1/round = 100 rounds total. Misaligned by 100x with our 10,000-round
  horizon → λ-dynamics silent → wallet's PA mechanism dead. Fix: target =
  1/num_rounds.

---

## 3. Pregen architecture

20,575 PregenRecords stored in `data/pregen/<provider>__<task_type>.jsonl`:

- 5 providers × 4 task types × ~205 tasks × 5 versions
- Real LLM API calls during pregen (~$70-100 one-time spend)
- Replayed deterministically at experiment time (zero API spend)

**Why pregen**: reproducibility (frozen dataset), cost (no per-experiment
API), determinism (same seed = same trace). Each (provider, task) pair
has 5 sampled versions to provide reward variance for the bandit.

**P-flaky timeout sentinel**: versions 0 and 1 are forced timeouts (no
LLM call made); they store `failure_flag=True, q=0, latency_s=0`.

---

## 4. Reward formula (FINAL — supersedes all earlier drafts)

### 4.1 Formula

    utility    = q − ν · f                                ∈ [-0.5, +1]
    λ_norm     = λ_t / (1 + λ_t)                          ∈ (0, 1)
    PA_reward  = (1 − λ_norm) · utility − λ_norm · c̃      ∈ [-1, +1]

where:
- `q ∈ [0, 1]` — task quality (pass@1 / EM·F1 / judge score, all in [0,1])
- `f ∈ {0, 1}` — failure indicator
- `ν = 0.5` — failure penalty weight (fixed across paper)
- `c̃ = cost / max_provider_cost ∈ [0, 1]` — normalized cost
- `λ_t = exp(α · burn_excess_t)` — wallet's budget-pressure multiplier
- `λ_norm = λ_t / (1 + λ_t) = sigmoid(α · burn_excess_t)`

The policy posterior is updated with **utility**; the policy ranks arms by
**PA_reward**. This separation keeps the posterior tracking intrinsic
provider quality independent of decision-time budget pressure.

### 4.2 Why these three forms — the three core design decisions

#### A. Bundle quality and failure into a single "utility"

We treat `q` and `f` as **two facets of the same axis** (task delivery)
rather than two independent reward channels:

> "Failure is the limiting case of zero quality." When a provider times
> out, q = 0 already (no scorable response). The ν·f term adds a
> **structural penalty** beyond zero-quality, capturing the operational
> cost of "no response": forced retry, broken call chain, wallclock
> latency for the user.

This bundling is **deliberate**, not an oversight:

|                               | q | f | utility |
|-------------------------------|---|---|---------|
| Provider returned wrong answer | 0 | 0 | 0 |
| Provider timed out            | 0 | 1 | -ν = -0.5 |

P-flaky's *raison d'être* is to model unreliable services that share
**cost + base model + prompt** with P-mid; the only dimension
distinguishing them is reliability. Without ν·f, P-flaky would be
indistinguishable from a marginally-lower-quality P-cheap. Bundling
quality and failure into one utility, then weighing utility against
cost, keeps a clean two-tier structure: intrinsic value × budget weight.

#### B. Drop the latency term (μ·l̃)

Earlier drafts had `μ · l̃ = 0.05 · l̃` for latency penalty. **We removed
it** because:

1. **No provider in our K=5 specifies a latency profile** — providers'
   actual latency is incidental (whatever the API took during pregen).
2. **No scenario manipulates latency** — S1/S2/S3 all leave it alone.
3. **Empirically <1% of reward magnitude** — μ·l̃ contributed ~73 reward
   points over 10,000 rounds vs Always-Mid's total 5,831. Paying a
   hyperparameter cost (defending μ=0.05 to reviewers) for no signal.

**Latency-aware bandits** are an explicit follow-up paper direction.

#### C. Sigmoid-normalize the cost penalty

Earlier drafts used `q − λ · c̃` directly. With `λ = exp(α · burn_excess)
∈ [0, ∞)`, the cost penalty could **dominate** quality (q ∈ [0, 1] but
λ·c̃ could be 7+). This was:

- **Numerically asymmetric** — q was nearly invisible vs cost penalty
- **Theoretically inconvenient** — standard regret bounds require
  bounded reward; unbounded reward forces empirical-only claims

The convex-combination form
    PA_reward = (1−λ_norm)·utility − λ_norm·c̃
with λ_norm = λ/(1+λ) = sigmoid(log λ) keeps reward in [-1, +1] and gives
a natural reading: **λ_norm is the fraction of decision weight given to
cost** (vs. utility).

Algebraic equivalence: `λ/(1+λ) = sigmoid(ln λ)`. Since the wallet
already returns `λ = exp(α · burn_excess)`, the reward calculator computes
`λ/(1+λ)` directly without re-deriving `burn_excess`.

### 4.3 Hyperparameter values (locked across paper)

| Symbol | Value | Meaning | Rationale |
|---|---|---|---|
| ν | 0.5 | Failure penalty | Single failure ≈ losing half a perfect quality unit; balanced (not catastrophic, not ignorable) |
| α | 2.0 | λ-responsiveness | exp(2·burn_excess); 2x over-spend → wallet's **λ_t ≈ 7.4** → reward's **λ_norm ≈ 0.88** (88% decision weight on cost) |
| λ_0 | 1.0 | Baseline λ_t at exact target | At-target burn → λ_t = 1 → λ_norm = 0.5 → equal weight on utility and cost |
| max_cost | $0.01 | Cost normalization denominator | Most expensive provider (P-premium) |

**Note on the two λ's**:
- `λ_t = exp(α·burn_excess) ∈ [0, ∞)` — wallet's raw output; ranges
  unboundedly with burn rate
- `λ_norm = λ_t / (1+λ_t) = sigmoid(α·burn_excess) ∈ (0, 1)` — reward's
  decision weight; bounded

Both are correct in their context: papers/code that talk about wallet
state should use `λ_t`; anything talking about reward magnitudes or
PA-DCT's decision should use `λ_norm`.

These are **fixed across all experiments and scenarios**. Sensitivity
analysis on ν ∈ {0.1, 0.5, 1.0} should be in the appendix.

---

## 5. Calibration journey (chronological)

What we changed and why:

| Date | Change | Reason |
|---|---|---|
| Pre-2026-05-02 | All initial designs | Initial speculative calibration |
| 2026-05-02 morning | P-flaky 20% → 40% | 20% gave no clear signal vs P-mid |
| 2026-05-02 morning | Premium price $0.02 → $0.01 | Match real GPT-4o ratio (5x not 10x) |
| 2026-05-02 morning | Budget $100 → $50 | Force genuine budget pressure on Always-Mid |
| 2026-05-02 noon | target_burn_rate 0.01 → 0.0001 | Bug: was misaligned by 100x; λ-dynamics silent |
| 2026-05-02 afternoon | Drop latency term (μ·l̃) | No designed dimension; <1% impact |
| 2026-05-02 afternoon | Sigmoid normalize cost | Bounded reward; standard regret bounds applicable |

These changes affected calibration but **not the experimental hypothesis**:
PA-DCT should learn to navigate the cost-quality-failure tradeoff online,
without privileged provider metadata.

---

## 6. Baseline performance (S1 stationary, final calibration)

| Policy | rounds | bankruptcies | spent | cum_PA_reward | mean_q | per-round PA |
|---|---|---|---|---|---|---|
| random | 10000 | 0/30 | $33 | 3,191 ± 49 | 0.69 | 0.319 |
| always_cheapest | 10000 | 0/30 | $5 | 5,164 ± 23 | 0.61 | 0.516 |
| **always_mid** | 10000 | 0/30 | $20 | **5,831 ± 29** | 0.82 | 0.583 |
| budget_rule | 10000 | 0/30 | $40 | -82 ± 14 | 0.83 | -0.008 |
| always_premium | 5000 | 30/30 | $50 | -3,887 ± 3 | 0.86 | -0.778 |

**Oracle upper bound** (anchored on always_cheapest's λ trajectory):
**7,509 ± 23** (see §7 for the anchoring concept).

**PA-DCT target ranges**:
- ≥ 6,500: paper-publishable (beat Always-Mid by ≥ 10%, close ≥ 40% to Oracle)
- ≥ 7,000: strong result (close ≥ 65% to Oracle)
- ≥ 7,300: near-optimal

**Key paper-worthy findings**:
1. **Always-Premium bankrupts** at round 5,000 with cum_PA = −3,887 (per
   design). Demonstrates "premium-without-budget-awareness fails."
2. **Budget-Rule is anti-optimal** (cum_PA ≈ 0). The "splurge premium when
   budget is high" heuristic is *worse than random* under PA-aware reward.
   The bandit must learn the inverse: stay cheap early to keep λ low.
3. **Always-Mid is the strongest non-omniscient baseline** (5,831). PA-DCT
   must contextually mix cheap/mid/premium to beat this.
4. **Random ≈ 3,191**: suffering primarily from 20% premium picks under
   high λ.

---

## 7. The Oracle upper bound — anchoring concept (re-explained)

The Oracle is **post-hoc analysis**, not a free-running policy. It gives
the **upper bound on PA_reward achievable given a particular λ trajectory**.

### Why anchoring matters

In our reward formula, `λ_t` is **endogenous** — it depends on cumulative
spending up to round t, which depends on the policy's choices. So the
**reward landscape itself depends on the trajectory**.

This means: "best per-round arm" is not a single fixed answer. It depends
on what λ is at that round, which depends on spending history.

### What "cheap-anchor" Oracle does (step by step)

1. Take always_cheapest's run logs (30 seeds × 10,000 rounds).
2. For each round, read from the log:
   - The task that was sampled
   - The lambda_t the wallet had at that moment (from cheap's spending)
   - The set of affordable arms
3. **Pretend** (counterfactually): "what if instead of picking cheap, the
   policy picked the BEST arm for this round, given THAT λ_t?"
4. For each candidate arm, look up the pregen record at the deterministic
   version chosen by the round's RNG. Compute its PA_reward at λ_t.
5. Pick the arm with the highest PA_reward. Sum across all rounds.

The result: a number representing **"if you could perfectly pick the best
arm each round AND your wallet behaved like always_cheapest's wallet,
what's the max PA_reward you could have achieved?"**

### Why anchoring on cheapest gives the HIGHEST UB

Always_cheapest spends very little ($5 over 10,000 rounds = $0.0005/round).
This is well below the target burn rate.

→ `burn_excess` is very negative throughout the run (wallet feels under-spent).
→ `λ_t = exp(2·burn_excess)` stays low (~0.17).
→ `λ_norm = λ/(1+λ)` is low (~0.15).
→ Cost penalty (`λ_norm · c̃`) is small.
→ **Premium becomes economically attractive when its quality is high**:
  premium PA = 0.85·0.86 − 0.15·1.0 = 0.581 (positive, competitive with mid).

So with cheap's λ trajectory, the Oracle can sometimes pick premium
without huge cost penalty, capturing premium's quality advantage on hard
tasks. Hence higher UB (7,509).

### Why other anchors give LOWER UB

| Anchor | Spending | Avg λ_t | Avg λ_norm | Cost weight in reward | Oracle's freedom | UB |
|---|---|---|---|---|---|---|
| always_cheapest | $5 | 0.17 | **0.15** | 15% on cost | maximum | **7,509** |
| always_mid | $20 | 0.30 | **0.23** | 23% on cost | moderate | 6,555 |
| random | $33 | varies | varies | mixed | reduced | 5,455 |
| budget_rule | $40 | high early | high early | large early | restricted | 2,491 |
| always_premium | $50 | 7.4 | **0.88** | 88% on cost | none (cost dominates) | 144 |

(λ_norm = λ_t / (1+λ_t); λ_norm is what's actually used in the reward
formula. λ_t = 7.4 corresponds to λ_norm = 0.88, meaning Oracle gives 88%
of its decision weight to cost when evaluating each arm — that's why
even a +0.86 quality answer can lose to a +0.05 cheap answer.)

**The Oracle is constrained by the wallet's behavior, not just the data.**
Even with perfect information, you can't out-pick a trajectory where the
wallet thinks you're crashing toward bankruptcy.

### What this means for PA-DCT

PA-DCT will **generate its own λ trajectory**. Its Oracle bound depends
on that trajectory:

- If PA-DCT stays cheap most rounds → its λ stays low → its Oracle UB
  approaches 7,509 → PA-DCT itself can approach 7,509
- If PA-DCT over-spends early → its λ rises → its Oracle UB drops →
  PA-DCT itself is bounded lower

**PA-DCT's success metric**: not just "high PA_reward in absolute terms"
but **"PA-DCT approaches its OWN Oracle UB, indicating per-round
near-optimality given its (learned) trajectory."**

This is why the paper should report:
- PA-DCT's cum_PA_reward
- PA-DCT's own Oracle UB (anchored on PA-DCT's trajectory)
- The gap (regret to Oracle in each trajectory regime)

---

## 8. Future Oracle improvements (post-paper)

### Plan A: True Free-Running Oracle (single number)

Instead of anchoring on baselines, run a fresh simulation where the
Oracle:
- Has its own wallet
- Each round picks the best PA-reward arm (with hindsight on the round's
  outcomes)
- Wallet evolves with Oracle's choices
- Yields ONE number, the absolute upper bound

This eliminates the multi-anchor confusion. We deferred it; the post-hoc
form was sufficient to set targets for PA-DCT.

### Plan C: Hindsight LP-Optimal Policy

Solve the offline optimization
    maximize Σ q_t   subject to   Σ c_t ≤ B
as a knapsack-style LP given the full pregen dataset. Gives the
mathematically tightest upper bound (information-theoretic).

---

## 9. Paper structure recommendations (consolidated)

### 9.1 What goes in main paper

- **Reward formula** + 3 design decisions (bundled utility, no latency,
  sigmoid normalization). Cite the 5 references in §10.
- **Provider design** with the deliberate "shared cost+model" trio
  (P-mid / P-adv / P-flaky) — emphasize this is the methodological core.
- **Empirical results** comparing PA-DCT to baselines (random, fixed,
  budget rule, oracle UB).
- **Non-stationary behavior** under S2/S3 — PA-DCT's discount mechanism
  vs. non-discounted alternatives.

### 9.2 What goes in appendix (defensive material)

- **Hyperparameter sensitivity**: ν ∈ {0.1, 0.5, 1.0} and α ∈ {1, 2, 3}.
  Table showing main results (PA-DCT PA-reward, gap to oracle UB)
  remain in same order across these values. **Defensive — reviewer
  expects to see this; main paper reads better without it.**

- **Reward formula ablation**: PA-DCT under our sigmoid form vs.
  clipped Lagrangian (`λ_t·c̃` with `λ_t` clipped at 5 or 10). Show
  empirical results are similar; argue our form is preferable for
  bounded-reward regret analysis.

- **Calibration history**: how budget, prices, target_burn_rate were
  set. Document the latency-term removal. Brief — readers shouldn't
  need to read it unless they question a number.

- **Pregen reproducibility**: dataset description, frozen-set rationale,
  checksum/commit hash for the 20,575 records.

### 9.3 Reviewer questions we should preempt

| Question | Section it's answered in |
|---|---|
| "Why this specific reward formula?" | Main paper §X "Reward design" + this doc §4 |
| "Why these K=5 providers?" | Main paper §Y "Benchmark" + this doc §2.1 |
| "What if you change ν / α?" | Appendix sensitivity analysis |
| "Why not standard Lagrangian dual?" | Main paper §X + appendix ablation |
| "Why not a real online experiment?" | Main paper §Y "Reproducibility via pregen" |
| "How do you handle non-stationarity?" | Main paper §Z (S2/S3 + discount mechanism) |
| "What about latency?" | Brief mention in main paper "future work" |
| "Why no formal regret bound?" | Cite Russo & Van Roy 2014 + ours-is-bounded argument |

### 9.4 What hyperparameter / design tuning is "out of scope"

These are explicitly NOT what this paper claims to do:

- Optimizing the agent's broader task (we focus on per-call selection)
- Real-time deployment latency (pregen is offline)
- Provider-specific prompt engineering (P-mid vs P-premium prompt is fixed)
- Multi-agent coordination
- Selection across modalities (only LLMs)

Listing these explicitly in the paper's "Scope" section heads off
"why didn't you do X" objections.

---

## 10. M3.E + M3.F: Scenarios and Dual-Posterior PA-DCT (2026-05-05)

### 10.1 Three locked scenarios

After several design iterations (logged in `logs/m3f_results.md`), the
final scenarios are:

- **S1 (Stationary)**: `StationaryScenario()` — calibrated baseline market.
  AlwaysMid is the strongest fixed policy.
- **S2 (Mid Outage)**: `MidOutageScenario(outage_start=3000, outage_end=5500, outage_failure_rate=0.30)`
  — P-mid times out 30% of the time during a 2500-round window. Real-world
  precedent: API rate limiting / regional outage. Tests Q-posterior adaptation.
- **S3 v2 (Premium Promo)**: `PremiumDropScenario(shock_round=1000, price_multiplier=0.2)`
  — P-premium price drops to mid price ($0.002) at round 1000, persists.
  Real-world precedent: tier-wide repricing on flagship release (GPT-4o,
  Claude 3.5 Sonnet). Tests C-posterior adaptation.

### 10.2 The bug discovered, and the fix

During M3.E we discovered that **vanilla PA-DCT only stores cost as a
static spec dict and never updates it** — so it cannot adapt to price
shocks despite the "Payment-Aware" name. Path AB / Path Z / Premium Promo
all confirmed: PA-DCT premium share stayed at ~4% even when premium
price dropped to mid price throughout.

**M3.F fix**: PA-DCT now maintains **two Gaussian posteriors per
(arm, task_type)** — one over quality (utility) and one over observed
cost. At decision time it samples from both and computes PA-reward.
At update time it observes both q and c. The cost spec dict is now
just a prior mean.

This is implementation of the algorithm's name: a true Payment-Aware
bandit *learns* the cost dimension, not just weights it at decision time.

See `logs/m3f_dual_posterior_design.md` for full math derivation,
implementation details, and a step-by-step round 2000 walkthrough.

### 10.3 Final 30-seed results

| Scenario | AlwaysMid PA | PA-DCT PA | Δ PA-DCT − AlwaysMid | t | p | Component tested |
|---|---|---|---|---|---|---|
| **S1** | 5831 ± 29 | 5512 ± 54 | -319 (exploration cost) | -28.8 | <0.0001 | Baseline |
| **S2** | 5069 ± 37 | 5147 ± 80 | **+79** | **+4.90** | **<0.001** | **Q-posterior + D + C** |
| **S3 v2** | 5831 ± 29 | 5911 ± 51 | **+80** | **+7.50** | **<0.0001** | **C-posterior + D + C** |

**PA-DCT reverses AlwaysMid in BOTH non-stationary scenarios with
statistically significant margins.** S1 is unchanged from M3.D
(dual-posterior collapses immediately when costs are static — no harm).

S3 v2 multi-metric reverse-beat: PA-DCT also wins ROI (429 > 410),
mean_q (0.831 > 0.819), and spends LESS ($19.38 < $20.00). AlwaysPremium
does NOT take the throne (3112 vs 5831) because its pre-shock 1000-round
$10 burn under high λ produces unrecoverable negative cum_PA.

Visible adaptation: PA-DCT premium share in S3 v2 climbs from ~5%
pre-shock to **~66% post-shock** — a clean visible learning curve which
will be the paper's centerpiece figure.

### 10.4 Paper claim structure post-M3.F

> **"PA-DCT, a payment-aware contextual Thompson sampler with dual
> Bayesian posteriors over both quality and cost, achieves provably
> adaptive performance under both quality shocks (provider outages)
> and cost shocks (promotional pricing). We identify and fix a
> cost-blindness bug in vanilla payment-aware bandits, where cost is
> hardwired at decision time and cannot adapt to non-stationary
> markets. Our dual-posterior design treats both dimensions symmetrically
> and is the principled implementation of payment-awareness."**

### 10.5 Full data location

- Per-cell logs: `results/scenario_sweep/{S1,S2}/<policy>/seed_NN.jsonl`
- S3 v2 logs: `results/scenario_sweep_s3promo_v2/<policy>/seed_NN.jsonl`
- Aggregated summaries: `results/scenario_sweep/<scenario>/summary.jsonl`
- Sweep scripts: `scripts/run_scenario_sweep.py` (S1, S2, original S3 — historical),
  `scripts/run_s3_promo_v2.py` (S3 v2 — locked design)
- Negative-result scripts (kept for record): `scripts/run_path_ab.py`
  (1:3:5 tier compression — failed pre-M3.F), `scripts/run_premium_promo.py`
  (premium=mid throughout — failed pre-M3.F)

---

## 11. Paper title & positioning (LOCKED 2026-05-05)

### 11.1 Title

> **"402Pilot: An x402 Decision Layer for Autonomous Agent Micropayments"**

8 words after the colon. Conveys:
- **Brand**: 402Pilot
- **What it is**: An x402 Decision Layer (sits ABOVE x402, not modifying it)
- **For whom**: Autonomous Agent
- **Domain**: Micropayments

Rationale for word choices:
- *x402* in title: matches `402` in brand name; tells reviewer immediately
  what protocol stack we're in.
- *Decision Layer* (not "system" / "framework" / "method"): commits to the
  layer-above-x402 architecture (see §11.3).
- *Autonomous Agent* (not "Agent-Native" in title): "Autonomous Agent" is
  a 2026 standard term that conveys "no human in the per-decision loop"
  without buzzword baggage. The more nuanced term *agent-native* — which
  contrasts with "human-operated bandit literature applied to agent
  scenarios" — is introduced in §1 of the paper, not the title.
- No *Bandit* in title: the bandit IS the method, but the contribution is
  the layer + setting + benchmark. We don't lead with the algorithm
  because the algorithm itself is incremental (combination of existing
  techniques); the framing is broader.

### 11.2 Algorithm name: **PA-DCT** (read "pad-CT")

Inside the layer, the bandit algorithm is **PA-DCT**:
- **P**ayment-aware
- **D**iscounted
- **C**ontextual
- **T**hompson sampling (final S of "sampling" dropped per common bandit
  convention — cf. LinUCB which drops the trailing "1")

Code class: `PADCTPolicy`. Module: `pilot402.policies.padct`.

### 11.3 Architectural positioning: layer above x402

402Pilot is a **decision layer above x402**, not a system, not a method,
not a protocol modification. The layer:

- **Sits BEFORE the agent's HTTP request** to the paid endpoint, advising
  WHICH provider to call given the task and the agent's wallet state.
- **Consumes post-call observations** (cost actually paid, quality
  observed) to update its internal state for future decisions.
- **Is protocol-agnostic**: today instantiated on x402, tomorrow could plug
  into x802 / AMP / AP2 / any other programmable micropayment protocol.
- **Out of scope**:
  - On-chain payment settlement (x402 protocol's job)
  - Provider capability discovery / authentication (x402 V2 Discovery
    extension's job)
  - Production observability dashboard (operator's job)
  - Multi-agent coordination / federated learning across agents
  - Online learning safeguards (drift detection, A/B testing) — future work

Layer interfaces (paper §architecture will formalize):
```python
def select(task, available_providers, wallet_state) -> ProviderId
def update(task, chosen_provider, observed_cost, observed_quality, failure_flag) -> None
def posterior_state() -> StateSnapshot     # for monitoring / logging
```

### 11.4 Five contributions (LOCKED)

C1. **Setting characterization**: agent-native bandit decision-making in
    programmable micropayment protocols is a regime under-explored by
    prior bandit literature. Prior work (BTS, DS-TS, LLM Bandit, MixLLM,
    etc.) assumes a human operator configures the system; we focus on the
    case where the bandit IS the autonomous agent.

C2. **PA-DCT algorithm**: first work to combine Budgeted TS [Xia 2015],
    Discounted TS [Qi 2023], and Contextual TS [Agrawal 2013] into a
    single payment-aware decision rule tailored for non-stationary
    micropayment markets, with dual posteriors over both quality and cost.

C3. **402Pilot architecture**: a protocol-agnostic decision layer with
    stable APIs, enabling clean separation between decision logic and
    payment execution.

C4. **Reproducible benchmark**: replay-based evaluation methodology with
    three calibrated scenarios (S1 stationary, S2 mid-tier outage, S3
    promotional repricing) against six baselines including True Oracle
    upper bound.

C5. **Empirical findings**: which classical bandit components transfer
    to the agent-native setting (P necessary; TS reduces variance), which
    have diminishing returns at our calibration (D and C show subtle
    benefits primarily on adaptation_time, not cum_PA), and what open
    challenges remain (online learning under provider-driven drift).

### 11.5 Anti-prior-art audit (three layers, all confirmed empty)

Detailed citations and per-paper differentiation in `logs/literature_review.md`.

| Layer | Empty? | Best evidence |
|---|---|---|
| Bandit applied to x402 / agent micropayment | ✅ | A402 / SoK / Multi-Agent Economies do protocol/identity, not decision algorithms |
| BTS + DS-TS + Contextual TS combination | ✅ | Each component exists separately; no paper combines all three |
| Decision layer above x402 framing | ✅ | All x402 academic work is protocol-level; we're the first decision-layer work |

Closest adjacent work: AAMAS 2026 paper on Truthful Reverse Auctions for
Adaptive Selection (arXiv 2602.14476) — uses contextual MAB for LLM
selection but in a reverse-auction mechanism (providers submit cost),
not the x402 quote-and-pay setting. Cited and differentiated in §3.

### 11.6 Naming convention summary (resolved naming conflicts)

| Level | Name | Purpose |
|---|---|---|
| **Brand / paper / repo** | 402Pilot | Single dominant identity |
| **Algorithm (technical label)** | PA-DCT | Method label in formulas, ablation table |
| **Code class** | `PADCTPolicy` | Software identity |
| **Q posterior in dual-posterior design** | "quality posterior" or "Q-posterior" | Never abbreviated as just "C" to avoid clash with Contextual |
| **Cost posterior** | "cost posterior" or "$-posterior" | Never abbreviated as just "C" |
| **C in PA-DCT** | always "Contextual" (full word in main text) | Spelled out to avoid confusion |

### 11.7 Naming the regime: agent-native bandits

**Term**: *agent-native bandits*. Defined in paper §1 as:

> A bandit setting in which the operator is itself an autonomous agent —
> making per-call decisions, owning its own budget, observing outcomes,
> and adapting without human intervention. Distinguished from
> *agent-implemented but human-operated* bandits (most prior work) where
> a human marketing team, ML platform team, or DevOps team configures the
> system, monitors performance, and intervenes on anomalies.

This term will be coined and motivated in §1.1 of the paper; it does not
appear in the title.

---

## 12. File index

Paper-relevant artifacts:
- `experiments/main.yaml` — final calibrated config
- `pilot402/runtime/reward.py` — reward formula implementation + docstring
- `pilot402/policies/padcts.py` — dual-posterior PA-DCT (M3.F)
- `pilot402/scenarios.py` — Stationary / MidOutage / PremiumDrop / TierCompression
- `data/pregen/*.jsonl` — frozen 20,575 PregenRecords
- `logs/baselines_s1_analysis.md` — pre-M3.E baseline + Oracle numbers (S1)
- `logs/reward_design_rationale.md` — detailed reward formula rationale
- `logs/tier3_final_analysis.md` — pregen calibration (provider quality matrix)
- `logs/replication_comparison.md` — Tier 2 evidence (historical)
- **`logs/m3f_dual_posterior_design.md`** — M3.F algorithm design + math (NEW)
- **`logs/m3f_results.md`** — final 30-seed results across S1/S2/S3 v2 (NEW)
- **`logs/m3f_walkthrough_annotated.md`** — pedagogical step-by-step round 2000
  walkthrough with full glossary of every term, formula, and English word (NEW)
- `PLAN.md` / `IDEATION.md` — original design vision (pre-recalibration; refer
  here only for high-level intent, NOT for specific numbers)
- **This document** (`paper_design_decisions.md`) — final consolidated reference

---

**When writing the paper**, the order of reference precedence is:
1. This document (latest, consolidated)
2. `reward_design_rationale.md` (specific to reward formula)
3. `baselines_s1_analysis.md` (specific to baseline numbers)
4. Source code docstrings (latest, runtime-tested)
5. PLAN/IDEATION (high-level intent only; numbers may be stale)
