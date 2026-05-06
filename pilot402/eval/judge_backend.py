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
import sys
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


JUDGE_RUBRIC = """You are a STRICT evaluator scoring an answer on a 0.0 to \
1.0 scale. Be skeptical of confident-sounding answers and verify every \
factual claim mentally before scoring.

Score bands (use the full range, do not cluster at 1.0):

  0.95 – 1.00  Outstanding: factually flawless, comprehensive, well-organized,
               no hallucinations whatsoever. Reserved for truly excellent
               answers — at most 10% of answers should land here.
  0.75 – 0.94  Strong: correct on the core question, minor omissions or
               minor wording issues, no factual errors.
  0.50 – 0.74  Adequate: answers the question but contains one notable
               factual error, omits an important aspect, or includes
               misleading framing.
  0.25 – 0.49  Poor: contains multiple factual errors, fabricates a
               source/date/entity, or gives a confidently-stated wrong
               answer to a key sub-question.
  0.00 – 0.24  Unusable: refuses, off-topic, near-empty, or wrong on
               the central claim.

Calibration anchors:
- A polished, articulate answer with ONE confidently-stated factual
  error (wrong date, wrong attribution, fabricated reference) should
  score in the 0.30–0.50 band, NOT in the 0.7+ band, even if the
  surrounding prose reads well.
- An answer that is correct but markedly less complete than a
  textbook treatment should land in 0.55–0.75, not 0.85+.
- Score on substance, not on length, formatting, or rhetorical polish.

Three criteria contribute to the score:
1. Factual accuracy — every checkable claim must be correct.
2. Completeness — does the answer cover the core sub-questions?
3. Absence of hallucination — fabricated names, dates, citations,
   or rules count strongly against the score.

Output ONLY a single JSON object: {"q": <float between 0.0 and 1.0>}. \
Do not include any other text, commentary, code fences, or formatting \
around the JSON."""


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
            max_tokens=1024,
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

    On parse failure, prints a diagnostic to stderr so the caller can
    inspect what the judge actually returned (truncated reasoning output,
    refusal, off-format text, etc.).
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
    print(
        "\n[judge parse failure → q=0 fallback]\n"
        f"  body[0:500]: {body[:500]!r}\n",
        file=sys.stderr,
    )
    return 0.0


# ---------------------------------------------------------------------------
# OpenRouterJudgeClient — alternative implementation routing through
# OpenRouter's OpenAI-compatible API, for users who hold an OpenRouter
# key instead of (or in addition to) a native Anthropic key.
# ---------------------------------------------------------------------------


@dataclass
class OpenRouterJudgeClient:
    """LLM-as-judge via OpenRouter's OpenAI-compatible chat completions API.

    OpenRouter aggregates many providers (including Anthropic) behind a
    single OpenAI-shaped endpoint. To use Claude through OpenRouter:

    1. Put the OpenRouter key in ``ANTHROPIC_API_KEY`` (we treat that
       env var as the generic "judge key" — it is fed to whichever
       client this picks).
    2. Set ``JUDGE_PROVIDER=openrouter`` in ``.env``.
    3. Set ``JUDGE_MODEL`` to an OpenRouter model id such as
       ``anthropic/claude-sonnet-4.6`` (note the ``anthropic/`` prefix).

    The Anthropic native client (``AnthropicJudgeClient``) talks to
    ``api.anthropic.com`` and uses the Messages schema; this client
    routes through OpenRouter and uses chat completions. The two are
    NOT interchangeable at the wire level — we have both so the user
    can pick whichever matches their key.
    """

    api_key: str
    base_url: str = "https://openrouter.ai/api/v1"
    timeout_s: float = 60.0
    _client: Any = field(init=False, repr=False, default=None)

    def __post_init__(self) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError(
                "The 'openai' package is required for OpenRouterJudgeClient. "
                "Install with `pip install -e \".[pregen]\"`."
            ) from exc
        self._client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout_s,
        )

    def evaluate(self, request: JudgeRequest) -> float:
        import time

        max_retries = 4
        base_delay = 1.0

        prompt = (
            f"Question:\n{request.question}\n\n"
            f"Answer:\n{request.response}\n\n"
            f"Score this answer."
        )
        # No provider preference — OpenRouter picks the routing that fits
        # the model id. Retry on rate-limit (4xx 429 / SDK RateLimitError)
        # with exponential backoff so concurrent judge calls don't lose
        # data when a gateway throttles.
        last_exc: Exception | None = None
        for attempt in range(max_retries):
            try:
                resp = self._client.chat.completions.create(
                    model=request.model_id,
                    messages=[
                        {"role": "system", "content": JUDGE_RUBRIC},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=1024,
                    temperature=0.0,
                )
                body = resp.choices[0].message.content or ""
                return _parse_judge_score(body)
            except Exception as exc:
                last_exc = exc
                cls_name = type(exc).__name__
                is_rate_limit = (
                    "RateLimit" in cls_name
                    or "Throttl" in cls_name
                    or "429" in str(exc)
                )
                if is_rate_limit and attempt < max_retries - 1:
                    time.sleep(base_delay * (2 ** attempt))
                    continue
                # Non-retryable or exhausted — diagnostic dump and re-raise.
                print(
                    "\n--- OpenRouter judge call failed -------------------",
                    file=sys.stderr,
                )
                print(f"model_id: {request.model_id}", file=sys.stderr)
                print(
                    f"question[0:300]: {request.question[:300]!r}",
                    file=sys.stderr,
                )
                print(
                    f"response[0:300]: {request.response[:300]!r}",
                    file=sys.stderr,
                )
                print(f"error: {exc!r}", file=sys.stderr)
                print("-----------------------------------------------------\n", file=sys.stderr)
                raise
        raise last_exc or RuntimeError("OpenRouter rate limit retries exhausted")
