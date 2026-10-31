# Evaluation Artifact Index (Observed Runs)

Purpose: one-page map of what exists today, with commands and artifact paths.
This index is for reporting observed results only.

Last verified run (UTC)
- 2026-01-21T10:01:49Z
- Updated: storage/observability/conversation_memory_eval_live.json
- Updated: storage/observability/memory_shadow_eval_live.json
- New report: artifacts/observability/fractal_eval_report_live_probes_20260121_075956.md

Where artifacts live
- storage/observability/ : live JSONL logs and rolling windows
- artifacts/observability/ : curated JSON reports and markdown summaries
- docs/proof/ : evidence reports and replication checklists

Publish snapshot (frozen)
- docs/proof/publish_snapshot.md
- artifacts/publish/2026-01-21/

Memory and continuity evals
- Conversation memory eval
  - Command: python scripts/conversation_memory_eval.py --live --dataset fram_eval/data/conversation_memory_live_probes.jsonl
  - Outputs: storage/observability/conversation_memory_eval_live.json and artifacts/observability/conversation_memory_eval_*.json
  - Measures: top1/topk hit rate, rank deltas, low-lex gate flags (add --details for per-probe output)
- Memory shadow eval
  - Command: python scripts/memory_shadow_eval.py --live
  - Outputs: storage/observability/memory_shadow_eval_live.json and artifacts/observability/memory_shadow_eval_*.json
  - Measures: embedding shift deltas after memory injection

Fractal trace evals
- Fractal eval report
  - Command: python scripts/run_fractal_eval_report.py --live --dataset fram_eval/data/conversation_memory_live_probes.jsonl --label live_probes
  - Outputs: artifacts/observability/fractal_eval_report_*.md and artifacts/observability/fractal_eval_report_*.json
  - Measures: top1/topk comparisons across semantic, lexical, and fractal; auto-flip recommendation
- Fractal falsification
  - Command: python scripts/fractal_falsification.py
  - Outputs: storage/observability/fractal_falsification.json and artifacts/observability/fractal_falsification_*.json
  - Measures: correlation and top-k consistency on synthetic systems

Fractal Influence Status (current head)
- Policy: OFF by default; traces can be generated, influence stays gated unless explicitly enabled.
- Gates: `FRAM_FRACTAL_ENABLED=1` (trace generation), `FRAM_FRACTAL_INFLUENCE=1` (ranking influence), `FRAM_FRACTAL_INFLUENCE_ALPHA` (weight), `FRAM_FRACTAL_QUAT_INFLUENCE=1` + `FRAM_FRACTAL_QUAT_WEIGHT` (optional).
- Latest evidence (KEEP_OFF): `artifacts/observability/fractal_autoflip_live_probes_20260121_075956.json`, `artifacts/observability/memory_shadow_eval_live_probes_20260121_075956.json`, `artifacts/observability/fractal_eval_report_live_probes_20260121_075956.md`.

Capsules (write-through evidence)
- Capsule inspector
  - Command: python tools/inspect_capsule.py storage/memory/capsules/<capsule>.json
  - Outputs: console summary and capsule JSON in storage/memory/capsules/
- Capsule falsification
  - Command: python tools/falsify_capsule.py storage/memory/capsules/<capsule>.json --json
  - Outputs: artifacts/observability/capsule_falsify_*.json
  - Evidence: docs/proof/memory_capsule_evidence_report.md

Calibration artifacts
- Harvest: python scripts/harvest_calibration.py --queries scripts/calibration_prompts/layout_anchor_queries.txt --quiet --json-out storage/observability/harvest_run.json
- Fit: python scripts/calibrate_confidence.py --log storage/observability/calibration.jsonl --out storage/index/demo_corpus/calibration.json --lint
- Outputs: storage/observability/calibration.jsonl, storage/index/demo_corpus/calibration*.json
- Summary: docs/WHAT_WORKS.md

Trace and observability logs
- Trace JSONL: storage/traces/trace_*.jsonl (via TraceLogWriter)
- Memory logs: storage/observability/memory_cognitive.jsonl and storage/observability/memory_fractal.jsonl
- Summary: python tools/trace_summary.py --storage-root storage --limit 50

Known limits (explicit non-claims)
- The 2026-01-21 conversation-memory eval's top1=0.000 result across all modes is explained, not mysterious: cognitive memory search applies a recency-decay half-life (now configurable via `FRAM_COGNITIVE_MEMORY_HALF_LIFE_HOURS`, default 12h, previously silently unconfigurable) that ages out any fixed benchmark's target episodes over weeks. See `docs/observability_2026-07-22-eval-anomaly.md` before re-running or trusting this eval's absolute numbers against an aging probe set.
- Memory capsule retrieval is implemented and wired into `/query`, but it is config-gated and still being tuned/validated (`FRAM_MEMORY_CAPSULE_RETRIEVAL_ENABLED`, `..._K`, `..._TURNS_PER_CAPSULE`, `..._HALF_LIFE_HOURS`).
- Fractal influence is gated by config and remains OFF by default.
- Layout chunkers + version lattice have a minimal correctness pass (ordering, table headers, as-of selection + trace visibility) but remain light stubs vs. full spec (no Hilbert ordering, no DAG diffs, no delta snippets).
- Sparse key index remains minimal (no Aho-Corasick); checksum validation + posting caps now exist, but matching is still simple.
