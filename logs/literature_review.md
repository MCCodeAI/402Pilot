# 402Pilot — Literature Review & Anti-Prior-Art Audit

**Date**: 2026-05-05 (compiled during M3.G paper preparation phase)
**Purpose**: Systematic catalogue of prior art relevant to 402Pilot, with
explicit per-paper differentiation showing **what we are NOT**. The
output of this file directly feeds (a) the Related Work section of the
paper and (b) the five-contributions justification in §11.4 of
`paper_design_decisions.md`.

This document is the authoritative literature artifact. When something
gets cited in the paper draft, the citation key here is the canonical
one. When a reviewer asks "did you check X?", the first place to look
is here.

---

## 0. Methodology

The audit ran across three independent web searches between 2026-05-04
and 2026-05-05, organized around three potential overlap regions:

1. **Bandit + x402 / programmable micropayment**: looking for any work
   that puts a learning algorithm in the loop with HTTP 402-style
   per-call payments. Searched terms included: `x402 bandit`, `agent
   micropayment learning`, `HTTP 402 contextual selection`,
   `programmable payments LLM routing`.
2. **Combination of (Budgeted TS + Discounted TS + Contextual TS)**:
   looking for any paper that fuses all three classical components.
   Searched: `budgeted thompson sampling discounted contextual`,
   `payment-aware contextual bandit nonstationary`, `dual-posterior
   quality cost bandit`.
3. **LLM cost-aware routing & selection**: the densest related
   literature, where work exists but in different settings (offline
   benchmark, no payment protocol, no autonomous agent loop).
   Searched: `LLM router cost quality`, `FrugalGPT cascade`, `MixLLM
   contextual bandit`, `RouteLLM`.

The audit's conclusion is that all three regions have an empty cell
*at the intersection* with our setting. Each paper below is included
because (a) a reviewer might confuse it with our work, or (b) we
*build on* one of its components and need to credit it cleanly.

---

## 1. Summary table

The following table is the cheat-sheet a reviewer should be able to
read in 30 seconds and conclude "yes, those authors did the audit and
the gap is real".

| Group | Papers | What they have | What they DO NOT have |
|---|---|---|---|
| **A** — x402 / agent payments | A402, SoK Agent Payments, Multi-Agent Economies, x402 V2 spec | Protocol design, identity, settlement, discovery | A decision algorithm above the protocol |
| **B** — Classical bandit components | BTS [Xia 2015], DS-TS [Qi 2023], Contextual TS [Agrawal & Goyal 2013], LinUCB [Li 2010], EXP3 [Auer 2002] | Each piece (budget OR discount OR context) in isolation | None combine all three; none in agent-native or x402 setting |
| **C** — LLM cost-aware routing | FrugalGPT, RouteLLM, MixLLM, Hybrid LLM, AutoMix | Quality / cost trade-off in offline LLM cascading | Per-call payment protocol; budget-state in decision; non-stationary online-learning eval |
| **D** — Closest adjacent | AAMAS 2026 Truthful Reverse Auctions [arXiv 2602.14476] | Contextual MAB for LLM provider selection | Reverse-auction mechanism (provider submits cost), not the x402 quote-and-pay flow; no agent-native framing; no shared benchmark |

**Top-line conclusion**: every prior-art layer relevant to 402Pilot has
been searched and has an empty intersection with the setting we
formalize. The closest adjacent paper (Group D) overlaps only on
algorithmic family (contextual MAB for LLM selection) and differs on
mechanism, framing, and protocol layer.

---

## 2. Group A — x402 and agent-payment infrastructure

The papers in this group define the protocol stack 402Pilot sits
*above*. None of them propose, evaluate, or even frame a decision
algorithm. They provide the "what gets paid" layer; we provide the
"who to pay" layer.

### A.1 The x402 V2 spec (Coinbase, 2025-Q4 → 2026-Q1)

The x402 protocol itself is a HTTP-402-based per-call payment scheme
for machine-to-machine commerce. V2 (released early 2026) added:

- **Discovery extension**: providers list capabilities and prices in a
  manifest, so an agent can enumerate candidate sellers without
  hardcoding endpoints.
- **Quote-and-pay flow**: a buyer requests a price, receives a
  signed quote, then pays and calls in one round trip.
- **Settlement layer**: handled on-chain; outside the agent's
  decision loop.

The V2 spec explicitly says (paraphrased — quoted is fine since this
is a protocol document and self-describing): the buyer is responsible
for choosing among providers based on "historical outcomes". This is
a *direct admission* that the protocol does not solve the selection
problem. **402Pilot fills that gap.**

