# F-RAM Roadmap

## Source-frame recognition checkpoint (2026-09-10)

- [x] Add an explicit, recurrence-checked source-frame scorer; preserve the
  legacy default, fixed weights and default-off influence.
- [x] Pass the unchanged exact-source diagnostic: 12/12 with the candidate,
  versus legacy 0/12; include perturbation, recipe and projection-limit tests.
- [x] Verify every bound trace recipe: 317 base / 382 augmented, with 591
  unbound historical traces retained and excluded in each corpus.
- [x] Complete both 216-capture production runs. All shadow checks now pass,
  including the previously failing augmented standard field.
- [ ] Establish the required top-one lift: base still ties 15/36 and 5/36;
  augmented still ties 13/36 and 4/36. Both decisions remain **KEEP_OFF**.
- [ ] Resolve document competition and separately validate any observed-history
  signal with independent labels. The new residual measures a 6-D projected
  source, not an independent lived trajectory or full embedding identity.

Evidence: `artifacts/coordination/2026-09-10/fractal-recognition/README.md`.
No source rewrite, installed store replacement or persistent activation.

## Fractal gate checkpoint (2026-09-10)

- [x] Preserve Rick's five supplied documents as 65 byte-exact, source-labelled
  imports in a separate evaluation candidate; original files remain unchanged.
- [x] Repair the negative soft-DTW reciprocal pole and transient Windows
  progress-receipt replacement; verify 303 focused tests and HTTP health.
- [x] Complete 432 original-dataset captures across base and added-document
  corpora, plus 36 separately frozen source-check captures. Both main gates
  remain **KEEP_OFF**: zero top-one lift, and augmented standard shadow fails.
- [ ] Resolve document competition: adding the sources lowered original-query
  top-one recall from 15/36 to 13/36 and low-overlap recall from 5/36 to 4/36.
- [ ] Replace the unsupported synthetic path comparison with a separately
  validated trajectory signal; exact-source synthetic diagnostic is currently
  0/12 for fractal versus 12/12 for vector cosine. Keep independent labels,
  source history and unchanged production/shadow gates before activation.

Evidence: `artifacts/coordination/2026-09-10/fractal-gate/README.md`.
No installed store replacement or persistent influence change occurred.

## Portable MCP checkpoint (2026-09-10)

- [x] POSIX core setup/launch parity with Windows H1: explicit startup, no
  hydration, external runtime, loopback default and opt-in profile/autolog.
- [x] MCP effect annotations, config secret redaction and isolated Windows
  HTTP/MCP verification. See `artifacts/coordination/2026-09-10/VERIFICATION.md`.
- [x] Current private-tunnel ChatGPT route and Mint handoff documented in
  `docs/portable_mcp_setup.md`.
- [ ] Verify Betty's OS/access and run native dependency, MCP and storage tests.
- [ ] Connect the synthetic fixture through ChatGPT; enforce authorized data
  scope before exposing personal memories.

Latest recovered-corpus activation remains **KEEP_OFF**. This checkpoint does
not activate influence, merge stores or complete the unfinished 3D work.

## Canonical integration baseline (2026-07-27)

- [x] Assemble the recovered Phase D/Phase E/Phase G and newer serving/memory
  lineages on isolated branch `firelink/full-merge`.
- [x] Preserve both explicit/latest version selection and manifest/ancestor/as-of
  filtering in one version lattice.
- [x] Restore the full observability route family, memory package compatibility,
  lifecycle behavior, and direct-run maintenance CLIs.
- [x] Integrate persisted cognitive ANN retrieval without disturbing
  document-only coverage order.
- [x] Recover the lossless Visual Evidence Ledger and deterministic contact-sheet
  tooling.
- [x] Preserve phase-history proof artifacts, power-trip recovery records,
  backup zips, and snapshot provenance.
- [x] Add the canonical Hopf map as a proof-track primitive with no runtime
  influence.
- [x] Add a compact, replaceable hot-context packet with a binding decision
  ledger, authority index, handoff template, and disk-derived lane census.
- [x] Add the deterministic Aizawa simulator to the falsification family and
  expose it through the direct-run evaluation harness.
- [x] Construct and falsify the fixed-shell Aizawa tangent field and declared
  Hopf connection; split integration-grade geometry from hypothesis-grade
  numerical evidence and remove unsupported Chern/recurrence claims.
- [x] Build the deterministic Chaos reconstruction core with golden simulator,
  logistic-diagnostic, rotational, complex-plane, and scene-memory contracts.
- [x] Replace stale full-context bootstraps with a bounded hot-first Atlas and
  add Git-verifiable packet and immutable Firelink snapshot tooling.
- [x] Commit and visibly render the exact Opus Chaos Playground browser
  artifact, then bind its default logistic metrics and cascade display to a
  shared Python/browser golden fixture.
- [x] Widen `LiftCapsule` to an ordered Givens product without changing the
  legacy default, independently falsify the proposed S3 repair, and add a
  versioned windowed-trajectory lift/re-entry report.
- [x] Preserve the supplied historical Chaos and Stateful Collaboration images
  byte-for-byte with hashes and explicit evidence/non-claim boundaries.

Full closeout and safety boundaries:
`docs/FIRELINK_CLOSEOUT_2026-07-27.md`. Current operational projection:
`docs/context/HOT_CONTEXT.md`.

## Vision
- Deliver F-RAM as a durable, fractal memory substrate for language models.
- Use hierarchical, multi-scale representations so short-, working-, and long-term recall coexist.
- Persist state on local storage so capacity scales with disk space while remaining reloadable between sessions.

## Current Baseline (2025-10-16)
- FastAPI in `fram_serving/app.py` exposes `/ui/memory`, `/query`, `/memory` (create/control/append/dismiss/search), `/observability/*`, `/metrics`, `/time`, `/where`, `/label`, `/calibration`, and `/config` on top of the shared `QueryOrchestrator`.
- Cognitive seeding is now on by default (`default_query_reads=5`, `cognitive_memory_k=12`, `cognitive_memory_token_budget=0`, `cognitive_memory_slot_budget=0` for unlimited), so bag-of-words episodes seed `/query` without a dev flag. Set `FRAM_COGNITIVE_MEMORY_K=0` to disable. `FRAM_DEV_PROFILE=1` still enables fractal traces, and `FRAM_FRACTAL_ENABLED=1` mirrors episodes into deterministic traces for replay experiments.
- `CognitiveMemoryStore` persists JSONL episodes/beliefs, `/memory/dismiss` logs cooldowns, and `/observability/memory/summary` / `tools/cognitive_memory_summary.py` surface those stats.
- `fram_core/pipeline.QueryOrchestrator` still uses hashing bag-of-words vectors and the demo corpus persisted at `storage/index/demo_corpus`, auto-rebuilding when sklearn versions drift.
- Observability tracks confidence/latency/memory, `/metrics` reports tau/alarms, and the pytest suite covers calibration CLIs, cognitive seeding, serving endpoints, layout chunkers, and the pipeline orchestrator.

## Baseline Archive (2025-09-25)
- FastAPI demo in `fram_serving/app.py` shares the production `QueryOrchestrator`, which now executes the full shortlist -> projection -> confidence -> coverage flow with curvature-driven anchor selection and projection diagnostics.
- Curvature anchor candidates now walk principal residual eigenpairs and score Delta/C with the configured lambda_tok/lambda_rerank costs (fram_core/pipeline.py, docs/FRAMv2.2-SPEC.md Section 11).
- QueryOrchestrator replays the last session's shortlist chunks when new runs request replay (fram_core/pipeline.py).
- `scripts/ingest_project_docs.py` renders every `docs/*.md` file into plain-text shards under `examples/data/`; `scripts/ingest_demo.py` persists that corpus (vectors, prototypes, claims, ANN index) to `storage/index/demo_corpus`.
- UTF-8 safe persistence in `fram_core/pipeline.save_corpus_cache` / `load_persisted_corpus` keeps rich doc content from breaking tests or reloads.
- Pytest suite passes (`75 passed`) with coverage, orchestrator, and ingestion regressions exercising the pipeline.
- Coverage selection now applies a section repeat penalty (`section_repeat_penalty` / `section_penalty_floor` in `FRAMConfig`) and the trace captures each chunk's `diversity_multiplier` so section spread is auditable.

