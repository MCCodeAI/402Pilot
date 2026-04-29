"""LLM-as-judge backend for T3b (open-ended web-search).

The judge is the only non-deterministic scorer in the pipeline. To stay
within the determinism contract (system_design §2.5):

* Every score is cached on disk by ``(prompt_hash, response_hash)`` in a
  single JSONL file. Subsequent lookups are byte-identical.
* Cache entries record judge ``model_id`` and ``seed`` as provenance — the
  paper says we do not guarantee bit-identity of the external judge service,
  but the cached score is what the experiment uses.

Real-call path lives in ``CachedJudgeBackend`` and routes through a
``JudgeClient`` Protocol. The default real client (Claude via Anthropic SDK)
is provided in ``backends.py`` (added before Tier 1 thin pregen). Tests use
``MockJudgeClient`` here.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from pilot402.core import EvaluatorBackend, QualityScore

# ---------------------------------------------------------------------------
# Client protocol + mock
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class JudgeRequest:
    question: str
    response: str
    model_id: str
    seed: int


class JudgeClient(Protocol):
    """One real or mock LLM-as-judge call. Returns a ``q ∈ [0, 1]``."""

    def evaluate(self, request: JudgeRequest) -> float: ...


@dataclass
class MockJudgeClient:
    """Deterministic stand-in for the real Claude judge.

    By default scores are derived from a hash of the inputs so tests can
    assert specific numeric values. Pass ``responder`` for richer behavior
    (e.g. different scores per response to simulate quality differences).
    """

    responder: Callable[[JudgeRequest], float] | None = None
    call_count: int = 0

    def evaluate(self, request: JudgeRequest) -> float:
        self.call_count += 1
        if self.responder is not None:
            return float(self.responder(request))
        # Hash-derived score, stable across runs.
        digest = hashlib.blake2b(
            f"{request.question}|{request.response}|{request.seed}".encode(),
            digest_size=4,
        ).digest()
        raw = int.from_bytes(digest, "big") / 2**32
        return round(raw, 4)


# ---------------------------------------------------------------------------
# JudgeBackend Protocol — what eval/composite.py calls
# ---------------------------------------------------------------------------


class JudgeBackend(Protocol):
    """Cached judge interface. ``score`` is what the composite calls."""

    def score(self, question: str, response: str) -> QualityScore: ...


# ---------------------------------------------------------------------------
# CachedJudgeBackend — adds JSONL on-disk cache around any JudgeClient
# ---------------------------------------------------------------------------


def _hash(text: str) -> str:
    return hashlib.blake2b(text.encode("utf-8"), digest_size=8).hexdigest()


def _cache_key(question: str, response: str) -> str:
    return f"{_hash(question)}:{_hash(response)}"


@dataclass
class CachedJudgeBackend:
    """Routes through a ``JudgeClient`` with an on-disk JSONL cache.

    Cache file format: one JSON object per line:
    ``{"key": "<hex>:<hex>", "q": <float>, "model_id": "...", "seed": <int>}``.

    The first call writes; subsequent calls with the same ``(question, response)``
    pair return the cached value without invoking the client. ``call_count``
    on the underlying client is therefore the API-billable call count.
    """

    client: JudgeClient
    cache_path: Path
    model_id: str
    seed: int = 0
    _cache: dict[str, QualityScore] = field(default_factory=dict, init=False)
    _loaded: bool = field(default=False, init=False)

    def _load_if_needed(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not self.cache_path.is_file():
            return
        with self.cache_path.open("r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line:
                    continue
                rec = json.loads(line)
                self._cache[rec["key"]] = QualityScore(
                    q=float(rec["q"]),
                    backend=EvaluatorBackend.JUDGE,
                    judge_model_id=rec.get("model_id"),
                    judge_seed=rec.get("seed"),
                )

    def _append_cache(self, key: str, score: QualityScore) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        rec = {
            "key": key,
            "q": score.q,
            "model_id": score.judge_model_id,
            "seed": score.judge_seed,
        }
        with self.cache_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def score(self, question: str, response: str) -> QualityScore:
        self._load_if_needed()
        key = _cache_key(question, response)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        q = self.client.evaluate(
            JudgeRequest(
                question=question,
                response=response,
                model_id=self.model_id,
                seed=self.seed,
            )
        )
        # Clamp to the valid range; the judge is asked for [0, 1] but we
        # defend against off-protocol responses.
        q = max(0.0, min(1.0, float(q)))
        score = QualityScore(
            q=q,
            backend=EvaluatorBackend.JUDGE,
            judge_model_id=self.model_id,
            judge_seed=self.seed,
        )
        self._cache[key] = score
        self._append_cache(key, score)
        return score


# ---------------------------------------------------------------------------
# AnthropicJudgeClient — real Claude implementation of JudgeClient
# ---------------------------------------------------------------------------


JUDGE_RUBRIC = """You are evaluating an answer to a question. Score the answer \
on a scale of 0.0 to 1.0 based on three criteria:

1. Factual accuracy — are the claims correct?
2. Completeness — does the answer address the question fully?
3. Absence of hallucination — does the answer avoid fabricated details?

Output ONLY a single JSON object: {"q": <float between 0.0 and 1.0>}. Do not \
include any other text, commentary, or formatting."""


_JSON_OBJECT_RE = re.compile(r"\{[^{}]*\}", re.DOTALL)


@dataclass
class AnthropicJudgeClient:
    """Real LLM-as-judge client backed by Anthropic's Messages API.

    Lazy-imports the Anthropic SDK so this module is importable in
    environments without ``anthropic`` installed. Wrap this client in
    ``CachedJudgeBackend`` so each (question, response) pair is billed
    at most once.
    """

    api_key: str
    timeout_s: float = 60.0
    _client: Any = field(init=False, repr=False, default=None)

    def __post_init__(self) -> None:
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise ImportError(
                "The 'anthropic' package is required for AnthropicJudgeClient. "
                "Install with `pip install -e \".[pregen]\"`."
            ) from exc
        self._client = Anthropic(api_key=self.api_key, timeout=self.timeout_s)

    def evaluate(self, request: JudgeRequest) -> float:
        prompt = (
            f"Question:\n{request.question}\n\n"
            f"Answer:\n{request.response}\n\n"
            f"Score this answer."
        )
        resp = self._client.messages.create(
            model=request.model_id,
            system=JUDGE_RUBRIC,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=128,
            temperature=0.0,
        )
        # Concatenate text blocks from the response.
        parts: list[str] = []
        for block in resp.content:
            text = getattr(block, "text", None)
            if isinstance(text, str):
                parts.append(text)
        body = "".join(parts).strip()
        return _parse_judge_score(body)


def _parse_judge_score(body: str) -> float:
    """Pull a ``{"q": <float>}`` object out of the judge's response.

    Defends against the model wrapping the JSON in prose or code fences.
    Returns 0.0 if no valid score is found — the cache layer will record
    the zero so the run is reproducible, and an analyst can grep the cache
    for q=0 to find judge-format failures.
    """

    candidates = _JSON_OBJECT_RE.findall(body)
    for raw in candidates:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        q = payload.get("q")
        if isinstance(q, (int, float)):
            return float(q)
    return 0.0
