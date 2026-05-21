# Repository Layout

This document describes the public GitHub layout. Internal working directories
used during paper writing, local analysis logs, and visualization drafts are
kept local and ignored by Git.

## Top Level

```text
402Pilot/
├── .env.example              # environment template, no secrets
├── .gitignore                # local artifacts and generated outputs
├── README.md                 # external project overview
├── artifacts/results/        # compact result summaries for verification
├── data/tasks/               # committed task subsets used by the benchmark
├── docs/                     # design notes and retained documents
├── experiments/              # locked YAML experiment configuration
├── infrastructure/x402/      # local x402 integration witness
├── pilot402/                 # Python package
├── scripts/                  # experiment and analysis entry points
├── tests/                    # unit and integration tests
└── pyproject.toml            # package and tool configuration
```

The following directories are intentionally local-only:

- `paper/`: working LaTeX source
- `logs/`: local analysis notes and generated markdown tables
- `viz/`, `viz-explainer/`: visualization prototypes
- `results/`: bulk experiment outputs, except the retained
  `results/hyperparam_sensitivity/` artifact

`data/pregen/` is intentionally committed as the frozen replay artifact for
reproducible experiments.

`artifacts/results/` is intentionally committed as the compact result artifact.
The full `results/` tree remains local-only because it contains per-round logs,
intermediate outputs, and archived runs.

## `pilot402/`

```text
pilot402/
├── core/        # config, shared types, interfaces, and seeding
├── eval/        # metric and judge backends used for scoring
├── policies/    # PA-DCT and baseline policies
├── pregen/      # loaders and generators for frozen replay records
├── runtime/     # bandit loop, wallet, reward, recorder, x402 executor
└── scenarios.py # S1/S2/S3 market transformations
```

The package is structured around the `Policy` and `PaymentExecutor`
interfaces. Experiments can replay frozen records for controlled evaluation,
while the x402 witness validates the quote-pay-receipt boundary locally.

## `data/`

`data/tasks/` is committed because it defines the benchmark task subset.
`data/pregen/` is also committed as the frozen replay artifact: it stores
pre-generated provider responses plus judge-cache records, allowing policy
sweeps to be reproduced without fresh LLM calls.

## `artifacts/results/`

This directory contains small, committed summaries derived from local runs:
main-table aggregates, per-seed compact summaries, ablation summaries,
significance tables, and the hyperparameter-sensitivity artifact. It is the
public result artifact; the larger local `results/` directory is not committed.

## `experiments/`

`experiments/main.yaml` is the locked configuration used by the reported main
sweeps. It defines the provider set, scenario defaults, budget, reward
constants, and paths used by the scripts.

## `scripts/`

The scripts directory contains command-line entry points for:

- generating or loading pre-generated response records
- running scenario sweeps and ablations
- computing main tables, ablation metrics, oracle results, significance tests,
  and sensitivity summaries
- running the local x402 witness

Most scripts write generated outputs to ignored local directories such as
`results/` or `logs/`.

## `infrastructure/x402/`

This directory contains a local Docker-based witness stack for the payment
boundary. It is not used to produce benchmark numbers. Its purpose is to show
that the same executor contract can perform a real quote-pay-receipt round trip
against a local x402-style stack.

## `docs/`

Markdown files describe system design, experiment design, and the current code
structure. LaTeX working sources are kept in the local-only `paper/` directory
rather than committed here.

## Tests

`tests/` contains unit tests for configuration, policies, runtime behavior,
reward calculation, recorder output, scenario transforms, provider plumbing, and
the x402 executor. The x402 integration test is opt-in and skipped during a
normal `pytest` run unless the local witness environment is enabled.