## Implementation Status (live checklist)

This ledger is the bridge between code and docs. Treat it as the source for session planning; if code and docs disagree, update this list to match the code, then adjust the plan.

- [x] Temperature scaling wired through confidence + calibrate CLI; surfaced in traces/metrics and tested (`fram_core/confidence.py`, `fram_core/calibrate.py`, `tests/test_confidence_calibration.py`).
- [x] Calibration pipeline with precedence (task → domain → global → default); `/calibration` endpoint and tests (`scripts/calibrate_confidence.py`, `tools/calibration_*`, `fram_serving/app.py:/calibration`, `tests/test_serving_calibration.py`, `tests/test_pipeline_orchestrator.py`).
- [x] Composite cost and Δ/C selection with CELF; budgets/λ/pairs tracked in traces and validated by tests (`fram_core/coverage.py`, `fram_core/pipeline.py`, `tests/test_pipeline_orchestrator.py`).
- [x] Working‑memory replay (zero‑read reuse) in orchestrator; corpus ingest of project docs and persisted ANN/vectorizers (`scripts/ingest_project_docs.py`, `scripts/ingest_demo.py`).
- [x] Observability: reliability tracker with avg tau/temperature by domain/task; calibration source logged (`fram_serving/observability.py`, `/observability/summary`).
- [x] Codebase review map with spec comparison and system wiring (`docs/Codebase_Review.md`).
- [x] Evaluation artifact index for observed runs (`docs/proof/eval_artifact_index.md`).
- [x] Pluggable ANN backend with FAISS fallback detection; persisted fingerprints and reload tests (`fram_core/pipeline.py`, `tests/test_pipeline_orchestrator.py`).
- [x] Status gate (optional CI check) to fail when "Next" items in this file are already implemented (Makefile test target now runs calibration sanity + pytest).
- [x] Serving surface + docs audit (2025-10-16): `/query`, `/memory` (create/control/append/dismiss/search), `/observability/*`, `/metrics`, `/time`, `/where`, `/label`, `/calibration` captured in docs; cognitive seeding via `FRAM_DEV_PROFILE=1`; spec, cheatsheet, and architecture refreshed to match the code.
- [x] Fractal replay prototype (2025-10-20): cognitive episodes mint deterministic 6D paths via `fram_serving/fractal_memory/*`; `/query` blends cosine + soft-DTW and emits replay nodes, `/memory/fractal_trace` and `/observability/memory/fractal/ping` surface traces, and observability logs land in `memory_fractal.jsonl`. Ablation helper: python tools/fractal_ablation.py --limit 20.
- [x] Phase C harness now reports fractal recall metrics end-to-end: the calibration CLI, CSV/Markdown outputs, and /observability/recall_report summarize fractal retriever stats alongside cognitive seeds (scripts/calibrate_phase_c.py, scripts/recall_report_phase_c.py, fram_serving/app.py).
- [x] Added a tuning map for memory/fractal dials and exposed ANN/retention/fractal influence knobs in config (`docs/FRAMv2.2-tuning.md`, `fram_serving/config.py`).
- [x] Conversational memory eval harness now includes synthetic + live probe sets, semantic vs lexical modes, live episode matching, and a fractal ablation mode (`fram_eval/conversation_memory_eval.py`, `scripts/conversation_memory_eval.py`).
- [x] Phase D scaffolding + scoring surface (2025-11-15): deterministic projection/quaternion similarity/logistic-alpha helpers, standalone batch scorer + `/phase_d/score` endpoint, optional Phase D scores/diagnostics returned from `/rank/relevance` when `phase_d.enabled` is on, shortlist embeddings exposed via `QueryOrchestrator.get_embeddings_for_shortlist`, and `/observability/recall_report` now emits gated Phase D diagnostics (`alpha_t`, `alpha_color`, `quat_avg`) when debug is enabled. Logistic delta gain tuned with regression tests + perf smoke; Tests: `tests/test_phase_d_placeholders.py`, `tests/test_pipeline_orchestrator.py::test_get_embeddings_for_shortlist_shapes`, `tests/test_semantic_reranker.py::test_recall_report_phase_d_diagnostics`, `tests/test_rank_relevance_phase_d.py` (Phase D on/off/debug cases).
- [x] Close-out guardrail (2025-11-24): added `tools/check_closeout.py` + `make closeout-check` to fail when diary/roadmap edits or autologging are missing at session end; memory seeds now reserve read slots and are tracked in selection budgets/traces.
- [x] Phase D priority stack (2025-11-25): unified naming (`phase_d_priority`, `graph_priority`, `final_priority_for_bridge`), added temporal/hysteresis gates (default OFF), semantic priority graph, priority inspector view, and memory-bridge priority integration with bounded, deterministic sorting and full observability coverage; tests cover gating, blending, and config defaults.
- [x] Cognitive → ANN bridge: stable candidate_id/version_id/origin metadata; gated merge with pre-merge + merged-layer telemetry (`cognitive_ann_premerge`, `memory_layers`, `cognitive_ann_merge`); persistence regression + as-of lattice filtering; memory search telemetry endpoint `/observability/memory_search.json`.
- [x] Shared /query helper (2025-12-05): extracted full query flow into `fram_serving/query_runner.py` and rewired FastAPI `/query` via `QueryContext`; MCP parity refactor (storage-backed traces + tools/tests) is queued next.
- [x] Spec-section-15 evaluation foundation (2026-08-04): completed the
  retrieval/QA/citation/efficiency/freshness metrics, strict JSONL evaluation
  cases, deterministic table/code/PDF smoke tasks, and the ordered eight-rung
  equal-wall-time ablation runner with QueryOrchestrator result normalization
  and diffable JSON reports (`fram_eval/metrics.py`, `fram_eval/datasets.py`,
  `fram_eval/ablations.py`, `tests/test_eval_*.py`).
- [x] Canonical rescue promotion (2026-08-04): independently repacked and
  verified the complete Git history, archived the sealed bundle on D:, promoted
  `firelink/full-merge` at `95c174f` into
  `D:\Dev\_firelink_recovered_20260804`, and preserved both the damaged
  predecessor and protected live tree untouched.
- [x] Fresh-corpus closeout guards (2026-08-04): preserve BOM-prefixed root
  headings during docs ingestion and reject calibration payloads whose negative
  centroid-distance coefficient would invert the spec-section-5 confidence
  sign; exact content-token overlap is also prioritized before candidate-budget
  truncation within a primary document/hierarchy metadata tier, without
  broadening metadata-only alignment claims. Regressions pin all three contracts,
  and both calibration fit paths constrain the raw distance
  weight before serialization so newly trained payloads satisfy the loader/lint
  guard.
