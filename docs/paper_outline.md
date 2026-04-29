# Paper Outline — 402Pilot

Target format: 9 pages of content + unbounded references + appendix
(NeurIPS-style). Compatible with ICML / AAAI with minor trimming.

The bullets under each section are *content beats*, not prose. Page estimates
are guidance for keeping the paper balanced.

---

## Abstract (~200 words)

Six-sentence structure:

1. AI agents can now pay for APIs via x402-style micropayment protocols —
   but payment execution alone does not make agents economically rational.
2. Agents lack a *finance layer* for deciding what to pay for under budget
   constraints, quality uncertainty, and non-stationary provider behavior.
3. We formulate paid service selection as a budget-aware, non-stationary
   contextual bandit problem with bandit feedback over irreversible payments.
4. We propose 402Pilot, a finance layer that sits above x402, and PA-DCTS
   (Payment-Aware Discounted Contextual Thompson Sampling), the policy
   that drives it.
5. We build 402Pilot-Bench: a pre-generated benchmark grounded in real LLM
   outputs across five heterogeneous providers — including an adversarial
   provider and a flaky provider — under three market scenarios.
6. PA-DCTS improves ROI and task success rate over fixed, rule-based, and
   non-contextual baselines, and adapts faster to provider drift; ablations
   confirm the contribution of each design component.

---

## 1. Introduction (~1.25 pages)

Beats:

- Agents are becoming economic actors: wallets, per-call APIs, micropayments.
- x402 solves payment *execution*; it does not solve payment *decision*.
- Existing budget guardrails constrain spending; LLM routing optimizes
  inference cost on a single platform. Neither handles wallet-level markets
  with provider heterogeneity, irreversible payments, adversarial providers,
  and provider drift.
- The gap: a finance layer that learns which service is worth paying for,
  adapts to market changes, and protects against unreliable providers.
- **Motivating example** (boxed): fixed budget, mixed task workload,
  five providers including one adversarial and one flaky; static rules
  fail; context- and budget-aware policy wins.
- Contributions (four bullets from PLAN.md §6).

---

## 2. Related Work (~0.5 page)

Four short paragraphs:

- **Agent payment protocols.** x402, A402, atomic service channels.
  Position: orthogonal — they execute payments; we decide payments.
- **Budget guardrails / spend management.** Tools that limit or approve
  spending. Position: rule-based caps, no online learning over heterogeneous
  providers.
- **LLM routing / model selection bandits.** Online multi-LLM selection,
  contextual-bandit routing under budget. Position: same algorithmic family,
  different problem — inference-cost optimization within one platform vs.
  irreversible economic spending across heterogeneous providers in a
  micropayment market with adversarial and flaky actors.
- **Non-stationary bandits.** Discounted TS, sliding-window methods, change
  detection. Position: borrowed and adapted, not invented.

---

## 3. Problem Formulation (~0.75 page)

- Round protocol: at round \(t\), context \(x_t\) arrives; agent picks
  \(a_t \in \{1,\dots,K\}\); pays \(c_{a_t}\); observes \((q_t, l_t, f_t)\)
  for the chosen arm only (bandit feedback).
- Reward:
  \[ r_t = q_t - \lambda_t \tilde{c}_t - \mu \tilde{l}_t - \nu f_t \]
  with normalized cost and latency. \(\lambda_t\) is budget-sensitive.
- Budget constraint: \(\sum_t c_{a_t} \le B\). Hard cutoff if exhausted.
- Non-stationarity: per-arm reward distribution depends on \(t\) (abrupt
  degradation, price shock).
- **Why bandit, not RL** — short paragraph: bandit feedback (only chosen
  arm observed), immediate reward, payment irreversibility, no long-horizon
  credit assignment required within a single service call.

---

## 4. The 402Pilot Finance Layer (~1 page)

- High-level diagram: agent planner → context encoder → budget manager →
  service selector → x402 executor → evaluator → policy updater.
- Position relative to x402: 402Pilot acts *before* the payment HTTP loop;
  payment execution is delegated unchanged to the x402 stack.
- Component contracts (one paragraph each). Detailed spec in
  `docs/system_design.md`.
- Pluggability: any policy implementing the `Policy` interface
  (`select(context) → arm`, `update(context, arm, reward) → None`) drops in,
  enabling apples-to-apples comparison across all comparators and ablations.

---

## 5. Method: PA-DCTS (~1.25 pages)

- **Posterior model.** Per-arm contextual reward model using Bayesian linear
  regression. State the prior, the update equation, and the discounted
  sufficient statistics.
- **Discount factor \(\gamma\).** Exponential discount on per-arm sufficient
  statistics; controls the effective observation window for non-stationary
  adaptation. Fixed in the main paper; sensitivity analysis in appendix.
- **Budget-aware \(\lambda_t\).** Function of remaining-budget ratio and
  remaining-time ratio; monotone non-decreasing in budget pressure. Raises
  the cost penalty as burn rate exceeds target rate.
- **Algorithm 1 (boxed pseudocode).** Selection step (Thompson sample +
  budget-aware reward projection) + update step (discounted sufficient
  statistic update).
- **Theoretical properties.** Short paragraph (no formal theorem): cites
  regret guarantees of contextual TS and discounted TS from prior work,
  notes which conditions transfer to our setting. Honest about what is a
  corollary vs. what requires additional assumptions.

---

## 6. Evaluation (~2.5 pages)

Full design in `docs/experiment_design.md`.

### 6.1 402Pilot-Bench setup (~0.5 page)

