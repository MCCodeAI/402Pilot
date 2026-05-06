# `scripts/devnet/` — reproducibility witness for the viz Devnet demo

These scripts exist for one purpose: let a reader open the viz, click
**Run one round** in `Explainer › Devnet demo`, and watch a real on-chain
USDC settlement complete on a local Anvil fork of Base.

**Scope.** This is *not* used by the experiments. Every number in the paper
comes from `scripts/run_experiment.py` reading pre-generated fixtures
(`docs/experiment_design.md §8`). The `viz/Explainer/DevnetDemo` component
exists to answer the reasonable reviewer question *"you say 402Pilot sits
above x402 — show me it actually integrates"*, not to provide measurements.

## What's here

```
scripts/devnet/
├── start_anvil.sh           # forks Base (Sepolia by default), funds 5 accts
├── deploy_facilitator.sol   # MockUSDC + minimal X402Facilitator
├── deploy.ts                # compiles + deploys, writes deployments.json
└── README.md
```

## One-time setup

You'll need:

- **foundry** (anvil + cast) — <https://book.getfoundry.sh/getting-started/installation>
- **solc** — `brew install solidity` or
  <https://docs.soliditylang.org/en/latest/installing-solidity.html>
- **node 20+** with `npx`

## Running it

```bash
# Terminal 1: start the fork
./scripts/devnet/start_anvil.sh

# Terminal 2: compile + deploy MockUSDC + X402Facilitator
cd viz && npx tsx ../scripts/devnet/deploy.ts

# Terminal 3: serve the viz locally
cd viz && npm run dev
# open http://localhost:5173/402Pilot/
```

In the page, scroll to **§1 Explainer › Devnet demo** at the bottom. The
status indicator should flip to **● local Anvil online**. Click **Run one
round** and watch the 6-step timeline; step 4 will issue a real RPC call
to your Anvil fork and complete in ~1–3 seconds.

## What the demo proves

1. The PA-DCT decision flow (steps 1–3) is independent of x402.
2. The wrapper interface (`pay_and_call`) actually executes against a
   chain when wired to one.
3. The reward path (steps 5–6) consumes the on-chain outcome correctly.

What it does **not** prove: any claim about ROI, regret, success rate, or
adaptation time. Those are in `Section 3 Results` and come from the 30
seeds × 3 scenarios benchmark, replayed deterministically from fixtures.
