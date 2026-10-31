# Postmortem: 2026-01-21 conversation-memory eval top1=0.000 collapse

Status: root-caused and fixed 2026-07-22, after a ~5-month gap in active
work. This was the single open, unexplained anomaly flagged when picking
this project back up (see `docs/RECONSTRUCTION_2026-07-21.md` section 7).

## The anomaly

`artifacts/observability/fractal_eval_report_live_probes_20260121_075956.md`
(run 2026-01-21T08:01:43Z) reported **conversation top1 accuracy of exactly
0.000 for all three retrieval modes** (semantic, lexical, fractal), across
both the 36 standard live probes and the 36 low-lexical-overlap probes.
Every single probe missed, in every mode, including the plain lexical
baseline - which should not go to exactly zero by chance on a real probe
set. This looked like a bug, not a genuine capability failure, and was
flagged as the cheapest, most concrete open thread from the last active
session.

## Root cause

`fram_serving/memory.py`'s `CognitiveMemoryStore.search()` multiplies every
candidate's relevance score by a recency-decay weight
(`_recency_weight`, `memory.py:1683-1692`) with a **12-hour half-life**.
That half-life was already being read via
`getattr(self._config, "cognitive_memory_half_life_hours", 12.0)` - but
**no matching `FRAMConfig` field ever existed**, so this call always,
silently, unconditionally resolved to the `12.0` fallback. There was no env
var, no config knob, nothing to change it - unlike essentially every other
tunable in this codebase.

`fram_eval/data/conversation_memory_live_probes.jsonl` is a **fixed
benchmark**: 36 probes pinned to specific episodes logged into the live
cognitive-memory store between 2025-10-20 and 2025-12-26. The live store
keeps accumulating fresh episodes from ordinary activity; none of the 36
target episodes get their `last_seen` touched again after being logged. As
real time passes, their contribution to the ranking score decays under the
12-hour half-life, while every newer episode's weight stays near 1.0. By
2026-01-21, the target episodes were 26-93 days old - decayed enough that
essentially any fresher, barely-relevant episode outscored them, in every
mode (fractal only re-ranks the same top-k pool semantic search already
produced, so it inherits semantic's collapse rather than rescuing it).

This was gradual, not sudden: the same eval on 2025-12-28 (targets 2-70
days old at the time) scored 0.25-0.36 top1; by 2026-01-21 the aging
crossed the tipping point. Nothing in the retrieval code changed between
those two dates - confirmed via `git log` on the eval harness, the probe
dataset, and `fram_serving/memory.py` (the `_recency_weight` code has been
unchanged since 2025-10-17).

## What was ruled out

- Probes referencing episode ids never seeded into the store - disproved:
  the raw JSON artifact shows `matched_by_id: 36/36, missing: 0`.
- A scoring bug that always returns zero - disproved: real, nonzero,
  differentiated scores were computed; they just consistently favored
  freshness over the benchmark's intended relevance match.
- Schema/version incompatibility between probes and store - disproved: all
  fields parsed cleanly, no errors.
- A code regression landing around 2026-01-21 - disproved: the relevant
  scoring code and the eval harness/dataset were both last touched well
  before that date.

## The fix

Added `FRAMConfig.cognitive_memory_half_life_hours: float = 12.0`
(env `FRAM_COGNITIVE_MEMORY_HALF_LIFE_HOURS`) so the value `memory.py` was
already trying to read actually exists and can be set. **Default is
unchanged (`12.0`)** - this closes a silent-gap-in-configurability, it does
not change any existing deployment's behavior by itself.

`tests/test_cognitive_memory_store.py::test_cognitive_memory_half_life_hours_reproduces_and_fixes_eval_anomaly`
reproduces the exact mechanism: an old-but-highly-relevant episode
(backdated 90 days, matching the probes' real age at collapse) loses to a
fresh-but-barely-relevant one under the default 12-hour half-life, and wins
once a realistic multi-year half-life is configured - proving the field is
genuinely read, not just accepted and ignored.

## What this does not fix

- It does not change today's default behavior. Anyone who wants the
  conversation-memory eval to keep scoring meaningfully against a
  long-lived, fixed probe set needs to **explicitly** set
  `FRAM_COGNITIVE_MEMORY_HALF_LIFE_HOURS` to something much larger than
  12 hours before running it (or accept that the benchmark measures
  "recency-weighted recall," not raw relevance, and will keep drifting
  toward zero as its target episodes age).
- It does not repair or refresh the existing 2026-01-21 artifact - that
  run's 0.000 result stands as correctly-recorded evidence of this
  mechanism, not a run to be re-executed and overwritten.
- It does not address whether 12 hours is the *right* production default
  for real (non-benchmark) usage - that's a separate product decision this
  postmortem takes no position on.

## Recommendation for future eval runs

Before running `scripts/conversation_memory_eval.py --live` or
`scripts/run_fractal_eval_report.py --live` against
`fram_eval/data/conversation_memory_live_probes.jsonl` (or any other fixed,
aging probe set), either:

1. Set `FRAM_COGNITIVE_MEMORY_HALF_LIFE_HOURS` to a value long enough that
   the probe set's target episodes won't have meaningfully decayed by the
   time the eval runs, or
2. Refresh the probe set periodically so its target episodes stay recent
   relative to whatever half-life is actually configured for production,
   or
3. Treat a collapsing top1 score over time as expected/diagnostic
   (evidence of decay working as designed) rather than a capability
   regression, and track "recency-adjusted top1" separately from raw
   relevance if the two need to be told apart going forward.
