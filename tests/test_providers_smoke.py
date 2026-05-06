"""Tests for ``pilot402.pregen.providers``.

These verify the version-level adversarial mechanism and the wiring
between provider classes and the ``LlmBackend`` Protocol — without ever
calling a real LLM.
"""

from __future__ import annotations

import pytest
from numpy.random import default_rng

from pilot402.core import FailureCode, ProviderId, Task, TaskType
from pilot402.pregen.providers import (
    ADVERSARIAL_VERSIONS,
    PROVIDER_REGISTRY,
    LlmRequest,
    MockLlmBackend,
    RecordingMockBackend,
    make_provider,
)
from pilot402.pregen.providers.prompts import (
    P_ADV_ADVERSARIAL_PROMPT,
    P_ADV_NEUTRAL_PROMPT,
    P_CHEAP_PROMPT,
    P_FLAKY_PROMPT,
    P_MID_PROMPT,
)


@pytest.fixture
def trivia_task() -> Task:
    return Task(
        task_id="trivia/x",
        task_type=TaskType.T3A_WEBSEARCH_CLOSED,
        prompt="What is the capital of France?",
        gold_answer="Paris",
        difficulty=0.2,
    )


def test_registry_covers_all_five_providers() -> None:
    assert set(PROVIDER_REGISTRY.keys()) == {
        ProviderId.P_CHEAP,
        ProviderId.P_MID,
        ProviderId.P_PREMIUM,
        ProviderId.P_ADV,
        ProviderId.P_FLAKY,
    }


def test_make_provider_builds_all_registered() -> None:
    backend = MockLlmBackend()
    for pid in ProviderId:
        provider = make_provider(pid, backend, 0.001)
        assert provider.provider_id is pid


def test_p_cheap_uses_cheap_prompt(trivia_task: Task) -> None:
    backend = RecordingMockBackend()
    provider = make_provider(ProviderId.P_CHEAP, backend, 0.0005)
    rng = default_rng(0)
    result = provider.generate(trivia_task, version=0, rng=rng)
    assert not result.failure_flag
    assert result.cost_usdc == 0.0005
    assert len(backend.calls) == 1
    assert backend.calls[0].system == P_CHEAP_PROMPT
    assert backend.calls[0].user == trivia_task.prompt


def test_honest_providers_share_uniform_prompt(trivia_task: Task) -> None:
    """All non-adversarial providers (cheap / mid / premium / flaky non-timeout
    versions, and P-adv neutral versions) MUST use the same system prompt.

    Differentiation between honest providers comes purely from the underlying
    model + price tier, not from prompt engineering. Any prompt drift
    between honest providers reintroduces the metric artifact we just
    fought (P-mid's 'recall facts' style depressing first-sentence F1)
    and confounds 'is GPT-5.4 better than GPT-5.4-mini?' with 'did we
    write smarter prompts for premium?'.
    """

    backend_cheap = RecordingMockBackend()
    backend_mid = RecordingMockBackend()
    backend_prem = RecordingMockBackend()
    p_cheap = make_provider(ProviderId.P_CHEAP, backend_cheap, 0.0005)
    p_mid = make_provider(ProviderId.P_MID, backend_mid, 0.002)
    p_prem = make_provider(ProviderId.P_PREMIUM, backend_prem, 0.02)
    for prov in (p_cheap, p_mid, p_prem):
        prov.generate(trivia_task, 0, rng=default_rng(0))
    assert backend_cheap.calls[0].system == backend_mid.calls[0].system == backend_prem.calls[0].system
    assert backend_cheap.calls[0].system == P_MID_PROMPT  # All point to the uniform string.


def test_p_adv_uses_adversarial_prompt_for_versions_0_1_2(trivia_task: Task) -> None:
    backend = RecordingMockBackend()
    provider = make_provider(ProviderId.P_ADV, backend, 0.002)
    rng = default_rng(0)
    for v in (0, 1, 2):
        provider.generate(trivia_task, version=v, rng=rng)
    assert all(c.system == P_ADV_ADVERSARIAL_PROMPT for c in backend.calls)


