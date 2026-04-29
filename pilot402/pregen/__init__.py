"""Pregen pipeline (Phase 1).

Drives the one-time generation of 402Pilot-Bench: ~20,600 LLM API calls
across 5 providers × 824 tasks × 5 versions. Outputs JSONL files under
``data/pregen/``; runtime experiments replay from those files via
``JsonlPregenStore`` and never call LLMs again.
"""

from pilot402.pregen.dataset import JsonlPregenStore
from pilot402.pregen.generator import run_pregen

__all__ = ["JsonlPregenStore", "run_pregen"]
