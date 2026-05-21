# 402Pilot: Learning What to Pay For in Agent Micropayment Markets
## System Design — Finance Layer

This document specifies the *what* of every component, plus the contracts
between them. The *how* (concrete algorithms, data structures, calibration
constants) is deferred to implementation.

---

## 1. Layer position

402Pilot is a **decision layer above x402**. It does not replace, fork, or
modify the x402 protocol. Its *selection decision* is made before the agent's
HTTP request hits the paid endpoint; its learning loop then consumes the
post-call outcome to update future decisions:

```
[Agent Planner]
      │  (task descriptor)
      ▼
┌─────────────────────────────────────────────────────────┐
│                      402Pilot                           │
│                                                         │
│  Context Encoder → Budget Manager → Service Selector    │
│                                            │            │
│                                            ▼            │
│                                  (chosen provider a*)   │
└─────────────────────────────────────────────────────────┘
      │
      ▼
[x402 Payment Executor]  ──→  [Provider a*]
      │
      ▼
   {response, cost, latency, failure_flag}
      │
      ▼
[Evaluator]  →  q_t  →  [Reward Calculator]  →  [Policy Updater]
```

A402-style atomic settlement, escrow, and dispute are *out of scope* and
treated as orthogonal. Anything 402Pilot needs from the x402 stack is exposed
through a thin wrapper interface so the layer can target multiple x402
implementations.

---

## 2. Components

### 2.1 Context Encoder
- **Input.** A task descriptor: type label, prompt content, optional metadata
  (deadline, target quality), historical agent state, and the current budget
  manager snapshot.
- **Output.** A fixed-dimension feature vector \(x_t \in \mathbb{R}^d\).
- **Initial feature set.**
  - Task type (one-hot over 4 sub-types: T1 coding, T2 multi-hop QA,
    T3a web-search closed-form, T3b OpenAssistant open-ended QA). T3a/T3b are
    treated as separate types because they use different evaluators
    (deterministic EM/F1 vs. LLM-as-judge); see §2.5.
  - Difficulty estimate (scalar, [0,1]).
  - Prompt-length / output-type signals (a few scalars).
  - Remaining-budget ratio.
  - Remaining-time ratio (rounds left / total).
  - Per-provider EWMA quality, cost, latency, failure (4 × K scalars).
  - Time-since-last-update per provider (K scalars).
- **Contract.** Pure function: same inputs → same vector. No side effects.
- **Notes.** Difficulty estimator is pluggable (heuristic, lightweight model,
  or LLM judge). Default: heuristic by task-type + prompt length.

### 2.2 Budget Manager
- **State.** Total budget B, remaining budget B_remaining, total rounds T,
  remaining rounds T_remaining, per-round running spend statistics.
- **Outputs.**
  - The cost-penalty multiplier \(\lambda_t\) used in the reward.
  - Per-candidate affordability signals; candidates with cost above remaining
    budget are blocked, and the round aborts only when no candidate is
    affordable.
- **Policy for \(\lambda_t\).** Monotone non-decreasing in budget pressure.
  Final form (locked 2026-05-02):
  \[ \lambda_t = \exp\!\big(\alpha \cdot \mathrm{burn\_excess}_t\big), \qquad
     \mathrm{burn\_excess}_t = \max\big(0,\ \mathrm{burn\_rate}_t - \mathrm{target\_rate}\big). \]
  The Reward Calculator (§2.6) feeds this into the bounded form
  \(\lambda_{\mathrm{norm}} = \lambda_t / (1 + \lambda_t)\). \(\alpha = 2\)
  is fixed across the paper.
- **Contract.** Idempotent reads. In the sequential benchmark runner, write
  only via `record_spend(c)` after a paid call resolves, where `c` is the
  actual charged amount. A budget block or uncharged payment failure records
  zero spend. Concurrent or live deployments must use a reserve/commit/release
  budget protocol to avoid overspending across simultaneous calls.

### 2.3 Service Selector (Policy Engine)
- **Input.** Context vector, current per-arm posterior or summary statistics,
  budget manager state.
- **Output.** Chosen arm \(a_t\).
- **Pluggability.** A single `Policy` interface (`select(context) → arm`,
  `update(context, arm, utility) → None`) is implemented by every
  comparator and ablation, as well as by PA-DCT. The signal passed in is
  the budget-pressure-free utility \(u_t = q_t - \nu f_t\) (§2.6), not the
  payment-aware reward \(r_t\); selection-time budget pressure is applied
  inside `select`. Provider-level outcome statistics are maintained
  outside the policy and encoded into the next round's context, keeping
  the policy interface aligned with the standard contextual-bandit update.
- **Default.** PA-DCT (see method section in paper outline).

### 2.4 x402 Payment Executor
- **Wraps.** An x402 client (real or mock). Exposed surface:
  - `pay_and_call(provider_id, request_payload) → response, cost, latency,
    failure_flag`.
- **Responsibilities.** Issue paid request, attach payment proof, await
  response, handle timeouts, and return a structured outcome. Benchmark runs
  disable retries by default so each round corresponds to one paid attempt. If
  retries are enabled in a live configuration, the returned outcome aggregates
  all attempts: total charged cost, wall-clock latency, final response,
  `failure_flag = true` only if all attempts fail, and an attempt count in the
  log record.
- **Failure modes.** Timeout, payment failure, schema-invalid response,
  budget block. Each maps to a normalized failure code.

