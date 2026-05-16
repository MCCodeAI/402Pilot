# Repository Layout

**Status:** historical target-layout draft. The current repository tree,
README, and ACM paper are the source of truth; this file is kept for design
history and may not describe every current module exactly.

This is the *target* repository layout. Only `IDEATION.md`, `PLAN.md`,
`README.md`, and `docs/` currently exist; everything else
(`pilot402/`, `experiments/`, `scripts/`, `tests/`, `paper/`, `viz/`,
`data/`, `results/`, `.env*`, `.gitignore`, `pyproject.toml`) is deferred
until plan sign-off. Module names use `snake_case`; package name is
`pilot402` (Python identifier; underscored alias for the `402Pilot` brand).

**Project rule.** All comments, docstrings, identifiers, and committed
documentation are in English.

The layout is chosen so that:

- Every `Policy` is a drop-in implementation of one interface, enabling clean
  apples-to-apples evaluation.
- Every selected provider in every experimental round is invoked through the
  `PaymentExecutor` interface, which is *always* backed by the real x402
  client (`x402/`) talking to the local Anvil DEVnet. There is no
  x402-bypass code path. The `env/` simulator owns task generation, scenario
  dynamics, and quality replay; payment execution is not part of the
  simulator.
- Reproducibility artifacts (configs, seeds, logs, figures) are first-class.

---

## Top level

```
402Pilot/                       # repository root (GitHub repo name)
├── IDEATION.md                 # original ideation (read-only)
├── PLAN.md                     # master plan
├── README.md
├── docs/                       # planning docs (this folder)
│   └── dataset_schema.md       # PregenRecord schema spec (consumed by env/, eval/)
├── pilot402/                   # main Python package (Python identifier; underscored alias for the 402Pilot brand)
├── experiments/                # experiment configs (YAML)
├── scripts/                    # CLI entry points
├── data/                       # calibration sources, pregen bench dataset (gitignored bulk)
│   ├── pregen/                 # PregenRecord JSONL — one file per (provider × task_type)
│   ├── calibration/            # raw cost/latency observations per provider
│   └── tasks/                  # cached HumanEval / HotpotQA / TriviaQA splits
├── results/                    # run outputs (gitignored bulk)
│   └── <run_id>/
│       ├── config.yaml         # frozen copy of the input experiment config
│       ├── log.jsonl           # per-round structured records (recorder.py output)
│       └── summary.json        # aggregated metrics for this run
├── paper/                      # LaTeX sources (added in writing phase)
├── viz/                        # interactive explainer (GitHub Pages, Phase 5 only)
├── tests/                      # unit + integration tests
├── .env.example                # template listing required env vars (committed)
├── .env                        # local secrets: LLM API keys, ANVIL_RPC_URL,
│                               #   x402 wallet private key (gitignored)
├── .gitignore
└── pyproject.toml              # package config
```

**`.env` contents (template lives in `.env.example`).**

```
# LLM provider keys — used only during pregen (Phase 1)
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
QWEN_API_KEY=...

# Local Anvil DEVnet (Phase 2+; no public testnet)
ANVIL_RPC_URL=http://127.0.0.1:8545
ANVIL_CHAIN_ID=31337

# x402 wallet — Anvil-funded test account, never used outside DEVnet
X402_WALLET_PRIVATE_KEY=0x...
X402_FACILITATOR_URL=http://127.0.0.1:4021

# LLM-as-judge backend (used in pregen scorer)
JUDGE_MODEL=claude-sonnet-4.6
```

`core.config` reads `.env` via `pydantic-settings`; nothing else in the
package touches `os.environ` directly.

---

## `pilot402/` package

