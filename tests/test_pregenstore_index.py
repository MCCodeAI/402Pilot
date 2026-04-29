"""Tests for ``pilot402.pregen.dataset.JsonlPregenStore``.

The store is the bridge between Phase 1 (pregen) and Phases 2-4
(experiments). These tests pin:

* Files are loaded and indexed correctly from a fixture directory.
* ``get`` returns the right record; missing records raise ``KeyError``.
* ``versions`` returns sorted version ids per (task, provider).
* Duplicate (task, provider, version) triples are rejected loudly.
* The store satisfies the ``PregenStore`` Protocol.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from pilot402.core import PregenStore, ProviderId
from pilot402.pregen.dataset import JsonlPregenStore

FIXTURE_FILE = Path(__file__).parent / "fixtures" / "pregen_records.jsonl"


@pytest.fixture
def populated_dir(tmp_path: Path) -> Path:
    """Copy the fixture into a temp directory shaped like ``data/pregen/``.

    The store expects per-(provider × task_type) JSONL files. Our fixture
    bundles records for several (provider, task_type) cells in one file —
    the store doesn't care about the filename, only the line contents, so
    this works for the indexing test.
    """

    out = tmp_path / "pregen"
    out.mkdir()
    shutil.copy(FIXTURE_FILE, out / "mixed.jsonl")
    return out


def test_store_implements_protocol(populated_dir: Path) -> None:
    store = JsonlPregenStore(populated_dir)
    assert isinstance(store, PregenStore)


def test_store_loads_all_records(populated_dir: Path) -> None:
    store = JsonlPregenStore(populated_dir)
    assert len(store) == 5  # the fixture has five lines


def test_get_returns_matching_record(populated_dir: Path) -> None:
    store = JsonlPregenStore(populated_dir)
    rec = store.get("trivia/test_001", ProviderId.P_CHEAP, version=0)
    assert rec.response == "Au"
    assert rec.cost_usdc == 0.0005
    assert rec.quality_score.q == 1.0


def test_get_missing_raises_keyerror(populated_dir: Path) -> None:
    store = JsonlPregenStore(populated_dir)
    with pytest.raises(KeyError):
        store.get("does/not/exist", ProviderId.P_CHEAP, version=0)
    with pytest.raises(KeyError):
        store.get("trivia/test_001", ProviderId.P_CHEAP, version=99)


def test_versions_returns_sorted_tuple(populated_dir: Path) -> None:
    store = JsonlPregenStore(populated_dir)
    vs = store.versions("trivia/test_001", ProviderId.P_CHEAP)
    assert vs == (0, 1)
    assert isinstance(vs, tuple)


def test_versions_empty_for_unknown(populated_dir: Path) -> None:
    store = JsonlPregenStore(populated_dir)
    assert store.versions("unknown", ProviderId.P_PREMIUM) == ()


def test_missing_dir_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        JsonlPregenStore(tmp_path / "nope")


def test_duplicate_records_rejected(tmp_path: Path) -> None:
    out = tmp_path / "pregen"
    out.mkdir()
    src = FIXTURE_FILE.read_text(encoding="utf-8")
    # Repeat the first line so (task_id, provider_id, version) collides.
    duplicated = src + src.splitlines()[0] + "\n"
    (out / "dupe.jsonl").write_text(duplicated, encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate pregen record"):
        JsonlPregenStore(out)
