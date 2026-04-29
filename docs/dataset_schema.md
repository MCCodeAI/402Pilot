# 402Pilot-Bench Dataset Schema

This document is the canonical specification of the pre-generated dataset
consumed by `pilot402/env/` and `pilot402/eval/` during experiments.

The dataset is produced once in Phase 1 by `pilot402/pregen/` (driving
~20,625 real LLM API calls: 5 providers × 825 tasks × 5 versions) and is
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

## Migration policy

When `schema_version` is bumped:

1. Document the change in this file and add a `## Migration: v1 → v2`
   section describing field-level differences.
2. Provide a one-shot script in `scripts/migrate_pregen_v{N}_to_v{N+1}.py`
   that rewrites old JSONL files to the new schema.
3. Do not silently support both schemas in `PregenStore`; reject reads of
   old-version records and require migration first.
