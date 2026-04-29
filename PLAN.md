# 402Pilot — Master Project Plan

> Single source of truth for the 402Pilot paper. All other planning documents
> live under `docs/` and are linked from here.

---

## 1. Title and thesis

**Title.** 402Pilot: Learning What to Pay For in Agent Micropayment Markets

**One-sentence thesis.** *x402 makes agents able to pay; 402Pilot makes agents
decide what is worth paying for.*

**Positioning sentence.** We formulate paid service selection in x402-based
agent micropayment markets as a budget-aware, non-stationary contextual bandit
problem, instantiate it with Payment-Aware Discounted Contextual Thompson
Sampling (PA-DCTS) — a policy that sits as a *finance layer* above x402 — and
evaluate it on 402Pilot-Bench, a pre-generated benchmark grounded in real LLM
outputs across five heterogeneous providers under three market scenarios.

---

## 2. Document map

| Document | Purpose |
|---|---|
| `IDEATION.md` | Original ideation. Read-only reference. |
| `PLAN.md` (this) | Master plan, key decisions, roadmap. |
| `docs/paper_outline.md` | Paper structure, section-by-section skeleton. |
| `docs/system_design.md` | 402Pilot finance-layer architecture and module contracts. |
| `docs/experiment_design.md` | The single comprehensive evaluation (402Pilot-Bench). |
| `docs/code_structure.md` | Repository layout and module responsibilities. |

---

## 3. Key decisions

### 3.1 System brand: `402Pilot`
Every artifact, code identifier, and paper mention uses `402Pilot`. This ties
the brand directly to HTTP 402 / x402.

### 3.2 Single unified evaluation: 402Pilot-Bench
All experiments collapse into one framework with three within-experiment
scenarios (S1 stationary, S2 abrupt degradation, S3 price shock). Every
experimental decision triggers a real x402 payment; there is no x402-bypass
code path. All runs execute on a **local DEVnet (Anvil fork of Base)** for
speed and reproducibility. Public testnet replication is not part of the current
experiment plan; if reviewers require real-network validation, a reduced subset
can be replicated on a public testnet at that point.

### 3.3 One named algorithm: PA-DCTS
Single algorithm name: **Payment-Aware Discounted Contextual Thompson Sampling
(PA-DCTS)**. "Payment-aware" covers cost penalty, budget-pressure λ_t, failure
penalty, and latency penalty — all tied to the act of paying. All ablations are
framed as removals from PA-DCTS (A1 no-context, A2 no-discount, A3 no-budget-λ,
A4 no-failure-penalty).

### 3.4 No formal regret theorem
PA-DCTS combines existing contextual TS and discounted TS techniques. A new
bound would be a trivial corollary or require unjustified novelty claims. The
method section contains a short *Theoretical properties* paragraph citing prior
regret guarantees and noting which conditions transfer.

### 3.5 Concrete market shape
- **K = 5 providers:** P-cheap (Qwen3-8B, no tools), P-mid (GPT-5.4-mini,
  BM25), P-premium (GPT-5.4, CoT + tools), P-adv (GPT-5.4-mini + adversarial
  system prompt), P-flaky (GPT-5.4-mini + 20% timeout injection). P-mid /
  P-adv / P-flaky share cost tier and base model — only reward feedback
  distinguishes them.
- **M = 3 task types:** T1 Coding (HumanEval, pass@1), T2 Multi-hop QA
  (HotpotQA, EM/F1), T3 Web Search (TriviaQA-web closed + custom open-ended).
- **T = 10,000** rounds per run.
- **N = 30** seeds per (policy × scenario) cell.
- **Budget B** sized so *Always-P-premium* exhausts wallet near round ~5,000.

### 3.6 Target venues
- **Primary:** NeurIPS (main track or Datasets & Benchmarks).
- **Secondary:** ICML, AAAI, UAI.

Paper written to NeurIPS-style budget: 9 pages content + unbounded refs +
appendix.

### 3.7 Scope boundaries (what we do not claim)
- Not a new x402 / payment-protocol design.
- Not a new Thompson Sampling algorithm.
- Not a reputation, escrow, or dispute system.
- Not long-horizon RL for agent planning.
- Complementary to A402 (post-selection atomicity); orthogonal to LLM routing
  within a single inference platform.

---

## 4. Contributions

1. **Problem formulation.** Paid service selection in x402-based agent
   micropayment markets as a budget-aware, non-stationary contextual bandit
   problem with bandit feedback over irreversible payments.
2. **Finance-layer system.** 402Pilot, an architecture that sits above x402
   and decides which paid service to invoke *before* payment execution.
3. **Algorithm.** PA-DCTS — combining contextual task/difficulty awareness,
   discounted non-stationarity adaptation, and dynamic budget-pressure cost
   weighting.
4. **Benchmark.** 402Pilot-Bench, a controlled micro-economy benchmark with
   pre-generated real LLM outputs, five heterogeneous providers, and three
   scripted market scenarios.

---

## 5. Roadmap

| Phase | Description | Status |
|---|---|---|
| **0 — Plan finalization** | All `docs/` frameworks approved and consistent. | ✅ Done |
| **1 — Pre-generation & scaffolding** | Run ~20,625 LLM API calls to generate 402Pilot-Bench dataset; implement replay environment, scenario scheduler, workload sampler; smoke tests with fixed comparators. | ⬜ Next |
| **2 — Policy zoo + PA-DCTS** | Implement all comparators (Always-P-premium, Budget rule, Oracle) and PA-DCTS with ablations A1–A4; unit-test against pre-generated dataset. | ⬜ |
| **3 — Full evaluation** | Run 402Pilot-Bench across S1–S3, all comparators and ablations, 30 seeds; produce all figures and tables. | ⬜ |
| **4 — Paper writing** | Write sections in order per `docs/paper_outline.md`. | ⬜ |
| **5 — Polish & submission** | Appendix, reproducibility checklist, code + dataset release. | ⬜ |
