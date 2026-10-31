# Architecture Map (Files & Responsibilities)



See also: `docs/README.md` for the canonical docs set and reading order.

- `fram_eval/production_memory_eval.py` and `scripts/production_memory_eval.py` -
  Offline actual `run_query` cognitive-selection capture, fixed-clock paired
  comparisons, verified disjoint shards and complete-scope activation checks.
  See [production memory gate](production_memory_gate.md) for its bounded claim,
  source-preservation contract and explicit profile/observation controls.



This map keeps future operators oriented on the FRAM v2.2 stack after the 2025-10-16 audit session.



- `fram_serving/app.py` - FastAPI surface (`/ui/memory`, `/ui/observability`, `/ui/experiments`, `/query`, `/memory` create/control/append/dismiss/search, `/memory/lived/*`, `/memory/constraint`, `/observability/*`, `/metrics`, `/time`, `/where`, `/label`, `/calibration`, `/health`, `/config`) plus the MCP mount. It warms the shared `QueryOrchestrator` cache on startup, persists traces under `storage/`, writes cognitive and lived-memory events, streams blended fractal scores/replay blocks into `/query`, exposes lived-memory status/search/session/integrity surfaces, `/memory/fractal_trace`, `/observability/memory/fractal/ping`, and the feature-gated read-only `/observability/continuity/witness`, omits secret-bearing fields from `/config`, and ships with cognitive seeding on by default (`default_query_reads=5`, `cognitive_memory_k=12`, `cognitive_memory_token_budget=0`, `cognitive_memory_slot_budget=0` for unlimited); `FRAM_DEV_PROFILE=1` additionally enables fractal traces.
- Phase D observability: `/observability/phase_d_memory` and `/observability/cognitive_summary` now include rollup stats (`phase_d_memory.stats`) with scored totals/averages, alpha/quaternion means, color counts, and `missing_alpha` when diagnostics are absent. CLI mirror: `python tools/phase_d_memory_summary.py --json`.

- `fram_serving/mcp_server.py` - MCP tools/resources (`fram.query`, `fram.memory_*`, `fram.get_trace_uri`) wiring session lifecycle controls through the shared orchestrator with telemetry logging. Explicit tool annotations distinguish reads from telemetry/mutations; `fram://config` omits `api_key` like REST `/config`.

- `fram_serving/mcp_auth.py` - Optional bearer-token validator for MCP clients.

- `scripts/bootstrap_env.sh`, `scripts/dev_run.sh`, `scripts/make_it_work.sh` -
  POSIX setup/launch parity: supported isolated Python, explicit startup,
  per-user runtime, loopback default, and opt-in development profile/autolog.
  `scripts/verify_mcp.py` verifies the live HTTP/MCP seam with content-minimal
  output. See [portable setup](portable_mcp_setup.md) for Linux and web gates.

- `fram_serving/config.py` - Pydantic settings with the shipped v2.2 defaults (including `default_query_reads`) and env overrides. `FRAM_STORAGE_ROOT` isolates mutable runtime state from the checkout; development-profile parsing accepts explicit boolean values and fails closed for false or invalid input.

- `fram_serving/ingest.py` - CLI helper that persists the current demo corpus to `storage/index/<corpus>` and exports claim logs.

- `fram_serving/observability.py` - JSONL logging plus summary stats (decisions, coverage deltas, budgets) including the fractal-memory sink.

- `fram_serving/fractal_memory/*` - Deterministic fractal trace types, generators, soft-DTW metrics, quaternion/lambda alignment helpers, and disk-backed storage that mirror cognitive episodes into higher-dimensional paths for scoring and replay. Provenance stores `seed_hash` plus generator seeds for deterministic replay; optional quaternion-weighted ranking is gated by config flags.

- `fram_serving/lived_memory.py` - SQLite-backed lived-event store with per-session parent lineage, full embeddings and text, shared 6D fractal projection, exact recursive lift into a configurable higher carrier, rolling lived state, digest-chain verification, restart persistence, and combined embedding/projection/state recall. `tools/import_lived_memory_zip.py` defaults source episodes to separate seed roots when the archive lacks session evidence; `tools/open_lived_memory_seeds.py` safely opens a legacy mixed import without mutating its source; `tools/lived_memory.py` provides status, search, session, and verification operations.

