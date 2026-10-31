# Phase C - Calibration Report

_Generated: 2025-11-27T10:12:02.093589Z_

## Macro Metrics
- Precision: **0.3333**
- Recall: **0.4167**
- F1: **0.3667**

## Fractal Recall Metrics
- Precision: **0.5556**
- Recall: **0.3889**
- F1: **0.4445**

## Worst 10 by F1

| id | P | R | F1 | exp | ret | F_P | F_R | F1_F |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| t3 | 0.0 | 0.0 | 0.0 | 1 | 0 | 0.0 | 0.0 | 0.0 |
| t4 | 0.0 | 0.0 | 0.0 | 0 | 1 | - | - | - |
| t1 | 0.6667 | 0.6667 | 0.6667 | 3 | 3 | 0.6667 | 0.6667 | 0.6667 |
| t2 | 0.6667 | 1.0 | 0.8 | 2 | 3 | 1.0 | 0.5 | 0.6667 |

## Addenda (2025-12-01)
- Version lattice manifest now persists to `storage/index/<corpus>/versions.jsonl` (mirrored to `lattice.json`) with `version_id`, `parent_id`, `timestamp`, `diff`; ingest stamps `version_id` on all shard sources (docs/FRAMv2.2-SPEC.md §13, Architecture.md).
- As-of(T) enforcement filters shortlist/coverage/replay/memory/connector candidates via `active_with_ancestors(as_of)`; traces include `as_of_filter` {as_of, active_nodes, dropped_candidates} and responses carry `delta_snippets` when serving older snapshots.
- Observability surfaces (HTML + JSON) now expose the as-of block and delta snippets so dashboards can confirm active nodes and dropped counts alongside calibration/phase D sections (docs/observability_dashboard.md).

