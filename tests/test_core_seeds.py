"""Tests for ``pilot402.core.seeds``.

Determinism is the cross-cutting contract. If two ``SeedSource(N)``
instances on different machines or different Python invocations produce
different sub-streams, every reproducibility claim in the paper falls.
"""

from __future__ import annotations

import numpy as np
import pytest

from pilot402.core import SeedSource


def test_same_master_seed_same_substream() -> None:
    a = SeedSource(42).derive("env").rng.uniform(size=128)
    b = SeedSource(42).derive("env").rng.uniform(size=128)
    np.testing.assert_array_equal(a, b)


def test_different_master_seeds_differ() -> None:
    a = SeedSource(42).derive("env").rng.uniform(size=128)
    b = SeedSource(43).derive("env").rng.uniform(size=128)
    assert not np.array_equal(a, b)


def test_different_subseed_names_independent() -> None:
    src = SeedSource(42)
    env_stream = src.derive("env").rng.uniform(size=128)
    policy_stream = src.derive("policy").rng.uniform(size=128)
    assert not np.array_equal(env_stream, policy_stream)


def test_derive_is_idempotent() -> None:
    """Calling ``derive`` twice with the same name yields a fresh Generator
    with identical starting state. Order of derive() calls must not matter."""
    src = SeedSource(42)
    first = src.derive("env").rng.uniform(size=64)
    _ = src.derive("policy").rng.uniform(size=64)  # interleave another stream
    second = src.derive("env").rng.uniform(size=64)
    np.testing.assert_array_equal(first, second)


def test_subseed_carries_provenance() -> None:
    sub = SeedSource(42).derive("env")
    assert sub.master_seed == 42
    assert sub.name == "env"


def test_grandchild_streams_independent() -> None:
    src = SeedSource(42)
    env = src.derive("env")
    a = env.derive("tasks").rng.uniform(size=64)
    b = env.derive("noise").rng.uniform(size=64)
    assert not np.array_equal(a, b)


def test_grandchild_path_in_name() -> None:
    sub = SeedSource(42).derive("env").derive("tasks")
    assert sub.name == "env/tasks"


def test_negative_master_seed_rejected() -> None:
    with pytest.raises(ValueError):
        SeedSource(-1)


def test_empty_derive_name_rejected() -> None:
    with pytest.raises(ValueError):
        SeedSource(42).derive("")


def test_stable_hash_is_session_independent() -> None:
    """Sanity-check that we are not relying on Python's randomized ``hash(str)``.

    If this test fails, ``derive`` is non-deterministic across processes
    and every reproducibility claim is broken.
    """
    from pilot402.core.seeds import _stable_uint32

    assert _stable_uint32("env") == _stable_uint32("env")
    assert _stable_uint32("env") != _stable_uint32("policy")
    # blake2b is bit-identical across platforms and Python versions, so this
    # value is fixed for the lifetime of the algorithm choice. If this fails,
    # someone changed the hash function and every existing seed-derived
    # stream is now incompatible.
    assert _stable_uint32("env") == 0xEFEA47DA
    assert _stable_uint32("policy") == 0xEBC947FC