- [ ] Calibration refresh + sweep: rerun calibration and optional UI/observability polish for memory search layers.
- [ ] ChatGPT App SDK prototype (Apps SDK preview): wrap FRAM via MCP so it can ship as a native ChatGPT app.
- [ ] Connector Registry integration: expose FRAM ingestion through OpenAI's unified data source registry (Dropbox/Drive/SharePoint/Teams/custom MCP).
- [ ] Guardrails adoption: wire the new open-source masking/jailbreak defenses into FRAM's serving pipeline.
- [x] Minimal observability dashboard page for traces/metrics (beyond JSON endpoints). (`/ui/observability`)
- [x] Eval Season cheat sheet (proof packet summary for presentations). (`docs/proof/eval_season_cheatsheet.md`)
- [x] Pre-Intent Layer (PIL) posture spec stub. (`docs/FRAM_PIL.md`)
- [x] Experiments review UI with filters + digest preview. (`/ui/experiments`)
- [x] Scheduled calibration refresh (automation wrapper around harvest → slice → fit → lint → status). (`tools/refresh_calibration.py`)
- [x] Cognitive memory retrieval integrated into shortlist beyond MVP (`fram_serving/query_runner.py`, `tests/test_cognitive_memory_seeding.py`).
- [x] Memory Capsule (no-ceiling) write path: append-only capsules with raw transcript, per-turn embeddings, fractal trace stack, and remembering definition stored under `storage/memory/capsules/` when `FRAM_MEMORY_CAPSULE_ENABLED=1` (`fram_serving/memory_capsule.py`, `/query` write-through). Retrieval now seeds `/query` when `FRAM_MEMORY_CAPSULE_RETRIEVAL_ENABLED=1` (per-turn cosine with lexical fallback; `fram_serving/query_runner.py`).
- [x] Recursive Rotational Lift (v0.3) prototype math (`fram_core/rotational_lift.py`) formalizing the 2026-07-01 lift/rotate/recurse sketch; wired write-side-only into capsule writes (`self_invariants`/`open_residuals`) when `FRAM_ROTATIONAL_LIFT_ENABLED=1`, off by default and never affecting retrieval (`fram_serving/memory_capsule.py`, `docs/rotational_lift.md`, `tests/test_rotational_lift.py`, `tests/test_memory_capsule_rotational_lift.py`).
- [x] Capsule session lineage: links a capsule to its most recent same-session predecessor (`continues` link + `LiftCapsule.parent_id`) when `FRAM_CAPSULE_SESSION_LINEAGE_ENABLED=1`, independently gated and off by default, never affecting retrieval (`fram_serving/memory_capsule.py`, `docs/rotational_lift.md`, `tests/test_memory_capsule_session_lineage.py`).
- [x] True cross-capsule trajectory continuity (v0.5): `FRAM_ROTATIONAL_LIFT_LINEAGE_WINDOW` walks back N ancestor capsules via their own `continues` links and folds their raw trajectory embeddings into this capsule's own lift, reconstructed exactly; a third independent opt-in on top of the two flags above, off by default, never affecting retrieval (`fram_serving/memory_capsule.py`, `docs/rotational_lift.md`, `tests/test_memory_capsule_lineage_window.py`).
- [x] Root-caused and fixed the 2026-01-21 conversation-memory eval's top1=0.000 collapse: cognitive memory search's recency-decay half-life was silently unconfigurable (always 12.0, no matching `FRAMConfig` field existed); added `cognitive_memory_half_life_hours` (`FRAM_COGNITIVE_MEMORY_HALF_LIFE_HOURS`, default unchanged at 12.0) so a fixed benchmark's aging target episodes can be evaluated fairly (`fram_serving/memory.py`, `fram_serving/config.py`, `docs/observability_2026-07-22-eval-anomaly.md`, `tests/test_cognitive_memory_store.py`).
- [x] Sparse key index hardening: checksum validation (ISBN/IBAN), posting caps, and deterministic ordering (`fram_index/sparse_keys.py`, `tests/test_sparse_keys.py`).
- [x] Layout + version lattice minimal correctness: deterministic layout ordering, table header windows, heading paths, as-of selection + trace visibility (still no Hilbert/DAG).
- [x] Append-only cognitive memory writes with file locks + fsync and explicit failure events (`fram_serving/memory.py`, `tests/test_cognitive_logging.py`).
- [x] Constraint memory v0 (scoped, auditable, derived layer) with refusal canary tests (`fram_serving/memory.py`, `fram_serving/query_runner.py`, `tests/test_constraint_memory.py`).
- [x] Full-experience preservation enforced (retention/decay/forgetting disabled by default; docs updated).

### Milestone: Calibrated QA bands (2025-10-05)
- QA/local vs anchors/globals sit around 0.84 / 0.52 / 0.26 p_temp across representative prompts.
- Task-conditioned payloads (qa vs definitional) validated via `tools/calibration_sanity.py` and locked into CI.
- Calibration workflow + prompt packs documented in `docs/WHAT_WORKS.md`; next focus shifts to ANN retrieval, observability UI, and cognitive memory.
- 2026-01-21: nudged task calibration temperatures (qa/definitional) to soften overconfident QA regressions in the demo corpus.

### DevDay 2025 Alignment
- Prepare FRAM for ChatGPT Apps SDK submissions once the directory opens.
- Plan Connector Registry onboarding so Dropbox/Drive/SharePoint data can flow through FRAM without custom glue.
- Evaluate OpenAI Guardrails for integration into FRAM's serving path (PII masking, jailbreak detection).
- Track AgentKit/Agent Builder releases for potential FRAM-backed agents.

## Next Steps

