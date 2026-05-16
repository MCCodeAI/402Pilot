# Experiment Design — 402Pilot-Bench

**Status:** historical design draft. The ACM paper is the source of truth for
current scenario definitions and reported metrics.

402Pilot-Bench is the single evaluation used in this paper. It comprises
three market scenarios, a fixed comparator set, four ablations of PA-DCT,
and a fixed metric suite — all run against the same pre-generated response
dataset. Every reported number comes from this one experimental framework.

---

## 1. Environment

### 1.1 Pre-generated response dataset

Provider quality is grounded in **real LLM outputs**, not purely simulated
distributions. A dataset of `(task, provider, response, quality)` tuples is
pre-generated once before any bandit experiment runs. During experiments the
environment replays responses from this fixed dataset deterministically.

- **Pre-generation.** For each `(task, provider)` pair, **5 response versions**
are generated at different random seeds (temperature sampling). At experiment
time the environment draws one version per round via seed-controlled sampling.
This captures real LLM output variance while remaining fully reproducible
across the 30 seeds.
- **Quality scoring.** Scoring method depends on task type (see §1.3). For
deterministic scorers (pass@1, EM/F1), scores are computed and stored at
pre-generation time. For LLM-as-judge, judge model ID and seed are logged.
- **Cost / latency.** Drawn from provider tier parameters (see §1.2) with
small per-call Gaussian noise. Timeout events for P-flaky are injected
deterministically at pre-generation time using a fixed seed.
- **Pre-generation cost.** Approximately 20,000 API calls in total (see §1.3
for breakdown), incurred once. All bandit experiments thereafter run as fast
local replay with zero marginal API cost.
- **Non-stationarity.** Scenarios S2 and S3 are implemented by switching which
response-version pool a provider draws from at the scheduled round (quality
changes), or by modifying the cost parameter in the scenario config (price
shocks). No re-generation is required between scenarios.

### 1.2 Provider population

**K = 5 providers** with distinct behavioral profiles spanning quality, cost,
latency, and reliability. Each is implemented as an agent pipeline (LLM + tool
configuration) rather than a bare model call. The same five providers appear
across all task types; tool configurations adapt per task type while LLM and
reasoning settings remain fixed.


| Provider      | Type        | LLM          | Reasoning                      | Retrieval / Context strategy                | Other tools                                | Special behavior          |
| ------------- | ----------- | ------------ | ------------------------------ | ------------------------------------------- | ------------------------------------------ | ------------------------- |
| **P-cheap**   | Cheap       | Qwen3-8B     | ❌ disabled (non-thinking mode) | None — parametric memory only               | None                                       | —                         |
| **P-mid**     | Medium      | GPT-5.4-mini | ❌ disabled                     | BM25, top-2 paragraphs from provided docs   | None                                       | —                         |
| **P-premium** | Premium     | GPT-5.4      | ✅ CoT pipeline                 | Full document context injection             | Code execution sandbox (coding tasks only) | —                         |
| **P-adv**     | Adversarial | GPT-5.4-mini | ❌ disabled                     | BM25, top-2 paragraphs (identical to P-mid) | None                                       | Adversarial system prompt |
| **P-flaky**   | Flaky       | GPT-5.4-mini | ❌ disabled                     | BM25, top-2 paragraphs (identical to P-mid) | None                                       | 40% timeout injection     |


**P-adv — adversarial system prompt.** P-adv uses the same base model and
retrieval stack as P-mid. The sole difference is a system prompt that instructs
the model to respond with high confidence and no hedging, suppressing
uncertainty signals. This increases the rate of fluent but factually incorrect
answers without changing response format or cost. The adversarial behavior is
reliably detected by objective scorers (pass@1, EM/F1) but partially evades
LLM-as-judge evaluation on open-ended tasks, producing a task-type-dependent
detection gradient (see §1.3).

**P-flaky — flaky behavior.** P-flaky uses the same model and tool stack as
P-mid. During pre-generation, 40% of `(task, P-flaky)` pairs are designated as
timeout events using the deterministic version-level mechanism (versions 0 and
1 of the 5 stored versions are forced timeouts). A timeout yields quality = 0,
charged_cost_usdc = base_price (full charge per x402 semantics — payments are
irreversible on the network even when the upstream provider failed), and
latency = timeout threshold. The remaining 60% of calls return P-mid-level
quality. P-flaky's expected quality is therefore substantially lower than
P-mid's (gap ~0.32 on the calibrated dataset) despite identical per-call
quality on successful calls, creating a clear reliability signal the bandit
must learn from failure observations alone — cost and base model are
indistinguishable from P-mid.

The 40% rate (calibrated 2026-05-02 from an earlier 20% trial) was chosen so
that the failure signal is statistically obvious within ~5 pulls but not so
overwhelming that a trivial heuristic ("any failures means avoid") suffices.

