# Phase F — Calibration, Stability & Maintenance Boundaries

Phase F does not change runtime behaviour. It tightens definitions, invariants, and tooling for the retention/decay/forgetting skeleton delivered in Phase E. All knobs stay gated off by default; tools and observability are read‑only.

## Knobs (as implemented)
- `enable_retention_curve` (bool, default `False`): when `True`, apply an exponential retention multiplier based on `retention_half_life_days`.
- `retention_half_life_days` (float, default `30.0`): half‑life for retention. Younger items stay near `1.0`; each half‑life halves the retention score.
- `enable_decay` (bool, default `False`): when `True`, apply a decay multiplier based on `forgetting_half_life_days`.
- `forgetting_half_life_days` (float, default `30.0`): half‑life for decay. Uses the same exponential form as retention; clamps to `[0.1, 1.0]`.
- `enable_hard_forgetting` (bool, default `False`): when `True`, evaluate hard forgetting decisions.
- `hard_forgetting_mode` (`"dry_run"`|`"enforce"`, default `"dry_run"`): dry run records decisions; enforce would drop items (Phase F keeps storage untouched).
- `forgetting_threshold` (float, default `0.05`): keep floor. `forget_score >= threshold` ⇒ KEEP; lower scores are candidates to forget. Because `forget_score` is a “keep” score, raising this threshold makes forgetting stricter (forgotten count is non‑decreasing as the threshold rises).
- `min_active_items` (int, default `100`): floor on active items. If `active_count <= min_active_items`, everything is kept.

Scales & units:
- `base_score` and `forgetting_threshold` are on the same scale as the pipeline’s `forget_score`, which is the post‑retention/post‑decay score used in `forgetting.py`.
- Age is defined as `now - last_seen` in **days**; both half‑life knobs use the same unit.
- Combination order follows the codepath: start from `base_score` → apply retention (if enabled) → apply decay (if enabled) → compare `forget_score` to `forgetting_threshold` (if hard forgetting is enabled).

## Phase F invariants (aligned to current code)
- Increasing `forgetting_threshold` cannot decrease the number of `FORGET_ENFORCE` decisions for a fixed dataset; it is a stricter keep floor.
- Increasing `min_active_items` cannot increase the number of `FORGET_ENFORCE` decisions (the floor only keeps more items).
- With gates OFF, decisions remain `KEEP` and scores remain unchanged.
- Very recent items with high base scores remain `KEEP` under defaults.
- Extremely old, low‑score items become `FORGET_*` when all gates are ON and `hard_forgetting_mode="enforce"`, provided `active_count > min_active_items`.

## Maintenance boundaries
- Phase F never mutates JSONL storage or the cognitive store. Calibration, replay, and observability are read‑only.
- Phase F does not compact, archive, or rewrite memory files.
- Phase F defines which items would be pruned and surfaces metrics; physical archival/compaction is deferred to a future lane (G).

## Tooling (Phase F)
- `tools/phase_f_calibrate.py`: synthetic sweep over `(age_days, base_score)` grid using the Phase E math; prints a table and optional JSON with `decision_counts` for `dry_run` and `enforce`.
- `tools/phase_f_replay.py`: non‑destructive replay over a JSONL log or synthetic entries to summarise lifecycle behaviour (counts, age buckets, floors respected).
- Observability: lifecycle summary (JSON + HTML) is shown only when lifecycle gates are ON and draws from the same data used in the CLI tools.

Completion criteria:
- Calibration + replay tools run and show the expected monotonic relations.
- Observability lifecycle summary matches the CLI shape/counts.
- This plan stays consistent with the implemented order (retain → decay → threshold) and units (days).
