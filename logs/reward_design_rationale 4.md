# Reward Function Design Rationale (Paper Reference)

**Date**: 2026-05-02 (final, post Tier 3 + baseline analysis)

This document captures the *why* behind every term in PA-DCT's reward formula.
It is intended as input to the paper's "Reward design" subsection (~3 paragraphs)
and to head off reviewer questions about hyperparameter choices.

## Final formula

```
utility    = q − ν · f                                ∈ [-ν, +1]
λ_norm     = λ_t / (1 + λ_t)                          ∈ (0, 1)
PA_reward  = (1 − λ_norm) · utility − λ_norm · c̃      ∈ [-1, +1]
```

where:

- `q` is the task quality score (pass@1 / EM·F1 / LLM-judge, all in [0, 1])
- `f ∈ {0, 1}` is the failure indicator
- `ν = 0.5` is the failure penalty weight (constant across the paper)
- `c̃ = cost / max_provider_cost ∈ [0, 1]` is normalized cost
- `λ_t = exp(α · burn_excess_t)` is the wallet's budget-pressure multiplier
(α = 2, see `pilot402/runtime/wallet.py`)
- `λ_norm = λ_t / (1 + λ_t) = sigmoid(log λ_t) = sigmoid(α · burn_excess_t)`

The policy posterior is updated with `utility`; the policy's per-round
arm selection ranks arms by `PA_reward`. This separation (system_design §2.6)
keeps the posterior tracking intrinsic provider quality independent of
decision-time budget pressure.

## Three deliberate design decisions

### 1. Bundle quality and failure into a single "utility"

**Decision**: `utility = q − ν · f`. We treat quality and failure as a single
composite axis ("did we get a useful answer?") rather than two independent
reward channels.

**Rationale**: failure is the *limiting case* of zero quality. When P-flaky
times out, q = 0 already (no scorable response exists); the failure flag
adds a structural penalty `ν · f` that captures the operational cost of "no
response" (forced retry, broken call chain, user-facing latency) beyond the
zero-quality signal alone. Both terms move along the same axis — task
delivery — and bundling them lets the formula's two-tier structure stay
clean: an "intrinsic value" (utility) modulated by a budget weighting
(λ_norm).

A reviewer might ask: "If `q = 0` already on failures, isn't `ν · f`
double-counting?" Our answer: yes, by design. The double-count distinguishes
two scenarios that produce identical `q = 0` but mean different things in
practice:


|                                | q   | f   | utility   |
| ------------------------------ | --- | --- | --------- |
| Provider returned wrong answer | 0   | 0   | 0         |
| Provider timed out / failed    | 0   | 1   | -ν = -0.5 |


This distinction is important for our experimental design. P-flaky shares
**cost, base model, and surface prompt** with P-mid; the *only* dimension
distinguishing them is reliability. Without `ν · f`, P-flaky would be
indistinguishable from a marginally-lower-quality P-cheap from the bandit's
reward signal alone — and the entire point of the P-flaky vs P-mid
comparison would collapse.

### 2. Drop the latency term

**Decision**: an earlier draft included `μ · l̃` for latency penalty. We
removed it on 2026-05-02.

**Rationale**: a term in the reward formula must correspond to a designed
dimension of the experiment. Three checks for latency:

1. **No provider in our K=5 specifies a latency profile.** The latency_s
  field in the pregen records is incidental wallclock from the actual
   API call; we did not design "P-cheap is fast, P-premium is slow" as a
   provider distinguishing characteristic.
2. **No scenario manipulates latency.** S1 (stationary), S2 (quality
  degradation + flaky timeout spike), S3 (price shock) all leave latency
   alone. There is no "latency shock" scenario.
3. **Empirically, μ · l̃ contributed ~1% of cumulative reward magnitude**
  (Always-Mid total reward ≈ 7,500; latency contribution ≈ 73). It
   was paying for its hyperparameter cost (one more `μ` to defend) with
   essentially no signal.

Latency-aware bandits are a clean follow-up paper: introduce per-provider
latency profiles, add an S4 latency-spike scenario, retain the term.
That's not this paper.

### 3. Sigmoid-normalize the cost penalty

**Decision**: replaced `q − λ · c̃` with `(1 − λ_norm) · utility − λ_norm · c̃`
where `λ_norm = λ / (1 + λ)`.

**Rationale**: the original `λ · c̃` form is the standard Lagrangian dual
for the budget constraint, and λ updating multiplicatively from
`exp(α · burn_excess)` is consistent with online convex optimization
literature. But it has two practical problems:

1. **Asymmetric scale.** With q ∈ [0, 1] and λ ∈ [0, ∞), the cost penalty
  can dominate quality entirely. In our experiments, Always-Premium had
   λ ≈ 7.4, making the per-round PA_reward ≈ 0.86 − 7.4 = −6.5. Cumulative
   over 5,000 rounds = −32,665. The "quality" half of the reward formula
   was nearly invisible relative to the cost half.
