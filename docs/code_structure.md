# Repository Layout

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
│   ├── generator.py            # drives ~20,625 LLM API calls (5 providers × 825 tasks × 5 versions)
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
│   └── padcts.py               # PA-DCTS (ours)
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
│       ├── p_cheap.py          # P-cheap   (Qwen3-8B, no tools)
│       ├── p_mid.py            # P-mid     (GPT-5.4-mini, BM25)
│       ├── p_premium.py        # P-premium (GPT-5.4, CoT + tools)
│       ├── p_adv.py            # P-adv     (GPT-5.4-mini + adversarial system prompt)
│       └── p_flaky.py          # P-flaky   (GPT-5.4-mini + 20% timeout injection)
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
└── export_viz_data.py          # exports results/ → viz/public/data/ JSON fixtures
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
├── test_padcts_correctness.py       # discount + budget-lambda behave as specified
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
Built with React + Vite; no server required. All data is loaded from
pre-exported JSON fixtures under `viz/public/data/` (generated by
`scripts/export_viz_data.py` from the experiment results).

**Three sections, one page.**

```
viz/
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json
│
├── public/
│   └── data/                   # pre-exported JSON fixtures (gitignored bulk)
│       ├── runs/               # per-seed per-scenario run logs
│       │   ├── S1_padcts_seed{0..29}.jsonl
│       │   ├── S2_padcts_seed{0..29}.jsonl
│       │   └── S3_padcts_seed{0..29}.jsonl
│       ├── summary.json        # aggregated mean ± std for all metrics × policies
│       └── posteriors/         # sampled posterior snapshots for animation
│           └── S1_padcts_seed0_posteriors.json
│
└── src/
    ├── main.tsx
    ├── App.tsx                 # top-level layout; three sections wired together
    ├── data/
    │   └── loaders.ts          # typed fetch wrappers for public/data fixtures
    │
    ├── sections/
    │   ├── Explainer/          # §1 — Algorithm principle animation
    │   │   ├── index.tsx       # section shell + scroll trigger
    │   │   ├── FlowDiagram.tsx # animated PA-DCTS loop:
    │   │   │                   #   Context → Budget → Selector → Provider → Reward
    │   │   ├── PosteriorViz.tsx# D3: 5 provider Beta/normal posteriors
    │   │   │                   #   evolving per round; scrubber-controlled
    │   │   └── LambdaChart.tsx # budget-aware λ_t vs. budget ratio
    │   │
    │   ├── Simulation/         # §2 — Experiment process replay
    │   │   ├── index.tsx       # section shell + play/pause/speed controls
    │   │   ├── RoundStepper.tsx# round scrubber (0–10 000), play/pause/speed
    │   │   ├── ProviderArms.tsx# D3: per-round arm widths (posterior uncertainty)
    │   │   ├── BudgetBar.tsx   # wallet depletion bar with event markers
    │   │   ├── EventMarker.tsx # S2/S3 change-point annotation (round 3k/5k)
    │   │   └── DetectionBadge.tsx  # badge when P-adv/P-flaky first "learned"
    │   │
    │   └── Results/            # §3 — Aggregated results dashboard
    │       ├── index.tsx       # section shell; scenario + policy filter controls
    │       ├── RegretCurve.tsx # Recharts: cumulative regret curves
    │       │                   #   PA-DCTS vs. ablations vs. baselines; 95% CI band
    │       ├── ROIChart.tsx    # Recharts: ROI over rounds; S3 price-shock event line
    │       ├── SuccessRate.tsx # Recharts: task-success-rate bar chart per policy
    │       ├── HeatMap.tsx     # D3: provider selection frequency (time × provider)
    │       └── StatsTable.tsx  # summary table: mean ± std, Welch t, effect size
    │
    └── components/             # shared UI primitives
        ├── ScenarioSelector.tsx    # S1 / S2 / S3 tab strip
        ├── PolicyToggle.tsx        # checkboxes: PA-DCTS, A1–A4, baselines
        ├── SeedSlider.tsx          # pick which of 30 seeds to replay
        └── Tooltip.tsx             # consistent hover tooltip
```

**Data flow.**
`scripts/export_viz_data.py` reads from `results/` and writes compact JSON
fixtures to `viz/public/data/`. The web app never touches raw experiment logs.
All fixtures are versioned by run ID; the export script is idempotent.

**Deployment.**
`gh-pages` branch; deploy via `npm run deploy` (Vite build → `gh-pages` push).
Canonical URL: `https://<org>.github.io/402Pilot/`.

**Technology choices.**
- React 18 + TypeScript + Vite — fast build, static output, no backend.
- D3 v7 — posterior distribution animation, provider arm widths, heatmap.
- Recharts — regret curves, ROI chart, success-rate bars (simpler API for
  standard chart types).
- Framer Motion — section-entry and flow-diagram step animations.
- CSS Modules — scoped styling, no runtime CSS-in-JS overhead.

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