- `fram_serving/memory_capsule.py` - Append-only Memory Capsule writer that stores raw transcripts (including working-memory session entries when provided), per-turn embeddings, and a fractal trace stack under `storage/memory/capsules/` when `FRAM_MEMORY_CAPSULE_ENABLED=1`; includes a lightweight retrieval scan (per-turn embedding cosine, lexical fallback) surfaced in `/query` when `FRAM_MEMORY_CAPSULE_RETRIEVAL_ENABLED=1`.

- `fram_serving/continuity.py` - Exact-allowlist, digest-verified query witness emitted only after final selection and all write outcomes. It excludes raw query/answer/content and has no retrieval or ranking caller.

- `fram_serving/ecological_strata.py` - Separate append-only Offer/Mirror/Correct/Consent/Bind/Return ledger with refusal, revocation, local autonomy, and identity-collapse guards. A valid bind is a scope-local protocol fact, never identity proof. Operator CLI: `tools/ecological_strata_ledger.py`.

- `fram_serving/trace.py` - Placeholder schema helpers for richer trace typing (extend as trace fields solidify).

- `fram_core/math_utils.py` - Whitening, robust z-scores, subspace projection, Mahalanobis distance, kNN mean distance utilities used across the pipeline.

- `fram_core/confidence.py` - Feature bundle assembly and logistic/conformal policy glue.

- `fram_core/claims.py` - Claim schema and lightweight extractors feeding coverage.

- `fram_core/coverage.py` - Concave coverage state, lazy/eager CELF selector, composite cost helpers.

- `fram_core/pipeline.py` - Query orchestration (shortlist → subspace projection → confidence → coverage) with projection diagnostics and curvature-aware anchors; still runs hashing bag-of-words vectors over the persisted demo corpus under `storage/index/demo_corpus`, logging calibration/coverage traces and exporting ingestion helpers. Before the read-budget truncation, exact document/hierarchy metadata matches retain the primary routing tier and stronger content-token overlap orders within each tier; alignment claims remain metadata-only. Calibration fitting projects the raw centroid-distance weight onto its non-positive sign constraint, while linting and runtime loading reject payloads whose stored `g` is negative; together these preserve the spec-section-5 `-g*d_c_z` contract. Ingest stamps `version_id` on every shard source (docs/tables, session replay, cognitive, ANN bridge, connector) and writes a version manifest; as-of(T) queries filter shortlist/coverage/replay/ANN/connector candidates to lattice-active nodes, log `as_of_filter` in traces, and emit delta snippets from lattice diffs when serving older snapshots. The shortlist now flows through retrieval → ANN → cognitive shortlist → merge (gated) → Phase D scoring → final shortlist, with telemetry for pre-merge/merged cognitive ANN layers.

- `fram_index/prototypes.py` - Prototype bank & ANN shortlist (demo scaffold: cosine over hashing vectors; real ANN/fractal bank still pending).

- `fram_index/sparse_keys.py` - Sparse key index for identifier/number claims with checksum validation (ISBN/IBAN), posting caps, and deterministic ordering (still no Aho-Corasick).

- `fram_index/version_lattice.py` - Version lattice with append-safe JSONL manifest (`storage/index/<corpus>/versions.jsonl`); nodes record `version_id`, `parent_id`, `timestamp`, optional `diff`, and support `active_with_ancestors(as_of)` for filters and delta snippet assembly.

- `fram_layout/*` - Chunkers and layout-aware assembly helpers (AST-based code chunking, CSV header windows, PDF fallback ordering with column markers + layout_uncertain flag).

