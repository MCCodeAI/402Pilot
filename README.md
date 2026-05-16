# 402Pilot: An x402 Decision Layer for Autonomous Agent Micropayments

**402Pilot** is a decision layer that sits above x402-style micropayment protocols. It gives autonomous agents an online policy for deciding *which* paid service to call — balancing output quality against cost under a fixed wallet budget, without prior knowledge of provider behavior.

The core algorithm is **PA-DCT** (Payment-Aware Discounted Contextual Thompson sampling): a budget-aware, non-stationary contextual bandit that learns from reward feedback across irreversible per-call payments, with dual Q- and cost posteriors.

---

## The Problem

x402 solves payment *execution*. It does not solve payment *decision*.

An agent with a $50 wallet and five provider options — ranging from cheap-but-unreliable to premium-but-expensive, including an adversarial provider that sounds correct but isn't, and a flaky provider that times out 40% of the time — cannot rely on static rules to allocate spend well. The right choice depends on the task type, remaining budget, and how each provider has been performing lately.

402Pilot learns this on the fly.

---

## Key Design Points

**Decision layer, not a protocol fork.** 402Pilot makes its selection decision before the HTTP request hits the paid endpoint. x402 handles settlement unchanged.

**Bandit, not RL.** Only the chosen arm is observed per round (bandit feedback). Payments are irreversible. No long-horizon credit assignment is needed within a single service call.

**PA-DCT reward signal.** Bounded in [-1, +1] via sigmoid weighting:

```
utility   = q − ν · f                                # tracks intrinsic provider quality
λ_norm    = λ_t / (1 + λ_t)                          # sigmoid budget pressure ∈ (0, 1)
PA_reward = (1 − λ_norm) · utility − λ_norm · c̃     # ranking criterion at decision time
```

`q` is task quality, `c̃` is normalized cost, `f` is a failure flag, `λ_t` is a budget-pressure multiplier that rises as the wallet depletes. Posterior updates use `utility` (λ-free), so the policy's beliefs track provider quality independently of decision-time budget pressure. The latency term in earlier drafts was retired — no provider in this benchmark specifies a latency profile, and ablations showed it contributed ~1% of reward magnitude.

**Dual posteriors over (Q, cost).** Each (arm, task-type) bucket maintains separate Gaussian posteriors for Q (utility as the service-quality signal) and cost, both with discount factor γ=0.999. The cost posterior lets the policy detect price shocks (S3) the same way the Q-posterior detects degradation (S2).

**Non-stationarity via discounted sufficient statistics.** Exponential discount on per-arm posteriors lets the policy adapt to provider drift without forgetting stable arms too quickly.

If `latexmk` is missing:

```bash
cd paper
pdflatex main && bibtex main && pdflatex main && pdflatex main
```

Five heterogeneous provider agents, four evaluation buckets, three market scenarios, 30 seeds × 10,000 rounds per cell. All responses pre-generated from real LLM calls (20,575 frozen `PregenRecord`s); experiments replay from fixed fixtures for reproducibility.

| Provider   | Model         | Special behavior                                |
| ---------- | ------------- | ----------------------------------------------- |
| P-cheap    | qwen3.5-flash | Uniform prompt                                  |
| P-mid      | GPT-5.4-mini  | Uniform prompt                                  |
| P-premium  | GPT-5.4       | Uniform prompt                                  |
| P-adv      | GPT-5.4-mini  | Adversarial system prompt (fluent but wrong)    |
| P-flaky    | GPT-5.4-mini  | 40% timeout injection                           |

P-mid, P-adv, and P-flaky share the same cost tier ($0.002) and base model. A rule-based policy cannot distinguish them — PA-DCT must learn the distinction from reward feedback alone.

| Scenario                | Event                                                                                              |
| ----------------------- | -------------------------------------------------------------------------------------------------- |
| **S1 — Stationary**     | No mid-run changes; baseline market.                                                               |
| **S2 — Mid outage**     | P-mid fails 30% of the time during rounds 3,000–5,500 (timeout injection); fully recovers after.   |
| **S3 — Premium promo**  | P-premium price drops at round 1,000 from $0.01 → $0.002 (matches mid); the agent has 9,000 rounds to detect the shift via the cost posterior and migrate. |

---

## Quickstart

```bash
# 1. Install in editable mode (Python ≥ 3.11)
pip install -e .

# 2. Run unit tests
pytest

# 3. Quick end-to-end smoke (3 scenarios × 3 seeds × 200 rounds; all policies + oracle)
python -m scripts.run_scenario_sweep --num-seeds 3 --num-rounds 200 --out-dir results/smoke

# 4. Full main sweep (30 seeds × 10,000 rounds × 7 policies × 3 scenarios)
python -m scripts.run_scenario_sweep

# 5. Four-component ablation matrix
python -m scripts.run_ablation_matrix

# 6. Compute the four official metrics
python -m scripts.compute_ablation_metrics
```

