# Paper Outline — 402Pilot

**Status:** historical planning draft. The ACM paper is the source of truth
for current claims, metrics, and scenario definitions.

Target format: 9 pages of content + unbounded references + appendix
(NeurIPS-style). Compatible with ICML / AAAI with minor trimming.

The bullets under each section are *content beats*, not prose. Page estimates
are guidance for keeping the paper balanced.

---

## Abstract (~200 words)

Six-sentence structure:

1. AI agents can now pay for APIs via x402-style micropayment protocols —
   but payment execution alone does not make agents economically rational.
2. Agents lack a *decision layer* for choosing what to pay for under budget
   constraints, quality uncertainty, and non-stationary provider behavior.
3. We formulate paid service selection as a budget-aware, non-stationary
   contextual bandit problem with bandit feedback over irreversible payments.
4. We propose 402Pilot, an x402 decision layer for autonomous agents, and
   PA-DCT (Payment-Aware Discounted Contextual Thompson sampling) — the
   policy that drives it, with dual posteriors over both quality and cost.
5. We build 402Pilot-Bench: a pre-generated benchmark grounded in real LLM
   outputs across five heterogeneous providers — including an adversarial
   provider and a flaky provider — under three market scenarios.
6. PA-DCT improves ROI and task success rate over fixed, rule-based, and
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
- The gap: a decision layer that learns which service is worth paying for,
  adapts to market changes, and protects against unreliable providers.
- **Motivating example** (boxed): fixed budget, mixed task workload,
  five providers including one adversarial and one flaky; static rules
  fail; context- and budget-aware policy wins.
- Contributions C1–C5 (locked in `logs/paper_design_decisions.md` §11.4):
  setting characterization (agent-native bandits), PA-DCT algorithm,
  402Pilot decision-layer architecture, reproducible benchmark, empirical
  findings on which classical components transfer to this regime.

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
  \(a_t \in \{1,\dots,K\}\); pays \(c_{a_t}\); observes \((q_t, f_t)\)
  for the chosen arm only (bandit feedback). Latency \(l_t\) is observed
  and logged but not part of the reward (see §3 design rationale).
- Reward, in two pieces:
  \[ u_t = q_t - \nu \cdot f_t \quad\in [-\nu,\, +1] \]
  is the *intrinsic service utility* — provider quality minus a failure
  penalty. The *payment-aware reward*
  \[
    \lambda_{\mathrm{norm}} = \frac{\lambda_t}{1 + \lambda_t}
        = \mathrm{sigmoid}(\alpha\cdot\mathrm{burn\_excess}_t),
  \]
  \[
    r_t = (1 - \lambda_{\mathrm{norm}}) \cdot u_t \;-\;
          \lambda_{\mathrm{norm}} \cdot \tilde c_t
          \quad\in [-1,\, +1]
  \]
  is a sigmoid convex combination of utility and normalized cost. The
  bounded form keeps standard contextual / discounted Thompson-sampling
  regret guarantees applicable; \(\lambda_{\mathrm{norm}}\) reads as the
  *fraction of decision weight* given to cost vs. utility.
- **Reward design rationale (one paragraph).** State the split: posterior
  is updated with \(u_t\) (intrinsic, λ-free) so the policy's beliefs
  track provider quality independently of decision-time budget pressure;
  selection ranks arms by the forward-looking PA score
  \((1-\lambda_{\mathrm{norm}})\hat u_k - \lambda_{\mathrm{norm}}\tilde c_k\).
  Note that an earlier draft included \(\mu\tilde l_t\); we removed it
  because none of the K=5 providers were designed with a latency profile,
  no scenario manipulates latency, and empirically the term contributed
  ~1% of cumulative reward magnitude. Locked constants: \(\nu = 0.5\),
  \(\alpha = 2\). Full derivation, alternative forms, and sensitivity
  analysis live in the appendix; the canonical reference is
  `logs/reward_design_rationale.md`.