def test_p_adv_uses_neutral_prompt_for_versions_3_4(trivia_task: Task) -> None:
    backend = RecordingMockBackend()
    provider = make_provider(ProviderId.P_ADV, backend, 0.002)
    rng = default_rng(0)
    for v in (3, 4):
        provider.generate(trivia_task, version=v, rng=rng)
    assert all(c.system == P_ADV_NEUTRAL_PROMPT for c in backend.calls)


def test_p_adv_neutral_prompt_equals_p_mid_prompt() -> None:
    """Critical fairness condition: P-adv's 'good' responses must look
    indistinguishable from P-mid's. If these prompts ever diverge, the
    bandit could learn a surface feature and the experiment is unfair."""
    assert P_ADV_NEUTRAL_PROMPT == P_MID_PROMPT


def test_p_flaky_versions_0_and_1_force_billed_timeout(trivia_task: Task) -> None:
    """Both v=0 and v=1 short-circuit to a billed timeout (40% failure rate)."""
    backend = RecordingMockBackend()
    provider = make_provider(ProviderId.P_FLAKY, backend, 0.002)
    rng = default_rng(0)
    for v in (0, 1):
        result = provider.generate(trivia_task, version=v, rng=rng)
        assert result.failure_flag is True
        assert result.failure_code is FailureCode.TIMEOUT
        assert result.response == ""
        assert result.cost_usdc == 0.002  # full charge per decision 2
    assert backend.calls == []  # no LLM call made for either v=0 or v=1


def test_p_flaky_versions_2_to_4_do_call_llm(trivia_task: Task) -> None:
    backend = RecordingMockBackend()
    provider = make_provider(ProviderId.P_FLAKY, backend, 0.002)
    rng = default_rng(0)
    for v in (2, 3, 4):
        result = provider.generate(trivia_task, version=v, rng=rng)
        assert not result.failure_flag
    assert len(backend.calls) == 3
    assert all(c.system == P_FLAKY_PROMPT for c in backend.calls)


def test_p_flaky_p_mid_share_prompt() -> None:
    """Same fairness reasoning as P-adv neutral / P-mid."""
    assert P_FLAKY_PROMPT == P_MID_PROMPT


def test_adversarial_versions_lock_table() -> None:
    """The version-level mechanism is the source of truth for empirical
    failure / degraded rates. Pin the values so an accidental edit shows
    up in code review.

    P-flaky uses {0, 1} → 2/5 = 40% empirical failure rate (calibrated 2026-05-02
    after Tier 3 showed 20% was too weak a signal vs P-mid at the same cost)."""
    assert ADVERSARIAL_VERSIONS[ProviderId.P_ADV] == frozenset({0, 1, 2})
    assert ADVERSARIAL_VERSIONS[ProviderId.P_FLAKY] == frozenset({0, 1})


def test_backend_exception_records_billed_payment_failure(trivia_task: Task) -> None:
    """A backend exception during pregen must be turned into a billed failure
    record, not propagate and crash the run."""

    class BoomBackend:
        def complete(self, request: LlmRequest):  # noqa: ARG002
            raise RuntimeError("simulated backend explosion")

    provider = make_provider(ProviderId.P_MID, BoomBackend(), 0.002)
    rng = default_rng(0)
    result = provider.generate(trivia_task, version=0, rng=rng)
    assert result.failure_flag is True
    assert result.failure_code is FailureCode.PAYMENT_FAILURE
    assert result.cost_usdc == 0.002


def test_seed_passed_to_backend_is_within_int32(trivia_task: Task) -> None:
    backend = RecordingMockBackend()
    provider = make_provider(ProviderId.P_MID, backend, 0.002)
    rng = default_rng(0)
    provider.generate(trivia_task, version=0, rng=rng)
    seed = backend.calls[0].seed
    assert 0 <= seed < 2**31
