# 402Pilot-Bench Dataset Schema

This document is the canonical specification of the pre-generated dataset
consumed by `pilot402/env/` and `pilot402/eval/` during experiments.

The dataset is produced once in Phase 1 by `pilot402/pregen/` (driving
~20,600 real LLM API calls: 5 providers × 824 tasks × 5 versions) and is
treated as a frozen artifact thereafter. `env/` and `eval/` MUST NOT call
LLMs during a bandit loop; they look up cached records by id.

The on-disk format is JSON Lines: one record per line, one file per
`(provider_id, task_type)` pair under `data/pregen/`.

```
data/pregen/
├── P-cheap__T1.jsonl
├── P-cheap__T2.jsonl
├── P-cheap__T3a.jsonl
├── P-cheap__T3b.jsonl
├── P-mid__T1.jsonl
├── ...
└── P-flaky__T3b.jsonl
```

## Record schema

Authoritative source: `pilot402.core.types.PregenRecord`.

| Field            | Type                | Notes                                                   |
|------------------|---------------------|---------------------------------------------------------|
| `schema_version` | `int`               | Currently `1`. Bumped on any breaking change below.      |
| `task_id`        | `str`               | Stable id from the source benchmark (HumanEval / HotpotQA / TriviaQA-web). |
| `task_type`      | `TaskType`          | One of `T1`, `T2`, `T3a`, `T3b`.                         |
| `provider_id`    | `ProviderId`        | One of the K=5 providers.                                |
| `version`        | `int ≥ 0`           | Which sampled response (0..4) for this `(task, provider)`. |
| `response`       | `str`               | Raw model output, untouched.                             |
| `cost_usdc`      | `float ≥ 0`         | Charged amount for this call. Replayed verbatim by env.  |
| `latency_s`      | `float ≥ 0`         | Wall-clock latency in seconds. Replayed verbatim.        |
| `failure_flag`   | `bool`              | True iff `failure_code != none`.                         |
| `failure_code`   | `FailureCode`       | Normalized code (`timeout`, `payment_failure`, ...).     |
| `quality_score`  | `QualityScore`      | Cached score; see below.                                 |
| `generated_at`   | `datetime` (ISO 8601)| Provenance timestamp; not consumed by the runtime.       |
| `temperature`    | `float ≥ 0`         | Sampling temperature used at generation time. Default 0.3 (since v2). |

`QualityScore` substructure:

| Field            | Type                | Notes                                                   |
|------------------|---------------------|---------------------------------------------------------|
| `q`              | `float ∈ [0,1]`     | The score replayed at experiment time.                   |
| `backend`        | `EvaluatorBackend`  | `em_f1` (T2/T3a) / `pass_at_1` (T1) / `judge` (T3b).     |
| `judge_model_id` | `str ?`             | Set iff `backend == judge`; logged as provenance.        |
| `judge_seed`     | `int ?`             | Set iff `backend == judge`.                              |

## Determinism contract

Per `system_design.md` §2.5:

* **T1 (coding) / T2 (multi-hop QA) / T3a (web search closed)** — backends
  are deterministic given `(response, gold_answer)`. Score is computed once
  during pregen and replayed exactly thereafter.
* **T3b (web search open)** — LLM-as-judge. Judge `model_id` and `seed`
  are recorded as provenance. We do not guarantee the external judge service
  can be re-run bit-identically; the cached score is what the experiment
  uses.

A bandit loop never re-scores. If `Evaluator.lookup` fails to find a
record, that is a bug, not a fallback condition.

## Immutability

Once a `(task_id, provider_id, version)` triple has a record on disk:

* `response`, `cost_usdc`, `latency_s`, `failure_flag`, `failure_code`,
  and `quality_score` MUST NOT be edited in place. Re-running pregen for
  that triple is the only legal change, and it produces a *new* record;
  the old one is overwritten only as a unit.
* `generated_at` is provenance and may differ between regenerations of the
  same triple — that is the intended signal that the record was rewritten.
* `schema_version` MUST be bumped if any field above is renamed, removed,
  or has its semantics changed. Old records carry the old version number.

## Versions per (task, provider)