```
pilot402/
├── __init__.py
│
├── core/                       # Types, interfaces, config schema
│   ├── types.py                # ProviderSpec, Task, Decision, Outcome, Reward
│   ├── interfaces.py           # Policy, Encoder, BudgetManager, Evaluator,
│   │                           #   PaymentExecutor, PregenStore protocols
│   ├── config.py               # typed config (pydantic) and YAML loader
│   └── seeds.py                # single random source, seeded per run
│
├── env/                        # Micro-economy simulator (replay-based)
│   ├── tasks.py                # task generator (3 task types: coding, multi-hop QA, web search)
│   ├── providers.py            # cost / latency / failure models; quality served via a
│   │                           #   PregenStore adapter (see core.interfaces.PregenStore) —
│   │                           #   env/ never imports pregen/ directly
│   ├── calibration.py          # cost/latency noise parameters and P-flaky timeout rate only
│   │                           #   (quality is NOT fitted here — it comes from real LLM outputs in pregen/)
│   ├── workload.py             # workload composition / arrival schedule
│   └── scenarios/              # scenario engine — each scenario is an explicit schedule object
│       ├── __init__.py         # registry: {"S1": Stationary, "S2": Degradation, "S3": PriceShock}
│       ├── stationary.py       # S1: parameters held constant for all 10,000 rounds
│       ├── degradation.py      # S2: P-mid quality cliff at round 3,000
│       └── price_shock.py      # S3: provider price multipliers shift at round 5,000
│
├── pregen/                     # Pre-generation pipeline (Phase 1 only; run once before any experiment)
│   ├── generator.py            # drives 20,575 LLM API calls (5 providers × 823 effective tasks × 5 versions)
│   ├── scorer.py               # computes and caches pass@1, EM/F1, and LLM-as-judge scores per response
│   └── dataset.py              # dataset schema (PregenRecord) + load/query interface used by env/
│
├── encoders/                   # Context encoders
│   ├── default.py              # the initial feature set described in system_design
│   └── difficulty.py           # difficulty estimator (heuristic / lightweight)
│
├── budget/                     # Budget manager
│   ├── manager.py              # state, record_spend, hard-block logic
│   ├── lambdas.py              # budget-aware lambda_t functions (cost-weight schedule)
│   └── sizing.py               # compute B such that Always-P-premium exhausts wallet
│                               #   near round ~5,000 given a scenario's price schedule
│                               #   (PLAN §3.5); used by experiments/ at config-load time
│                               #   so B is recorded in the run log, never a magic number
│
├── policies/                   # Selector implementations
│   ├── base.py                 # Policy ABC
│   ├── fixed.py                # always-cheap / medium / premium / random
│   ├── rule.py                 # difficulty-rule, budget-rule
│   ├── eg.py                   # epsilon-greedy
│   ├── ts.py                   # vanilla TS, contextual TS
│   ├── dts.py                  # discounted TS (non-contextual)
│   ├── linucb.py               # LinUCB
│   └── padct.py               # PA-DCT (ours)
│
├── reward/                     # Reward calculator
│   ├── normalizer.py           # cost / latency normalization stats
│   ├── weights.py              # the three penalty weights:
│   │                           #     lambda_t — budget-aware cost weight (delegates to budget.lambdas)
│   │                           #     mu       — latency weight (constant; configured per experiment)
│   │                           #     nu       — failure weight (constant; configured per experiment)
│   │                           #   single source of truth so reward.py never reaches into other modules
│   └── reward.py               # r = q - lambda_t * c~ - mu * l~ - nu * f
│
├── eval/                       # Evaluators (quality scoring)
│   ├── metric_backend.py       # exact match, F1, pass@1  [used at pregen time]
│   ├── judge_backend.py        # LLM-as-judge wrapper (logged, seedable)  [used at pregen time]
│   └── composite.py            # per-task-type composite evaluator
│                               #   two modes: score(task, response) for pregen;
│                               #   lookup(task_id, provider_id, version) → cached float for experiments
│                               #   experiment runs ALWAYS use lookup; score is never called during a bandit loop
│
├── x402/                       # x402 integration — mandatory in every experimental round
│   ├── client.py               # PaymentExecutor implementation over a real x402 client
│   ├── wallet.py               # Anvil DEVnet wallet (Anvil-funded test account; never
│   │                           #   used outside the local fork — see experiment_design.md)
│   └── server/                 # local paid endpoints — one per provider in the K=5 market;
│       │                       #   cost differences are encoded in the per-endpoint x402
│       │                       #   price; behavioural differences (quality / latency / failure)
│       │                       #   come from env/providers.py via the PregenStore replay
│       ├── __init__.py         # provider registry and make_p_* factories
│       │                       #   for P-cheap, P-mid, P-premium, and P-adv
│       └── p_flaky.py          # P-flaky timeout wrapper
│
├── runner/                     # Experiment runner
│   ├── loop.py                 # per-round orchestration only:
│   │                           #   sample task → policy.select → x402.pay →
│   │                           #   PregenStore quality lookup → reward.compute →
│   │                           #   recorder.write → delegate post-round bookkeeping to updater
│   ├── updater.py              # Policy Updater (system_design §2.7):
│   │                           #   per-provider EWMA stats, per-arm discount,
│   │                           #   policy.update(ctx, arm, utility);
│   │                           #   pure function of (state, outcome) → new state for testability
│   ├── recorder.py             # structured JSON-line logging (no business logic)
│   └── orchestrator.py         # multi-seed, multi-scenario sweeps
│
└── analysis/                   # Plotting and stats
    ├── tables.py               # main result tables, ablation tables
    ├── plots.py                # regret, utility-per-dollar, adaptation curves
    └── stats.py                # significance tests, CIs
```