2. **Standard regret bounds require bounded reward.** Algorithms like
  UCB, Thompson Sampling, and their discounted variants have regret
   guarantees that scale with the reward range. Unbounded reward forces
   the paper into "we observe empirically" claims rather than principled
   bounds.

The convex combination `(1 − λ_norm) · utility − λ_norm · c̃` with
`λ_norm = sigmoid(log λ)` keeps reward bounded in [-1, +1] and gives a
natural reading: λ_norm is the *fraction of decision weight* given to cost
vs. utility. Low λ ("no budget pressure") → all weight on utility; high λ
("severe over-spend") → all weight on -cost. The transition is smooth.

Algebraic equivalence: `λ / (1 + λ) = sigmoid(ln λ)`. Since the wallet
already returns `λ = exp(α · burn_excess)`, the reward calculator computes
`λ / (1 + λ)` directly without re-deriving `burn_excess`.

## Why nu = 0.5 specifically

A failure costs `ν` units of utility. Setting `ν = 0.5` means a single
failure ≈ losing half a perfect-quality round.


| ν                | E[utility] for P-flaky | Interpretation                                        |
| ---------------- | ---------------------- | ----------------------------------------------------- |
| 0.0              | 0.486                  | Failure = wrong answer; bandit can barely distinguish |
| 0.1              | 0.446                  | Mild penalty                                          |
| **0.5 (locked)** | **0.286**              | **Strong but bounded**                                |
| 1.0              | 0.086                  | Failure ≈ "anti-success"; very strong penalty         |
| 2.0              | -0.314                 | Single failure dominates the round                    |


We picked **ν = 0.5** because:

1. It makes P-flaky's gap to P-mid (Δ = 0.286 vs 0.81 = 0.524) clearly
  detectable above the typical reward noise (σ ≈ 0.15) without dominating
   the cost-vs-quality story.
2. It is symmetric: a failure costs the same as half a quality unit, so
  reward magnitudes stay roughly balanced.
3. It is *not* tuned per provider — fixed across all experiments per the
  "no per-experiment hyperparameter tuning" commitment in PLAN §3.5.

We acknowledge `ν = 0.5` is a heuristic, not a derived constant. The
paper's appendix should include a sensitivity analysis showing main results
are robust for `ν ∈ {0.1, 0.5, 1.0}`.

## What ν was NOT chosen for

We did not pick `ν` to inflate any specific result. In particular, with the
sigmoid normalization, `ν` only affects `utility` directly; the cost-vs-
utility weighting (λ_norm) is independent. A larger `ν` makes failures
sharper but does not change the fundamental P-flaky < P-mid relationship.

## Equivalent forms (for paper math)

The PA_reward formula is equivalent to:

```
PA_reward = utility − λ_norm · (utility + c̃)
          = utility − [λ_t / (1 + λ_t)] · (utility + c̃)
```

This makes the budget pressure interpretation explicit: a "cost-aware"
adjustment that *subtracts* an amount proportional to (utility + c̃),
weighted by sigmoid-bounded budget pressure.

Equivalently, in the form most familiar to bandit theorists:

```
PA_reward = utility − [λ_norm / (1 − λ_norm)] · c̃ · (1 − λ_norm)
          = utility − λ_t · c̃ · (1 − λ_norm)
          = utility − λ_eff · c̃        (where λ_eff = λ_t · (1 − λ_norm) ∈ [0, 1])
```

So one can read it as the standard `r = u − λ · c̃` form with an effective
λ_eff bounded in [0, 1]. The sigmoid does the bounding implicitly.

## Numerical examples (post-recalibration)

Reward magnitudes for 4 typical (provider, λ) combinations at S1 stationary:


| Provider × policy       | q    | f   | c̃   | λ_t  | utility | λ_norm | PA_reward |
| ----------------------- | ---- | --- | ---- | ---- | ------- | ------ | --------- |
| Always-Cheap (low λ)    | 0.62 | 0   | 0.05 | 0.17 | 0.62    | 0.145  | 0.523     |
| Always-Mid (mod λ)      | 0.81 | 0   | 0.20 | 0.30 | 0.81    | 0.231  | 0.577     |
| Always-Premium (high λ) | 0.86 | 0   | 1.00 | 7.40 | 0.86    | 0.881  | -0.779    |
| P-flaky timeout cell    | 0.00 | 1   | 0.20 | 0.30 | -0.50   | 0.231  | -0.431    |


Cumulative over 10,000 rounds (or 5,000 for Always-Premium until bankruptcy)
gives the new baseline numbers reported in `logs/baselines_s1_analysis.md`.

## Files

- Reward implementation: `pilot402/runtime/reward.py`
- Reward config: `pilot402/core/config.py::RewardConfig`
- This rationale: `logs/reward_design_rationale.md`
- Baseline numbers under new formula: `logs/baselines_s1_analysis.md`

