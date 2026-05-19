"""Aggregate the hyperparameter sensitivity sweep into a paper-ready table.

Consumes ``results/hyperparam_sensitivity/cells.jsonl`` (one row per
(cell, policy, seed); written by ``run_hyperparam_sensitivity.py``) and
emits:

* a Markdown table to stdout, paper-appendix ready
* ``results/hyperparam_sensitivity/agg.json`` — per-cell mean ± SE of every
  reported metric, in case downstream paper scripts want machine-readable
  input
* optional ``results/hyperparam_sensitivity/sensitivity.png`` — a 4-panel
  matplotlib figure (one per perturbed param) plotting the headline
  metric across the 3 values

Metric formulas mirror ``scripts/compute_main_table.py`` exactly so the
appendix numbers and the main table use the same definitions:

    q_bar_T   = (1/T) * sum_t quality_t       (unserved rounds count as 0)
    budget %  = 100 * total_spent / B0
    ROI       = sum_t quality_t / sum_t cost_t
    PA-gap/T  = mean_s (R_oracle[s] - R_padct[s]) / T   (paired by seed,
                                                         lower is better)
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

# Canonical cell ordering for the table — same shape as run_hyperparam_sensitivity.
_CELL_ORDER = (
    "default",
    "gamma_low",   "gamma_high",
    "nu_low",      "nu_high",
    "alpha_low",   "alpha_high",
    "cmax_low",    "cmax_high",
)

# Map cell -> (perturbed param symbol, value). Used to render the
# "perturbation" column in the Markdown table without re-introspecting
# the cells.jsonl rows.
_PERTURBATIONS: dict[str, tuple[str, str]] = {
    "default":    ("---", "(locked default)"),
    "gamma_low":  ("$\\gamma$",   "0.99"),
    "gamma_high": ("$\\gamma$",   "0.9995"),
    "nu_low":     ("$\\nu$",      "0.25"),
    "nu_high":    ("$\\nu$",      "1.0"),
    "alpha_low":  ("$\\alpha$",   "1.0"),
    "alpha_high": ("$\\alpha$",   "4.0"),
    "cmax_low":   ("$c_{\\max}$", "0.005"),
    "cmax_high":  ("$c_{\\max}$", "0.02"),
}


def _mean_se(xs: list[float]) -> tuple[float, float]:
    """Sample mean and standard error of the mean (SE = stdev / sqrt(n))."""
    if not xs:
        return float("nan"), float("nan")
    if len(xs) == 1:
        return xs[0], 0.0
    return statistics.mean(xs), statistics.stdev(xs) / math.sqrt(len(xs))


def _aggregate(rows: list[dict], num_rounds: int, budget: float) -> dict:
    """Aggregate rows from cells.jsonl into per-cell metrics."""
    # by_cell[cell][policy] = list of per-seed row dicts
    by_cell: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        by_cell[r["cell"]][r["policy"]].append(r)

    agg: dict[str, dict] = {}
    for cell_id, pol_map in by_cell.items():
        padct = pol_map.get("padct", [])
        oracle = pol_map.get("oracle", [])

        q_bar = [r["q_bar_T"] for r in padct]
        spent = [r["total_spent"] for r in padct]
        bankrupt = [1.0 if r["bankrupt"] else 0.0 for r in padct]
        # ROI: per-seed sum_q / sum_c, then mean.
        roi = [
            (r["cum_quality"] / r["total_spent"]) if r["total_spent"] > 0 else 0.0
            for r in padct
        ]

        # PA-gap/T: paired by seed. Skip if oracle absent or seeds don't align.
        pa_gap_per_t: list[float] = []
        oracle_by_seed = {r["seed"]: r for r in oracle}
        for r in padct:
            o = oracle_by_seed.get(r["seed"])
            if o is None:
                continue
            pa_gap_per_t.append(
                (o["cum_pa_reward"] - r["cum_pa_reward"]) / num_rounds
            )

        q_mean, q_se = _mean_se(q_bar)
        spent_mean, spent_se = _mean_se(spent)
        roi_mean, roi_se = _mean_se(roi)
        bk_mean, _ = _mean_se(bankrupt)
        gap_mean, gap_se = _mean_se(pa_gap_per_t)

        agg[cell_id] = {
            "n_padct_seeds": len(padct),
            "n_oracle_seeds": len(oracle),
            "q_bar_T_mean": q_mean,    "q_bar_T_se": q_se,
            "budget_pct_mean": 100 * spent_mean / budget if budget else float("nan"),
            "budget_pct_se":   100 * spent_se   / budget if budget else float("nan"),
            "ROI_mean": roi_mean,      "ROI_se": roi_se,
            "bankrupt_rate": bk_mean,
            "PA_gap_T_mean": gap_mean, "PA_gap_T_se": gap_se,
        }
    return agg


def _markdown_table(agg: dict, *, with_oracle: bool) -> str:
    """Render the per-cell aggregates as a Markdown table for the appendix."""
    headers = [
        "Cell", "Perturbation",
        "$\\bar q_T$",
        "Budget \\%",
        "ROI",
    ]
    if with_oracle:
        headers.append("PA-gap/T")
    headers.append("Bankrupt")

    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("|" + "|".join("---" for _ in headers) + "|")

    for cell_id in _CELL_ORDER:
        if cell_id not in agg:
            continue
        a = agg[cell_id]
        sym, val = _PERTURBATIONS[cell_id]
        perturb_str = f"{sym} = {val}" if sym != "---" else val
        cells = [
            cell_id,
            perturb_str,
            f"{a['q_bar_T_mean']:.3f} ± {a['q_bar_T_se']:.3f}",
            f"{a['budget_pct_mean']:.1f} ± {a['budget_pct_se']:.1f}",
            f"{a['ROI_mean']:.1f} ± {a['ROI_se']:.1f}",
        ]
        if with_oracle:
            cells.append(f"{a['PA_gap_T_mean']:+.5f} ± {a['PA_gap_T_se']:.5f}")
        cells.append(f"{a['bankrupt_rate']:.0%}")
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _plot_panels(agg: dict, out_path: Path) -> None:
    """4-panel sensitivity figure: one panel per perturbed param."""
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed; skipping figure.", file=sys.stderr)
        return

    panels = [
        ("$\\gamma$",      ["gamma_low",  "default", "gamma_high"],  [0.99,  0.999, 0.9995]),
        ("$\\nu$",         ["nu_low",     "default", "nu_high"],     [0.25,  0.5,   1.0]),
        ("$\\alpha$",      ["alpha_low",  "default", "alpha_high"],  [1.0,   2.0,   4.0]),
        ("$c_{\\max}$",    ["cmax_low",   "default", "cmax_high"],   [0.005, 0.01,  0.02]),
    ]
    fig, axes = plt.subplots(1, 4, figsize=(11, 2.6), sharey=True)
    for ax, (label, cells, xs) in zip(axes, panels, strict=True):
        ys, errs = [], []
        for c in cells:
            ys.append(agg.get(c, {}).get("q_bar_T_mean", float("nan")))
            errs.append(agg.get(c, {}).get("q_bar_T_se",   0.0))
        ax.errorbar(xs, ys, yerr=errs, marker="o", capsize=3, linewidth=1.5)
        ax.set_xlabel(label)
        ax.grid(True, axis="y", linestyle=":", linewidth=0.5, alpha=0.6)
        if label == "$\\gamma$":
            ax.set_xscale("function", functions=(lambda x: 1 - x, lambda y: 1 - y))
    axes[0].set_ylabel("$\\bar q_T$ (mean ± SE)")
    fig.suptitle("Stationary sensitivity (S1, 10 seeds, $T{=}10{,}000$)", y=1.02)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight", dpi=160)
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cells-file", type=Path,
        default=Path("results/hyperparam_sensitivity/cells.jsonl"),
    )
    parser.add_argument(
        "--out-dir", type=Path, default=Path("results/hyperparam_sensitivity"),
    )
    parser.add_argument("--num-rounds", type=int, default=10000)
    parser.add_argument("--budget", type=float, default=50.0)
    parser.add_argument(
        "--no-figure", action="store_true",
        help="Skip matplotlib figure generation.",
    )
    args = parser.parse_args(argv)

    if not args.cells_file.is_file():
        print(f"ERROR: {args.cells_file} not found. Run scripts.run_hyperparam_sensitivity first.",
              file=sys.stderr)
        return 1

    rows = [
        json.loads(line)
        for line in args.cells_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not rows:
        print(f"ERROR: {args.cells_file} is empty.", file=sys.stderr)
        return 1

    agg = _aggregate(rows, num_rounds=args.num_rounds, budget=args.budget)
    with_oracle = any(a["n_oracle_seeds"] > 0 for a in agg.values())

    table = _markdown_table(agg, with_oracle=with_oracle)
    print(table)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "agg.json").write_text(json.dumps(agg, indent=2))

    if not args.no_figure:
        _plot_panels(agg, args.out_dir / "sensitivity.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
