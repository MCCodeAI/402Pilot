"""Tests for ``pilot402.eval.judge_backend.CachedJudgeBackend``.

The cache is the only reason the LLM-as-judge can satisfy the determinism
contract (system_design §2.5). These tests pin its behavior:

* First call hits the underlying client.
* Second call returns the cached value without hitting the client.
* The on-disk cache survives instance reconstruction.
* Cache entries record judge model_id / seed as provenance.
"""

from __future__ import annotations

from pathlib import Path

from pilot402.core import EvaluatorBackend
from pilot402.eval.judge_backend import (
    CachedJudgeBackend,
    JudgeRequest,
    MockJudgeClient,
)


def test_first_call_hits_client(tmp_path: Path) -> None:
    client = MockJudgeClient()
    backend = CachedJudgeBackend(
        client=client,
        cache_path=tmp_path / "cache.jsonl",
        model_id="claude-sonnet-4.6",
        seed=0,
    )
    score = backend.score("question?", "an answer")
    assert client.call_count == 1
    assert score.backend is EvaluatorBackend.JUDGE
    assert score.judge_model_id == "claude-sonnet-4.6"
    assert score.judge_seed == 0


def test_repeat_call_uses_cache(tmp_path: Path) -> None:
    client = MockJudgeClient()
    backend = CachedJudgeBackend(
        client=client,
        cache_path=tmp_path / "cache.jsonl",
        model_id="claude-sonnet-4.6",
    )
    a = backend.score("q", "r")
    b = backend.score("q", "r")
    assert a == b
    assert client.call_count == 1  # second call did not hit the client


def test_distinct_inputs_hit_client_distinctly(tmp_path: Path) -> None:
    client = MockJudgeClient()
    backend = CachedJudgeBackend(
        client=client,
        cache_path=tmp_path / "cache.jsonl",
        model_id="m",
    )
    backend.score("q1", "r1")
    backend.score("q1", "r2")
    backend.score("q2", "r1")
    assert client.call_count == 3


def test_cache_survives_instance_reconstruction(tmp_path: Path) -> None:
    cache_path = tmp_path / "cache.jsonl"
    first_client = MockJudgeClient()
    first = CachedJudgeBackend(client=first_client, cache_path=cache_path, model_id="m")
    first.score("q", "r")

    second_client = MockJudgeClient()
    second = CachedJudgeBackend(client=second_client, cache_path=cache_path, model_id="m")
    second.score("q", "r")
    assert second_client.call_count == 0  # served from disk


def test_score_clamped_to_unit_interval(tmp_path: Path) -> None:
    """Defend against an off-protocol judge response."""

    def bad_responder(_: JudgeRequest) -> float:
        return 99.0  # garbage

    client = MockJudgeClient(responder=bad_responder)
    backend = CachedJudgeBackend(
        client=client,
        cache_path=tmp_path / "cache.jsonl",
        model_id="m",
    )
    score = backend.score("q", "r")
    assert score.q == 1.0


def test_negative_score_clamped_to_zero(tmp_path: Path) -> None:
    client = MockJudgeClient(responder=lambda _: -0.5)
    backend = CachedJudgeBackend(
        client=client,
        cache_path=tmp_path / "cache.jsonl",
        model_id="m",
    )
    score = backend.score("q", "r")
    assert score.q == 0.0


def test_mock_judge_default_response_is_deterministic() -> None:
    a = MockJudgeClient().evaluate(JudgeRequest(question="q", response="r", model_id="m", seed=0))
    b = MockJudgeClient().evaluate(JudgeRequest(question="q", response="r", model_id="m", seed=0))
    assert a == b
    assert 0.0 <= a <= 1.0