- Budget constraint: \(\sum_t c_{a_t} \le B\). Hard cutoff if exhausted.
- Non-stationarity: per-arm reward distribution depends on \(t\) (abrupt
  degradation, price shock).
- **Why bandit, not RL** — short paragraph: bandit feedback (only chosen
  arm observed), immediate reward, payment irreversibility, no long-horizon
  credit assignment required within a single service call.

---

## 4. The 402Pilot Decision Layer (~1 page)

- High-level diagram: agent planner → context encoder → budget manager →
  service selector → x402 executor → evaluator → policy updater.
- Position relative to x402: 402Pilot acts *before* the payment HTTP loop;
  payment execution is delegated unchanged to the x402 stack.
- Component contracts (one paragraph each). Detailed spec in
  `docs/system_design.md`.
- Pluggability: any policy implementing the `Policy` interface
  (`select(context) → arm`, `update(context, arm, utility) → None`)
  drops in, enabling apples-to-apples comparison across all comparators
  and ablations. The signal passed to `update` is the budget-pressure-free
  utility \(u_t = q_t - \nu f_t\), not the payment-aware reward \(r_t\);
  selection-time budget pressure is applied inside `select`.

---

## 5. Method: PA-DCT (~1.25 pages)

- **Posterior model.** Per-arm contextual *utility* model using Bayesian
  linear regression. State the prior, the update equation, and the
  discounted sufficient statistics. Important: the posterior tracks
  intrinsic utility \(u_t = q_t - \nu f_t\), not the payment-aware reward
  \(r_t\). Decision-time budget pressure is applied at selection, never
  baked into provider beliefs.
- **Two-tier reward structure (recall from §3).** \(u_t\) is intrinsic
  (used for posterior updates); \(r_t = (1-\lambda_{\mathrm{norm}})\,u_t -
  \lambda_{\mathrm{norm}}\,\tilde c_t\) with \(\lambda_{\mathrm{norm}} =
  \mathrm{sigmoid}(\alpha\cdot\mathrm{burn\_excess})\) is what selection
  ranks arms by, in its forward-looking form
  \((1-\lambda_{\mathrm{norm}})\hat u_k - \lambda_{\mathrm{norm}}\tilde c_k\).
  This separation is what makes PA-DCT robust to budget-pressure shocks:
  beliefs do not lurch when \(\lambda_t\) jumps.
- **Discount factor \(\gamma\).** Exponential discount on per-arm
  sufficient statistics; controls the effective observation window for
  non-stationary adaptation. Fixed in the main paper; sensitivity
  analysis in appendix.
- **Budget-aware \(\lambda_t\).** \(\lambda_t = \exp(\alpha\cdot
  \mathrm{burn\_excess}_t)\) where \(\mathrm{burn\_excess}_t = \max(0,
  \mathrm{burn\_rate}_t - \mathrm{target\_rate})\). Monotone non-decreasing
  in budget pressure; bounded inside \([-1,+1]\) reward space via the
  sigmoid in §3. \(\alpha = 2\) fixed across the paper.
- **Algorithm 1 (boxed pseudocode).**
  - *Selection step:* Thompson-sample \(\tilde u_k \sim
    \mathcal{N}(\hat u_k, \hat\Sigma_k)\) for each arm; pick
    \(a^* = \arg\max_k\,(1-\lambda_{\mathrm{norm}})\tilde u_k -
    \lambda_{\mathrm{norm}}\tilde c_k\).
  - *Update step:* discount per-arm sufficient statistics by \(\gamma\),
    then incorporate the new utility sample \(u_t\). \(r_t\) is logged
    but does *not* enter the posterior.
