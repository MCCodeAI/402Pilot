# 402Pilot — Interactive Explainer (`viz/`)

Static SPA companion to the paper. Built with React 18 + Vite + TypeScript;
deploys to GitHub Pages. **Phase 5 only** — does not block any pilot402
work. See `docs/code_structure.md` for the full design.

## Three sections

1. **Explainer** — *why PA-DCT works*
   - **Hidden Twin Test** (hero) — D3 ridges of P-mid / P-adv / P-flaky
     posteriors over rounds. Same price tier, same base model. Watch them
     separate from reward feedback alone.
   - **FlowDiagram** — 6-step PA-DCT loop. Step 4 (x402) grayed: the
     settlement boundary 402Pilot deliberately does not cross.
   - **RewardDecompose** — two-step reveal of `utility = q − ν·f` and
     `PA_reward = (1 − λ_norm)·utility − λ_norm·c̃`. Click any term.
   - **LambdaChart** — `λ_norm = sigmoid(α·burn_excess)` S-curve.
   - **NuPanel** — why ν = 0.5.
   - **Devnet demo** *(optional)* — single-round live trace against a
     local Anvil fork. Disabled on GitHub Pages; enabled locally.
2. **Simulation Replay** — *watch one run*
   - Scenario × task type × seed × speed controls; round scrubber;
     per-arm running utility; wallet bar with event markers; round log;
     P-adv detection badges per task type (T3b deliberately shows "not
     detected" — see paper §7).
3. **Results** — *what the numbers say*
   - StatsTable (mean ± std), RegretCurve with 95% CI, ROIChart with
     event markers, RegretByTaskType, HeatMap, AblationBars.

## Local development

```bash
cd viz
npm install --no-audit --no-fund
npm run dev                           # http://localhost:5173/402Pilot/
```

## Build

```bash
npm run typecheck
npm run build                         # outputs to dist/
```

## Deploy (gh-pages)

```bash
npm run deploy
```

The canonical URL is `https://<org>.github.io/402Pilot/`.

## Data fixtures

All experimental data is loaded from JSON / JSONL fixtures under
`public/data/`:

```
public/data/
├── summary.json                          # cells, regret_curves, roi_curves,
│                                         # heatmaps, ablations
├── posteriors/
│   └── S{1,2,3}_padct_seed{i}_posteriors.jsonl
└── runs/
    └── S{1,2,3}_padct_seed{i}.jsonl
```

The fixtures currently shipped are **real** — exported by
`scripts/export_viz_data.py` from:

- `results/scenario_sweep/{S1,S2}/` — locked S1 + S2 sweeps (30 seeds × 7 policies)
- `results/scenario_sweep_s3promo_v2/` — locked S3 v2 sweep (PremiumDropScenario,
  shock at round 1000, premium price ×0.2). The earlier
  `results/scenario_sweep/S3/` is M3.E historical S3, kept on disk for
  traceability but **not** used by viz.
- `results/ablation_matrix/{no_c,no_d,no_p,no_ts}/{S1,S2,S3}/padct/` — 4 ablations × 3 scenarios × 30 seeds.

To regenerate after a new run:

```bash
python3 scripts/export_viz_data.py
```

The JSONL contract matches `docs/system_design.md §3` exactly:

```
{round, context, arm, cost, latency, quality, failure,
 utility, reward, budget_remaining}
```

## Devnet demo

The Devnet demo at the bottom of §1 is a reproducibility witness. It is
**not** the source of any number in the paper. To enable it, run the
helper scripts in a separate terminal:

```bash
# 1. start anvil fork of Base
./scripts/devnet/start_anvil.sh

# 2. compile + deploy MockUSDC + X402Facilitator
cd viz && npx tsx ../scripts/devnet/deploy.ts

# 3. start the dev server in another terminal
cd viz && npm run dev
```

See `scripts/devnet/README.md` for details.