### 2.5 Evaluator
- **Input.** Task, response.
- **Output.** Quality score \(q_t \in [0,1]\).
- **Backends, per task type.**
  - **Coding (T1):** pass@1 — execute generated code against unit tests.
    Fully deterministic.
  - **Multi-hop QA (T2):** normalized Exact Match + token-level F1; score =
    max(EM, F1). Deterministic given the gold answer string.
  - **Web search — closed-form (T3a):** same EM/F1 protocol as T2.
  - **Open-ended QA (T3b, OpenAssistant oasst1):** LLM-as-judge with a structured rubric
    (factual accuracy, completeness, absence of hallucination).
    Non-deterministic; judge model ID and seed are logged per call.
- **Determinism contract.** Deterministic backends (T1, T2, T3a) store scores
  at pre-generation time and replay them exactly. The LLM-as-judge backend
  (T3b) also caches judge scores during pre-generation and replays those
  cached scores during experiments. Judge model identity, version when
  available, rubric, and seed are logged as provenance, not as a guarantee
  that an external judge service can be re-run bit-identically later.

### 2.6 Reward Calculator

> Final design as of 2026-05-02. The latency term was dropped because the
> benchmark provider specifications do not include a latency profile, no
> scenario manipulates latency, and the measured contribution was negligible
> relative to quality, failures, and cost. The final reward uses a sigmoid
> convex combination so payment pressure remains bounded while the utility
> posterior stays independent of wallet state.

- **Input.** Quality \(q_t \in [0,1]\), cost \(c_t\), failure flag
  \(f_t \in \{0,1\}\), and the current budget-pressure multiplier
  \(\lambda_t\) from the Budget Manager.
- **Output.** Two related scalar quantities:
  - Service utility (intrinsic provider value, decoupled from budget pressure):
    \[ u_t = q_t - \nu \cdot f_t \quad \in [-\nu,\ +1]. \]
  - Payment-aware reward (sigmoid convex combination of utility and
    normalized cost):
    \[
      \lambda_{\mathrm{norm}} = \frac{\lambda_t}{1 + \lambda_t}
        = \mathrm{sigmoid}(\alpha \cdot \mathrm{burn\_excess}_t)
        \quad \in (0,1),
    \]
    \[
      r_t = (1 - \lambda_{\mathrm{norm}}) \cdot u_t \;-\;
            \lambda_{\mathrm{norm}} \cdot \tilde c_t
            \quad \in [-1,\ +1],
    \]
    with \(\tilde c_t = c_t / c_{\max}\) the normalized cost.
- **Use.**
  - The policy posterior is updated with \(u_t\). Dynamic budget pressure
    \(\lambda_t\) is a known decision-time multiplier, not a stable
    provider-quality signal, so it must not enter the posterior.
  - At selection time, PA-DCT ranks arms by the forward-looking
    payment-aware score
    \( (1 - \lambda_{\mathrm{norm}}) \cdot \hat u_k - \lambda_{\mathrm{norm}}
       \cdot \tilde c_k \).
  - \(r_t\) is logged and used for regret / objective accounting.
- **Why this form.**
  - Bounding \(r_t \in [-1, +1]\) lets the standard contextual TS and
    discounted TS regret bounds apply without empirical hand-waving about
    unbounded reward.
  - The convex combination has a natural reading: \(\lambda_{\mathrm{norm}}\)
    is the *fraction of decision weight* given to cost vs. utility. Low
    \(\lambda_{\mathrm{norm}}\) (no budget pressure) → all weight on
    utility; high \(\lambda_{\mathrm{norm}}\) (severe over-spend) → all
    weight on \(-\tilde c\). The transition is smooth.
- **Latency term.** An earlier draft included a \(\mu \tilde l_t\) term;
  it was removed on 2026-05-02. None of the K=5 providers were designed
  with a latency profile, no scenario manipulates latency, and empirically
  the term contributed ≈ 1% of cumulative reward magnitude — not enough
  to justify the extra hyperparameter. Latency is still observed and
  logged (it is part of the round record), just not part of the reward.
- **Locked constants.** \(\nu = 0.5\) is fixed across the paper (sensitivity
  analysis for \(\nu \in \{0.1, 0.5, 1.0\}\) lives in the appendix).
  \(\alpha = 2\) inside \(\lambda_t = \exp(\alpha \cdot \mathrm{burn\_excess})\).
  Neither is tuned per scenario or per method.

### 2.7 Policy Updater
- **Input.** \((x_t, a_t, u_t)\), plus \(r_t\) and \(\mathrm{outcome}_t\) for
  logging and provider-summary maintenance.
- **Behavior.** Updates external provider summaries from
  \(\mathrm{outcome}_t\) (EWMA quality, cost, latency, failure, and
  time-since-last-update), then calls `policy.update(context, arm, utility)`.
  For discounted policies, applies per-arm discount on prior sufficient
  statistics before incorporating the new utility sample.
- **Logging.** Every round emits a structured record consumed by the analysis
  pipeline.

---

## 3. Cross-cutting contracts

- **Determinism.** All randomness flows through a single `Random` source seeded
  per run. Non-deterministic external services (judges, real x402 endpoints)
  are isolated and logged.
- **Logging.** Each round produces a JSON-line record:
  `{round, context, arm, cost, latency, quality, failure, utility, reward, budget_remaining}`.
- **Time abstraction.** Rounds are logical, not wall-clock. The environment
  drives time deterministically via the pre-generated response dataset.
- **Configuration.** Single typed config object loaded from YAML; no
  per-module ad hoc settings.
- **Failure isolation.** Component failures (e.g., judge crash) raise typed
  errors; the runner can choose to skip, retry, or abort the run.

---

## 4. What lives outside the system

These are explicit non-goals for the layer (and the paper):

- Custody, key management, cryptographic settlement guarantees.
- Escrow, dispute, slashing, on-chain reputation.
- Cross-agent coordination or auction mechanisms.
- Long-horizon multi-step planning (delegated to the agent planner above
  402Pilot).
