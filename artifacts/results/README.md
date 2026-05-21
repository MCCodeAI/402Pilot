# Reported Result Artifacts

This directory contains compact outputs for checking the benchmark numbers
without committing the full local `results/` tree.

The full local run directory is about 11 GB and contains per-round logs, smoke
tests, archived runs, and intermediate outputs. Those files are intentionally
ignored by Git. The files here are the small summaries used for tables,
statistical checks, ablation summaries, and sensitivity reporting.

## Contents

- `main_table/agg.json`: aggregated main-result metrics by scenario and policy.
- `main_table/per_cell.jsonl`: per-seed compact main-result records.
- `scenario_summaries/`: per-seed summaries for S1, S2, and S3.
- `ablation_matrix/`: per-seed summaries for the component ablation runs.
- `s3_cost_posterior_ablation/`: per-seed summary for the S3 cost-posterior
  diagnostic ablation.
- `hyperparam_sensitivity/`: compact sensitivity sweep table and figure.
- `tables/ablation_5metrics_table.md`: paper-ready ablation metric table.
- `tables/significance_table.md`: paired-seed significance table.

These summaries are derived from the committed frozen replay records in
`data/pregen/`.
