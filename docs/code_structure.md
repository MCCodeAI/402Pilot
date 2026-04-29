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
├── env/                        # Calibrated micro-economy simulator
│   ├── tasks.py                # task generator (3 task types: coding, multi-hop QA, web search)
│   ├── providers.py            # quality / cost / latency / failure models
│   ├── calibration.py          # fit provider distributions to public benchmarks
│   ├── dynamics.py             # scenario engine: S1 stationary, S2 abrupt-degradation, S3 price-shock
│   └── workload.py             # workload composition / arrival schedule
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
│   ├── metric_backend.py       # exact match, F1, pass@1
│   ├── judge_backend.py        # LLM-as-judge wrapper (logged, seedable)
│   └── composite.py            # per-task-type composite evaluator
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
│   ├── loop.py                 # the per-round loop
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
├── run_experiment.py           # python -m scripts.run_experiment <config.yaml>
├── make_figures.py             # builds all paper figures from results/
├── make_tables.py              # builds all paper tables from results/
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

## Conventions

- **Language.** Python ≥ 3.11 for the package; LaTeX for the paper.
- **Comments and docstrings.** All English (per project rule).
- **Style.** Type-annotated; configs validated with pydantic.
- **Determinism.** All randomness via `core.seeds`; never call top-level
  `random` / `numpy.random` directly.
- **Logs.** JSON-lines under `results/<run_id>/`. The same loader feeds
  tables, figures, and tests.
- **No global state in modules.** Every module is exercised by a unit test
  with a fresh config and seed.