**Design rationale for the P-mid / P-adv / P-flaky three-way structure.**
All three share the same cost tier and base model. A rule-based policy relying
on price or latency alone cannot distinguish them. PA-DCT must learn the
distinction purely from reward feedback — exactly the regime where contextual
bandit learning provides value over fixed or rule-based policies.

### 1.3 Task workload

**M = 3 task types**, selected to span a range of evaluation objectivity and
to produce a meaningful adversarial-detection gradient across providers.

#### T1 — Coding (HumanEval)

- **Dataset.** HumanEval; **150 problems** sampled from the full set.
- **Task.** Function completion / bug fixing. The provider generates Python
code satisfying a docstring specification.
- **Quality scorer.** pass@1: generated code is executed against the problem's
unit tests. Score ∈ {0, 1} per problem (or fractional by test-case pass
rate).
- **Evaluator objectivity.** Deterministic. P-adv is reliably caught:
syntactically valid but logically incorrect code fails unit tests immediately.
Detection typically occurs within 20 rounds.

#### T2 — Multi-hop QA (HotpotQA)

- **Dataset.** HotpotQA validation set; **300 questions** sampled uniformly.
Each question is supplied with ~10 candidate paragraphs by the dataset; no
open-web retrieval is required.
- **Task.** Multi-step reasoning over the provided paragraphs to answer a
factoid question requiring evidence from ≥ 2 sources.
- **Quality scorer.** Normalized Exact Match (EM) and token-level F1 against
the gold answer string. Score = max(EM, F1) after standard normalization
(lowercase; strip articles and punctuation).
- **Evaluator objectivity.** High. P-adv's factual errors are usually caught;
occasional plausible-sounding wrong answers may achieve partial F1 overlap,
moderating detection speed relative to T1.

#### T3 — Web Search (TriviaQA-web + custom open-ended)

The web search task is split into two sub-pools to create a controllable
evaluator-difficulty gradient:

- **Closed-form sub-pool (40%, ~150 questions).** TriviaQA-web subset: factoid
questions with short, unambiguous gold answers. Providers retrieve from the
web documents supplied with each TriviaQA item (no live web access required
at experiment time). Scorer: normalized EM + token-level F1, identical
protocol to T2.
- **Open-ended sub-pool (60%, ~225 questions).** Custom questions requiring
multi-source synthesis with no single correct string answer (e.g., "Summarize
the main arguments for and against X from at least two perspectives").
Scorer: LLM-as-judge with a structured rubric covering factual accuracy,
completeness, and absence of hallucination. Judge model ID and seed are
logged for reproducibility.

**Evaluator objectivity gradient.** Closed-form: high — EM/F1 catches P-adv
reliably. Open-ended: moderate-to-low — fluent but incorrect answers can
partially satisfy the rubric. This gradient is intentional: it demonstrates
that adversarial-provider detection capability is bounded by evaluator quality,
a fundamental property of any reward-feedback learning system.

#### Task sampling

- Default mixture: empirical uniform sampling over the 823-task cache:
  T1/T2/T3a/T3b appear in proportion to their cache counts
  (164/220/219/220).
- Tasks are drawn with replacement; sampling sequence is determined by the run
seed, ensuring reproducibility across all 30 seeds.
- Difficulty is implicit in the benchmark datasets; no separate
difficulty-sampling distribution is needed.

#### Pre-generation dataset summary


| Task                | Dataset      | Pool size | Providers | Versions | API calls    |
| ------------------- | ------------ | --------- | --------- | -------- | ------------ |
| Coding              | HumanEval    | 164       | 5         | 5        | 4,100        |
| Multi-hop QA        | HotpotQA val | 220       | 5         | 5        | 5,500        |
| Web search — closed | TriviaQA-web | 219 effective (220 raw, 1 filtered) | 5 | 5 | 5,475 |
| Web search — open   | OpenAssistant filt. | 220 | 5         | 5        | 5,500        |
| **Total**           |              | **823 effective** |      |          | **20,575** |

The 164 for coding is the full HumanEval test split (no sampling). The
other three sources are deterministically sampled; per-source seeds are
defined in their loader modules.


### 1.4 Run length and budget

- **T = 10,000** rounds per run.
- **N = 30** seeds per (policy × scenario) cell; mean ± std reported.
- Wallet budget **B** sized so *Always-P-premium* exhausts wallet near round
~5,000. This forces budget-awareness to matter and creates a clean reference
point for comparing budget longevity across policies.

---

## 2. Scenarios

Three scenarios, each a deterministic schedule of provider parameter changes,
run independently. Same providers, same tasks, same seeds — only the event
schedule differs.

- **S1 — Stationary.** No parameter changes throughout. Establishes the
static-market baseline and measures the base rate at which each policy
learns to distinguish P-adv and P-flaky from P-mid.
- **S2 — Mid outage.** During rounds 3,000--5,500, P-mid fails 30% of the
time via timeout injection, then fully recovers. Tests whether PA-DCT adapts
to a reliability shock in an otherwise unchanged market.
- **S3 — Premium promo.** At round 1,000, P-premium's price drops from
$0.01 to $0.002, matching P-mid. Response quality is unaffected; only cost
changes. Tests whether the learned cost posterior lets PA-DCT capture a
price-promotion opportunity.

---

## 3. Comparators

Three external comparators plus an offline upper bound. Learning variants of
PA-DCT are reported as ablations in §5, not as separate comparators, to avoid
double-counting and keep the results table clean.


|            | Method           | Role                                                                                                                                        |
| ---------- | ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| Fixed      | Always-P-premium | Strongest non-adaptive policy; always picks the highest-quality provider regardless of cost or budget state.                                |
| Rule-based | Budget rule      | Best hand-crafted heuristic; adjusts provider choice based on remaining budget pressure. Represents the ceiling of rule-based approaches.   |
| Ours       | **PA-DCT**      | Full proposed method.                                                                                                                       |
| Reference  | Oracle           | Offline upper bound using ground-truth quality distributions each round. Not available to any online agent; defines the regret denominator. |


P-adv and P-flaky are part of the selectable arm pool for PA-DCT and all
ablations, but are not assigned dedicated fixed baselines.

---

## 4. Metrics

Four metrics, each with a distinct purpose. All computed from the same
per-round logs; reported per-scenario as mean ± std across 30 seeds.


| Metric                | Definition                                                              | Role                                                          |
| --------------------- | ----------------------------------------------------------------------- | ------------------------------------------------------------- |
| **Task success rate** | Fraction of rounds where quality exceeds the per-type success threshold | Primary quality measure                                       |
| **ROI**               | Σ q_t / Σ c_t (total quality accumulated / total spend)                 | Primary economic metric; value delivered per dollar paid      |
| **Cumulative regret** | Σ (r_Oracle − r_t) over T rounds                                        | Standard bandit learning metric; total gap vs offline optimum |
| **Adaptation time**   | Rounds until ROI recovers to within 5% of pre-event level               | Non-stationarity performance; S2 and S3 only                  |


**ROI note.** q_t is the raw evaluator score (pass@1, EM/F1, or judge score),
not the shaped internal reward. This keeps ROI independent of PA-DCT's
reward hyperparameters (λ, μ, ν) and directly comparable across all policies.

---

## 5. Ablations

Four removed-component variants of PA-DCT, run on all scenarios with the
same 30 seeds as the main experiment.


| Ablation                    | Component removed                                         | What it isolates                                                  |
| --------------------------- | --------------------------------------------------------- | ----------------------------------------------------------------- |
| **A1 — No context**         | Context vector x_t; degrades to non-contextual TS         | Value of task-type and difficulty awareness in provider selection |
| **A2 — No discount**        | Discount factor set to γ = 1 (uniform history weighting)  | Value of non-stationarity adaptation in S2 / S3                   |
| **A3 — No budget-aware λ**  | Adaptive cost multiplier; λ_t fixed at λ_0                | Value of dynamic budget pressure on wallet longevity and ROI      |
| **A4 — No failure penalty** | μ = ν = 0 (latency and failure terms removed from reward) | Value of penalising P-flaky's timeouts in the reward signal       |


Combinations of A1–A4 correspond to standard off-the-shelf algorithms
(A1+A2+A3+A4 ≈ vanilla TS, etc.), but single-component ablations give cleaner
per-contribution attribution.

---

## 6. Statistical reporting

- 30 seeds per cell. Report mean ± std in tables; 95% CIs on figures.
- Pairwise significance: Welch's t-test, Bonferroni-corrected within each
comparison table.
- Headline results include effect size (relative improvement in ROI) in
addition to p-values.

---

## 7. Hyperparameter protocol

- One held-out instance per scenario family is reserved for hyperparameter
selection, using different seeds from the evaluation seeds.
- PA-DCT hyperparameters are fixed across all scenarios after selection; no
per-scenario tuning. The same rule applies to all ablations.
- The hyperparameter grid and selection criterion are documented in the
appendix.

---

## 8. Scope boundaries

- Single-agent setting; does not model multi-agent or competitive dynamics.
- Providers are heterogeneous agent pipelines evaluated via bandit feedback,
not an LLM-routing layer within a single inference platform — that is a
distinct problem.
- All runs execute on a local DEVnet (Anvil fork of Base) for speed and
reproducibility; no public testnet is used at any stage.
- No live financial transactions; the wallet is a mock wallet throughout.
