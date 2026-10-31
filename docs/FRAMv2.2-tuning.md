# F-RAM v2.2 Tuning Map (Operator Notes)

This is a living, practical map of the main dials that affect memory recall, budgets, and fractal replay. Defaults are conservative. Adjust one knob at a time and use the observability logs to verify the impact before changing more.

Spec refs: docs/FRAMv2.2-SPEC.md Section 11 (budgets + coverage), Section 12 (memory behavior).

## Dial status (tuned vs untuned)

Status key:
- tuned: validated with recent eval artifacts
- baseline: default value, not tuned yet
- gated: keep off until auto-flip says enable

| Dial | Default | Status | Notes |
| --- | --- | --- | --- |
| default_query_reads | 5 | baseline | Raise if reads feel constrained. |
| cognitive_memory_k | 12 | baseline | Candidate pool before token packing. |
| cognitive_memory_token_budget | 0 (unlimited) | baseline | Only cap if memory crowding is real. |
| cognitive_memory_slot_budget | 0 (unlimited) | baseline | Decouples memory slots from read budget. |
| working_memory_dedupe_window_sec | 2 | baseline | Ignore duplicate appends in a short window (set 0 to disable). |
| fractal_influence_enabled | False | gated | Enable only when auto-flip says yes. |
| fractal_influence_alpha | 0.05 | baseline | Strength of the influence blend. |
| fractal_blend_alpha | 0.4 | baseline | Cosine vs soft-DTW blend. |
| fractal_downsample_target | 256 | baseline | Trace downsampling target. |
| fractal_quat_influence | False | gated | Enable only when auto-flip says yes. |
| fractal_quat_weight | 0.2 | baseline | Quaternion alignment weight. |
| fractal_quat_use_lambda | True | baseline | Lambda-weighted alignment when enabled. |

## Core budgets and slots

- `default_query_reads` (env: `FRAM_DEFAULT_QUERY_READS`, default 5)
  - Total read budget for each query.
  - Memory slots are reserved first unless `cognitive_memory_slot_budget` is set.
  - If this is low, retrieval can be constrained even when memory is strong.
- `headroom` (config-only, default 0.15)
  - Reserve a slice of the budget for widening/backoffs.
- `lambda_tok` / `lambda_rerank` (env: `FRAM_LAMBDA_TOK`, `FRAM_LAMBDA_RERANK`)
  - Increase to make token/pair costs bite harder; decrease to prioritize recall.

## Cognitive memory retrieval

- `cognitive_memory_k` (env: `FRAM_COGNITIVE_MEMORY_K`, default 12)
  - How many candidates the cognitive store returns before token packing.
- `cognitive_memory_token_budget` (env: `FRAM_COGNITIVE_MEMORY_TOKEN_BUDGET`, default 0)
  - Token cap for admitted cognitive entries; `0` means unlimited (breathing mode).
  - If you see `selected_dropped` in `memory_cognitive.jsonl` under a positive cap, raise this.
- `cognitive_memory_slot_budget` (env: `FRAM_COGNITIVE_MEMORY_SLOT_BUDGET`, default 0)
  - Cap on admitted memory entries; `0` means unlimited slots (memory is no longer bound to `default_query_reads`).
- `cognitive_memory_trace_k` (env: `FRAM_COGNITIVE_MEMORY_TRACE_K`, default 3)
  - How many fractal traces to score for memory replay hooks.
- `session_memory_k` (config-only, default 2)
  - How many selected chunks are cached for replay in the next call.
- `cognitive_memory_embedding_backend` (env: `FRAM_COGNITIVE_MEMORY_EMBEDDING_BACKEND`)
  - `hashing` is the default; keep ingestion and query aligned.
- `cognitive_memory_semantic_model` (env: `FRAM_COGNITIVE_MEMORY_SEMANTIC_MODEL`, default `all-MiniLM-L6-v2`)
  - Used when `cognitive_memory_embedding_backend=semantic` (requires `sentence-transformers`).
- `cognitive_memory_query_recall_weight` (env: `FRAM_COGNITIVE_MEMORY_QUERY_RECALL_WEIGHT`, default 0.2)
  - Blend factor for query-only token recall when ranking episodes; raises short-query matches without retraining.
- `cognitive_memory_half_life_hours` (env: `FRAM_COGNITIVE_MEMORY_HALF_LIFE_HOURS`, default 12.0)
  - Recency-decay half-life applied to every candidate's score during search; lower values favor freshness more aggressively, higher values let older-but-relevant episodes compete longer.
  - Raise this substantially before benchmarking against a fixed, long-lived probe set - see `docs/observability_2026-07-22-eval-anomaly.md` for why the default silently zeroed out a 2026-01-21 eval run.
- `negative_cue_cooldown_minutes` (config-only, default 10)
  - How long dismissed memory entries stay suppressed.

## Fractal memory and replay

- `fractal_enabled` (env: `FRAM_FRACTAL_ENABLED`, default off)
  - Generates deterministic fractal traces for episodes.