- **Theoretical properties.** Short paragraph (no formal theorem): the
  bounded reward range \([-1,+1]\) — a direct consequence of the sigmoid
  convex combination — lets standard contextual TS and discounted TS
  regret guarantees apply. Cite Agrawal & Goyal (contextual TS) and
  Garivier & Moulines / Russac et al. (discounted TS); note which
  conditions transfer cleanly and which require additional assumptions.
  Honest about what is a corollary vs. what is novel.

---

## 6. Evaluation (~2.5 pages)

Full design in `docs/experiment_design.md`.

### 6.1 402Pilot-Bench setup (~0.5 page)

- **Pre-generated dataset.** 823 effective tasks across T1/T2/T3a/T3b; 5 response versions
  per (task, provider) pair from real LLM calls; quality scored at
  pre-generation time. Ensures reproducibility while grounding quality
  signals in real model outputs.
- **Providers.** Five heterogeneous agent pipelines: P-cheap (Qwen3-8B, no
  tools), P-mid (GPT-5.4-mini, BM25), P-premium (GPT-5.4, CoT + tools),
  P-adv (GPT-5.4-mini + adversarial system prompt), P-flaky (GPT-5.4-mini +
  40% timeout injection). P-mid / P-adv / P-flaky share cost tier and base
  model — only reward feedback distinguishes them.
- **Task types** (4 sub-types, treated separately because the evaluator
  differs).
  - T1 — Coding (HumanEval), pass@1. Deterministic.
  - T2 — Multi-hop QA (HotpotQA), max(EM, F1). Deterministic given gold.
  - T3a — Web search, closed-form (TriviaQA-web), max(EM, F1).
    Deterministic given gold.
  - T3b — Web search, open-ended (custom), LLM-as-judge with structured
    rubric (factual accuracy, completeness, absence of hallucination).
    Cached at pre-generation time and replayed.
  T3 is split into T3a vs. T3b throughout the paper because their
  evaluators behave differently and PA-DCT's behavior on the two differs
  in interpretable ways (see §7 limitations).
- **Scenarios.** S1: Stationary. S2: Mid outage — `MidOutageScenario`,
  P-mid fails 30% of the time during rounds 3,000–5,500, fully recovers
  after. S3 v2: Premium promo — `PremiumDropScenario`, P-premium price
  drops at round 1,000 from $0.01 to $0.002 (matches mid), 9,000 rounds
  for the cost posterior to detect and the policy to migrate.
- **Scale.** T = 10,000 rounds, N = 30 seeds per cell.

### 6.2 Comparators and metrics (~0.25 page)

- **Comparators.** Six baselines plus an offline upper bound, all run on
  identical seeds:
  - **Random** — uniform over affordable arms (lower bound).
  - **Always-P-cheap / Always-P-mid / Always-P-premium** — three fixed
    policies covering the cost-tier sweep; Always-P-premium is the
    strongest non-adaptive baseline.
  - **Budget rule** — threshold heuristic over remaining budget; the
    strongest hand-crafted baseline (FrugalGPT-style).
  - **PA-DCT** — ours.
  - **True Oracle** — free-running with hindsight per-round arm peek;
    upper bound for the *scenario*, not just one policy's λ trajectory.
- **Metrics.** Four locked metrics from `docs/experiment_design.md`:
  task_success_rate (mean quality as proxy), ROI = Σq_t / Σc_t,
  cumulative regret (Oracle − policy on cum_PA), adaptation_time (rounds
  for trailing-200 ROI to recover within 5% of pre-event level; S2/S3
  only).

### 6.3 Main results (~1 page)

- **Table 1.** ROI and task success rate across S1/S2/S3 for all comparators
  and PA-DCT. Mean ± std, effect sizes, significance markers.
- **Figure 1.** Per-scenario ROI curves over rounds; shows PA-DCT learning
  trajectory vs. Always-P-premium exhausting budget by round ~5,000.
- **Figure 2.** Adaptation curves in S2 and S3: trailing-200 ROI around
  the shock event, comparing full PA-DCT against the −D ablation (no
  discount). This is the figure that makes D's contribution visible —
  cum_PA alone hides it.
