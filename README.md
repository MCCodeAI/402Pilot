# 402Pilot: Learning What to Pay For in Agent Micropayment Markets

**402Pilot** is a finance layer that sits above x402-style micropayment protocols. It gives AI agents an online policy for deciding *which* paid service to call — balancing output quality, cost, latency, and reliability under a fixed wallet budget, without prior knowledge of provider behavior.

The core algorithm is **PA-DCTS** (Payment-Aware Discounted Contextual Thompson Sampling): a budget-aware, non-stationary contextual bandit policy that learns from reward feedback across irreversible per-call payments.

> Paper target: NeurIPS / ICML / AAAI (9 pages). Status: **pre-implementation — plan and experiment design locked.**

---

## The Problem

x402 solves payment *execution*. It does not solve payment *decision*.

An agent with a $10 wallet and five provider options — ranging from cheap-but-unreliable to premium-but-expensive, including one adversarial provider that sounds correct but isn't, and one flaky provider that times out 20% of the time — cannot rely on static rules to allocate spend well. The right choice depends on the task type, remaining budget, and how each provider has been performing lately.

402Pilot learns this on the fly.

---

## Key Design Points

**Finance layer, not a protocol fork.** 402Pilot makes its selection decision before the HTTP request hits the paid endpoint. x402 handles settlement unchanged.

**Bandit, not RL.** Only the chosen arm is observed per round (bandit feedback). Payments are irreversible. No long-horizon credit assignment is needed within a single service call.

**PA-DCTS reward signal:**

```
r_t = q_t − λ_t · c̃_t − μ · l̃_t − ν · f_t
```

where `q_t` is task quality, `c̃_t` is normalized cost, `l̃_t` is normalized latency, `f_t` is a failure flag, and `λ_t` is a budget-pressure multiplier that rises as the wallet depletes.

**Non-stationarity via discounted sufficient statistics.** Exponential discount on per-arm posteriors lets the policy adapt to provider drift (quality degradation, price shocks) without forgetting stable arms too quickly.

---

## Benchmark: 402Pilot-Bench

Five heterogeneous provider agents, three task types, three market scenarios, 30 seeds × 10,000 rounds per cell. All responses pre-generated from real LLM calls; experiments replay from fixed fixtures for reproducibility.

| Provider | Model | Special behavior |
|---|---|---|
| P-cheap | Qwen3-8B | No tools, parametric memory only |
| P-mid | GPT-5.4-mini | BM25 retrieval |
| P-premium | GPT-5.4 | CoT + code execution |
| P-adv | GPT-5.4-mini | Adversarial system prompt (fluent but wrong) |
| P-flaky | GPT-5.4-mini | 20% timeout injection |

P-mid, P-adv, and P-flaky share the same cost tier and base model. A rule-based policy cannot distinguish them — PA-DCTS must learn the distinction from reward feedback alone.

| Scenario | Event |
|---|---|
| S1 — Stationary | No changes |
| S2 — Abrupt degradation | P-premium quality drops at round 3,000; P-flaky timeout rate spikes at round 5,000 |
| S3 — Price shock | P-premium doubles, P-mid halves at round 5,000 |

---

## Repository Layout

```
402Pilot/
├── docs/               # Design documents
│   ├── paper_outline.md
│   ├── system_design.md
│   ├── experiment_design.md
│   └── code_structure.md
├── pilot402/           # Python package (to be implemented)
├── experiments/        # Experiment configs (YAML)
├── scripts/            # CLI entry points
├── viz/                # Interactive explainer (GitHub Pages, writing phase)
├── paper/              # LaTeX sources (writing phase)
├── results/            # Run outputs (gitignored)
└── tests/
```

Full module layout: [`docs/code_structure.md`](docs/code_structure.md)

---

## Interactive Explainer

A companion web app (React + D3, deployed to GitHub Pages) will ship alongside the paper with three sections:

- **Algorithm Explainer** — animated PA-DCTS loop; Thompson Sampling posterior evolution per provider
- **Simulation Replay** — round-by-round playback with scrubber; P-adv / P-flaky detection events highlighted
- **Results Dashboard** — cumulative regret curves, ROI evolution, provider selection heatmaps, ablation comparison

> Status: planned. Implementation follows experiment completion.

---

## Comparators

| Policy | Type |
|---|---|
| Always-P-premium | Fixed (strongest non-adaptive) |
| Budget rule | Rule-based (strongest hand-crafted) |
| **PA-DCTS** | **Ours** |
| Oracle | Offline upper bound (not available online) |

Ablations A1–A4 remove one PA-DCTS component at a time (context, discount, budget-aware λ, failure penalty) to isolate each contribution.

---

## Status

| Component | Status |
|---|---|
| Paper outline | ✅ Locked |
| System design | ✅ Locked |
| Experiment design | ✅ Locked |
| Code structure | ✅ Locked |
| Pre-generation (LLM calls) | ⏳ Pending |
| Core implementation | ⏳ Pending |
| Experiments | ⏳ Pending |
| Interactive explainer | ⏳ Pending |
| Paper writing | ⏳ Pending |

---

## License

MIT
