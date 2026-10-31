# FRAM v2.2 - Docs Index (Canonical)

This index reduces hops and keeps sessions consistent. Start from the compact
current-state packet, then expand only into the authority-bearing source needed
for the question.

- Start Here
  - `docs/context/HOT_CONTEXT.md` - current commit, invariants, active lanes, gates, and blind edges (kept below 8 KiB)
  - `docs/context/ATLAS_INDEX.md` - question-to-source map and authority ladder
  - `docs/context/DECISIONS.md` - append-only decisions; load only active/task-relevant IDs
  - `docs/context/HANDOFF_TEMPLATE.md` - CLAIM/CHECKPOINT/HANDOFF transition packet
  - `docs/FIRELINK_CLOSEOUT_2026-07-27.md` - assembled-lineage closeout and safety boundary
  - `docs/Architecture.md` - file map and responsibilities
  - `docs/CONTINUITY_WITNESS_AND_ECOLOGICAL_STRATA.md` - non-authoritative query witness and explicit consent-led relationship ledger
  - `docs/lived_memory.md` - transactional lived-event storage, fractal projection, recall, verification, and ZIP import
  - `docs/Codebase_Review.md` - planned code review and spec comparison map
  - `docs/FRAMv2.2-cheatsheet.md` - working summary (calibration, thresholds, knobs)
  - `docs/F-RAM-roadmap.md` - long-term plan and current baseline
  - `docs/CODEX_DIARY.md` - latest session notes (all entries consolidated here)
  - `docs/Operations.md` - runbook (server, calibration refresh, tests, closeout)
  - `docs/FRAM_MCP_Guide.md` - MCP usage guide (safe context gateway)
  - `docs/FRAM_PIL.md` - Pre-Intent Layer (PIL) posture spec stub

- Full Spec
  - `docs/FRAMv2.2-SPEC.md` - target blueprint; when spec and code diverge, code is source of truth (note deltas in summaries)

- Evidence & Proof Packs
  - `docs/proof/memory_capsule_evidence_report.md` - external-ready capsule capture + falsification report
  - `docs/proof/memory_capsule_replication_checklist.md` - third-party replication checklist for capsule capture + falsify
  - `docs/proof/fractal_core_proof.md` - fractal trace proof packet (coord6/q/lambda)
  - `docs/proof/eval_artifact_index.md` - one-page index of eval artifacts and outputs
  - `docs/proof/eval_season_cheatsheet.md` - one-page eval story + where evidence lives
  - `docs/proof/tool_surface_eval_matrix.md` - tool surface eval matrix (skills, MCP, app-server readiness)
  - `docs/proof/tool_surface_evidence_anchor.md` - publish-safe commit + test anchor
  - `docs/proof/hopf_aizawa_bridge.md` - proof boundary and experiment gates
  - `docs/CHAOS_PLAYGROUND_RECONSTRUCTION.md` - recovered visual contract, simulator APIs, and acceptance gates

- Serving & Config
  - `fram_serving/app.py` - FastAPI surface (`/ui/memory`, `/ui/observability`, `/ui/experiments`, `/query`, `/memory`, `/observability/*`, `/metrics`, `/time`, `/where`, `/label`, `/calibration`, `/config`)
  - `GET /ui/observability` - quick in-browser observability view (metrics, traces, memory, recall)
  - `GET /ui/experiments` - experiment + decision review UI with filters and digest preview
  - `fram_serving/config.py` - `FRAMConfig` defaults and env overrides
  - `docs/FRAMv2.2-tuning.md` - operator tuning map (budgets, memory dials, fractal flags)
  - Dev run
    - macOS/Linux: `scripts/dev_run.sh`
    - Windows (PowerShell): `scripts/dev_run.ps1`
    - Windows defaults to loopback, isolated runtime storage, no dev profile, and no cognitive autolog. Pass `-EnableDevProfile` or `-EnableAutolog` explicitly when required.
    - Optional: set `FRAM_DEV_PROFILE=1` to enable the tuned demo profile (also turns on fractal traces; `0`, `false`, `no`, and `off` remain disabled).

- Calibration artifacts (persisted beside the corpus)
  - Global: `storage/index/demo_corpus/calibration.json`
  - Domain: `storage/index/demo_corpus/calibration_<domain>.json`
  - Task: `storage/index/demo_corpus/calibration_task_<task>.json`
  - Precedence: task → domain → global → defaults (see `/calibration`)

- Ingestion & Corpus
  - `scripts/ingest_project_docs.py` renders `docs/*.md` into `examples/data/docs_ingest_*.txt`
  - `scripts/ingest_demo.py` builds the persisted corpus under `storage/index/demo_corpus/`
  - Legacy redirect placeholders (files starting with "# This file moved") are skipped during ingest.

Workflow reminders
- At session start, run `python tools/check_context_packet.py`, read
  `docs/context/HOT_CONTEXT.md`, then consume only Firelink events newer than
  its anchor.
- Checker exit 1 (`FAIL`) blocks writes. Exit 2 (`REVIEW_REQUIRED`) requires
  review of watched post-packet changes plus a lead refresh or acknowledgment.
- Open only active decision IDs/sections named by the hot packet or routed by
  the task; the append-only decision ledger is not a bounded bootstrap file.
- Firelink is append-only provenance; the lead alone refreshes the replaceable
  hot packet after a head, claim, gate, or user-direction change.
- After editing docs, re-run `python scripts/ingest_project_docs.py` then `python scripts/ingest_demo.py`
- Shortcut: `make refresh-docs` (lists recent docs, rebuilds doc ingest + demo corpus, lints calibration payloads)
- Shortcut: `make refresh-calibration` (harvest -> backfill -> slice -> fit -> lint -> status for calibration payloads)
- At session start, run `python tools/list_recent_docs.py --hours 48` to see which docs changed
- Hydrate cognitive memory with `python tools/bootstrap_memory.py --window 5`
- Audit cognitive memory usage with `python tools/cognitive_memory_summary.py`
- Via MCP, call `fram.memory_bootstrap` to hydrate/inspect episodes
- Shortcut: `python tools/session_warmup.py --json` to combine doc scan + cognitive snapshot
- Use `GET /calibration` and `/metrics` to verify payloads and live reliability
- Slow tests are intentionally heavy; expect ~1h for `pytest -m slow --durations=20`.
- Keep changes small; when behavior shifts, update cheatsheet + Architecture