### 0. Always-On Memory (critical path)
- [x] Verify MCP append dedupe guard: confirmed MCP append dedupe via `tests/test_mcp_server.py` and logged the result in `docs/CODEX_DIARY.md`.
- [x] **Upgrade memory relevance scoring:** replace bag-of-words scoring with shared embeddings and optional ANN (`FRAM_EMBEDDING_BACKEND`) so memory recall scales. Persist lightweight diagnostics to `storage/observability/memory_search.json`. [done Jan 2026 - ANN index uses sklearn/FAISS; memory_search.json ships].
- **Expose the assistant bridge:** ship an MCP/HTTP bootstrap helper (e.g. `python tools/bootstrap_memory.py`) that hydrates from `/memory/search` + `/memory/summarize` before reading docs; add regression coverage (`tests/test_memory_bridge.py`). [done Oct 2025 - CLI + tests].
- **Telemetry & diagnostics:** persist cognitive-memory search logs to `storage/observability/memory_cognitive.jsonl` and surface summaries via `python tools/cognitive_memory_summary.py`. [done Oct 2025].
- **Agent bootstrap wiring:** prompts now hydrate via `tools/bootstrap_memory.py`; legacy warm-up removed and identity set to Lumen. [done Oct 2025].
- **Auto-logging soak:** enable `COGMEM_AUTOLOG=1` so the harness runs `tools/log_chat_turn.py --warn-log logs/cogmem_autolog_warnings.jsonl`; failures write WARN records while segmented storage preserves full experience (no retention pruning). [done Oct 2025].
- [x] Autowire ack log for write confirmation (logs/fram_write_ack.jsonl, optional stdout echo).
- **Conversational capture:** `tools/log_chat_turn.py` records user/assistant turns with session metadata; prompts instruct automatic logging per exchange + close-out. [done Oct 2025].
- **Close-out enforcement (NEW):** guardrail now lives in `tools/closeout_guard.py` with a `make closeout-check` entry. [done]
- [x] Automate doc + calibration refresh: added `make refresh-docs` to run `tools/list_recent_docs.py`, `scripts/ingest_project_docs.py`, `scripts/ingest_demo.py`, and calibration lint/status.
- [x] **Document and test the flow:** update cheatsheet/spec and add regression coverage proving prior session answers surface via memory during a new run.
- **Live probe expansion + auto-flip gate (ongoing):** keep adding fresh episodes to the live probe set and re-run the conversation/shadow evals; latest run at 28 probes keeps auto-flip at KEEP_OFF (`storage/observability/conversation_memory_eval_live_28_details.json`, `storage/observability/memory_shadow_eval_live_28.json`, `storage/observability/fractal_autoflip_28.json`). Semantic backend run (pool_multiplier=3) also keeps KEEP_OFF (`storage/observability/conversation_memory_eval_live_28_semantic_details.json`, `storage/observability/memory_shadow_eval_live_28_semantic.json`, `storage/observability/fractal_autoflip_28_semantic.json`). Episodic-only alpha sweep (0.10/0.20/0.30) further reduced fractal top1 and still kept KEEP_OFF (`artifacts/observability/conversation_memory_eval_live_28_semantic_episode_alpha010.json`, `..._alpha020.json`, `..._alpha030.json` plus matching shadow/autoflip files). Quaternion sweeps (weights 0.10/0.20/0.30, lambda off/on) on episodic-only live probes kept auto-flip at KEEP_OFF (`artifacts/observability/conversation_memory_eval_live_baseline_quatguard.json`, `artifacts/observability/memory_shadow_eval_live_baseline_quatguard.json`, `artifacts/observability/fractal_autoflip_baseline_quatguard.json`, plus `artifacts/observability/*quat_w0*_l*.json`). Expanded low-lex probes to 36 and reran episodic-only baselines; top1 dropped (probe 0.250/0.250/0.222, low-lex 0.139/0.194/0.111), auto-flip stayed KEEP_OFF (`artifacts/observability/conversation_memory_eval_live_baseline_quatguard_expanded.json`, `artifacts/observability/memory_shadow_eval_live_baseline_quatguard_expanded.json`, `artifacts/observability/fractal_autoflip_baseline_quatguard_expanded.json`). Semantic backend rerun on the 36-probe set kept auto-flip KEEP_OFF (probe top1 0.222/0.250/0.222, low-lex 0.194/0.194/0.222; `artifacts/observability/conversation_memory_eval_live_baseline_quatguard_expanded_semantic.json`, `artifacts/observability/memory_shadow_eval_live_baseline_quatguard_expanded_semantic.json`, `artifacts/observability/fractal_autoflip_baseline_quatguard_expanded_semantic.json`). Tightened low-lex phrasing to remove anchor tokens; baseline moved to probe top1 0.278/0.222/0.250 and low-lex top1 0.111/0.167/0.083, auto-flip stayed KEEP_OFF (`artifacts/observability/conversation_memory_eval_live_baseline_quatguard_expanded_tight.json`, `artifacts/observability/memory_shadow_eval_live_baseline_quatguard_expanded_tight.json`, `artifacts/observability/fractal_autoflip_baseline_quatguard_expanded_tight.json`). Switched low-lex probes to direct phrase-recall prompts; low-lex top1 rebounded to 0.222 across modes but shadow avg_delta turned negative; auto-flip stayed KEEP_OFF (`artifacts/observability/conversation_memory_eval_live_baseline_quatguard_expanded_phrase.json`, `artifacts/observability/memory_shadow_eval_live_baseline_quatguard_expanded_phrase.json`, `artifacts/observability/fractal_autoflip_baseline_quatguard_expanded_phrase.json`). Phrase-recall alpha sweep (0.10/0.20/0.30) raised low-lex top1 at alpha 0.30 (0.389) while probe top1 dropped; auto-flip stayed KEEP_OFF (`artifacts/observability/conversation_memory_eval_live_phrase_alpha010.json`, `..._alpha020.json`, `..._alpha030.json` plus matching shadow/autoflip files). Detailed comparison of phrase-recall baseline vs alpha 0.30 shows 8 low-lex items improved (miss -> hit), 1 regression, suggesting selective gains rather than broad lift (`artifacts/observability/conversation_memory_eval_live_phrase_baseline_details.json`, `artifacts/observability/conversation_memory_eval_live_phrase_alpha030_details.json`). Micro-probe set (9 items) confirms alpha 0.30 can boost fractal low-lex top1 to 0.778 without hurting probe top1, though global auto-flip still stays KEEP_OFF (`artifacts/observability/conversation_memory_eval_live_phrase_micro_baseline.json`, `artifacts/observability/memory_shadow_eval_live_phrase_micro_baseline.json`, `artifacts/observability/conversation_memory_eval_live_phrase_micro_alpha030.json`, `artifacts/observability/memory_shadow_eval_live_phrase_micro_alpha030.json`). Added an eval-only low-lex gate (token overlap threshold) to frugal fractal ranking; initial gate run (threshold 0.15) produced zero low-lex hits because overlap min was ~0.166, so metrics matched baseline (`artifacts/observability/conversation_memory_eval_live_phrase_gate.json`, `artifacts/observability/memory_shadow_eval_live_phrase_gate.json`, `artifacts/observability/fractal_autoflip_phrase_gate.json`). Threshold sweep (0.18/0.20/0.25) raised low-lex gate hits to 1/3/6 but probe/low-lex top1 stayed flat and auto-flip remained KEEP_OFF (`artifacts/observability/conversation_memory_eval_live_phrase_gate_t018.json`, `..._t020.json`, `..._t025.json`, plus matching shadow/autoflip files). Updated the gate to ignore quoted phrase tokens; rerun at threshold 0.20 saw gate hits=3 with no top1 lift, so auto-flip stayed KEEP_OFF (`artifacts/observability/conversation_memory_eval_live_phrase_gate_quoted.json`, `artifacts/observability/memory_shadow_eval_live_phrase_gate_quoted.json`, `artifacts/observability/fractal_autoflip_phrase_gate_quoted.json`). Rewrote the micro probe low-lex prompts as paraphrases and reran the gate (threshold 0.20): low-lex hits stayed at 3 with no top1 change, KEEP_OFF (`artifacts/observability/conversation_memory_eval_live_phrase_micro_paraphrase.json`, `artifacts/observability/memory_shadow_eval_live_phrase_micro_paraphrase.json`, `artifacts/observability/fractal_autoflip_phrase_micro_paraphrase.json`). Rewrote the full 36-probe low-lex prompts as paraphrases and reran the gate (threshold 0.20): low-lex hits=15, but fractal low-lex top1=0.333 trailed semantic/lexical (0.472/0.444), KEEP_OFF (`artifacts/observability/conversation_memory_eval_live_paraphrase_gate.json`, `artifacts/observability/memory_shadow_eval_live_paraphrase_gate.json`, `artifacts/observability/fractal_autoflip_paraphrase_gate.json`). Raised the paraphrase gate threshold to 0.30: low-lex hits=22 and fractal low-lex top1=0.306, still below semantic/lexical (0.472/0.444), KEEP_OFF (`artifacts/observability/conversation_memory_eval_live_paraphrase_gate_t030.json`, `artifacts/observability/memory_shadow_eval_live_paraphrase_gate_t030.json`, `artifacts/observability/fractal_autoflip_paraphrase_gate_t030.json`). Paraphrase gate alpha sweep (0.10/0.20, threshold 0.20) reduced fractal top1 further (probe 0.25/0.194, low-lex 0.111/0.083), KEEP_OFF (`artifacts/observability/conversation_memory_eval_live_paraphrase_alpha010_gate.json`, `..._alpha020_gate.json`, plus matching shadow/autoflip files). Similarity gate run at sim<=0.30 fired 50 hits and further reduced fractal low-lex top1 to 0.083 (semantic/lexical unchanged at 0.472/0.444), KEEP_OFF (`artifacts/observability/conversation_memory_eval_live_paraphrase_sim_gate_t030.json`, `artifacts/observability/memory_shadow_eval_live_paraphrase_sim_gate_t030.json`, `artifacts/observability/fractal_autoflip_paraphrase_sim_gate_t030.json`). Answer-only overlap gate (threshold 0.20) fired 21 hits and kept fractal low-lex top1 at 0.306, still below semantic/lexical (0.472/0.444); auto-flip stayed KEEP_OFF (`artifacts/observability/conversation_memory_eval_live_paraphrase_answer_gate_t020.json`, `artifacts/observability/memory_shadow_eval_live_paraphrase_answer_gate_t020.json`, `artifacts/observability/fractal_autoflip_paraphrase_answer_gate_t020.json`). Details run for the answer-only gate shows 5 probes where semantic hits but fractal misses (nova_anchor, anchor_palimpsest, thread_slate, signal_fathom, anchor_meridian) in `artifacts/observability/conversation_memory_eval_live_paraphrase_answer_gate_details.json`. Hard-micro set from those 5 probes shows fractal low-lex top1 stays 0.0 at alpha 0.0 and 0.3 while semantic/lexical remain 1.0 (`artifacts/observability/conversation_memory_eval_live_paraphrase_hard_micro_alpha000.json`, `..._alpha030.json`, plus matching shadow/autoflip files). Trace diagnostics for the hard-micro probes show soft-DTW scores near zero across traces and cosine signs flipping between expected vs top hits (`artifacts/observability/fractal_trace_probe_hard_micro.json`). Soft-DTW tuning (gamma=1.0, band=0.5) on the hard-micro set kept fractal low-lex top1 at 0.0 and auto-flip KEEP_OFF (`artifacts/observability/conversation_memory_eval_live_paraphrase_hard_micro_dtw_g1_b05_alpha030.json`, `artifacts/observability/memory_shadow_eval_live_paraphrase_hard_micro_dtw_g1_b05_alpha030.json`, `artifacts/observability/fractal_autoflip_paraphrase_hard_micro_dtw_g1_b05_alpha030.json`). Centroid-only cosine (gamma=1.0, band=0.5) on the hard-micro set reduced fractal probe top1 to 0.2 and kept low-lex top1 at 0.0 (`artifacts/observability/conversation_memory_eval_live_paraphrase_hard_micro_dtw_g1_b05_centroid_alpha030.json`, `artifacts/observability/memory_shadow_eval_live_paraphrase_hard_micro_dtw_g1_b05_centroid_alpha030.json`, `artifacts/observability/fractal_autoflip_paraphrase_hard_micro_dtw_g1_b05_centroid_alpha030.json`). Exp score-mode (gamma=1.0, band=0.5) matched the inverse path (fractal low-lex top1 0.0) (`artifacts/observability/conversation_memory_eval_live_paraphrase_hard_micro_dtw_g1_b05_exp_alpha030.json`, `artifacts/observability/fractal_autoflip_paraphrase_hard_micro_dtw_g1_b05_exp_alpha030.json`). Expanded hard-micro set to 9 probes; fractal low-lex top1 remains 0.0 (`artifacts/observability/conversation_memory_eval_live_paraphrase_hard_micro_expanded_dtw_g1_b05_alpha030.json`, `artifacts/observability/memory_shadow_eval_live_paraphrase_hard_micro_expanded_dtw_g1_b05_alpha030.json`, `artifacts/observability/fractal_autoflip_paraphrase_hard_micro_expanded_dtw_g1_b05_alpha030.json`). Trace diagnostics now include candidate distributions and expected/top percentiles for the expanded set (`artifacts/observability/fractal_trace_probe_hard_micro_expanded.json`). Hard-micro expanded trace similarity ablations (turn_hist/lag_dist/radius_hist/curvature_hist) kept low-lex top1 at 0.0 and auto-flip KEEP_OFF (`artifacts/observability/conversation_memory_eval_live_paraphrase_hard_micro_expanded_dtw_g1_b05_turnhist_alpha030.json`, `artifacts/observability/conversation_memory_eval_live_paraphrase_hard_micro_expanded_dtw_g1_b05_lagdist_alpha030.json`, `artifacts/observability/conversation_memory_eval_live_paraphrase_hard_micro_expanded_dtw_g1_b05_radiushist_alpha030.json`, `artifacts/observability/conversation_memory_eval_live_paraphrase_hard_micro_expanded_dtw_g1_b05_curvhist_alpha030.json`, plus matching shadow/autoflip files). Percentile trace normalization (composite mode) raised probe top1 to 0.556 but low-lex stayed 0.0 (`artifacts/observability/conversation_memory_eval_live_paraphrase_hard_micro_expanded_dtw_g1_b05_pct_alpha030.json`, `artifacts/observability/memory_shadow_eval_live_paraphrase_hard_micro_expanded_dtw_g1_b05_pct_alpha030.json`, `artifacts/observability/fractal_autoflip_paraphrase_hard_micro_expanded_dtw_g1_b05_pct_alpha030.json`). Trace probes for turn_hist/lag_dist show expected percentile means below top hits (`artifacts/observability/fractal_trace_probe_hard_micro_expanded_turnhist_k3.json`, `artifacts/observability/fractal_trace_probe_hard_micro_expanded_lagdist_k3.json`). IFS-conditioned query paths on the hard-micro v3 set raised expected score percentiles (probe ~0.57, low-lex ~0.54) and improved fractal top1 to 0.083/0.167; auto-flip stays KEEP_OFF (`artifacts/observability/fractal_trace_probe_hard_micro_v3_ifs_20251229_101417.json`, `artifacts/observability/fractal_eval_report_hard_micro_v3_ifs_20251229_102025_20251229_082031.md`, plus matching conversation/shadow/autoflip JSONs).
- **IFS hard-micro v3 follow-up:** IFS paths lifted hard-micro v3 fractal top1 to 0.083/0.167; percentile normalization with IFS raised probe top1 to 0.250 (low-lex held 0.167), auto-flip KEEP_OFF (`artifacts/observability/fractal_eval_report_hard_micro_v3_ifs_20251229_102025_20251229_082031.md`, `artifacts/observability/fractal_eval_report_hard_micro_v3_ifs_pct_20251229_105827_20251229_085834.md`, plus matching conversation/shadow/autoflip JSONs).
- **IFS ablation:** hard-micro v3 ablation shows cosine deltas drive the lift (~0.59 probe, ~0.57 low-lex) while soft-DTW/quat deltas are near zero (`artifacts/observability/fractal_trace_ablation_hard_micro_v3_ifs_20251229_104757.json`).
- **Live probe A/B (IFS vs synthetic paths):** pool_multiplier=3 on the 36 live probes kept fractal probe top1 at 0.111 but lifted low-lex top1 from 0.028 (synth) to 0.222 (IFS); shadow avg_delta improved on low-lex (0.115 -> 0.173) with a dip on probe (0.130 -> 0.096), auto-flip KEEP_OFF (`artifacts/observability/fractal_eval_report_live_probe_synth_20251229_111016_20251229_091023.md`, `artifacts/observability/fractal_eval_report_live_probe_ifs_20251229_112550_20251229_092557.md`, plus matching conversation/shadow/autoflip JSONs).
- **Live probe A/B details:** per-probe diff shows new probe hits on kestrel_marker, marker_cairn, vanta_signal, zephyr_anchor, quill_marker, sigma_thread_alt, with regressions on beacon_orbit, signal_fathom, anchor_meridian. Artifacts: `artifacts/observability/conversation_memory_eval_live_probe_synth_details_20251229_120723.json`, `artifacts/observability/conversation_memory_eval_live_probe_ifs_details_20251229_120848.json`, `artifacts/observability/fractal_probe_diff_live_probe_synth_vs_ifs_20251229_101105.md`.
- **Live probe regression drill:** top-k previews for the three regressions show IFS over-selecting nearby beacon/echo episodes; report at `artifacts/observability/fractal_probe_regressions_live_probe_ifs_20251229_101803.md`.
- **Live probes with IFS + percentile normalization:** pool_multiplier=3 lifted fractal top1 to 0.306 (probe) / 0.139 (low-lex) with shadow avg_delta 0.113/0.190; auto-flip recommends ENABLE, but semantic/lexical top1 collapsed in this run (probe 0.056/0.083, low-lex 0.0) so treat as a candidate signal until we sanity-check the baseline. Artifacts: `artifacts/observability/fractal_eval_report_live_probe_ifs_pct_20251229_102454.md`, plus matching conversation/shadow/autoflip JSONs.
- **Live probes IFS + percentile (episodes-only):** with `--kinds episode`, fractal top1 = 0.278 (probe) / 0.222 (low-lex) and shadow avg_delta 0.221/0.175, while semantic/lexical baselines remain higher (0.444/0.333 probe, 0.500/0.417 low-lex); auto-flip returns to KEEP_OFF, suggesting belief crowding drove the earlier ENABLE. Artifacts: `artifacts/observability/fractal_eval_report_live_probe_ifs_pct_episodes_20251229_124240.md` plus matching conversation/shadow/autoflip JSONs.
- **Episodes-only A/B (synthetic + percentile):** with `--kinds episode`, synthetic query paths land at fractal top1 = 0.306 (probe) / 0.139 (low-lex) and shadow avg_delta 0.270/0.177; auto-flip remains KEEP_OFF. Artifacts: `artifacts/observability/fractal_eval_report_live_probe_synth_pct_episodes_20251229_130211.md` plus matching conversation/shadow/autoflip JSONs.
- **Episodes-only per-probe diff (percentile):** IFS boosts low-lex hits (14/36 vs 10/36) but trims probe hits (22/36 vs 23/36); see per-probe diff for the affected cues (`artifacts/observability/fractal_probe_diff_live_probe_pct_episodes_synth_vs_ifs_20251229_112124.md`, plus matching details JSONs).
- **Low-lex IFS gate (episodes-only):** added a low-lex query-path override and ran synthetic base + percentile with IFS only when the low-lex gate fires (overlap threshold 0.2, answer mode). Fractal top1 = 0.278 (probe) / 0.111 (low-lex), gate hits 12/72, auto-flip KEEP_OFF (`artifacts/observability/fractal_eval_report_live_probe_synth_pct_episodes_lowlexifs_20251229_133413.md`, plus matching JSONs).
- **Low-lex IFS gate (similarity):** semantic similarity gate at 0.35 fires 53/72 queries; fractal top1 = 0.222 (probe) / 0.222 (low-lex) with shadow avg_delta 0.229/0.175; auto-flip KEEP_OFF (`artifacts/observability/fractal_eval_report_live_probe_synth_pct_episodes_lowlexifs_sim_20251229_134920.md`, plus matching JSONs).
- **Low-lex IFS gate sweep:** similarity thresholds 0.30 and 0.25 fire 49/72 and 40/72 queries, respectively. Fractal top1 stays 0.222/0.222 at 0.30 and rises to 0.278/0.194 at 0.25, with shadow avg_delta around 0.239/0.175; auto-flip remains KEEP_OFF (`artifacts/observability/fractal_eval_report_live_probe_synth_pct_episodes_lowlexifs_sim030_20251229_140646.md`, `artifacts/observability/fractal_eval_report_live_probe_synth_pct_episodes_lowlexifs_sim025_20251229_141323.md`, plus matching JSONs).
- **Sim025 vs baseline diff (episodes-only):** per-probe diff shows +4 low-lex hits (9 gains, 5 regressions) and a -1 probe hit (2 regressions). Artifacts: `artifacts/observability/fractal_probe_diff_live_probe_pct_episodes_sim025_vs_synth_20251229_123004.md` and `artifacts/observability/conversation_memory_eval_live_probe_synth_pct_episodes_sim025_details_20251229_142534.json`.
- **Two-pass episodes-only bound:** merged probe metrics from synth+percentile with low-lex metrics from IFS+percentile; fractal top1 = 0.306 (probe) / 0.222 (low-lex) with shadow avg_delta 0.270/0.175; auto-flip KEEP_OFF. Artifacts: `artifacts/observability/fractal_eval_report_live_probe_two_pass_pct_episodes_20251229_152539.md` plus matching conversation/shadow/autoflip JSONs.
- **Two-pass harness:** added `scripts/run_fractal_two_pass_eval.py` and reran the two-pass episodes-only bound (synthetic probe + IFS low-lex); results match the prior merge (fractal top1 0.306/0.222, shadow avg_delta 0.270/0.175), auto-flip KEEP_OFF. Artifacts: `artifacts/observability/fractal_eval_report_live_probe_two_pass_pct_episodes_v2_20251229_133409.md` plus matching JSONs.
- **Decision:** keep single-pass synthetic as the baseline; treat two-pass as the best-case bound, and leave sim025 gating off unless needed for a targeted low-lex push.
- **Identity trace check (stored embeddings):** run `scripts/fractal_trace_identity_check.py` to score each episode's trace against its own stored embedding and see if self-match shows up without the query vectorizer. Latest run (77 eligible episodes, k_max=5, pool=25) yielded top1=0.026 and mean rank 12.12 with dims matched at 1024 (`artifacts/observability/fractal_trace_identity_check_20251229_075921.json`). Percentile normalization + alpha=1.0 nudged top1 to 0.065 and mean rank 11.70 (`artifacts/observability/fractal_trace_identity_check_pct_alpha100_20251229_082804.json`). Raw vectors (no normalization) lifted top1 to 0.052 with mean rank 13.05 (`artifacts/observability/fractal_trace_identity_check_raw_20251229_084921.json`). Using IFS-conditioned query paths (raw vectors + `query_path_mode=ifs`) jumped top1 to 0.182 and mean rank 8.70 (`artifacts/observability/fractal_trace_identity_check_ifs_raw_20251229_094735.json`).
- **Trace alignment probe:** run `scripts/fractal_trace_alignment_probe.py` to compare raw vs normalized embeddings against stored traces. Initial 25-episode probe shows seed match raw=1.0 vs norm=0.0, and soft-DTW favors raw vectors (`artifacts/observability/fractal_trace_alignment_probe_20251229_084800.json`).
- **Close-out enforcement:** guardrail added via `tools/check_closeout.py` + `make closeout-check` (fails when diary/roadmap are untouched or `COGMEM_AUTOLOG` is off).
- **Automate doc + calibration refresh:** build a Make target that runs `tools/list_recent_docs.py`, re-ingests docs, rebuilds the demo corpus, and revalidates calibration payloads whenever memory artefacts change.
- **Document and test the flow:** update cheatsheet/spec and add regression coverage proving prior session answers surface via memory during a new run.
- **Phase D signals -> cognitive recall (NEW):** surface Phase D outputs (alpha_t, alpha_color, quat_avg, blended scores) as optional features when ranking cognitive memory shards, gated by config. Outline: (1) reuse `get_embeddings_for_shortlist` for cognitive episodes, (2) score with `phase_d_score_batch` alongside memory cosine/recency, (3) emit diagnostics in traces under a new `phase_d_memory` block, (4) keep default off; add harness tests for cognitive->Phase D bridge.
- **Phase D observability (NEW):** `phase_d_memory` now appears in traces/recall_report; lightweight dashboard/CLI summaries (`/observability/phase_d_memory`, `/observability/cognitive_summary`, tools/phase_d_memory_summary.py) stay behind `phase_d.enable_memory_bridge`. Dashboards and the CLI now aggregate counts/averages (scored totals, alpha/quat averages, color counts) alongside recent events.
- **Priority graph scope (audit 2025-12-04):** Graph boosting is applied in serving memory search but not in `fram_core/pipeline.py`/memory bridge. Decide whether to extend it into the pipeline or document serving-only scope, then add tests.
- **Cognitive ANN gating (audit 2025-12-04):** Pipeline merge currently requires both `enable_cognitive_ann_bridge` and `phase_d.enable_memory_bridge`. Confirm intended default (likely ANN should not depend on Phase D) and adjust gates + regression tests if needed.
- **Calibration refresh (2025-12-04):** Refit roadmap/spec/diary/task=qa payloads from `storage/observability/calibration.jsonl` (harvested via scripts/harvest_calibration.py). `calibration_status` now reports temps: roadmap=0.95, spec=0.73, diary=0.66, task qa=0.84; globals unchanged. Schedule periodic re-harvests as logs grow.
- **Phase D memory observability:** Recent logs show zero scored Phase D memory events; exercise bridge diagnostics or clarify default-off expectation.
- **Artifact check (2025-12-04):** Demo corpus persisted 2025-11-27 with `versions.jsonl`; calibration payloads present but stale; cognitive memory logs at 77 events (hashing backend).
- **MCP parity next (2025-12-05):** Next task: MCP integration using the shared helper (storage-backed traces, fram.query parity tests, MCP trace fetch/list, observability + memory control tools).