---

## `experiments/` configs

```
experiments/
├── main.yaml                   # 402Pilot-Bench full sweep (all scenarios,
│                               #   all comparators, 30 seeds)
├── ablation_no_context.yaml          # A1
├── ablation_no_discount.yaml         # A2
├── ablation_no_budget_lambda.yaml    # A3
└── ablation_no_failure.yaml          # A4 (no-failure-penalty; nu = 0)
```

Names map 1:1 to PLAN §3.3 A1–A4. If a future revision adds an A5
(e.g., no-latency-penalty, mu = 0), add a matching `ablation_no_latency.yaml`
here at the same time.

Each YAML is the only source of truth for a run; nothing about a run is
specified in code.

---

## `scripts/` CLI

```
scripts/
├── run_pregen.py               # python -m scripts.run_pregen <config.yaml>  [Phase 1 entry point]
│                               #   calls pregen/generator.py + pregen/scorer.py; writes to data/
├── run_experiment.py           # python -m scripts.run_experiment <config.yaml>
├── make_figures.py             # builds all paper figures from results/
├── make_tables.py              # builds all paper tables from results/
├── export_viz_data.py          # exports results/ → viz/public/data/ JSON fixtures
└── devnet/                     # Phase 5 only — reproducibility witness for viz/Explainer/DevnetDemo
    ├── start_anvil.sh          # forks Base at a pinned block; funds a test wallet
    ├── deploy_facilitator.sol  # minimal x402 facilitator + USDC mock
    ├── deploy.ts               # Foundry/Hardhat deploy script
    └── README.md               # one-page run instructions
```

There is no separate x402 smoke-test script: `run_experiment.py` exercises
the full x402 path on every invocation, and `tests/test_x402_loop.py`
covers the round-trip + budget-enforcement assertions.

---

## `tests/`

```
tests/
├── test_env_scenarios.py            # S1/S2/S3 scenario objects produce expected schedules
├── test_calibration.py              # fitted distributions match held-out subsets
├── test_policies_smoke.py           # every policy exposes the same interface
├── test_policies_padct.py           # discount + budget-lambda behave as specified
├── test_reward_correctness.py       # r = q - lambda*c~ - mu*l~ - nu*f, including
│                                    #   weight-zero edge cases used by ablations A3/A4
├── test_pregen_scorer_determinism.py# same response → same score across runs
│                                    #   (deterministic backends: exact match, F1, pass@1)
├── test_replay_endtoend.py          # tiny fixture (e.g. 50 rounds, 2 providers) →
│                                    #   known cumulative regret; guards against silent
│                                    #   regressions in env/runner/reward integration
├── test_runner_determinism.py       # same seed → same logs
└── test_x402_loop.py                # Anvil DEVnet round-trip, budget enforcement
```

---

## `viz/` interactive explainer (GitHub Pages) — Phase 5 only

> **Scope note.** `viz/` is built only in Phase 5 (polish & submission). It is
> not on the critical path for Phases 1–4 and consumes only frozen exports
> from `results/`; nothing in `pilot402/` depends on it.

Static single-page web app deployed to GitHub Pages alongside the paper.
Built with React + Vite; no server required. All experimental data is loaded
from pre-exported JSON fixtures under `viz/public/data/` (generated by
`scripts/export_viz_data.py` from the experiment results). One optional
section (`DevnetDemo`) talks to a local Anvil RPC if and only if the visitor
runs the repo locally — the GitHub Pages deployment renders it disabled.

**Reward / utility convention.** All posterior visualizations use
`utility = q − ν·f` (per `logs/reward_design_rationale.md`, 2026-05-02 final).
The latency term `μ·l̃` was removed from the reward and is not visualized.
Selection-time ranking uses the sigmoid-bounded payment-aware reward
`PA_reward = (1 − λ_norm)·utility − λ_norm·c̃`, with
`λ_norm = λ_t / (1 + λ_t) = sigmoid(α·burn_excess)`. The viz must not
re-introduce the deprecated `r = q − λ·c̃ − μ·l̃ − ν·f` form.

**Top-level UX rules.**
- A persistent disclaimer banner under the header reads:
  *"Experiments: 10,000 rounds × 30 seeds × 3 scenarios, fully replayed from
  fixtures. Mock wallet. x402 settlement boundary preserved at the executor
  layer; no public testnet."*
