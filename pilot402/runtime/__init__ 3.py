"""Replay-time runtime for 402Pilot bandit experiments.

The pregen pipeline (``pilot402.pregen``) produces a frozen dataset of
``PregenRecord`` instances. The runtime layer consumes that dataset and
plays back rounds: per round, sample a task, ask the policy to choose a
provider, look up the cached LLM outcome, charge the wallet, compute the
reward, update the policy, and write a structured log record.

Module layout::

    pilot402/runtime/
        sampler.py    — WorkloadSampler   (chooses next Task)
        wallet.py     — Wallet            (BudgetManager impl with λ-dynamics)
        reward.py     — RewardCalculator  (PA = (1−λ_norm)·(q − ν·f) − λ_norm·c̃)
        encoder.py    — NaiveEncoder      (Encoder impl — task-type one-hot + budget)
        recorder.py   — JsonlRecorder     (Recorder impl — append-mode JSONL)
        loop.py       — run_one_seed()    (single-seed orchestration)

Each replaceable component (Policy, Encoder, BudgetManager, Recorder) is
referenced via the Protocols in ``pilot402.core.interfaces`` so unit tests
can stub any of them without touching the rest of the loop.
"""

from __future__ import annotations

from pilot402.runtime.encoder import NaiveEncoder
from pilot402.runtime.loop import LoopRunStats, run_one_seed
from pilot402.runtime.oracle_loop import OracleRunStats, run_true_oracle_seed
from pilot402.runtime.recorder import JsonlRecorder
from pilot402.runtime.reward import RewardCalculator
from pilot402.runtime.sampler import WorkloadSampler
from pilot402.runtime.wallet import Wallet

__all__ = [
    "JsonlRecorder",
    "LoopRunStats",
    "NaiveEncoder",
    "OracleRunStats",
    "RewardCalculator",
    "Wallet",
    "WorkloadSampler",
    "run_one_seed",
    "run_true_oracle_seed",
]