### 1. Calibration & Confidence Tuning (short term)
- Continue harvesting `storage/observability/calibration.jsonl` and refitting `tau1/tau2` via `scripts/calibrate_confidence.py`. [ongoing]
- Maintain domain/task overrides in `FRAMConfig`; record payload deltas in `docs/WHAT_WORKS.md`. [operational]

### 2. Spec & Docs Sync (supporting)
- Align `docs/FRAMv2.2-SPEC.md` with shipped behaviour (calibration precedence, memory bridge). [in progress]
- Keep `docs/Architecture.md`, cheatsheet, and roadmap snapshots current as memory surfaces evolve. [ongoing]

### 3. Observability & Corpus Tooling (maintenance)
- Preserve trace hooks, doc ingest automation, and section-penalty sweeps; iterate when the memory roadmap requires new signals.

### 4. Future Enhancements (post-memory)
- Connector Registry integration, Guardrails adoption, ChatGPT Apps SDK packaging, observability dashboards, scheduled calibration automation, layout upgrades, and version-lattice durability remain queued but stay subordinate to the always-on memory bridge until it ships.

Scope guardrails (current focus)
- Sparse key hardening: ISBN/IBAN checksum validation, posting cap 256, deterministic ordering; no Aho-Corasick.
- Layout + version lattice minimal correctness: L1-L5, C1-C3, V1-V4 only; no OCR, no full DAG rewrites.
## Priority Map