- `fram_eval/*` - Retrieval, QA, citation, calibration, latency, and freshness
  metrics; a typed eight-rung spec-section-15 ablation runner with equal
  per-rung wall-time budgets and JSON artifacts; strict JSONL evaluation cases
  plus deterministic table/code/PDF smoke tasks; and the existing fractal and
  conversational-memory falsification harnesses. The read-only wake/orient
  harness compares an F-RAM probe with compact-text, painting-description, and
  combined cues, plus an F-RAM-first staged bundle and typed untrusted-cue
  boundary; it never writes the evaluated lived store. The separate
  `fram_eval/visual_seed.py` canary compares provenance-ledger-backed raster
  embeddings against deduplicated lived-event text while preserving F-RAM
  primary order. It is bounded, privacy-minimal by default, source/output-alias
  safe, human-labelled, `KEEP_OFF`, and not imported by serving or ranking.
  `EvaluationOutcome.from_mapping`
  accepts the current `QueryOrchestrator.run()` result shape, including its
  nested decision trace.

- `scripts/ingest_demo.py` - Persists the demo corpus (including vectorizers/ANN) into `storage/`.

- `scripts/ingest_project_docs.py` - NEW: renders `docs/*.md` into normalized text shards (`examples/data/docs_ingest_*.txt`) so FRAM can reason about its own roadmap/specs; strips a leading UTF-8 BOM before heading conversion so the root hierarchy marker is preserved.
- `scripts/fractal_falsification.py` - Synthetic dynamical systems harness for falsifying fractal trace claims.

- `fram_eval/document_candidate.py` and `scripts/prepare_document_candidate.py`
  preserve explicit documents as byte-exact, source-labelled imports in a new
  offline cognitive candidate. They retain duplicate-edition provenance and
  distinguish documents from lived events; derived vectors/IFS traces do not
  replace source bytes. `scripts/run_production_memory_gate.py` supervises
  bounded actual-selection shards and verifies their complete paired merge.
  See `docs/production_memory_gate.md` for scope, custody and gate requirements.
- `soft_dtw_similarity` in `fram_serving/fractal_memory/metrics.py` handles
  negative soft-DTW costs without the old reciprocal pole. All reciprocal
  fractal scorers share this conversion; weights and activation thresholds
  remain unchanged. The synthetic self-recall diagnostic is kept separate
  from production-gate and reconstruction evidence.
- `fram_serving/fractal_memory/source_frame.py` provides an explicit candidate
  selected by `FRAM_FRACTAL_SCORING_MODE=source_frame` (default `legacy`). It
  recovers the projected seed from the first recorded affine step, validates
  the complete coordinate recurrence and replays the query in that same frame.
  Parent cosine and contraction-normalized aligned replay similarity use the
  existing 0.4 blend and 0.05 influence weights. This candidate does not use
  soft-DTW or quaternion blending; unsupported quaternion influence raises an
  error. Both app and shared runner dispatch to the same scorer. Unknown
  recipes, incomplete seeds, invalid coordinates and recurrence mismatches
  supply no candidate influence; unbound traces remain excluded beforehand.
  This checks internal consistency, not source authentication. Its distance is
  algebraically a normalized residual in the stored 6-D projection, which can
  collide for different full embeddings and contains no independent observed
  history. Activation flags and Section 15 quality gates remain unchanged.

- `tests/*` - Sanity/regression coverage across calibration CLIs, cognitive memory, serving endpoints, layout chunkers, and the pipeline orchestrator; extend alongside new behaviour.



Start with math utils and the orchestrator when making retrieval changes, then expand layout and durability. Run `python scripts/ingest_project_docs.py` whenever the docs change so the demo corpus stays aligned with the plan.







## Cognitive Memory (MVP)



F-RAM v2.2 now includes a minimal durable "self" memory alongside the working-memory session buffer.



- MVP (implemented)

  - JSONL-backed `CognitiveMemoryStore` in `fram_serving/memory.py` with:

  - Beliefs now persist as segmented JSONL files (`beliefs.00001.jsonl`, ...) with `schema_version="cogmem-1"`, per-turn hashes, monotonic `seq_no`, and `source.kind` metadata. Logging clients should call `tools/log_chat_turn.py --warn-log logs/cogmem_autolog_warnings.jsonl` so `pair_id` + hash de-dupe, replay inserts set `source.kind="replay"`, and segments roll over safely with full-experience preservation (no retention pruning).

    - Append-only, crash-safe cognitive writes (lock + fsync) with explicit failure events.
    - `append_episode`, `append_belief`, `append_link`
    - `append_constraint` stores derived constraint/correction records (scoped, auditable) without pruning the underlying experience.

    - `search(query, k, filters)` over episodes/beliefs (vector cosine or bag-of-words fallback)
    - `cognitive_ann_candidates` for ANN-bridge boosts (sklearn/FAISS index over episode vectors; default on)

    - `summarize(window)` for quick counts and recency

  - Write-through from `/query`: each request appends an Episode with `query/answer/citations/trace_id` and calibration summary.

  - Endpoint: `GET /memory/search?query=...&k=...&domain=&task=`



