# Repository Layout

This is the *target* repository layout. Nothing in `pilot402/`, `experiments/`,
`scripts/`, or `paper/` exists yet — implementation is deferred until plan
sign-off. Module names use `snake_case`; package name is `pilot402` (Python
identifier; underscored alias for the `402Pilot` brand).

The layout is chosen so that:

- Every `Policy` is a drop-in implementation of one interface, enabling clean
  apples-to-apples evaluation.
- The simulator (`env/`) and the real x402 client (`x402/`) are
  interchangeable behind a `PaymentExecutor` interface, enabling the
  x402-in-the-loop probe without rewriting policy code.
- Reproducibility artifacts (configs, seeds, logs, figures) are first-class.

---

## Top level

```
PayPilot/                       # repository root (existing folder name kept)
├── IDEATION.md                 # original ideation (read-only)
├── PLAN.md                     # master plan
├── docs/                       # planning docs (this folder)
├── pilot402/                   # main Python package (to be created)
├── experiments/                # experiment configs (YAML)
├── scripts/                    # CLI entry points
├── data/                       # calibration sources, fixtures (gitignored bulk)
├── results/                    # run outputs (gitignored bulk)
├── paper/                      # LaTeX sources (added in writing phase)
├── viz/                        # interactive explainer (GitHub Pages, added in writing phase)
├── tests/                      # unit + integration tests
└── pyproject.toml              # package config
```

---

## `pilot402/` package

```
pilot402/
├── __init__.py
│
├── core/                       # Types, interfaces, config schema
│   ├── types.py                # ProviderSpec, Task, Decision, Outcome, Reward
│   ├── interfaces.py           # Policy, Encoder, BudgetManager, Evaluator,
│   │                           #   PaymentExecutor protocols
│   ├── config.py               # typed config (pydantic) and YAML loader
│   └── seeds.py                # single random source, seeded per run
│
├── env/                        # Micro-economy simulator (replay-based)
│   ├── tasks.py                # task generator (3 task types: coding, multi-hop QA, web search)
│   ├── providers.py            # cost / latency / failure models; quality replayed from pregen dataset
│   ├── calibration.py          # cost/latency noise parameters and P-flaky timeout rate only
│   │                           #   (quality is NOT fitted here — it comes from real LLM outputs in pregen/)
│   ├── dynamics.py             # scenario engine: S1 stationary, S2 abrupt-degradation, S3 price-shock
│   └── workload.py             # workload composition / arrival schedule
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
│   └── lambdas.py              # budget-aware lambda_t functions
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
│   └── reward.py               # r = q - lambda*c~ - mu*l~ - nu*f
│
├── eval/                       # Evaluators (quality scoring)
│   ├── metric_backend.py       # exact match, F1, pass@1  [used at pregen time]
│   ├── judge_backend.py        # LLM-as-judge wrapper (logged, seedable)  [used at pregen time]
│   └── composite.py            # per-task-type composite evaluator
│                               #   two modes: score(task, response) for pregen;
│                               #   lookup(task_id, provider_id, version) → cached float for experiments
│                               #   experiment runs ALWAYS use lookup; score is never called during a bandit loop
│
├── x402/                       # x402-in-the-loop integration
│   ├── client.py               # PaymentExecutor over a real x402 client
│   ├── wallet.py               # mock / testnet wallet
│   └── server/                 # local paid mock services (3 tiers)
│       ├── cheap.py
│       ├── medium.py
│       └── premium.py
│
├── runner/                     # Experiment runner
│   ├── loop.py                 # the per-round loop; also owns Policy Updater logic (system_design §2.7):
│   │                           #   updates per-provider EWMA stats, calls policy.update(ctx, arm, utility),
│   │                           #   applies per-arm discount, emits the structured log record
│   ├── recorder.py             # structured JSON-line logging
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
├── ablation_no_context.yaml
├── ablation_no_discount.yaml
├── ablation_no_budget_lambda.yaml
└── ablation_no_lat_fail.yaml
```

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
└── x402_demo.py                # smoke test for the x402-in-the-loop wiring
```

---

## `tests/`

```
tests/
├── test_env_dynamics.py        # scenarios produce expected schedules
├── test_calibration.py         # fitted distributions match held-out subsets
├── test_policies_smoke.py      # every policy exposes the same interface
├── test_padcts_correctness.py  # discount + budget-lambda behave as specified
├── test_runner_determinism.py  # same seed → same logs
└── test_x402_loop.py           # mock x402 round-trip, budget enforcement
```

---

## `viz/` interactive explainer (GitHub Pages)

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
- **Comments and docstrings.** All English (per project rule).
- **Style.** Type-annotated; configs validated with pydantic.
- **Determinism.** All randomness via `core.seeds`; never call top-level
  `random` / `numpy.random` directly.
- **Logs.** JSON-lines under `results/<run_id>/`. The same loader feeds
  tables, figures, and tests.
- **No global state in modules.** Every module is exercised by a unit test
  with a fresh config and seed.
