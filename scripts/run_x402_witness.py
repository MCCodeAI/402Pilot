"""Minimal x402 integration witness for 402Pilot.

Runs 1–3 rounds of the PA-DCT decision loop where the
:class:`pilot402.runtime.x402_executor.X402PaymentExecutor` replaces the
benchmark's frozen-replay substrate. The script reuses the same
components the benchmark uses for selection (``NaiveEncoder``,
``Wallet``, ``PADCTPolicy``, ``RewardCalculator``); only the executor
differs. This makes it a real witness that the ``PaymentExecutor``
Protocol from ``pilot402/core/interfaces.py`` is satisfiable on a live
HTTP 402 round-trip — not a parallel demo with a hand-rolled policy.

Critical properties (mirror the design memo we agreed on):

* This script never writes to ``results/`` or any benchmark output path.
* It is not imported by any benchmark module. Failure here cannot affect
  any reported quantitative result.
* The benchmark loop (``pilot402/runtime/loop.py``) reads cached
  ``PregenRecord`` rows directly and does not consume
  ``X402PaymentExecutor``.

Usage
-----

Before running, bring up the local x402 stack:

    cd infrastructure/x402 && docker compose up -d

Then, from the repository root (after ``pip install -e .``):

    python -m scripts.run_x402_witness [--rounds N] [--seed S]

The script picks up the wallet key, facilitator URL, and Anvil RPC URL
from the existing ``X402Settings`` (env-sourced via ``.env``). Set those
in ``infrastructure/x402/.env`` per the example file.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

from pilot402.core.config import X402Settings
from pilot402.core.types import ProviderId, Task, TaskType
from pilot402.policies.padct import PADCTPolicy
from pilot402.runtime.encoder import NaiveEncoder
from pilot402.runtime.reward import RewardCalculator
from pilot402.runtime.wallet import Wallet
from pilot402.runtime.x402_executor import X402PaymentExecutor

# The witness reads x402 connection details from infrastructure/x402/.env
# (NOT the repo-root .env that the benchmark uses). Keeping them separate
# means changing x402 config never risks perturbing benchmark settings.
_X402_ENV_FILE = (
    Path(__file__).resolve().parent.parent
    / "infrastructure" / "x402" / ".env"
)

# ---------------------------------------------------------------------------
# Local-stack defaults
# ---------------------------------------------------------------------------
# Resource-server endpoints. Must match infrastructure/x402/resource_server.py.
_RESOURCE_URLS: dict[ProviderId, str] = {
    ProviderId.P_CHEAP:   "http://127.0.0.1:8000/p-cheap",
    ProviderId.P_MID:     "http://127.0.0.1:8000/p-mid",
    ProviderId.P_PREMIUM: "http://127.0.0.1:8000/p-premium",
}

# Spec prices matching the local resource server's PRICES_USDC. These are
# witness-only PRIOR MEANS for the PADCTPolicy cost posteriors; benchmark
# measurements use the frozen replay prices in experiments/main.yaml.
_PROVIDER_COSTS: dict[ProviderId, float] = {
    ProviderId.P_CHEAP:   0.001,
    ProviderId.P_MID:     0.002,
    ProviderId.P_PREMIUM: 0.010,
}


# ---------------------------------------------------------------------------
# Witness-only scaffolding (would normally come from the dataset loader)
# ---------------------------------------------------------------------------

def _make_task(round_idx: int) -> Task:
    """Build a trivial in-memory Task.

    The witness validates the transport and contract, not the evaluator,
    so we don't need real T1/T2/T3 data — any well-formed Task with a
    matching ``task_type`` works.
    """
    return Task(
        task_id=f"witness-{round_idx}",
        task_type=TaskType.T1_CODING,
        prompt="What is 2 + 2?",
        gold_answer="4",
        difficulty=0.2,
        metadata={"source": "x402_witness", "round": round_idx},
    )


def _dummy_quality(failure_flag: bool) -> float:
    """Stand-in for the real evaluator.

    The witness's purpose is to demonstrate the executor / interface
    works, not to grade response quality. A deterministic stand-in keeps
    the witness output stable across runs.
    """
    return 0.0 if failure_flag else 0.8


# ---------------------------------------------------------------------------
# Main loop — mirrors the per-round flow specified in paper §4
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "x402 integration witness (NOT a benchmark). "
            "Runs a few rounds of PA-DCT against the local x402 stack."
        ),
    )
    parser.add_argument("--rounds", type=int, default=3, help="Number of rounds (1–10).")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed for PA-DCT sampling.")
    parser.add_argument(
        "--budget-usdc",
        type=float,
        default=1.0,
        help="Wallet total. Kept tiny so the witness cannot be mistaken for a benchmark.",
    )
    args = parser.parse_args()

    if not (1 <= args.rounds <= 10):
        print("ERROR: --rounds must be between 1 and 10 for the witness.", file=sys.stderr)
        return 2

    # Pull x402 connection details from infrastructure/x402/.env explicitly
    # (overriding pydantic-settings' default `.env` lookup which would
    # resolve to repo root). If the file is missing, fall back to env vars
    # so shell-level `export X402_WALLET_PRIVATE_KEY=…` still works.
    if _X402_ENV_FILE.exists():
        settings = X402Settings(_env_file=str(_X402_ENV_FILE))
    else:
        settings = X402Settings()

    if not settings.x402_wallet_private_key:
        print(
            f"ERROR: X402_WALLET_PRIVATE_KEY is not set.\n"
            f"  Expected env file: {_X402_ENV_FILE}\n"
            f"  Copy infrastructure/x402/.env.example there and fill it in, "
            f"or export the variable in your shell.",
            file=sys.stderr,
        )
        return 1

    # ---- Components (same contracts as the benchmark loop) ----
    rng     = np.random.default_rng(args.seed)
    wallet  = Wallet(total_usdc=args.budget_usdc)
    encoder = NaiveEncoder()
    reward  = RewardCalculator(nu=0.5, max_provider_cost_usdc=0.01)
    policy  = PADCTPolicy(
        rng=rng,
        wallet=wallet,
        provider_costs=_PROVIDER_COSTS,
    )

    # ---- The witness-specific PaymentExecutor ----
    executor = X402PaymentExecutor(
        resource_urls=_RESOURCE_URLS,
        facilitator_url=settings.x402_facilitator_url,
        wallet_private_key=settings.x402_wallet_private_key,
        anvil_rpc_url=settings.anvil_rpc_url,
    )

    # ---- Banner ----
    print("=" * 72)
    print(" 402Pilot x402 integration witness (NOT a benchmark)")
    print("=" * 72)
    print(f" rounds:       {args.rounds}")
    print(f" seed:         {args.seed}")
    print(f" budget:       ${args.budget_usdc:.4f}")
    print(f" facilitator:  {settings.x402_facilitator_url}")
    print(f" anvil:        {settings.anvil_rpc_url} (chain id {settings.anvil_chain_id})")
    print(f" providers:    {[p.value for p in _RESOURCE_URLS]}")
    print("=" * 72)

    # ---- Per-round loop (paper §4 flow) ----
    for r in range(args.rounds):
        task = _make_task(r)

        # (1) encode context from task + wallet snapshot
        snap = wallet.snapshot()
        context = encoder.encode(task, {
            "remaining_fraction": snap["remaining_fraction"],
            "lambda_t":           snap["lambda_t"],
        })

        # (2) determine affordable set (paper notation: A_t)
        affordable = tuple(
            pid for pid, c in _PROVIDER_COSTS.items() if wallet.affordable(c)
        )
        if not affordable:
            print(f"[round {r}] wallet exhausted; stopping early.")
            break

        # (3) policy.select  (paper notation: a_t)
        chosen_arm = policy.select(context, affordable)

        # (4) pay_and_call — the *only* step that touches the network
        outcome = executor.pay_and_call(
            provider_id=chosen_arm,
            request_payload={
                "task_id": task.task_id,
                "prompt":  task.prompt,
            },
        )

        # (5) quality (witness uses a stand-in scorer; see _dummy_quality)
        quality = _dummy_quality(outcome.failure_flag)

        # (6) reward (same calculation as benchmark)
        rw = reward.compute(
            quality=quality,
            cost_usdc=outcome.cost_usdc,
            failure_flag=outcome.failure_flag,
            lambda_t=wallet.get_lambda(),
        )

        # (7) policy.update and wallet.record_spend — same order as
        #     pilot402.runtime.loop.run_one_seed
        policy.update(context, chosen_arm, rw.utility, outcome.cost_usdc)
        wallet.record_spend(outcome.cost_usdc)

        # (8) stdout line — NEVER write to results/
        tx = outcome.receipt.tx_id if outcome.receipt and outcome.receipt.tx_id else "-"
        print(
            f"[round {r}] arm={chosen_arm.value:<10} "
            f"failure={str(outcome.failure_flag):<5} "
            f"code={outcome.failure_code.value:<16} "
            f"cost=${outcome.cost_usdc:.6f} "
            f"latency={outcome.latency_s:.3f}s "
            f"utility={rw.utility:+.3f} "
            f"tx={tx}"
        )

    print("=" * 72)
    print(" witness complete")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
