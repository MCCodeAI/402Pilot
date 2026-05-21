# Frozen Replay Artifact

This directory contains the frozen pre-generated records used by
402Pilot-Bench. The benchmark replays these records under paired seeds so that
policy comparisons are not affected by live API drift.

## Contents

- `P-{provider}__T{task_type}.jsonl`: provider responses and cached scores for
  each provider/task-type cell.
- `judge_cache.jsonl`: cached judge scores for open-ended QA records.

The committed snapshot contains 20,575 provider-response records:

- 5 providers
- 823 effective tasks
- 5 response versions per task-provider pair

Each response record includes task id, task type, provider id, response version,
response text, realized cost, latency, failure flag, cached quality score, judge
metadata when applicable, timestamp, and generation temperature.

## Reproducibility Scope

These files are the replay substrate for the benchmark experiments. They let a
reader rerun policy sweeps and metric computation without paying for fresh LLM
generation or re-running the open-ended QA judge.

The records intentionally contain generated model responses. They do not contain
API keys or wallet secrets.