Planned extensions:



F-RAM v2.2 ships calibrated retrieval and working-memory replay but lacks a durable "self" memory. The planned Cognitive Memory layer adds persistent episodes and beliefs:



- Models

  - `Episode`/`Decision`/`Thought`/`Belief`/`Link` with IDs, timestamps, domain/task, provenance, confidence, and citations.

  - Belief graph with typed edges: supports, contradicts, refines.

- Store

  - `MemoryStore` interface with a JSONL backend under `storage/memory/` (append-only) plus periodic summaries.

  - APIs: `append_episode`, `append_belief`, `search(query, k, filters)`, `summarize(window)`.

- Integration

  - Write-through from `/query`: persist a `DecisionEpisode` using the existing trace (selection, calibration source, taus, features) and incorporate `/label` outcomes.

  - Read path: `/memory/search` to retrieve episodes/beliefs; seed orchestrator with top-k episodes alongside session replay.

- Indexing

  - Start with TF-IDF/"vocab" embeddings for search; add ANN later.

- Validation

  - Unit tests for append/search/summarize and a regression that demonstrates retrieval of prior commitments.



### Critical Path to Always-On Memory (Oct 2025)



- Promote `CognitiveMemoryStore.search` results into `fram_core/pipeline.QueryOrchestrator` alongside session replay (feature gate via `FRAMConfig.cognitive_memory_k`).

- Replace bag-of-words matching with shared embeddings/ANN so cognitive search scales with corpus size; persist diagnostics under `storage/observability/memory_search.json`. [hashing-based cosine scoring shipped Oct 2025; ANN index now uses sklearn/FAISS for episode vectors].

- Expose an assistant bootstrap helper (CLI or MCP tool) that hydrates from `/memory/search` + `/memory/summarize` before doc loading, enabling FRAM-backed recall for agents. [tools/bootstrap_memory.py].

- Add regression coverage (`tests/test_memory_bridge.py`) confirming prior-session answers surface after a restart. [tests/test_cognitive_memory_bridge.py].

- Update cheatsheet/spec once integrated so operators can enable the bridge without spelunking source.

- Config: `FRAMConfig.cognitive_memory_embedding_backend` (env `FRAM_COGNITIVE_MEMORY_EMBEDDING_BACKEND`) selects the scoring backend (defaults to hashing cosine).



- Observability: cognitive selections stream to `storage/observability/memory_cognitive.jsonl`; use `python tools/cognitive_memory_summary.py` for quick diagnostics.



This layer makes "retrieval of documents" complement "persistence of self," enabling reasoning continuity across sessions.

## Continuity control plane and north-star boundary (2026-07-27)

Rick's recovered Stateful Collaboration diagrams are preserved under
`artifacts/recovery/2026-07-27/`. Their durable control-plane vocabulary is:

1. orient intent and current context;
2. retrieve bounded memory;
3. discover the relevant tool, path, or worker;
4. plan and route bounded lanes;
5. execute;
6. observe and evaluate;
7. write, commit, and preserve provenance.

The Firelink CLAIM/CHECKPOINT/HANDOFF protocol, hot context packet, Atlas, Git
lanes, and immutable evidence artifacts implement pieces of that operator
workflow today. Fast working state, mid task/project state, slow identity/world
state, and durable F-RAM provenance are the target continuity taxonomy.

This is an architecture boundary, not a model-internals claim. The diagrams do
not establish that four latent tensors, persistent model-internal sub-agents,
dynamic RL updates, automated consent enforcement, or a complete Continuity OS
currently run in production.

