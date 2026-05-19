"""One-at-a-time hyperparameter sensitivity sweep on S1.

Reports robustness of the stationary trade-off to perturbations of the
four locked hyperparameters $(\\gamma, \\nu, \\alpha, c_{\\max})$. For each
of the 9 cells (1 default + 4 params × 2 values), this script runs
PA-DCT and a matching True Oracle so that PA-gap/T values are comparable
across cells (oracle's objective uses the same ν / c_max as PA-DCT in
that cell — important because ν and c_max change the utility / cost
normalisation, not just policy knobs).

Outputs::

    results/hyperparam_sensitivity/<cell_id>/padct/seed_NN.jsonl
    results/hyperparam_sensitivity/<cell_id>/oracle/seed_NN.jsonl
    results/hyperparam_sensitivity/cells.jsonl   # one row per (cell, policy, seed)

Usage (from repo root, after ``pip install -e .``)::

    python -m scripts.run_hyperparam_sensitivity                          # full 9×10 sweep
    python -m scripts.run_hyperparam_sensitivity --num-seeds 2 --num-rounds 500  # smoke
    python -m scripts.run_hyperparam_sensitivity --cells default gamma_low       # subset

The runner is intentionally a sibling of ``run_scenario_sweep.py``: it
borrows the same per-cell layout, resume support, and oracle pairing, but
fixes scenario=S1 and varies only $(\\gamma, \\nu, \\alpha, c_{\\max})$.
Nothing in ``pilot402/`` is modified; cfg overrides go through pydantic's
``model_copy(update=...)``.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from numpy.random import default_rng

from pilot402.core import (
    ExperimentConfig,
    ProviderId,
    ScenarioConfig,
    ScenarioId,
)
from pilot402.core.config import load_config
from pilot402.policies import PADCTPolicy
from pilot402.pregen import JsonlPregenStore
from pilot402.pregen.tasks import load_all_tasks
from pilot402.runtime import (
    JsonlRecorder,
    NaiveEncoder,
    RewardCalculator,
    Wallet,
    run_one_seed,
    run_true_oracle_seed,
)
from pilot402.scenarios import build_scenario

# Same provider price table as run_scenario_sweep.py — provider_costs is
# the PADCTPolicy's cost-posterior prior, NOT the per-round wallet price
# (which comes from the calibrated YAML providers list at decision time).
_PROVIDER_PRICES = {
    ProviderId.P_CHEAP: 0.0005,
    ProviderId.P_MID: 0.002,
    ProviderId.P_PREMIUM: 0.01,
    ProviderId.P_ADV: 0.002,
    ProviderId.P_FLAKY: 0.002,
}

# Default values — matching main.yaml and PADCTPolicy defaults.
_DEFAULT_GAMMA = 0.999
_DEFAULT_NU = 0.5
_DEFAULT_ALPHA = 2.0
_DEFAULT_CMAX = 0.01


@dataclass(frozen=True)
class Cell:
    """One sensitivity cell: which (param, value) is perturbed from default."""

    cell_id: str
    gamma: float
    nu: float
    alpha: float
    cmax: float


_CELLS: tuple[Cell, ...] = (
    # default — single anchor; every other cell perturbs exactly one knob.
    Cell("default",     _DEFAULT_GAMMA, _DEFAULT_NU, _DEFAULT_ALPHA, _DEFAULT_CMAX),
    # gamma: half-life 69 / 693 / 1386 rounds
    Cell("gamma_low",   0.99,           _DEFAULT_NU, _DEFAULT_ALPHA, _DEFAULT_CMAX),
    Cell("gamma_high",  0.9995,         _DEFAULT_NU, _DEFAULT_ALPHA, _DEFAULT_CMAX),
    # nu: half / default / double
    Cell("nu_low",      _DEFAULT_GAMMA, 0.25,        _DEFAULT_ALPHA, _DEFAULT_CMAX),
    Cell("nu_high",     _DEFAULT_GAMMA, 1.0,         _DEFAULT_ALPHA, _DEFAULT_CMAX),
    # alpha: half / default / double
    Cell("alpha_low",   _DEFAULT_GAMMA, _DEFAULT_NU, 1.0,            _DEFAULT_CMAX),
    Cell("alpha_high",  _DEFAULT_GAMMA, _DEFAULT_NU, 4.0,            _DEFAULT_CMAX),
    # c_max: half / default / double
    Cell("cmax_low",    _DEFAULT_GAMMA, _DEFAULT_NU, _DEFAULT_ALPHA, 0.005),
    Cell("cmax_high",   _DEFAULT_GAMMA, _DEFAULT_NU, _DEFAULT_ALPHA, 0.02),
)


# ---------------------------------------------------------------------------
# Helpers — log parsing borrowed (read-only) from run_scenario_sweep.py
# ---------------------------------------------------------------------------

def _read_log_lines(log_path: Path) -> list[dict]:
    """Parse a per-seed JSONL log, tolerating a single truncated trailing line."""
    lines = [
        line for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    while lines:
        try:
            json.loads(lines[-1])
            break
        except json.JSONDecodeError:
            lines.pop()
    return [json.loads(line) for line in lines]


def _is_complete(log_path: Path, num_rounds: int) -> bool:
    """A cell is complete iff log is full-length OR cleanly bankrupted."""
    if not log_path.is_file():
        return False
    rows = _read_log_lines(log_path)
    if not rows:
        return False
    if len(rows) >= num_rounds:
        return True
    last_remaining = rows[-1].get("budget_remaining_usdc", 0.0)
    return last_remaining < min(_PROVIDER_PRICES.values())


def _row_from_log(
    policy_name: str,
    cell_id: str,
    seed_idx: int,
    log_path: Path,
    num_rounds: int,
) -> dict:
    """One per-seed summary row. Same shape as run_scenario_sweep's _row_from_log
    plus the cell_id column so the aggregator can group by perturbation.
    """
    rows = _read_log_lines(log_path)
    n = len(rows)
    cum_pa = sum(r.get("payment_aware_reward", 0.0) for r in rows)
    cum_util = sum(r.get("utility", 0.0) for r in rows)
    quality_sum = sum(r.get("quality", 0.0) for r in rows)
    total_spent = sum(r.get("charged_cost_usdc", 0.0) for r in rows)
    n_failures = sum(1 for r in rows if r.get("failure_flag"))
    last_remaining = rows[-1].get("budget_remaining_usdc", 0.0) if rows else 0.0
    arm_counts: dict[str, int] = defaultdict(int)
    for r in rows:
        arm = r.get("chosen_arm")
        if arm is not None:
            arm_counts[arm] += 1
    bankrupted = n < num_rounds and last_remaining < min(_PROVIDER_PRICES.values())
    return {
        "cell": cell_id,
        "policy": policy_name,
        "seed": seed_idx,
        "rounds": n,
        "bankrupt": n < num_rounds and bankrupted,
        "bankruptcy_round": n if bankrupted else None,
        "total_spent": total_spent,
        "failures": n_failures,
        "cum_pa_reward": cum_pa,
        "cum_utility": cum_util,
        "cum_quality": quality_sum,
        "q_bar_T": (quality_sum / num_rounds) if num_rounds else 0.0,
        "arm_counts": dict(arm_counts),
    }


def _apply_cell_overrides(cfg: ExperimentConfig, cell: Cell) -> ExperimentConfig:
    """Return a copy of ``cfg`` with ``cell``'s ν, α applied to YAML-sourced
    sub-configs. γ and c_max are constructor-level on PADCTPolicy and
    don't live in the YAML schema, so they're handled at policy/reward
    construction time instead.
    """
    return cfg.model_copy(update={
        "budget": cfg.budget.model_copy(update={"alpha": cell.alpha}),
        "reward": cfg.reward.model_copy(update={"nu": cell.nu}),
    })


def _run_padct_cell(
    cfg: ExperimentConfig,
    cell: Cell,
    *,
    seed: int,
    tasks: list,
    store: JsonlPregenStore,
    log_path: Path,
) -> dict:
    """Run one PA-DCT cell with all four sensitivity knobs overridden."""
    cfg = _apply_cell_overrides(cfg, cell)
    sc_cfg = ScenarioConfig(name=ScenarioId.S1_STATIONARY)
    scenario = build_scenario(sc_cfg, master_seed=seed)
    cfg = cfg.model_copy(update={"scenario": sc_cfg})

    wallet = Wallet(
        total_usdc=cfg.budget.total_usdc,
        lambda_0=cfg.budget.lambda_0,
        alpha=cell.alpha,
        target_burn_rate=cfg.budget.target_burn_rate,
    )
    policy = PADCTPolicy(
        rng=default_rng(seed * 6271 + 13),
        wallet=wallet,
        provider_costs=_PROVIDER_PRICES,
        max_provider_cost=cell.cmax,
        gamma=cell.gamma,
        gamma_cost=cell.gamma,
    )
    encoder = NaiveEncoder()
    reward_calc = RewardCalculator(nu=cell.nu, max_provider_cost_usdc=cell.cmax)

    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        log_path.unlink(missing_ok=True)
    except PermissionError:
        log_path.open("w").close()
    with JsonlRecorder(path=log_path) as rec:
        run_one_seed(
            cfg, tasks=tasks, store=store,
            policy=policy, wallet=wallet,
            encoder=encoder, reward_calc=reward_calc,
            recorder=rec, seed=seed, scenario=scenario,
            progress_every=None,
        )
    return _row_from_log("padct", cell.cell_id, seed, log_path, cfg.num_rounds)


def _run_oracle_cell(
    cfg: ExperimentConfig,
    cell: Cell,
    *,
    seed: int,
    tasks: list,
    store: JsonlPregenStore,
    log_path: Path,
) -> dict:
    """Run the matching True Oracle for this cell (same ν, c_max, α)."""
    cfg = _apply_cell_overrides(cfg, cell)
    sc_cfg = ScenarioConfig(name=ScenarioId.S1_STATIONARY)
    scenario = build_scenario(sc_cfg, master_seed=seed)
    cfg = cfg.model_copy(update={"scenario": sc_cfg})

    wallet = Wallet(
        total_usdc=cfg.budget.total_usdc,
        lambda_0=cfg.budget.lambda_0,
        alpha=cell.alpha,
        target_burn_rate=cfg.budget.target_burn_rate,
    )
    encoder = NaiveEncoder()
    reward_calc = RewardCalculator(nu=cell.nu, max_provider_cost_usdc=cell.cmax)

    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        log_path.unlink(missing_ok=True)
    except PermissionError:
        log_path.open("w").close()
    with JsonlRecorder(path=log_path) as rec:
        run_true_oracle_seed(
            cfg, tasks=tasks, store=store,
            wallet=wallet, encoder=encoder, reward_calc=reward_calc,
            recorder=rec, seed=seed, scenario=scenario,
        )
    return _row_from_log("oracle", cell.cell_id, seed, log_path, cfg.num_rounds)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("experiments/main.yaml"))
    parser.add_argument(
        "--num-seeds", type=int, default=10,
        help="Per-cell seeds. Default 10 (sensitivity needs less than main_table's 30).",
    )
    parser.add_argument(
        "--num-rounds", type=int, default=None,
        help="Override cfg.num_rounds (handy for smoke runs).",
    )
    parser.add_argument(
        "--out-dir", type=Path, default=Path("results/hyperparam_sensitivity"),
    )
    parser.add_argument(
        "--cells", nargs="+", default=None,
        help="Subset of cells to run (e.g. 'default gamma_low'). Defaults to all 9.",
    )
    parser.add_argument(
        "--skip-oracle", action="store_true",
        help="Skip oracle runs; cell summary will lack PA-gap/T.",
    )
    parser.add_argument(
        "--no-resume", action="store_true",
        help="Re-run every cell even if a complete log exists.",
    )
    args = parser.parse_args(argv)

    if not args.config.is_file():
        print(f"ERROR: config not found: {args.config}", file=sys.stderr)
        return 1

    cfg = load_config(args.config)
    if args.num_rounds is not None:
        cfg = cfg.model_copy(update={"num_rounds": args.num_rounds})

    selected = (
        _CELLS if args.cells is None
        else tuple(c for c in _CELLS if c.cell_id in set(args.cells))
    )
    if not selected:
        print(f"ERROR: no cells matched {args.cells}", file=sys.stderr)
        return 1

    tasks = load_all_tasks(cfg.paths.tasks_dir)
    store = JsonlPregenStore(cfg.paths.pregen_dir)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = args.out_dir / "cells.jsonl"
    # Truncate the summary file so we always end up with a coherent rollup.
    summary_path.write_text("")

    print(
        f"=== sensitivity sweep — {len(selected)} cell(s) × {args.num_seeds} "
        f"seed(s) × {cfg.num_rounds} rounds on S1 ===",
        file=sys.stderr,
    )
    rows: list[dict] = []
    for cell in selected:
        cell_dir = args.out_dir / cell.cell_id
        for policy_name, runner in (
            ("padct", _run_padct_cell),
            *(() if args.skip_oracle else (("oracle", _run_oracle_cell),)),
        ):
            for seed_idx in range(args.num_seeds):
                log_path = cell_dir / policy_name / f"seed_{seed_idx:02d}.jsonl"
                if not args.no_resume and _is_complete(log_path, cfg.num_rounds):
                    print(
                        f"  [skip] {cell.cell_id}/{policy_name}/seed={seed_idx} "
                        f"(already complete)", file=sys.stderr,
                    )
                    row = _row_from_log(
                        policy_name, cell.cell_id, seed_idx, log_path, cfg.num_rounds,
                    )
                else:
                    print(
                        f"  [run]  {cell.cell_id}/{policy_name}/seed={seed_idx}",
                        file=sys.stderr,
                    )
                    row = runner(
                        cfg, cell, seed=seed_idx,
                        tasks=tasks, store=store, log_path=log_path,
                    )
                # Stash the perturbation knobs alongside the row so the
                # aggregator never has to reach back into _CELLS.
                row["gamma"] = cell.gamma
                row["nu"] = cell.nu
                row["alpha"] = cell.alpha
                row["cmax"] = cell.cmax
                rows.append(row)
                with summary_path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(row) + "\n")

    print(
        f"=== done — {len(rows)} (cell, policy, seed) rows, summary at "
        f"{summary_path} ===",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