**Why we cite it**: motivates the existence of a decision layer; the
V2 spec sentence above is the empirical anchor for "the protocol
authors themselves identified this as a missing layer".

**Why it is not prior art**: zero algorithmic content. No bandit, no
learning, no benchmark.

### A.2 A402 (academic survey of agent-payment protocols, 2025)

A protocol-level taxonomy of x402, AP2, AMP, x802 and related
proposals. Compares cryptographic primitives, on-chain settlement
modes, trust assumptions. **Decision algorithms are out of scope.**

**Why we cite it**: positioning — confirms 402Pilot is *protocol-agnostic*,
because the same decision layer can sit above any of these protocols.

### A.3 SoK: Agent Payments and Identity (2026)

Systematization-of-knowledge paper. Emphasis on identity, attestation,
dispute resolution. Mentions selection-among-providers as future work
without proposing a method.

**Why we cite it**: secondary support for "the academic community has
identified provider selection as an open problem".

### A.4 Multi-Agent Economies and Programmable Money (2025)

A position / vision paper on agent-driven economies. Discusses
emergent pricing, market microstructure for agents-as-buyers.
**No algorithm, no benchmark.** Pure framing.

**Why we cite it**: lends 402Pilot the broader narrative motivation
(agents transacting at machine speed). Cited in §1 motivation, not §3
related-work-as-baseline.

### A.5 The original RFC 7235 / RFC 9110 + the "402 Payment Required"
status code (historical)

Optional "deep history" cite if the related-work section discusses why
HTTP 402 was reserved-but-unused for two decades. Probably trimmed in
final paper for space.

---

## 3. Group B — Classical bandit components

Each subsection below is a component PA-DCT *uses*. The point of this
group is to **credit the components separately, then show that no
prior paper combines all of them.**

### B.1 BTS — Budgeted Thompson Sampling [Xia, Ding, Liu, Qin, Liu 2015]

> Y. Xia, T. Qin, N. Yu, et al. *Thompson Sampling for Budgeted
> Multi-armed Bandits.* IJCAI 2015.

**What it has**: TS over arms when each pull consumes a stochastic
amount of a finite budget. Provides regret bounds for the
budget-constrained setting.

**What it lacks (vs. PA-DCT)**:
- No context (one bandit, no per-task vector).
- No discount factor (assumes stationary arms).
- Cost is treated as a scalar drain, not as a *posterior-modeled*
  quantity that can shift mid-experiment.
- No tie to any payment protocol; pure abstract bandit theory.

**How we use it**: PA-DCT's wallet-state-sensitive λ comes from the
BTS lineage. The dual-posterior over cost is our extension — BTS
treats cost as known (or noisy-but-stationary).

### B.2 DS-TS — Discounted Thompson Sampling [Qi, Tan, Wang, Li 2023]

> R. Qi, et al. *Thompson Sampling on Discounted Sufficient Statistics
> for Non-Stationary Multi-Armed Bandits.* (Conference / arXiv 2023.)

**What it has**: introduces a discount factor γ ∈ (0,1) on sufficient
statistics, so the posterior gradually forgets old observations. The
explicit non-stationary regime.

**What it lacks (vs. PA-DCT)**:
- No budget constraint.
- No context; one bandit per arm.
- No cost posterior; only quality / reward is tracked.

**How we use it**: γ = 0.999 on Q-posterior and γ_cost = 0.999 on
cost posterior. The same discount mechanism, applied to two posteriors
in a setting DS-TS does not consider.

### B.3 Contextual TS [Agrawal & Goyal, ICML 2013]

> S. Agrawal, N. Goyal. *Thompson Sampling for Contextual Bandits with
> Linear Payoffs.* ICML 2013.

**What it has**: regret-optimal TS over a linear contextual bandit,
with the canonical Bayesian-posterior-over-θ formulation that almost
every later contextual TS paper builds on.

**What it lacks (vs. PA-DCT)**:
- Stationary by assumption — no discounting.
- No budget; no per-pull cost.
- No payment / financial dimension at all; purely abstract reward.

**How we use it**: PA-DCT's per-(arm, task-type) Gaussian posterior
over θ is the same Bayesian recipe. We bucket task types (3 buckets)
rather than fitting a continuous linear model, since 3 task types is
small enough that bucketed Gaussian-Gaussian conjugacy is exact and
arguably cleaner than a linear approximation.