Configuration is in `experiments/main.yaml`. Pregen data lives in `data/pregen/*.jsonl`.

---

## Comparators

Six baselines plus an offline upper bound, all run on identical seeds:

| Policy            | Type                                                          |
| ----------------- | ------------------------------------------------------------- |
| Random            | Uniform random over affordable arms                           |
| Always-P-cheap    | Fixed (cheapest)                                              |
| Always-P-mid      | Fixed (mid tier)                                              |
| Always-P-premium  | Fixed (strongest non-adaptive)                                |
| Budget rule       | Threshold heuristic over remaining budget                     |
| **PA-DCT**        | **Ours** (dual-posterior contextual TS with budget penalty)   |
| True Oracle       | Free-running with hindsight per-round arm peek (upper bound)  |

**Four-component ablation** (each removes one PA-DCT component):

- **−P** (Payment-aware): policy ranks by raw utility instead of `(1−λ_norm)·u − λ_norm·c̃`
- **−D** (Discount): γ = 1 (no forgetting)
- **−C** (Contextual): single global bucket instead of per-task-type buckets
- **−TS** (Thompson sampling): greedy on posterior mean instead of sampling

---

## Headline Results

PA-DCT has the most robust non-oracle trade-off profile across quality, ROI, and PA-gap. It is not the winner of every individual metric: cheap fixed routing maximizes ROI by under-spending, and some fixed/rule policies win isolated quality cells. The main result is that PA-DCT adapts under both reliability and price shocks while staying top-three on every rank-comparable main-table metric. Detail:

| Scenario | Full PA-DCT cum_PA | vs Oracle gap | Adaptation time          |
| -------- | ------------------ | ------------- | ------------------------ |
| S1       | 5512 ± 54          | 1325          | n/a (no shock)           |
| S2       | 5147 ± 80          | 1662          | 1467 rounds (30/30)      |
| S3 v2    | 5911 ± 51          | 1206          | 200 rounds (30/30)       |

Ablations reveal that **P** is uniformly necessary (cum_PA collapses to negative without it), **D** primarily speeds up shock recovery (35% faster in S2), **C** helps when task-type heterogeneity is exploitable (S3) but not when shocks are uniform (S2), and **TS** reduces seed variance 5–9× without changing the mean. See `logs/ablation_4metrics_table.md` for the full 4 × 4 × 3 matrix.

For workshops, also set `\workshoptitle{...}` after `\title{...}`.

## Notation reference

```
402Pilot/
├── docs/               # Design documents
│   ├── paper_outline.md
│   ├── system_design.md
│   ├── experiment_design.md
│   └── code_structure.md
├── pilot402/           # Python package
│   ├── core/           # types, config, seeds, interfaces (Protocols)
│   ├── pregen/         # frozen-fixture loaders for replay
│   ├── policies/       # PADCTPolicy + 5 baselines
│   ├── runtime/        # main bandit loop + Oracle loop
│   └── scenarios.py    # S1 / S2 / S3 transforms
├── experiments/        # Locked YAML configs
├── scripts/            # CLI entry points (sweeps, ablations, metrics)
├── data/               # Frozen pregen + tasks (gitignored bulk)
├── results/            # Run outputs (gitignored)
├── viz/                # Interactive explainer (React + Vite, GitHub Pages)
├── logs/               # Design-decision docs + analysis writeups
└── tests/              # unit and integration tests
```

Full module layout: [`docs/code_structure.md`](docs/code_structure.md). All paper-relevant decisions consolidated in [`logs/paper_design_decisions.md`](logs/paper_design_decisions.md). Anti-prior-art audit in [`logs/literature_review.md`](logs/literature_review.md).

---

## Status

| Component                      | Status        |
| ------------------------------ | ------------- |
| Pre-generation (LLM calls)     | ✅ Complete (20,575 records) |
| Core implementation            | ✅ Complete |
| Main sweep S1/S2/S3            | ✅ Complete (30 seeds × 7 policies) |
| 4-component ablation matrix    | ✅ Complete (360 cells) |
| 4 official metrics             | ✅ Computed |
| Statistical significance       | ✅ Computed |
| Hyperparameter sensitivity     | ✅ γ sweep reported in appendix |
| Paper writing                  | 🟡 In progress |
| Interactive viz (`viz/`)       | ✅ Built; data fixtures regenerated against locked sweeps |
| Paper figures                  | ⏳ Deferred to paper finalization |

---

## License

MIT