- Every chart has an inline caption (≤ 60 words) explaining what the reader
  is looking at and why it matters. Captions are content, not decoration.
- All method-name references say **PA-DCT**, never PA-DCTS.

**Three primary sections + one optional demo.**

```
viz/
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json
│
├── public/
│   └── data/                   # pre-exported JSON fixtures (gitignored bulk)
│       ├── runs/               # per-seed per-scenario per-policy run logs
│       │   ├── S{1,2,3}_padct_seed{0..29}.jsonl
│       │   ├── S{1,2,3}_a{1..4}_seed{0..29}.jsonl       # ablations
│       │   └── S{1,2,3}_{premium,budget,oracle}_seed{0..29}.jsonl
│       ├── summary.json        # aggregated mean ± std for all metrics × policies
│       │                       #   stratified by (scenario, task_type ∈
│       │                       #   {T1, T2, T3a, T3b}, policy)
│       └── posteriors/         # sampled posterior snapshots (utility-space)
│           └── S{1,2,3}_padct_seed0_posteriors.jsonl
│                               #   per round t: {arm: {mean, var}}
│
└── src/
    ├── main.tsx
    ├── App.tsx                 # top-level layout; banner + 3 sections + demo
    ├── data/
    │   └── loaders.ts          # typed fetch wrappers for public/data fixtures
    │
    ├── sections/
    │   ├── Explainer/                    # §1 — Why PA-DCT works
    │   │   ├── index.tsx                 # section shell + scroll trigger
    │   │   ├── HiddenTwinTest.tsx        # D3: utility posteriors of P-mid /
    │   │   │                             #   P-adv / P-flaky over rounds
    │   │   │                             #   (same price tier, same base model)
    │   │   │                             #   — section hero
    │   │   ├── FlowDiagram.tsx           # 6-step PA-DCT loop:
    │   │   │                             #   Context → Budget(λ_t) → Selector
    │   │   │                             #   → [x402 Executor]* → Evaluator
    │   │   │                             #   → Reward + Posterior Update
    │   │   │                             #   * step 4 rendered grayed/dashed
    │   │   │                             #   with "out of scope" label
    │   │   ├── RewardDecompose.tsx       # 2-step reveal:
    │   │   │                             #   utility = q − ν·f, then
    │   │   │                             #   PA_reward = (1−λ_n)·u − λ_n·c̃
    │   │   ├── LambdaChart.tsx           # x: burn_excess_t, y: λ_norm
    │   │   │                             #   sigmoid curve
    │   │   ├── NuPanel.tsx               # mini bar: P-flaky E[utility] for
    │   │   │                             #   ν ∈ {0.0, 0.1, 0.5, 1.0, 2.0}
    │   │   │                             #   highlighting locked ν=0.5
    │   │   └── DevnetDemo.tsx            # optional: see §Devnet demo below
    │   │
    │   ├── Simulation/                   # §2 — Replay one run
    │   │   ├── index.tsx                 # controls + main stage
    │   │   ├── ControlBar.tsx            # tabs: scenario S1/S2/S3,
    │   │   │                             #   task_type T1/T2/T3a/T3b;
    │   │   │                             #   seed slider 0–29; speed; play/pause
    │   │   ├── RoundStepper.tsx          # round scrubber 0–10,000
    │   │   ├── ProviderArms.tsx          # D3: per-round utility posteriors
    │   │   │                             #   (5 providers, violin / ridge)
    │   │   ├── BudgetBar.tsx             # wallet depletion + event markers
    │   │   ├── RoundLog.tsx              # last 10 rounds: t | task | a* |
    │   │   │                             #   q | c | utility | PA_reward
    │   │   ├── EventMarker.tsx           # S2/S3 change-points (3k/5k)
    │   │   └── DetectionBadge.tsx        # per (scenario, task_type) round
    │   │                                 #   when P-adv selection prob first
    │   │                                 #   drops below 5% and stays
    │   │
    │   └── Results/                      # §3 — Aggregated dashboard
    │       ├── index.tsx                 # tabs + filter controls
    │       ├── StatsTable.tsx            # mean ± std for ROI, success rate,
    │       │                             #   regret; rows = policies, cols =
    │       │                             #   scenarios; PA-DCT bolded
    │       ├── RegretCurve.tsx           # cumulative regret with 95% CI band
    │       │                             #   per (scenario), all policies
    │       ├── RegretByTaskType.tsx      # 3-up small multiples: T1, T2, T3
    │       │                             #   (T3 split T3a vs T3b inside)
    │       ├── ROIChart.tsx              # ROI over rounds, S3 shock line
    │       ├── HeatMap.tsx               # D3: provider selection frequency
    │       │                             #   x = round bucket, y = provider
    │       └── AblationBars.tsx          # ΔROI vs full PA-DCT for A1–A4,
    │                                     #   grouped by scenario
    │
    └── components/                       # shared UI primitives
        ├── DisclaimerBanner.tsx          # fixed banner under header
        ├── Caption.tsx                   # inline chart caption (≤60 words)
        ├── ScenarioSelector.tsx          # S1 / S2 / S3 tab strip
        ├── TaskTypeSelector.tsx          # T1 / T2 / T3a / T3b tabs
        ├── PolicyToggle.tsx              # checkboxes: PA-DCT, A1–A4, baselines
        ├── SeedSlider.tsx                # pick one of 30 seeds to replay
        └── Tooltip.tsx                   # consistent hover tooltip
```