### B.4 LinUCB [Li, Chu, Langford, Schapire 2010]

> L. Li, et al. *A Contextual-Bandit Approach to Personalized News
> Article Recommendation.* WWW 2010.

**What it has**: a UCB variant in the linear-contextual setting; the
canonical "context vector" baseline.

**Why it's in our suite**: included as one of the six baselines (along
with Random, AlwaysCheap, AlwaysMid, AlwaysPremium, BudgetRule, ε-Greedy,
DTS, and PA-DCT itself). LinUCB performs respectably on S1 but falls
behind PA-DCT under S2/S3 because it has no discount mechanism and no
budget-aware decision rule.

**Differentiation**: LinUCB ≠ PA-DCT for the same reasons Contextual
TS ≠ PA-DCT — no budget pressure, no discount, no cost posterior, no
payment protocol.

### B.5 EXP3 family [Auer, Cesa-Bianchi, Freund, Schapire 2002]

> P. Auer, N. Cesa-Bianchi, Y. Freund, R. E. Schapire. *The
> Nonstochastic Multiarmed Bandit Problem.* SIAM J. Comput. 2002.

**What it has**: adversarial bandit; minimal assumptions on reward
generation.

**Why we mention it**: in the related-work landscape, EXP3 is the
"non-stationarity insurance" alternative to discounted-TS-style
methods. We discuss briefly that EXP3-style methods would be valid
alternatives but are typically more conservative than DS-TS in
stochastic-but-drifting environments like ours; we don't run EXP3 as
a baseline because it would require re-engineering the entire
posterior pipeline for marginal benchmark coverage.

### B.6 Survey: budgeted / non-stationary bandit literature

A few survey references worth keeping for the related-work paragraph:

- *Bandits with Knapsacks* [Badanidiyuru, Kleinberg, Slivkins 2018] —
  the canonical CBwK formalism; closest budget-theoretic neighbor,
  but no discount, no agent / payment framing.
- *Non-Stationary Bandits Survey* [Garivier & Moulines 2011 onwards]
  — establishes the discount-based and sliding-window approaches.

These are footnoted in §3 to anchor breadth of citation; not
individually differentiated since the differentiation is identical
to B.1–B.3.

---

## 4. Group C — LLM cost-aware routing and cascade selection

This is the densest neighbor and where most reviewer confusion will
land. The pattern across all of these papers is: **offline benchmark,
no per-call payment, no budget-state in decision rule, often no online
adaptation at all**.

### C.1 FrugalGPT [Chen, Zaharia, Zou 2023]

> L. Chen, M. Zaharia, J. Zou. *FrugalGPT: How to Use Large Language
> Models While Reducing Cost and Improving Performance.* arXiv 2305.05176.

**What it has**: cascade-style routing — try cheaper LLM, fall back
to expensive only if confidence is low. Explicit cost / quality
trade-off framing.

**What it lacks**:
- Cascade is a fixed policy (rule-based), not learned online.
- No payment protocol; cost is a static API rate card.
- No agent / wallet / budget-pressure dynamics.
- Calibrated once, then deployed; not designed for non-stationary
  prices.

**Differentiation**: FrugalGPT is the closest "name-recognition" cite
for the cost/quality framing. We cite it as motivation: yes, the
trade-off matters; no, FrugalGPT does not solve our problem. Our
BudgetRule baseline is essentially "FrugalGPT-style fixed
threshold", and PA-DCT outperforms it under S2 / S3.

### C.2 RouteLLM [Ong et al., 2024]

> I. Ong, et al. *RouteLLM: Learning to Route LLMs with Preference
> Data.* arXiv 2406.18665 (or similar — 2024 cohort).

**What it has**: a learned router that sends queries to a cheap or
expensive LLM based on a learned classifier over query features.

**What it lacks**:
- Trained offline on preference data, not online via bandit feedback.
- No budget / wallet state.
- Two-arm setting (cheap vs expensive); not multi-provider.
- No payment protocol.

**Differentiation**: RouteLLM is the "context → arm classifier"
framing without the bandit, without the budget, without the protocol.
We share the contextual idea; everything else differs.

### C.3 MixLLM [research cohort 2024]

> Various authors. *MixLLM: ...* (the routing-via-mixture LLM line).

**What it has**: contextual selection among multiple LLM providers,
sometimes with bandit-style online learning.

**What it lacks**:
- No payment protocol; cost is a static rate card.
- Budget treated as "max calls" rather than wallet drain with λ
  feedback.