The default is 5 versions (`version ∈ {0,1,2,3,4}`) per `(task_id, provider_id)`.
This gives the env enough variability to model provider stochasticity without
exploding the pregen call count. The runtime `PregenStore.get(task, provider, v)`
draws a specific version; `PregenStore.versions(task, provider)` enumerates.

## File naming

`data/pregen/{provider_id}__{task_type}.jsonl` — double underscore separator.
One JSONL line per record. Files are append-only during pregen and read-only
thereafter.

## Sampling temperature

All pregen calls use `temperature = 0.3` (defined in
`pilot402.pregen.providers.base.DEFAULT_TEMPERATURE`). This trades a small
loss in coding pass@1 (Qwen3-8B on HumanEval drops from ~0.80 at T=0 to
~0.75 at T=0.3) for genuine sampling diversity across the 5 versions per
`(task, provider)` pair. At T=0 the API ignores the seed and returns
identical responses for all 5 versions, defeating the purpose of
`version_count`. T=0.3 is on the conservative side of the
HumanEval-paper precedent (T=0.2 for pass@1, T=0.6 for pass@k).

The temperature is recorded per-record so a future ablation that runs at
a different temperature stays distinguishable in mixed datasets.

## Schema version 2 changes (2026-04-30)

* Added `temperature` field. Default 0.0 lets v1 records load through
  pydantic without an explicit migration step; new records always
  populate `temperature` explicitly with the value the provider used.
* `schema_version` default bumped to 2.

## Migration policy

When `schema_version` is bumped:

1. Document the change in this file and add a `## Migration: v1 → v2`
   section describing field-level differences.
2. Provide a one-shot script in `scripts/migrate_pregen_v{N}_to_v{N+1}.py`
   that rewrites old JSONL files to the new schema.
3. Do not silently support both schemas in `PregenStore`; reject reads of
   old-version records and require migration first.

---

# Task source layer (`data/tasks/`)

Separate from `data/pregen/` is `data/tasks/`, the pre-LLM intermediate
produced by `scripts/prepare_tasks.py` from the four public sources
(HumanEval / HotpotQA / TriviaQA-web / OpenAssistant). One file per source:

```
data/tasks/
├── humaneval.jsonl    (165 tasks)
├── hotpotqa.jsonl     (220 tasks)
├── triviaqa.jsonl     (220 tasks)
└── openweb.jsonl      (220 tasks)
```

Each line is a `Task` (`pilot402.core.types.Task`) — small enough that all
four files together fit in well under 5 MB. **They are committed to git**
so reviewers can run pregen without re-downloading the large parquet
sources from HuggingFace.

## Loader format version

Per-source loader-format version is recorded in `Task.metadata` under the
key `loader_format_version`. When a loader's output format changes
(e.g. adding context to the prompt), bump the constant
`<Loader>.LOADER_FORMAT_VERSION` and update every Task it writes. The
`is_cache_stale` helper auto-detects caches written by older versions and
forces a rebuild on the next `load`. To wipe caches manually:

```
python -m scripts.prepare_tasks --force --sources hotpotqa
```

## T2 (HotpotQA) — reading-comprehension setting

HotpotQA's intended use is reading comprehension over 10 supplied
paragraphs, not closed-book recall. Loader version 2 (since 2026-04-30)
formats the 10 paragraphs into the `Task.prompt`:

```
Read the following passages and answer the question that follows.

[1] {title_1}
{paragraph_1}

[2] {title_2}
{paragraph_2}

... (10 total)

Question: {question}
```

`Task.metadata` carries:

* `loader_format_version`: 2
* `level`: `easy` / `medium` / `hard` (from the source dataset).
* `type`: `comparison` / `bridge` (from the source dataset).
* `supporting_titles`, `supporting_sent_ids`: which sentences in which
  paragraphs are gold supporting facts. **Logged for analysis only**;
  never shown to the model — that would leak the answer chain.
* `question_only`: the bare question, useful for downstream display.

Loader v1 (closed-book; question only, no context) is no longer supported.
Caches written by v1 are detected as stale by `is_cache_stale` and
rebuilt automatically; no manual migration is needed.