1. **Always-On Memory Bridge:** cognitive retrieval → shortlist integration, assistant bootstrap tooling, regression coverage.
2. Memory relevance upgrades (shared embeddings, ANN, scoring telemetry).
3. Calibration upkeep aligned with memory routing (payload sanity, `/calibration` assertions).
4. Corpus and doc automation (ingest, refresh, diff tooling).
5. Follow-on platform work (Connectors, Guardrails, Apps SDK, dashboards, lattice durability).
## Milestones (Detailed Plan to Full Spec)

The goal is to make progress in small, testable steps. Each milestone includes acceptance criteria and concrete test hooks so future sessions can continue cleanly.

M1 - ANN + Embeddings hardening (short)
- Tasks
  - [x] Swap demo k‑NN to a pluggable ANN (keep scikit fallback; support `faiss-cpu` in [tool.poetry.extras].)
  - [x] Persist ANN index metadata with fingerprint checks (already scaffolded).
- Acceptance
  - [x] Tests prove ANN reloads across runs without recalculation.
  - [x] Fingerprint or backend mismatch triggers rebuild; match logged in traces.

M2 - Calibration pipeline maturity (short)
- Tasks
  - Harden tools/calibration_* CLIs (status/lint already present) with richer output and docs.
  - Add a "calibration pack" metadata blob emitted alongside payloads (source log slices, fit params, hash).