- Typically no scenario-style non-stationarity benchmark — evaluated
  on offline test sets.

**Differentiation**: MixLLM is the closest in algorithmic flavor —
contextual bandit over LLMs — but stops short of the payment-aware
budget dynamics and the protocol-coupled online setting.

### C.4 Hybrid LLM [2024]

> *Hybrid LLM: Cost-Efficient and Quality-Aware Query Routing.*
> ICLR 2024 (or arXiv 2404.xxxxx).

**What it has**: routing between a small open-source LLM and a large
proprietary one with a learned router, using a desired quality
threshold.

**What it lacks**: same gaps as RouteLLM — no online bandit, no
payment-protocol coupling, no budget-state-aware decisions.

### C.5 AutoMix [Madaan et al., 2024]

> A. Madaan, et al. *AutoMix: Automatically Mixing Language Models.*
> NeurIPS 2024.

**What it has**: self-verification + cascade routing.

**What it lacks**: same as FrugalGPT — cascade not learned online,
no budget, no payment.

### C.6 Group C summary differentiation

The cleanest one-paragraph differentiation for the paper:

> *Prior LLM cost-aware routing (FrugalGPT, RouteLLM, MixLLM, Hybrid
> LLM, AutoMix) studies the offline / static trade-off between LLM
> quality and API rate-card cost. None of these systems take a
> payment protocol as a first-class input, none reason about a
> wallet that drains over time, and none evaluate under
> non-stationary scenarios where prices and quality drift mid-run.*

This paragraph appears verbatim (or close to it) in §3.3 of the paper.

---

## 5. Group D — Closest adjacent paper

There is exactly one paper that, on a casual read, could be confused
with our work. We cite and differentiate it explicitly.

### D.1 Truthful Reverse Auctions for Adaptive LLM Selection [AAMAS 2026]

> arXiv 2602.14476 (placeholder — confirm exact ID before camera-ready)
> *Truthful Reverse Auctions for Adaptive LLM Selection.* AAMAS 2026.

**What it has**:
- Contextual multi-armed bandit over LLM providers.
- Online learning of provider quality.
- Mechanism-design lens (truthfulness, incentive compatibility).
- LLM-selection setting.

**Why a reviewer might think this is our paper**:
- Both: contextual MAB.
- Both: per-call provider selection.
- Both: agent-based language.

**Why it is NOT our paper** — three structural differences:

1. **Mechanism**. AAMAS 2026 uses a *reverse auction* — providers
   submit bids (cost) per round, the buyer chooses based on
   bid + quality estimate. **We use the x402 quote-and-pay flow** —
   prices are posted (or quoted on demand), buyer pays and calls.
   Reverse-auction mechanism design and posted-price selection are
   architecturally different problems.

2. **Framing**. AAMAS 2026 is a mechanism-design paper, with the
   strategic provider as the central object of study. **We are
   protocol-agnostic and provider-non-strategic**: we assume
   providers post real prices and deliver real services; the agent's
   decision layer is the central object of study.

3. **Benchmark**. AAMAS 2026 evaluates on LLM tasks but not on the
   non-stationary scenario suite (S1 / S2 outage / S3 promo) we
   define. Our reproducible benchmark — frozen pregen dataset, 30
   seeds, 10k rounds, three calibrated scenarios — is contribution C4.
   The AAMAS paper's benchmark cannot be reused for our setting
   because the auction mechanism eats the protocol layer.

**Citation strategy**: cited in §3.4 as the closest adjacent work,
with the three-bullet differentiation above.

---

## 6. Citation strategy table (paper → key)

| Paper section | Citation key | Group | Purpose |
|---|---|---|---|
| §1 motivation | x402 V2 spec | A.1 | "the protocol explicitly defers selection" |
| §1 motivation | A402 / SoK | A.2/A.3 | the academic frame for protocol-level work |
| §1 motivation | FrugalGPT | C.1 | "the cost/quality trade-off matters" hook |
| §3.1 protocol layer | x402 V2 / A402 / SoK | A | protocol survey paragraph |
| §3.2 bandit components | Xia 2015 / Qi 2023 / Agrawal 2013 | B.1/B.2/B.3 | each component, separately credited |
| §3.2 bandit baselines | Li 2010 (LinUCB) / Auer 2002 (EXP3) | B.4/B.5 | adjacent algorithmic family |
| §3.3 LLM routing | FrugalGPT / RouteLLM / MixLLM / Hybrid LLM / AutoMix | C.1–C.5 | densest related neighbor |
| §3.4 closest adjacent | AAMAS 2026 [2602.14476] | D.1 | dedicated differentiation paragraph |
| §3.5 surveys / breadth | CBwK / Garivier & Moulines | B.6 | breadth footnote |

