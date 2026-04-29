"""Single random source for the entire run.

Every component (env, policy, judge, x402 wallet sampler, ...) draws from a
named sub-stream derived from one master seed. Same master seed → bit-identical
sub-streams across machines and Python invocations.

Design rules (cross-cutting contract from system_design §3 and code_structure
'Determinism'):

* No module ever calls top-level ``random`` or ``numpy.random`` directly.
* Sub-streams are keyed by ``name``, not by call order, so reordering
  ``derive()`` calls does not change downstream results.
* Master seed and every derived name are recorded in the run log.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from numpy.random import Generator, SeedSequence, default_rng


def _stable_uint32(name: str) -> int:
    """Deterministic 32-bit hash of ``name``, stable across Python sessions.

    ``hash(str)`` is randomized per process (PYTHONHASHSEED), so we use
    blake2b which is identical for any interpreter on any machine.
    """
    digest = hashlib.blake2b(name.encode("utf-8"), digest_size=4).digest()
    return int.from_bytes(digest, "big")


@dataclass(frozen=True)
class SubSeed:
    """A named, derived sub-stream. Carries enough provenance to reproduce."""

    master_seed: int
    name: str
    rng: Generator

    def derive(self, name: str) -> SubSeed:
        """Further derive a grand-child stream under ``self``.

        The grand-child key is ``f"{self.name}/{name}"`` so the full path is
        traceable in logs.
        """
        full_name = f"{self.name}/{name}"
        seq = _seq_for(self.master_seed, full_name)
        return SubSeed(master_seed=self.master_seed, name=full_name, rng=default_rng(seq))


def _seq_for(master_seed: int, name: str) -> SeedSequence:
    """Build a SeedSequence from (master_seed, name).

    Using both as entropy means: changing master_seed re-randomizes everything;
    changing the name re-randomizes only that sub-stream.
    """
    return SeedSequence(entropy=[master_seed, _stable_uint32(name)])


class SeedSource:
    """Master random source for one run.

    Typical use::

        seeds = SeedSource(cfg.seed)
        env_rng = seeds.derive("env").rng
        policy_rng = seeds.derive("policy").rng
        judge_rng = seeds.derive("judge").rng

    Each ``derive`` call is idempotent: ``seeds.derive("env").rng`` always
    yields a fresh Generator with the same starting state.
    """

    def __init__(self, master_seed: int) -> None:
        if master_seed < 0:
            raise ValueError(f"master_seed must be non-negative, got {master_seed}")
        self._master_seed = master_seed

    @property
    def master_seed(self) -> int:
        return self._master_seed

    def derive(self, name: str) -> SubSeed:
        """Return a named sub-stream. Calling twice with the same ``name``
        produces two Generators with identical starting state but independent
        positions thereafter (each call constructs a fresh Generator).
        """
        if not name:
            raise ValueError("derive(name) requires a non-empty name")
        seq = _seq_for(self._master_seed, name)
        return SubSeed(master_seed=self._master_seed, name=name, rng=default_rng(seq))

    def __repr__(self) -> str:
        return f"SeedSource(master_seed={self._master_seed})"


__all__ = ["SeedSource", "SubSeed"]