- Acceptance
  - /calibration reflects pack metadata; tests assert presence and consistency.

M3 - Coverage + Anchors finalize (short)
- Tasks
  - Confirm CELF and diversity multipliers against additional ablations; expand tests for segment penalties.
  - Trace: ensure anchor residual step details appear for auditability.
- Acceptance
  - New tests in tests/test_celf_selection.py cover edge constraints; traces include `residual_steps` snippets.

M4 - Layout improvements (medium)
- Tasks
  - Tighten pdfplumber extraction thresholds; add simple column grouping heuristics.
  - Enrich assembler with region headers and improved table context.
- Acceptance
  - Layout tests demonstrate stable headers and region grouping against a small PDF fixture.

M5 - Version lattice durability (medium)
- Tasks
  - Add ingestion hooks to persist version nodes for documents; attach doc nodes to chunks.
  - Enforce as‑of(T) filtering across all selection paths using lattice timestamps.
- Acceptance
  - New tests assert that queries with older as‑of exclude newer shards; traces log active node set size.

M6 - Corpus ingestion beyond demo (medium)
- Tasks
  - CLI: `fram-ingest` expands to accept folders/URLs with simple adapters; resume-safe with fingerprints.
  - Persist summaries (chunk counts, token totals) for quick health checks.
  - Ingest the bird-species spreadsheet (≈2 MB) as a stress-test corpus once user supplies the file.
- Acceptance
  - Ingest tests assert idempotency and correct summaries; where/observability surfaces show the new corpus.

M7 - Cognitive Memory advanced (medium)
- Tasks
  - [x] Belief links (supports/contradicts/refines) and `/memory/link` endpoint.
  - Search ranking: add score per token + recency boosts. [Shipped in MVP: hashing-vector cosine + recency weighting + token-budget packer]
  - Config: gating for seeding (`cognitive_memory_k`, `token_budget`, `trace_k`) already added.
- Acceptance
  - Tests assert belief linking round-trip; search pref ranking; trace contains link counts when present.

M8 - Observability dashboards (short)
- Tasks
  - [x] Minimal HTML view for recent traces with key fields (`/ui/observability`).
  - [x] CLI: tools/trace_summary.py to dump top-level metrics from traces.
- Acceptance
  - tests/test_observability_traces.py covers endpoints; manual run renders a basic page.

M9 - MCP tooling completeness (short)
- Tasks
  - Ensure MCP tools cover memory search/summary and trace fetch.
- Acceptance
  - Basic MCP end‑to‑end run produces answers + memory traces.

M10 - Release notes + docs (short)
- Tasks
  - Update docs/FRAMv2.2-cheatsheet.md and Architecture.md to final state.
  - Add a short "Operations" guide (backup, calibration refresh cycle, dev profile usage). [done: `docs/Operations.md`]
- Acceptance
  - Docs build reviewed; quickstart runs end‑to‑end with dev profile.

Session Flow (for future chats)
- Status‑first warm‑up:
  - Read this file's "Implementation Status" and "Next Steps".
  - Run `pytest -q` locally to confirm the baseline.
  - Verify calibration state: `GET /calibration` and `python tools/calibration_status.py --json`.
  - If code and ledger disagree, update this file before changing code.
- Then pick the next unchecked item; add a test; implement; validate with `pytest -q`.
- Capture results in `docs/CODEX_DIARY.md`, update the checkboxes here, keep diffs small.








## Phase D - Non-linear + Rotational Recall
- [x] Spec added (docs/phase_d_plan.md).
- [x] Quaternion + lambda alignment metrics wired into fractal scoring for evaluation; ranking influence remains behind `FRAM_FRACTAL_QUAT_INFLUENCE` (default off).
- [x] Falsification harness for fractal traces (`scripts/fractal_falsification.py`); A/B results still pending.
- [x] Review synthetic falsification results in `storage/observability/fractal_falsification.json` before enabling quaternion-weighted influence.
- [x] Multi-seed sweep (seeds 0-3, count 6, steps 32, n_nodes 64) run per-system; aggregate still weak and unstable, so keep quaternion influence off.
- Goal: >= +2 % MRR lift with < 10 % latency cost.

