"""Pytest configuration for the integration test suite.

The main ``pyproject.toml`` uses ``--strict-markers``, so any custom
marker must be registered. We register ``integration`` here rather than
in ``pyproject.toml`` to keep the witness change set strictly additive
(see the design memo: no modifications to existing files).
"""

from __future__ import annotations


def pytest_configure(config) -> None:  # noqa: ANN001 - pytest hook signature
    config.addinivalue_line(
        "markers",
        "integration: marks a test as requiring the live x402 stack "
        "(skipped unless X402_INTEGRATION_TEST=1).",
    )