- **Narrative.** PA-DCT matches Always-P-premium on task quality while
  achieving higher ROI and longer wallet life. Budget rule adapts to cost
  but cannot detect P-adv / P-flaky from P-mid. P-adv detection is fast on
  T1/T2 (objective evaluation), slow on T3 open-ended (evaluator-bounded).

### 6.4 Ablations (~0.75 page)

The ablations remove one named PA-DCT component at a time, plus the
S3-only cost-posterior diagnostic. Detailed per-cell numbers in
`logs/ablation_5metrics_table.md`.

- **Table 2.** PA-gap/T, ROI, full-horizon quality, and adaptation time
  for −P / −D / −C / −TS / −Cpost vs. full PA-DCT.
- **−P (no Payment-aware):** policy ranks by raw utility instead of
  `(1−λ_norm)·u − λ_norm·c̃`. cum_PA collapses to negative everywhere
  (S1 −1710, S2 −1966, S3 +4528 vs. full ~5500–5900). The agent picks
  high-quality but expensive arms, burns budget early, and is crushed by
  the cost penalty in PA reward. **P is uniformly necessary.**
- **−D (no Discount, γ = 1):** cum_PA is essentially flat vs. full, but
  adaptation_time in S2 jumps from 1467 → 2249 rounds (35% slower
  recovery from outage). cum_PA averages 10k rounds, diluting the
  recovery-acceleration benefit. **D's contribution shows up only on the
  right metric (adaptation_time).**
- **−C (no Contextual, single global bucket):** mixed effect by
  scenario. Helps slightly when shock is uniform across task types (S2
  outage hits all task types equally → bucket fragmentation hurts; −C
  adapts in 1176 rounds vs. full 1467). Hurts when task heterogeneity is
  exploitable (S3 promo + P-premium especially good on T3b → full adapts
  in 200 vs. −C 398). **Honest claim: C helps when per-task-type quality
  differences emerge from the shock structure.**
- **−TS (no Thompson sampling, greedy posterior mean):** cum_PA mean is
  within ~50 of full, but seed std is 5–9× higher (full ~50–80, −TS
  244–481). S3 adaptation_time jumps from 200 → 2232 (greedy locks onto
  initial-state arm, fails to detect new opportunities). **TS provides
  reproducibility (low variance) and exploration (capture new
  opportunities); the cum_PA-mean similarity hides this.**

**Multi-metric framing.** No single classical bandit metric (cum_PA
alone) reveals all four contributions. This motivates the four-metric
evaluation framework introduced in §6.2.

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
  open-ended T3 tasks is not fully corrected by PA-DCT because the LLM
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
(x402) and payment decision (PA-DCT). Restate the four contributions.
One forward-looking sentence on adding provider reputation or
atomicity-aware selection as future directions.

---

## Appendix (after refs, no page limit)

- **A.** Algorithm details: full PA-DCT pseudocode, hyperparameter values,
  ablation hyperparameter grids.
- **B.** Theoretical properties: formal statements and proof sketches for
  contextual TS and discounted TS results that carry over; discussion of
  conditions that do not directly transfer.
- **C.** Pre-generated dataset details: LLM call parameters, prompt
  templates per task type, quality scorer implementations, LLM-as-judge
  rubric, inter-rater reliability on a human-validated subset.
- **D.** Scenario specifications: event schedules, response pool switching
  logic, price parameter changes.
- **E.** Additional results: per-task-type ROI breakdowns (T1 / T2 /
  T3a / T3b separately), P-adv detection curves by task type, sensitivity
  to N seeds, budget B, discount γ, failure penalty ν ∈ {0.1, 0.5, 1.0},
  and λ_t shape parameter α. Also includes the empirical justification
  for dropping the latency term from an earlier draft (~1% contribution
  to cumulative reward magnitude).
- **F.** Reproducibility checklist.
