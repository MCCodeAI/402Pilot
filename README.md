# 402Pilot

402Pilot is a buyer-side decision layer for autonomous agent micropayments. It
sits above x402-style payment execution and decides which paid provider an
agent should call under a finite wallet, uncertain service quality, and
changing provider reliability or prices.

The core policy is **PA-DCT**: Payment-Aware Discounted Contextual Thompson
Sampling. PA-DCT maintains separate discounted posteriors over provider utility
and realized cost, then ranks affordable providers using both task context and
current wallet pressure.

## Why This Exists

x402-style protocols make payment execution programmable: a service can publish
a payable endpoint, an agent can receive payment requirements, and a request can
settle per call. That still leaves a buyer-side question:

> Given several payable services and a draining wallet, which one should the
> agent buy now?

402Pilot treats that as an online learning problem. Each round reveals only the
outcome of the provider that was actually paid for, and each payment is
irreversible. The policy must therefore balance quality, cost, exploration, and
adaptation to market changes.

## Method

At each round, 402Pilot receives a task context and a set of quoted providers.
The wallet filters this set to affordable providers. PA-DCT samples provider
utility and cost beliefs for the current task bucket, scores each affordable
arm, pays for the selected provider through the executor interface, and updates
only from the chosen provider's receipt and service outcome.

The payment-aware score is:

```text
utility   = q - nu * failure
lambda_n  = lambda_t / (1 + lambda_t)
score     = (1 - lambda_n) * utility_sample
            - lambda_n * normalized_cost_sample
```

`lambda_t` increases when the wallet burns faster than the target schedule, so
the same learned provider quality can lead to different choices depending on
remaining budget.

## Benchmark

402Pilot-Bench evaluates provider selection over frozen replay. Provider
responses are pre-generated, scored, and replayed under paired seeds so that
policy differences are not confounded by live API drift.

The benchmark uses five provider pipelines:

| Provider | Price | Role |
| --- | ---: | --- |
| P-cheap | 0.0005 USDC | low-cost baseline |
| P-mid | 0.002 USDC | reliable mid-tier baseline |
| P-premium | 0.01 USDC | strongest but initially expensive provider |
| P-adv | 0.002 USDC | same tier as P-mid, adversarially prompted |
| P-flaky | 0.002 USDC | same tier as P-mid, with billed timeouts |

The benchmark experiments use three market scenarios:

| Scenario | Event |
| --- | --- |
| S1 Stationary | no mid-run market change |
| S2 Mid outage | P-mid fails during rounds 3,000-5,500 |
| S3 Premium promo | P-premium drops from 0.01 to 0.002 USDC at round 1,000 |

Each main cell uses 30 paired seeds and 10,000 rounds with a 50 USDC wallet.
Metrics include mean quality, budget use, ROI, and payment-aware gap to a replay
oracle.

## Results

PA-DCT is not designed to win one isolated metric in every static setting. Its
goal is robust buyer behavior under changing market conditions. In the benchmark
experiments, PA-DCT remains budget-feasible, adapts away from the mid-tier
outage in S2, and captures the premium price promotion in S3.

## Repository Layout

```text
402Pilot/
├── data/tasks/              # committed benchmark task subsets
├── docs/                    # design notes and retained documents
├── experiments/             # locked experiment configuration
├── infrastructure/x402/     # local x402 quote-pay-receipt witness
├── pilot402/                # core Python package
├── results/hyperparam_sensitivity/
│                            # retained compact sensitivity artifact
├── scripts/                 # experiment, metric, and witness entry points
└── tests/                   # unit and integration tests
```

Local-only working directories such as `paper/`, `logs/`, `viz/`,
`viz-explainer/`, and bulk `results/` outputs are intentionally ignored by Git.
The frozen replay records under `data/pregen/` are committed as the
reproducibility artifact.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

The core package requires Python 3.11 or newer.

## Running Tests

```bash
pytest
```

The x402 integration test is skipped by default because it requires the local
Docker witness stack. See [infrastructure/x402/README.md](infrastructure/x402/README.md)
for that setup.

## Running Experiments

A quick smoke run can be launched with:

```bash
python -m scripts.run_scenario_sweep \
  --num-seeds 3 \
  --num-rounds 200 \
  --out-dir results/smoke \
  --scenarios S1 S2 S3
```

The locked main configuration is [experiments/main.yaml](experiments/main.yaml).
Full benchmark-scale sweeps replay the committed frozen records under
`data/pregen/`.

## Data Availability

The task subsets in `data/tasks/` and the frozen replay records in
`data/pregen/` are committed. The pre-generated artifact is about 11 MB and
contains 20,575 provider-response records plus the judge cache used for
open-ended QA scoring. This lets readers rerun policy sweeps without making
fresh LLM calls.

## License

Research and educational use is permitted. Commercial use requires prior
written authorization from Yin Li. See [LICENSE](LICENSE).
