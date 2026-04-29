# 402Pilot — developer entry points.
#
# `make check` is the per-milestone verification gate: types, lint, import
# smoke, and pytest. The same command runs at every milestone (M1, M2, ...);
# the only thing that changes is which source files and tests exist.

.PHONY: help install check lint typecheck test smoke clean

help:
	@echo "Targets:"
	@echo "  install    Install package + dev deps in editable mode."
	@echo "  check      Full M1 gate: typecheck + lint + smoke + test."
	@echo "  typecheck  mypy --strict on the package."
	@echo "  lint       ruff check on package and tests."
	@echo "  smoke      Import the public API surface."
	@echo "  test       pytest -ra."
	@echo "  clean      Remove caches."

install:
	pip install -e ".[dev]"

typecheck:
	mypy pilot402/

lint:
	ruff check pilot402/ tests/

smoke:
	python -c "from pilot402.core import Task, Policy, ExperimentConfig, SeedSource, LogRecord, PregenRecord; print('OK')"

test:
	pytest -ra

check: typecheck lint smoke test

clean:
	rm -rf .mypy_cache/ .pytest_cache/ .ruff_cache/ build/ dist/ *.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