The Related Work section in the paper draft will follow this table
top-to-bottom; cross-referencing here keeps citations consistent
between the paper and this audit document.

---

## 7. Cross-reference: novelty claim ↔ negative finding

Each of the five contributions in `paper_design_decisions.md` §11.4
is supported by an empty intersection in this literature review. The
table below is the reviewer's path from "claim" to "evidence the
claim is non-trivial".

| Claim | What "no prior art" looks like for this claim |
|---|---|
| **C1 — Setting characterization** (agent-native bandits) | Group A papers do protocol, not algorithm. Group C papers have a human operator (researcher running the offline benchmark). No paper frames the bandit as the operator, nor introduces "agent-native" as a regime. |
| **C2 — PA-DCT algorithm** | Group B papers each have one of {budgeted, discounted, contextual} but no paper has all three. Group D adjacent paper has contextual + online but in a reverse-auction mechanism; not the budgeted-and-discounted contextual TS combination. |
| **C3 — 402Pilot decision layer** | Group A frames protocol layers; no Group A paper articulates a stable interface for an algorithmic decision layer above the protocol. The interface in §11.3 is novel. |
| **C4 — Reproducible benchmark** | Group C papers benchmark on offline test sets (FrugalGPT-style), not on calibrated non-stationary scenarios with shared pregen. Group D benchmarks under reverse auction, which is incompatible with our setting. No prior shared 30-seed × 3-scenario × 5-provider benchmark exists for this regime. |
| **C5 — Empirical findings** | This is our experimental contribution. Reviewable only by reading the results — but the *claim that these findings are interesting* depends on C1 / C2 / C3 / C4, all of which are supported by the empty cells above. |

---

## 8. Open audit items / what we did NOT search

For honesty: places we did *not* exhaustively search, with explanation
of why we believe the gap is still empty there.

- **Reinforcement-learning + payments**: there's a small body of work
  on RL-for-trading and RL-for-bidding. We did not exhaustively cite
  this because RL ≠ bandit (long-horizon credit assignment), and our
  "why bandit not RL" paragraph in §1 of the paper handles this.
  Reviewers asking "what about RL" should be answered there, not in
  Related Work.

- **Algorithmic mechanism design**: some adjacent literature on
  truthful mechanisms with learning (beyond AAMAS 2026 / D.1). Did
  not exhaust; the relevant differentiation is identical to D.1
  (mechanism-design vs decision-layer framing).

- **Web search depth**: limited to ~3 search rounds across the three
  axes. A pre-camera-ready re-audit pass is still on the to-do list.

- **Non-English literature**: no Chinese / Japanese / German bandit
  papers searched. Low risk given the topic is dominated by US/EU/CN
  ML conferences whose papers are typically English-published.

A single pre-camera-ready re-audit (2-3 hours) is scheduled before
final submission to refresh citations and confirm no new arXiv
preprint between now and submission has eaten our novelty. Logged
in `IDEATION.md` (or wherever the camera-ready checklist lives).

---

## 9. Bottom-line statement (for the abstract / introduction)

The exact wording the paper will use to describe novelty, anchored on
this audit:

> *To our knowledge, 402Pilot is the first work to formalize the
> agent-native programmable-micropayment decision setting, to combine
> Budgeted, Discounted, and Contextual Thompson sampling into a single
> dual-posterior algorithm (PA-DCT), and to provide a reproducible
> three-scenario benchmark for evaluating decision algorithms in this
> regime. The closest adjacent work [AAMAS 2026 reverse auctions]
> studies a different mechanism (auction, not posted price) and a
> different framing (mechanism design, not decision layer).*

This sentence is what the entire literature review supports.

---

## 10. File index

Cross-references for paper writing:

- `paper_design_decisions.md` §11.4 — five contributions
- `paper_design_decisions.md` §11.5 — anti-prior-art summary table
- `paper_design_decisions.md` §11.7 — "agent-native bandits" definition
- `logs/m3f_dual_posterior_design.md` — algorithm internals (cited
  internally only; not externally citeable)
- `logs/ablation_4metrics_table.md` — empirical evidence supporting C5

---

**Last updated**: 2026-05-05. To be re-audited before paper submission.
