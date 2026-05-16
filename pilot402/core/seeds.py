"""Deterministic seed derivation utilities."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from numpy.random import Generator, default_rng


@dataclass(frozen=True)
class DerivedSeed:
    """A derived integer seed plus its ready-to-use RNG."""

    seed: int
    rng: Generator


@dataclass(frozen=True)
class SeedSource:
    """Derive independent RNG streams from a master seed and string label."""

    master_seed: int

    def derive(self, label: str) -> DerivedSeed:
        payload = f"{self.master_seed}:{label}".encode("utf-8")
        digest = hashlib.blake2b(payload, digest_size=8).digest()
        seed = int.from_bytes(digest, "big") % (2**32)
        return DerivedSeed(seed=seed, rng=default_rng(seed))


__all__ = ["DerivedSeed", "SeedSource"]