- Trace storage is backend-specific (hashing -> `storage/memory/fractal`, semantic -> `storage/memory/fractal_semantic`).
- `fractal_influence_enabled` (env: `FRAM_FRACTAL_INFLUENCE`, default off)
  - Blends fractal scores into cognitive ranking (alpha-weighted).
- `fractal_influence_alpha` (env: `FRAM_FRACTAL_INFLUENCE_ALPHA`, default 0.05)
  - Strength of the cognitive ranking influence.
- `fractal_blend_alpha` / `fractal_downsample_target`
  - Env: `FRAM_FRACTAL_BLEND_ALPHA`, `FRAM_FRACTAL_DOWNSAMPLE_TARGET`.
- Quaternion alignment (keep OFF until falsification shows signal):
  - `fractal_quat_influence` (env: `FRAM_FRACTAL_QUAT_INFLUENCE`)
  - `fractal_quat_weight` (env: `FRAM_FRACTAL_QUAT_WEIGHT`)
  - `fractal_quat_use_lambda` (env: `FRAM_FRACTAL_QUAT_USE_LAMBDA`)
- Auto-flip guardrail defaults (see `scripts/fractal_autoflip.py`):
  - Require top1 lift >= 0.02 on both `probe` and `probe_low_lex`.
  - Allow shadow avg_delta to be up to 0.01 below baseline (margin -0.01).

## Optional ANN bridge (cognitive memory)

- `enable_cognitive_ann_bridge` (env: `FRAM_ENABLE_COGNITIVE_ANN_BRIDGE`, default on)
  - Adds an ANN-based shortlist to the cognitive recall.
- `cognitive_ann_top_k` (env: `FRAM_COGNITIVE_ANN_TOP_K`, default 8)
- `cognitive_ann_weight` (env: `FRAM_COGNITIVE_ANN_WEIGHT`, default 1.0)
- `cognitive_ann_floor_boost` (env: `FRAM_COGNITIVE_ANN_FLOOR_BOOST`, default 0.01)
- ANN backend follows `FRAM_ANN_BACKEND` (sklearn default; FAISS when available). Search telemetry lands in `storage/observability/memory_search.json`.

## Retention / decay / forgetting (disabled under full-experience preservation)

F-RAM now preserves full experience by default. When `preserve_full_experience` is enabled,
retention/decay/forgetting knobs are forced off and should not be used to prune memory.

If preservation is explicitly disabled (not recommended for production), the following flags
may be used with care. To override, set `FRAM_PRESERVE_FULL_EXPERIENCE=0`.

- `enable_retention_curve` (env: `FRAM_ENABLE_RETENTION_CURVE`, default off)
  - `retention_half_life_days` (env: `FRAM_RETENTION_HALF_LIFE_DAYS`, default 30)
- `enable_decay` (env: `FRAM_ENABLE_DECAY`, default off)
  - `forgetting_half_life_days` (env: `FRAM_FORGETTING_HALF_LIFE_DAYS`, default 30)
- `enable_hard_forgetting` (env: `FRAM_ENABLE_HARD_FORGETTING`, default off)
  - `forgetting_threshold` (env: `FRAM_FORGETTING_THRESHOLD`, default 0.05)
  - `hard_forgetting_mode` (env: `FRAM_HARD_FORGETTING_MODE`, default `dry_run`)
  - `min_active_items` (env: `FRAM_MIN_ACTIVE_ITEMS`, default 0)

## Domain/task overrides and time sensitivity

- `domain_overrides` / `task_overrides` adjust `tau1`, `tau2`, and budget parameters per domain/task.
- `time_sensitivity_task` / `time_sensitivity_domain` set recency weighting expectations.
- `tau_domain_days` controls freshness decay across domains.

## Observability check loop

1. Run a few `/query` calls with the changes.
2. Inspect `storage/observability/memory_cognitive.jsonl` and `storage/observability/memory_fractal.jsonl`.
3. Use `python tools/cognitive_memory_summary.py` for aggregate drops and budget pressure.
4. Keep `FRAM_FRACTAL_QUAT_INFLUENCE=0` until the falsification harness shows signal.
5. When switching to `cognitive_memory_embedding_backend=semantic`, run
   `python tools/backfill_cognitive_embeddings.py` once to populate vectors for existing episodes.

## First tuning pass (safe defaults)

- Raise `FRAM_DEFAULT_QUERY_READS` and (if capped) `FRAM_COGNITIVE_MEMORY_TOKEN_BUDGET` modestly.
- Watch `selected_dropped` and `token_budget` in the cognitive trace.
- Only then increase `cognitive_memory_k` or tune the ANN bridge weights.

## Current default profile (memory-focused)

These settings are now the global defaults (and are also applied by `FRAM_DEV_PROFILE=1`):

- `FRAM_DEFAULT_QUERY_READS=5` (retrieval read budget)
- `FRAM_COGNITIVE_MEMORY_TOKEN_BUDGET=0` (unlimited)
- `FRAM_COGNITIVE_MEMORY_SLOT_BUDGET=0` (unlimited)
- `FRAM_COGNITIVE_MEMORY_K=12`