- **Pre-generated dataset.** 824 tasks across T1/T2/T3; 5 response versions
  per (task, provider) pair from real LLM calls; quality scored at
  pre-generation time. Ensures reproducibility while grounding quality
  signals in real model outputs.
- **Providers.** Five heterogeneous agent pipelines: P-cheap (Qwen3-8B, no
  tools), P-mid (GPT-5.4-mini, BM25), P-premium (GPT-5.4, CoT + tools),
  P-adv (GPT-5.4-mini + adversarial system prompt), P-flaky (GPT-5.4-mini +
  20% timeout injection). P-mid / P-adv / P-flaky share cost tier and base
  model — only reward feedback distinguishes them.
- **Task types.** T1: Coding (HumanEval, pass@1); T2: Multi-hop QA
  (HotpotQA, EM/F1); T3: Web Search (TriviaQA-web closed-form + custom
  open-ended, EM/F1 + LLM-as-judge).
- **Scenarios.** S1: Stationary. S2: Abrupt degradation (P-premium quality
  drop at round 3,000; P-flaky timeout spike at round 5,000). S3: Price
  shock (P-premium doubles, P-mid halves at round 5,000).
- **Scale.** T = 10,000 rounds, N = 30 seeds per cell.

### 6.2 Comparators and metrics (~0.25 page)

- **Comparators.** Always-P-premium (strongest fixed policy), Budget rule
  (strongest rule-based policy), Oracle (offline upper bound).
- **Metrics.** Task success rate; ROI = Σq_t / Σc_t; cumulative regret;
  adaptation time (S2/S3 only).

### 6.3 Main results (~1 page)

- **Table 1.** ROI and task success rate across S1/S2/S3 for all comparators
  and PA-DCTS. Mean ± std, effect sizes, significance markers.
- **Figure 1.** Per-scenario ROI curves over rounds; shows PA-DCTS learning
  trajectory vs. Always-P-premium exhausting budget by round ~5,000.
- **Figure 2.** Adaptation curves in S2 and S3: ROI around the shock event,
  comparing PA-DCTS (A2 ablation) against non-discounted counterpart.
- **Narrative.** PA-DCTS matches Always-P-premium on task quality while
  achieving higher ROI and longer wallet life. Budget rule adapts to cost
  but cannot detect P-adv / P-flaky from P-mid. P-adv detection is fast on
  T1/T2 (objective evaluation), slow on T3 open-ended (evaluator-bounded).

### 6.4 Ablations (~0.75 page)

- **Table 2.** Delta in ROI and adaptation time for A1–A4 vs. full PA-DCTS,
  across all three scenarios.
- **A1 (no context):** Largest ROI drop on mixed workloads — confirms
  task-type context drives provider differentiation.
- **A2 (no discount):** Largest adaptation-time increase in S2/S3 —
  confirms discount is load-bearing for non-stationarity.
- **A3 (no budget-aware λ):** Budget exhaustion accelerates; ROI drops in
  late rounds — confirms dynamic λ_t extends wallet life.
- **A4 (no failure penalty):** P-flaky usage increases, reducing effective
  task success rate — confirms failure term is necessary.

---

## 7. Discussion and Limitations (~0.5 page)

- Pre-payment decision layer; complementary to A402 post-selection atomicity.
- No escrow, dispute, or reputation system — acceptable for the decision
  layer; what would change if reputation signals were available as context.
- **Dataset fidelity.** Pre-generated responses capture real LLM quality
  distributions but freeze model behavior. Live model updates would require
  periodic re-generation; the discount mechanism partially mitigates stale
  priors in practice.
- **Evaluator quality bounds adversarial detection.** P-adv's impact on
  open-ended T3 tasks is not fully corrected by PA-DCTS because the LLM
  judge occasionally accepts fluent-but-wrong answers. Stronger evaluators
  would tighten this gap.
- **Single-agent scope.** Multi-agent dynamics, auction mechanisms, and
  cross-agent coordination are out of scope and left for future work.
- **Provider performance ordering assumed consistent across task types.**
  The global EWMA statistics in the context encoder do not stratify provider
  performance by task type. This is a deliberate simplification: the paper's
  experimental providers are differentiated primarily by model scale and
  capability tier, so their relative quality ordering is expected to hold
  broadly across task types — larger, more capable models perform better
  across coding, QA, and web search alike. The system design does not
  preclude per-(provider, task-type) statistics, but extending to settings
  where provider rankings invert across task types (e.g., a specialist model
  that excels at one task but underperforms on others) is left for future
  work.

---

## 8. Conclusion (~0.25 page)

Restate the thesis: 402Pilot bridges the gap between payment execution
(x402) and payment decision (PA-DCTS). Restate the four contributions.
One forward-looking sentence on adding provider reputation or
atomicity-aware selection as future directions.

---

## Appendix (after refs, no page limit)

- **A.** Algorithm details: full PA-DCTS pseudocode, hyperparameter values,
  ablation hyperparameter grids.
- **B.** Theoretical properties: formal statements and proof sketches for
  contextual TS and discounted TS results that carry over; discussion of
  conditions that do not directly transfer.
- **C.** Pre-generated dataset details: LLM call parameters, prompt
  templates per task type, quality scorer implementations, LLM-as-judge
  rubric, inter-rater reliability on a human-validated subset.
- **D.** Scenario specifications: event schedules, response pool switching
  logic, price parameter changes.
- **E.** Additional results: per-task-type ROI breakdowns, P-adv detection
  curves by task type, sensitivity to N seeds, budget B, and γ.
- **F.** Reproducibility checklist.