**Data flow.**
`scripts/export_viz_data.py` reads from `results/` and writes compact JSON
fixtures to `viz/public/data/`. The web app never touches raw experiment logs.
All fixtures are versioned by run ID; the export script is idempotent. JSONL
records follow the system-design contract exactly:
`{round, context, arm, cost, latency, quality, failure, utility, reward, budget_remaining}`.
The viz reads `utility` and `reward` directly; it does not recompute either
from raw fields.

**Deployment.**
`gh-pages` branch; deploy via `npm run deploy` (Vite build → `gh-pages` push).
Canonical URL: `https://<org>.github.io/402Pilot/`.

**Technology choices.**
- React 18 + TypeScript + Vite — fast build, static output, no backend.
- D3 v7 — Hidden Twin Test, ProviderArms, HeatMap (custom shapes).
- Recharts — RegretCurve, ROIChart, AblationBars (standard chart types).
- Framer Motion — section transitions, FlowDiagram step animation,
  RewardDecompose reveal.
- CSS Modules — scoped styling, no runtime CSS-in-JS overhead.
- `viem` — minimal Ethereum client used only by `DevnetDemo` (no full
  ethers.js).

---

### Devnet demo — reproducibility witness, not benchmark data

`Explainer/DevnetDemo.tsx` is a single-round live trace that touches a local
Anvil fork of Base. Its purpose is to show that 402Pilot's x402 wrapper is a
real integration, not a paper-only stub. **It is not the source of any number
in the paper.** The benchmark replays remain fully fixture-driven.

**Default state on GitHub Pages.** Disabled. The component pings
`http://127.0.0.1:8545` on mount; if no Anvil RPC responds, the Run button is
grayed out with a one-line hint:
*"Run locally to enable: clone repo & `./scripts/devnet/start_anvil.sh`."*

**When enabled (local run).** Two-pane panel:

- *Left pane:* `Run one round` button; read-only fields for task type,
  budget remaining (drives λ_t), wallet address, Anvil RPC URL.
- *Right pane:* a 6-step timeline. Each step prints its inputs/outputs as
  PA-DCT executes one synthetic round. Step 4 (`x402 Payment Executor`) is
  the only step that issues a real RPC call; it shows the tx hash, block
  number, gas used, USDC transferred, and observed wall-clock latency.

**Supporting scripts** live outside `viz/` to keep the web app static:

```
scripts/devnet/
├── start_anvil.sh              # forks Base at a pinned block; funds a test wallet
├── deploy_facilitator.sol      # minimal x402 facilitator + USDC mock
├── deploy.ts                   # Hardhat/Foundry deploy script
└── README.md                   # one-page run instructions
```

**Caption shown above the demo:**
*"This demo runs one round end-to-end against a local Anvil fork of Base.
Step 4 is the only step that touches the chain. In Section 2 (Simulation
Replay), Step 4 is replaced by a deterministic pre-generated record — no
chain access. See `experiment_design.md §8`."*

---

## Conventions

- **Language.** Python ≥ 3.11 for the package; LaTeX for the paper;
  TypeScript + React 18 for the `viz/` explainer.
- **Comments and docstrings.** English only (see project rule above).
- **Style.** Type-annotated; configs validated with pydantic.
- **Determinism.** All randomness via `core.seeds`; never call top-level
  `random` / `numpy.random` directly.
- **Logs.** JSON-lines under `results/<run_id>/`. The same loader feeds
  tables, figures, and tests.
- **No global state in modules.** Every module is exercised by a unit test
  with a fresh config and seed.
