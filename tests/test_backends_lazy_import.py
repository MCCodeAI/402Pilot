"""Tests for ``pilot402.pregen.providers.backends``.

The non-trivial guarantee is that this module imports cleanly even when
the LLM SDKs (``openai``, ``anthropic``, ``dashscope``) are not installed.
Instantiation may fail with a clear ``ImportError`` — that's the expected
contract — but `from pilot402.pregen.providers.backends import ...` MUST
succeed.

The point: ``make check`` in the sandbox does not require the [pregen]
extras, but somebody running ``scripts.run_pregen`` will need them.
"""

from __future__ import annotations

import pytest

from pilot402.pregen.providers import LlmBackend
from pilot402.pregen.providers.backends import (
    AnthropicBackend,
    OpenAIBackend,
    QwenBackend,
)


def test_module_imports_without_sdks() -> None:
    """Import succeeded reaching this point — the assertion is just to
    make the guarantee explicit in pytest output."""
    assert OpenAIBackend.__name__ == "OpenAIBackend"
    assert AnthropicBackend.__name__ == "AnthropicBackend"
    assert QwenBackend.__name__ == "QwenBackend"


def _try_construct_or_skip_if_sdk_missing(
    cls: type, *, expected_pkg: str, **kwargs: object
) -> object:
    try:
        return cls(**kwargs)
    except ImportError as exc:
        pytest.skip(f"{expected_pkg} not installed in this env ({exc})")


def test_openai_backend_instantiates_or_clearly_errors() -> None:
    backend = _try_construct_or_skip_if_sdk_missing(
        OpenAIBackend, expected_pkg="openai", api_key="sk-test"
    )
    assert isinstance(backend, LlmBackend)


def test_anthropic_backend_instantiates_or_clearly_errors() -> None:
    backend = _try_construct_or_skip_if_sdk_missing(
        AnthropicBackend, expected_pkg="anthropic", api_key="sk-test"
    )
    assert isinstance(backend, LlmBackend)


def test_qwen_backend_instantiates_or_clearly_errors() -> None:
    backend = _try_construct_or_skip_if_sdk_missing(
        QwenBackend, expected_pkg="dashscope", api_key="sk-test"
    )
    assert isinstance(backend, LlmBackend)


def test_anthropic_judge_client_lazy_import_or_skip() -> None:
    from pilot402.eval import AnthropicJudgeClient

    try:
        client = AnthropicJudgeClient(api_key="sk-test")
    except ImportError as exc:
        pytest.skip(f"anthropic SDK missing ({exc})")
    assert client is not None