# Update 2025-12-01 (version lattice)
- Version manifest persisted to `storage/index/<corpus>/versions.jsonl`; ingest stamps `version_id` on all shard sources (docs, tables, replay, cognitive, ANN bridge, connectors, injected memory).
- As-of(T) enforcement now filters shortlist/coverage/replay/memory/connector candidates; traces log `as_of_filter` and delta snippets from lattice diffs.

## Update 2026-08-11 (continuity witness + Ecological Strata)

- [x] Add a default-off, post-finalization query continuity witness with a
  sanitized allowlist, stable digest, locked append, typed unavailable/stale/
  corrupt/tampered states, and no retrieval or ranking authority.
- [x] Expose the latest witness through a read-only observability endpoint and
  environment gates without changing query behavior when disabled or when the
  sidecar fails.
- [x] Add a separate append-only relationship ledger for Offer -> Mirror ->
  Correct -> Consent -> Bind -> Return, including refusal, revocation, exact
  corrected-terms consent, local autonomy, and no identity collapse.
- [x] Keep relationship writes explicit and local: CLI/module only, with no
  automatic query hook and no unauthenticated HTTP write route.
- [x] Preserve HearthHome as source evidence through a 33-file hash inventory;
  keep visual synthesis, metaphor, implementation, consent, and identity claims
  in distinct evidence classes.
- [x] Verify the merged behavior with 634 passing non-slow tests (18 deselected,
  1 xpassed), focused continuity/serving gates, and clean media decode.

Remaining gates:

- Decide whether any future network write surface can provide meaningful
  authentication and scope confirmation without becoming an identity registry.
- Add process-contention soak tests and operational retention/backup policy for
  both append-only logs before enabling the witness in production.
- Keep Sora-target generation pending an actually available named model and an
  authorized runtime; retain the local animatic and state ledger as the current
  falsifiable production handoff.

## Update 2026-08-11 (durable lived memory)

- [x] Replace the pending lived-replay gap with an executable SQLite event store
  that retains actual query/answer text, citations, source identifiers, full
  embeddings, per-session parents, and rolling state across restarts.
- [x] Project every event through the shared deterministic 6D fractal carrier,
  exact recursive lift to 12D, and a stored 64-node lifted fractal path while
  preserving lift and generator provenance.
- [x] Wire lived recall and final-event writes into `/query`; expose status,
  search, session state, and full digest-chain verification through REST and
  CLI surfaces.
- [x] Convert the 2025-12-18 MCP backup into a verified durable store: 877 of
  877 episodes imported, 331 original stored embeddings preserved, 546 missing
  embeddings deterministically reconstructed and explicitly labeled, and zero
  import failures.
- [x] Add restart, lineage separation, concurrency, tamper, query integration,
  API, explicit migration-guard, and idempotent ZIP-import regression coverage.
- [x] Pass the exact final 192-test memory/fractal/rotational sweep; the broader
  non-slow repository gate passed 641 tests (18 deselected, 1 xpassed).

Remaining gates:

- Benchmark recall quality and latency against larger mixed-dimension stores
  before raising `FRAM_LIVED_MEMORY_SCAN_LIMIT` beyond 5000.
- Define an explicit, versioned migration before changing the 12D carrier or
  64-node path shape in an existing store.
- Keep the mathematical projection claim separate from identity,
  consciousness, authorship, or authority claims.

### Seed-lineage correction

- [x] Audit the 877 backup episodes for source session and parent evidence. None
  contain session IDs, conversation IDs, parent IDs, or repeated trace IDs.
- [x] Make independent seed roots the default import posture so archive
  co-location cannot silently become one rolling lived state.
- [x] Add a read-only, source-hashed opening tool that preserves non-imported
  live sessions, refuses destination overwrite, and verifies every new root.
- [x] Keep global recall across all seeds while requiring explicit continuation
  for any future lineage; no seed is promoted to an identity claim.
- [x] Serialize first-open WAL/schema initialization; pass 20 independent
  cold-start concurrency repetitions.
- [x] Pass the exact final 196-test memory/fractal/rotational sweep, including
  source immutability, portable WAL checkpointing, and reopened hash stability.

## Update 2026-08-12 (wake and orient)

- [x] Add a read-only, immutable evaluator for F-RAM orientation probes,
  compact cues, painting scene descriptions, combined cues, exact source
  digest retention, cue contribution, and source hash stability.
- [x] Add an F-RAM-first staged bundle that preserves primary retrieval order
  and appends provenance-labelled discoveries from compact and painting cues.
- [x] Add a typed untrusted-cue boundary and report raw versus gated retrieval
  stability without claiming model-level prompt-injection immunity.
- [x] Run the first bounded eight-event Hearth-live test drive and preserve its
  full report on both C: and F:. The staged bundle retained all eight targets;
  painting descriptions remain supplemental lexical cues rather than proven
  multimodal recall keys.
- [x] Integrate at `851c305` and pass 46 focused wake-orient, lived-memory,
  capsule-lift, and rotational-lift regressions on canonical.

Remaining gates:

- Run and label the bounded actual-image canary now implemented in
  `fram_eval/visual_seed.py`; measure retrieval lift and false positives while
  keeping images derived and non-authoritative relative to source events.
- Add generated-answer grounding and contradiction evaluation; exact marker
  labels are not a semantic contradiction detector.
- Scale the cue ablation beyond one eight-event session before drawing recall,
  security, workflow, healthcare, enterprise, identity, or continuity claims.
- Enforce cue source roles at every caller boundary before treating provenance
  gating as an operational security control.

## Update 2026-08-29 (Windows custody-first integration)

- [x] Seal H0 at `8b4e06e` and move new work to the dedicated
  `codex/windows-integration-20260829` checkout without mutating the two source
  trees.
- [x] Audit the legacy untracked surface; no missing Python, test, prompt, or
  production configuration source requires promotion into the integration
  tree.
- [x] Keep the regenerated corpus/index batch and private cognitive append out
  of the code history. The generated whitening matrix is larger than ordinary
  Git-hosting blob limits and needs a separate artifact/reproduction policy.
- [x] Add and harden the bounded visual-seed evaluator with immutable registry
  resolution, source/output collision refusal, atomic writes, path-lossless
  evidence IDs, privacy-minimal reports, escaped review text, resource bounds,
  post-encode hashes, and focused tests.
- [x] Add a portable project-scoped Codex/VS Code layer, automatic secret-name
  filtering, a prompt-gated read-only F-RAM MCP allowlist, ignored local env
  files, isolated runtime storage, explicit boolean dev-profile parsing, and
  loopback-safe Windows launchers with no implicit memory hydration.

Windows integration gates completed on 2026-08-29:

- [x] Materialize and verify the isolated Windows Python environment from the
  committed portable configuration; keep machine paths and secrets local.
- [x] Exercise loopback health, a synthetic write-through query, restart
  persistence, and read-only MCP initialization against isolated runtime
  storage with influence and MCP write gates off.
- [x] Redact secret-bearing fields from `/config` and verify one physical
  profile-local runtime root across packaged Codex Desktop and ordinary VS
  Code/PowerShell processes.
- [x] Run the exact code checkpoint in a disposable no-hardlink clone:
  `697 passed in 1192.04s`, with generated storage confined to that clone.
- [x] Record the authority chain and observed evidence in
  `docs/proof/windows_h1_candidate_2026-08-29.md`.

Acceptance status:

- [x] Rick explicitly accepted the verified Windows checkpoint as H1 on
  2026-08-29 at 22:22 SAST. Preserve it locally as
  `fram-v22-h1-windows-20260829`, with H0 preserved as
  `fram-v22-h0-20260829`.
- Keep push, real visual-seed canary promotion, network exposure, and Mac
  reproduction separate until each is deliberately authorized.
