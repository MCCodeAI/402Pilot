"""Drive a pregen run from an experiment YAML.

Usage::

    # Tier 1 thin pregen (1 provider × 5 tasks × 5 versions = 25 calls)
    python -m scripts.run_pregen experiments/main.yaml \\
        --providers P-cheap \\
        --limits humaneval=5 hotpotqa=0 triviaqa=0 openweb=0

    # Tier 2 calibration probe (5 providers × 20 tasks × 5 versions = 500 calls)
    python -m scripts.run_pregen experiments/main.yaml \\
        --limits humaneval=5 hotpotqa=5 triviaqa=5 openweb=5

    # Full pregen (5 providers × 823 effective tasks × 5 versions = 20,575 calls)
    python -m scripts.run_pregen experiments/main.yaml

    # Dry run — print the call plan without invoking any LLMs
    python -m scripts.run_pregen experiments/main.yaml --dry-run

The script reads API keys from ``.env`` via ``ExperimentConfig`` and
constructs real backends. For testing, ``run_pregen`` itself accepts
mock backends — see ``tests/test_generator_e2e_mock.py``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pilot402.core import ExperimentConfig, ProviderId, QualityScore, load_config
from pilot402.eval import (
    AnthropicJudgeClient,
    CachedJudgeBackend,
    JudgeBackend,
    OpenRouterJudgeClient,
)
from pilot402.eval.judge_backend import JudgeClient
from pilot402.pregen import run_pregen
from pilot402.pregen.providers import LlmBackend
from pilot402.pregen.providers.backends import (
    OpenAIBackend,
    QwenBackend,
)
from pilot402.pregen.tasks.loader import DEFAULT_LIMITS

_OPENAI_PROVIDERS: frozenset[ProviderId] = frozenset(
    {ProviderId.P_MID, ProviderId.P_PREMIUM, ProviderId.P_ADV, ProviderId.P_FLAKY}
)


def _parse_limits(pairs: list[str]) -> dict[str, int | None]:
    out: dict[str, int | None] = {}
    for raw in pairs:
        key, _, value = raw.partition("=")
        if not key or not value:
            raise SystemExit(f"--limits expects KEY=VALUE pairs, got {raw!r}")
        out[key.strip()] = int(value)
    return out


def _parse_offsets(pairs: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for raw in pairs:
        key, _, value = raw.partition("=")
        if not key or not value:
            raise SystemExit(f"--offsets expects KEY=VALUE pairs, got {raw!r}")
        n = int(value)
        if n < 0:
            raise SystemExit(f"--offsets value must be non-negative, got {raw!r}")
        out[key.strip()] = n
    return out


def _build_real_backends(
    cfg: ExperimentConfig,
    needed: frozenset[ProviderId],
) -> dict[ProviderId, LlmBackend]:
    """Construct ``LlmBackend`` instances only for providers in ``needed``.

    P-cheap → Qwen / DashScope. The other four → OpenAI. API keys are
    only checked for backends actually being built — running just P-cheap
    does not require ``OPENAI_API_KEY`` and vice versa.
    """

    backends: dict[ProviderId, LlmBackend] = {}

    if ProviderId.P_CHEAP in needed:
        if not cfg.llm_keys.qwen_api_key:
            raise SystemExit(
                "QWEN_API_KEY is empty in .env; required for P-cheap."
            )
        backends[ProviderId.P_CHEAP] = QwenBackend(api_key=cfg.llm_keys.qwen_api_key)

    needed_openai = needed & _OPENAI_PROVIDERS
    if needed_openai:
        if not cfg.llm_keys.openai_api_key:
            raise SystemExit(
                "OPENAI_API_KEY is empty in .env; required for "
                f"{sorted(p.value for p in needed_openai)}."
            )
        openai_backend = OpenAIBackend(api_key=cfg.llm_keys.openai_api_key)
        for pid in needed_openai:
            backends[pid] = openai_backend

    return backends


class _UnconfiguredJudge:
    """Stub judge used when ``ANTHROPIC_API_KEY`` is not configured.

    Raises with a clear error if the orchestrator ever reaches a T3b task
    and tries to score it. Lets Tier 1 / Tier 2 runs that limit themselves
    to T1 / T2 / T3a proceed without an Anthropic key.
    """

    def score(self, question: str, response: str) -> QualityScore:  # noqa: ARG002
        raise SystemExit(
            "T3b open-ended scoring was attempted but ANTHROPIC_API_KEY is "
            "empty in .env. Either set the key or limit this run to "
            "T1 / T2 / T3a tasks (e.g. add `--limits openweb=0`)."
        )


def _build_real_judge(
    cfg: ExperimentConfig,
    t3b_in_scope: bool,
) -> JudgeBackend:
    """Real Claude judge if needed; otherwise a stub that raises on use.

    The judge backend is selected by ``cfg.judge.judge_provider``:

    * ``anthropic`` (default) — talks to ``api.anthropic.com`` via the
      Anthropic SDK using the Messages schema.
    * ``openrouter``         — talks to OpenRouter's OpenAI-compatible
      chat completions endpoint via the OpenAI SDK. Use when the user
      has an OpenRouter key in ``ANTHROPIC_API_KEY`` instead of a native
      Anthropic key. ``JUDGE_MODEL`` should then be an OpenRouter model
      id like ``anthropic/claude-sonnet-4.6``.

    The orchestrator never invokes the judge for failed calls or for
    non-T3b task types, so a stub is safe whenever T3b is excluded.
    """

    if not t3b_in_scope:
        return _UnconfiguredJudge()
    if not cfg.llm_keys.judge_api_key:
        raise SystemExit(
            "JUDGE_API_KEY is empty in .env; required for the T3b judge. "
            "It holds whichever credential matches JUDGE_PROVIDER "
            "(Anthropic key for 'anthropic', OpenRouter key for 'openrouter', "
            "Vercel key for 'vercel', etc.)."
        )

    provider = cfg.judge.judge_provider.lower()
    client: JudgeClient
    if provider == "openrouter":
        # Default OpenRouter base URL; allow override via JUDGE_BASE_URL.
        base_url = cfg.judge.judge_base_url or "https://openrouter.ai/api/v1"
        client = OpenRouterJudgeClient(
            api_key=cfg.llm_keys.judge_api_key,
            base_url=base_url,
        )
    elif provider in ("vercel", "openai_compatible"):
        # Generic OpenAI-compatible gateway (Vercel AI Gateway, Cloudflare,
        # native OpenAI, etc.). Requires JUDGE_BASE_URL to be explicit.
        if not cfg.judge.judge_base_url:
            raise SystemExit(
                f"JUDGE_PROVIDER={provider!r} requires JUDGE_BASE_URL in .env "
                f"(e.g. https://ai-gateway.vercel.sh/v1)."
            )
        client = OpenRouterJudgeClient(
            api_key=cfg.llm_keys.judge_api_key,
            base_url=cfg.judge.judge_base_url,
        )
    elif provider == "anthropic":
        client = AnthropicJudgeClient(api_key=cfg.llm_keys.judge_api_key)
    else:
        raise SystemExit(
            f"Unknown JUDGE_PROVIDER={cfg.judge.judge_provider!r}; "
            f"must be 'anthropic', 'openrouter', 'vercel', or 'openai_compatible'."
        )

    cache_path = cfg.paths.pregen_dir / "judge_cache.jsonl"
    return CachedJudgeBackend(
        client=client,
        cache_path=cache_path,
        model_id=cfg.judge.judge_model,
        seed=cfg.judge.judge_seed,
    )


def _t3b_in_scope(
    limits_overrides: dict[str, int | None] | None,
) -> bool:
    """Will any T3b (open-ended) tasks be loaded under these limits?"""

    effective = {**DEFAULT_LIMITS, **(limits_overrides or {})}
    cap = effective.get("openweb")
    return cap is None or cap > 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path, help="experiment YAML path.")
    parser.add_argument(
        "--providers",
        nargs="+",
        choices=tuple(p.value for p in ProviderId),
        help="subset of providers to run (default: all five from cfg).",
    )
    parser.add_argument(
        "--limits",
        nargs="*",
        default=[],
        metavar="KEY=N",
        help="per-source caps; e.g. `--limits humaneval=5 hotpotqa=0`.",
    )
    parser.add_argument(
        "--offsets",
        nargs="*",
        default=[],
        metavar="KEY=N",
        help=(
            "per-source offsets into the deterministic task order; pair with "
            "--limits to run a replication on a disjoint slice."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=(
            "override pregen output directory (default: cfg.paths.pregen_dir). "
            "Use with --offsets to keep replication runs isolated."
        ),
    )
    parser.add_argument(
        "--version-count",
        type=int,
        default=5,
        help="versions per (provider, task) pair (default: 5).",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=8,
        help="concurrent LLM calls (default: 8). 1 = strict sequential.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the call plan and exit without invoking any LLM.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help=(
            "skip cells already present in the output directory. Use after "
            "Ctrl+C to continue an interrupted run; resume granularity is "
            "per (provider, task, version) cell."
        ),
    )
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    provider_subset: tuple[ProviderId, ...] | None = (
        tuple(ProviderId(p) for p in args.providers) if args.providers else None
    )
    limits = _parse_limits(args.limits) or None
    offsets = _parse_offsets(args.offsets) or None

    needed_providers: frozenset[ProviderId] = frozenset(
        provider_subset
        if provider_subset is not None
        else (p.provider_id for p in cfg.providers)
    )

    if args.dry_run:
        # Construct mock backends just to satisfy the orchestrator's input
        # validation; never invoked.
        from pilot402.pregen.providers import MockLlmBackend

        backends: dict[ProviderId, LlmBackend] = {
            pid: MockLlmBackend() for pid in ProviderId
        }
        from pilot402.eval import MockJudgeClient

        judge: JudgeBackend = CachedJudgeBackend(
            client=MockJudgeClient(),
            cache_path=Path("/tmp/_pregen_dry_run_cache.jsonl"),
            model_id="dry-run",
        )
    else:
        backends = _build_real_backends(cfg, needed=needed_providers)
        judge = _build_real_judge(cfg, t3b_in_scope=_t3b_in_scope(limits))

    n = run_pregen(
        cfg,
        backends=backends,
        judge=judge,
        pregen_out_dir=args.output_dir,
        limits=limits,
        offsets=offsets,
        provider_subset=provider_subset,
        version_count=args.version_count,
        concurrency=args.concurrency,
        dry_run=args.dry_run,
        resume=args.resume,
    )
    print(f"{'PLAN' if args.dry_run else 'DONE'}: {n} cells")
    return 0


if __name__ == "__main__":
    sys.exit(main())
