"""Deterministic scoring backends.

* ``pass_at_1`` for T1 (HumanEval-style coding) — runs the model's code in
  a subprocess against the task's test harness with a wall-clock timeout.
* ``em_score`` / ``f1_score`` for T2 (HotpotQA) and T3a (TriviaQA-web
  closed-form). Standard SQuAD-style normalization.
* ``max_em_f1`` is the composite scalar used in the paper for T2 / T3a:
  ``max(EM, F1)``. EM gives full credit for exact matches; F1 gives partial
  credit and stays informative when the model paraphrases the answer.

All three are pure functions; same inputs → same outputs across runs and
machines. The pregen pipeline calls these once per response and caches
the score in ``QualityScore.q``.
"""

from __future__ import annotations

import re
import string
import subprocess
import sys
import tempfile
from pathlib import Path

from pilot402.core import Task

# ---------------------------------------------------------------------------
# Token-based scoring (T2 / T3a)
# ---------------------------------------------------------------------------

_ARTICLES_RE = re.compile(r"\b(a|an|the)\b", re.UNICODE)
_PUNCT_TABLE = str.maketrans("", "", string.punctuation)
_WHITESPACE_RE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    """SQuAD-style normalization: lowercase, drop articles + punctuation,
    collapse whitespace. Matches the reference HotpotQA/TriviaQA evaluator."""

    text = text.lower()
    text = _ARTICLES_RE.sub(" ", text)
    text = text.translate(_PUNCT_TABLE)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text


def em_score(prediction: str, gold: str) -> float:
    """Exact match after normalization. Returns 1.0 on match, 0.0 otherwise."""

    return 1.0 if _normalize(prediction) == _normalize(gold) else 0.0


def f1_score(prediction: str, gold: str) -> float:
    """Token-level F1 of normalized strings. Returns a value in [0, 1]."""

    pred_tokens = _normalize(prediction).split()
    gold_tokens = _normalize(gold).split()
    if not pred_tokens and not gold_tokens:
        return 1.0
    if not pred_tokens or not gold_tokens:
        return 0.0
    common: dict[str, int] = {}
    for tok in pred_tokens:
        if tok in gold_tokens:
            common[tok] = min(pred_tokens.count(tok), gold_tokens.count(tok))
    overlap = sum(common.values())
    if overlap == 0:
        return 0.0
    precision = overlap / len(pred_tokens)
    recall = overlap / len(gold_tokens)
    return 2 * precision * recall / (precision + recall)


def max_em_f1(prediction: str, gold: str) -> float:
    """Composite ``max(EM, F1)`` used as the T2 / T3a scalar in the paper."""

    return max(em_score(prediction, gold), f1_score(prediction, gold))


# ---------------------------------------------------------------------------
# Sandboxed code execution (T1)
# ---------------------------------------------------------------------------


_CODE_FENCE_RE = re.compile(r"```(?:python)?\n?(.*?)```", re.DOTALL)
_IMPORT_LINE_RE = re.compile(r"^\s*(?:from\s+\S+\s+import\s+|import\s+)", re.MULTILINE)


def _extract_imports(text: str) -> str:
    """Pull every ``import`` / ``from ... import`` line out of ``text``.

    Used by ``_assemble_program`` to defend against the common LLM behavior
    of writing a complete function definition without re-emitting the
    imports that were already in the prompt. Without this, a perfectly
    correct response that uses ``List[int]`` (HumanEval/3 style) would
    fail with ``NameError: List`` at test time.
    """

    lines = []
    for match in _IMPORT_LINE_RE.finditer(text):
        line_start = text.rfind("\n", 0, match.start()) + 1
        line_end = text.find("\n", match.end())
        if line_end == -1:
            line_end = len(text)
        lines.append(text[line_start:line_end].rstrip())
    return "\n".join(lines)


def _strip_code_fence(response: str) -> str:
    """Pull the largest fenced code block out of a response, if any."""

    matches: list[str] = _CODE_FENCE_RE.findall(response)
    if not matches:
        return response
    # Return the longest block — model often emits a tiny example fence first.
    return str(max(matches, key=len))


def _assemble_program(task: Task, response: str) -> str:
    """Build the runnable program for HumanEval-style evaluation.

    Strategy:
    * If the cleaned response already defines the entry-point function, use
      it standalone (the model wrote a complete function).
    * Otherwise treat the response as a body continuation of ``task.prompt``
      and prepend the prompt (typical when the model just continues the
      docstring).
    """

    code = _strip_code_fence(response)
    metadata = task.metadata or {}
    entry_point = str(metadata.get("entry_point", "")).strip()
    test = str(metadata.get("test", "")).strip()
    if not entry_point or not test:
        raise ValueError(
            "pass_at_1 requires 'entry_point' and 'test' in task.metadata"
        )

    if f"def {entry_point}(" in code:
        # Response is a complete function. Prepend any imports from the
        # prompt that the response did not re-emit, so symbols like
        # ``List[int]`` resolve. ``_IMPORT_LINE_RE`` is anchored at the start
        # of a line so module-level only.
        prompt_imports = _extract_imports(task.prompt)
        response_imports = _extract_imports(code)
        missing_imports = "\n".join(
            line for line in prompt_imports.splitlines() if line not in response_imports
        )
        body = (missing_imports + "\n\n" + code) if missing_imports else code
    else:
        # Response is a body continuation. Prepend the entire prompt so the
        # function signature + docstring are present.
        body = task.prompt + code

    return body + "\n\n" + test + f"\n\ncheck({entry_point})\n"


def pass_at_1(
    task: Task,
    response: str,
    *,
    timeout_s: float = 5.0,
) -> float:
    """Execute the model's code against the task's test harness.

    Returns 1.0 if the test runs to completion with exit code 0, else 0.0.
    Any exception, assertion failure, syntax error, or timeout maps to 0.0.

    The program runs in a fresh ``python`` subprocess with a hard wall-clock
    timeout. This is the standard HumanEval evaluation protocol; safer than
    ``exec`` in-process but still NOT a security boundary — only run pregen
    on inputs you trust.
    """

    program = _assemble_program(task, response)
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py",
        delete=False,
        encoding="utf-8",
    ) as fh:
        path = Path(fh.name)
        fh.write(program)
    try:
        try:
            result = subprocess.run(
                [sys.executable, str(path)],
                capture_output=True,
                timeout=timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return 0.0
        return 1.0 if result.returncode == 0 else 0.0
    finally:
        path.unlink(missing_ok=True)
