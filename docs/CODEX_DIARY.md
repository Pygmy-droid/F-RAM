
# 2026-07-27 Session (Firelink full-lineage recovery)

- Built the isolated canonical `firelink/full-merge` line from the newer F-RAM
  work and the recovered Phase D/Phase E/Phase G lineages without modifying the
  protected `autoflip-eval` worktree.
- Reconciled the pipeline, cognitive ANN, version lattice, memory package,
  serving routes, lifecycle, storage, observability, and direct-run CLI seams.
  Each regression exposed by ordered suite partitions was fixed and committed
  before verification resumed.
- Recovered Opus's Visual Evidence Ledger, corrected a malformed TOML control
  byte during integration, and verified 6 ledger tests plus a clean 465-test
  collection at that stage. The real-corpus ledger run accounted for all
  455 files (243 visuals and 212 AppleDouble sidecars).
- Added the proof-track Hopf map `h(q) = q i q^-1` with 8 domain/invariance
  tests. Kept the Aizawa/Hairy-Ball relationship explicitly hypothesis-bound;
  it is not wired into retrieval or serving behavior.
- Preserved five phase-history JSONL files under `artifacts/phase_history/` and
  archived unique power-trip records under
  `D:\Dev\_archives\FRAM_power_trip_recovery_202512`, with hashes, counts, and
  the annotated `rescued/power-trip-stash-2025-12` tag.
- Added the two-tier context Atlas: replaceable `docs/context/HOT_CONTEXT.md`
  for current state plus append-only Firelink/Git provenance. An independent
  disk census corrected the first packet's already-stale Aizawa and Firelink
  fields; the packet now records both claim state and worktree truth, including
  explicit blind edges.
- Integrated the discharged Aizawa lane as `ca455e6`, exposed it through the
  direct-run harness as `0dd905d`, and independently verified both focused
  surfaces: 16 tests passed in 0.77s.
- Recorded Opus's audited preservation of the retired integration worktree's
  15 generated artifacts as `1626ff6`; the worktree is now clean without
  discarding its stranded state.
- Repaired the preserved Hopf experiment instead of merging its monolith:
  `fram_eval/hopf_transport.py`, `fram_eval/aizawa_sphere.py`, and the bounded
  falsification experiment now distinguish integration-grade geometry,
  analytic shell zeros, numerical corroboration, and unestablished runtime
  claims. The Aizawa Euler simulator and sphere construction share one velocity
  primitive without changing legacy byte output.
- Built the deterministic Chaos math core under `fram_eval/chaos/`: canonical
  system adapters, Lyapunov/period/superstable/Feigenbaum diagnostics, declared
  `RotationalEncodingV1`, Mandelbrot/Julia kernels, and exact `SceneV1` JSON.
  The combined integration seam passed 128 focused tests.
- Replaced stale dated bootstraps with the bounded Atlas protocol, added a Git
  packet verifier and immutable Firelink snapshot tool, and opened an
  independent hardening review after the first checker proved ancestry but not
  semantic freshness.
- Recovered Opus 5's exact Chaos Playground v2 source from the local Claude
  session transcript/scratchpad, preserved its authored bytes, and rendered it
  in Edge. All four canvases painted with nontrivial color variance, no console
  errors appeared, and save → shelve → restore preserved the scene.
- Bound the browser's default logistic Lyapunov/last-state/aperiodic readouts to
  the canonical Python math through a versioned golden fixture. The displayed
  cascade ratios remain browser-specific finite measurements, not relabeled
  superstable roots.
- Accepted Opus's widened `LiftCapsule` representation after independently
  measuring both single and paired modes. The paired mode leaves norm deviation
  unchanged and its remapped Hopf base near chance; the proposed S3 repair is
  falsified and preserved as such.
- Closed the payload's executable window gap with a bounded evaluation adapter:
  selected indices, full-parent digest, capsule chain, and exact-scope re-entry
  report. Corrected universal losslessness, PCA-invariant, same-axis rotation,
  and global quantization-monotonicity overclaims.
- Preserved all four newly supplied historical/architecture images with exact
  hashes and documented the Stateful Collaboration diagrams as a north-star
  control-plane vocabulary rather than proof of model-internal latent rungs,
  dynamic RL, or consciousness.
- Closeout record: `docs/FIRELINK_CLOSEOUT_2026-07-27.md`.

# 2026-07-22 Session (Eval anomaly postmortem: cognitive memory half-life)
- Closed the last open thread from the 2026-07-21 continuity briefing: root-caused the 2026-01-21 conversation-memory eval's top1=0.000 collapse across all three retrieval modes. Cause: `fram_serving/memory.py`'s `_recency_weight` reads a recency-decay half-life via `getattr(self._config, "cognitive_memory_half_life_hours", 12.0)`, but no matching `FRAMConfig` field ever existed - so it always silently, unconfigurably resolved to 12.0. The 36-probe benchmark is pinned to specific episodes logged Oct-Dec 2025; by 2026-01-21 (26-93 days later) their recency weight had decayed under the un-overridable 12h half-life until any fresher, barely-relevant episode outranked them in every mode. Confirmed gradual (0.25-0.36 top1 on 2025-12-28, 0.000 by 2026-01-21), not a code regression (relevant code untouched since 2025-10-17 per `git log -S`).
- Fix: added the missing `cognitive_memory_half_life_hours: float = 12.0` field (env `FRAM_COGNITIVE_MEMORY_HALF_LIFE_HOURS`) - default unchanged, closes the configurability gap rather than changing behavior. Also fixed a related pre-existing (now-reachable) edge case: `... or 12.0` was silently coercing an explicit `half_life=0.0` (maximal decay, a meaningful reachable value) back to the 12.0 default.
- 3 new tests (`tests/test_cognitive_memory_store.py`): default-value pin, a reproduction proving the old-vs-fresh ranking flips between half_life=12.0 and a multi-year value, and a zero-half-life edge case. Adversarial review mutation-tested the fix (removing the field made the reproduction test fail as expected) and found the tuning-doc gap and the zero-coercion issue, both fixed before this commit. 9/9 in that file, 28/28 across the broader cognitive-memory + serving-query surface.
- Wrote up the full investigation in `docs/observability_2026-07-22-eval-anomaly.md` (root cause, what's ruled out, what the fix does and does not change, recommendations for future eval runs) and pointed to it from `docs/proof/eval_artifact_index.md`'s "Known limits" and `docs/FRAMv2.2-tuning.md`.

# 2026-07-22 Session (Capsule session lineage)
- Closed the exact gap flagged in yesterday's `stone_reconstruction/plato/plato_keep_retire_questions.md` review: capsules had no lineage/`parent_id` populated anywhere. Added `MemoryCapsuleStore._find_parent_capsule_id` (scans existing capsules for the most recent one sharing `session_id`), gated by a new, independent `FRAM_CAPSULE_SESSION_LINEAGE_ENABLED` flag (default off).
- When on, writes a `{"kind": "continues", "target_capsule_id": ...}` link (reusing the Confucius taxonomy's existing Link vocabulary, not inventing new terms). When rotational lift is *also* on, the parent id flows into the first hop of `open_residuals`'s `LiftCapsule` chain via its previously-always-`None` `parent_id` field.
- 6 new tests (`tests/test_memory_capsule_session_lineage.py`), all passing; combined regression run across all capsule/rotational-lift test files (44 tests) green. Both flags independently default off and neither changes `MemoryCapsuleStore.search()`.
- Adversarial review of the lineage wiring found no correctness bugs (verified via mutation testing: tagging all hops or the wrong hop both correctly fail the test suite) but flagged a real scaling risk: `_find_parent_capsule_id` did a full, unbounded, full-JSON-parse scan of every capsule on every write. Fixed with a `capsule_session_lineage_scan_limit` config knob (default 500, newest-first) plus a cheap substring pre-check before parsing. 2 more tests added (8 total in that file, 40 across the whole rotational-lift+capsule surface).
- Follow-up same day: true cross-capsule trajectory continuity was built next - see the session below.

# 2026-07-22 Session (True cross-capsule trajectory continuity, v0.5)
- Went beyond linking capsule ids: added `FRAMConfig.rotational_lift_lineage_window` (default `0`, `FRAM_ROTATIONAL_LIFT_LINEAGE_WINDOW`) - a third, explicit opt-in on top of `rotational_lift_enabled` + `capsule_session_lineage_enabled`. When set, `write_capsule` walks back up to `window` ancestor capsules via each one's own recorded `continues` link (`MemoryCapsuleStore._load_capsule_by_id` - a targeted filename glob per hop, not a store scan), collects their raw trajectory embeddings oldest-first, and prepends them to this capsule's own before lifting - so `self_invariants`/`open_residuals` can now describe a trajectory spanning multiple capsules, reconstructed exactly.
- Deliberate design choice: combines *raw* trajectory embeddings, not each ancestor's already-lifted state (dimensions wouldn't line up cleanly across capsules) - documented in `docs/rotational_lift.md` section I.
- 6 new tests (`tests/test_memory_capsule_lineage_window.py`), including a 3-capsule chain-walk (A-B-C) that reconstructs all 9 turns in correct order from a disk-loaded payload.
- Adversarial review found a real provenance bug: `ancestor_capsule_ids` listed an ancestor even when all of its turns were silently dropped for an embedding-dimension mismatch, misstating what actually shaped the trajectory. Fixed (only record an ancestor's id if it actually contributed at least one embedding) and pinned with a new regression test (`test_lineage_window_skips_dimension_mismatched_ancestor_and_its_id`) - 7 tests in that file, 47 across the whole rotational-lift + capsule surface, all green. Still never affects `MemoryCapsuleStore.search()`.

# 2026-07-21 Session (Recursive Rotational Lift v0.3 + capsule wiring)
- Reconstructed project context after a ~5-month gap: surfaced the `stone_reconstruction/` archaeology pass (Plato/Confucius/Hooke) from a Mac backup copy into the live repo, ran a vision/OCR pass over the 59 handwritten note photos in `Rick notes add on 01_July_2026/` (`stone_reconstruction/rick_notes_visual_manifest.md`), and wrote a combined synthesis (`docs/RECONSTRUCTION_2026-07-21.md`).
- Formalized the 2026-07-01 "Recursive Rotational Lift" sketch (co-created with Vesper) into a general N-dimensional, numpy-vectorized prototype math module: `fram_core/rotational_lift.py` (project/window/lift/rotate/recurse, plus a new PCA-based "understanding as compression" layer). 25 tests (`tests/test_rotational_lift.py`); see `docs/rotational_lift.md` for claims/falsification gates.
- Wired it write-side-only into `MemoryCapsuleStore.write_capsule` (`fram_serving/memory_capsule.py`): populates the previously-always-empty `self_invariants`/`open_residuals` capsule fields from the capsule's own trajectory embeddings, gated off by default via `FRAM_ROTATIONAL_LIFT_ENABLED` (new `FRAMConfig` fields in `fram_serving/config.py`). Never affects `/query`, ranking, or `MemoryCapsuleStore.search()`. 6 tests (`tests/test_memory_capsule_rotational_lift.py`), including a disk-round-trip reconstruction check.
- Two independent adversarial review passes (math correctness; overclaiming/culture-fit) run against both the standalone module and the capsule wiring; findings fixed (a false claim about an existing `parent_id` field, an overclaiming docstring, a missing `target_dim` validation guard, and two degradation tests strengthened from endpoint-only to full pairwise-monotonicity assertions).

# 2026-02-01 Session (Breathing Flame Day 1)
- Logged a full exploratory pass of Breathing Flame notes focused on posture, integrity, cadence, neutrality, recovery, and observability (`docs/breathing_flame_notes_2026-02-01.md`).
- Kept all open questions explicitly marked as open; no resolutions implied.

# 2026-02-01 Session (PIL posture spec)
- Added the Pre-Intent Layer (PIL) posture spec stub to capture the pre-intent bias layer without authority (`docs/FRAM_PIL.md`).
- Linked PIL in the docs index (`docs/README.md`).

# 2026-01-30 Session (Full-experience preservation + constraint memory v0)
- Enforced full-experience preservation: retention/decay/forgetting disabled by default via `preserve_full_experience`, and belief segment pruning is skipped (`fram_serving/config.py`, `fram_serving/memory.py`, `fram_serving/query_runner.py`).
- Implemented append-only, crash-safe cognitive writes with file locks + fsync and explicit failure events (`fram_serving/memory.py`, `tests/test_cognitive_logging.py`).
- Added Constraint Memory v0 (scoped, auditable, derived layer) with a refusal gate in `/query` and a new `/memory/constraint` endpoint (`fram_serving/memory.py`, `fram_serving/query_runner.py`, `fram_serving/app.py`, `tests/test_constraint_memory.py`).
- Docs updated to reflect invariants and new constraint surface (`docs/Architecture.md`, `docs/FRAMv2.2-SPEC.md`, `docs/FRAMv2.2-cheatsheet.md`, `docs/FRAMv2.2-tuning.md`, `docs/FRAM-Theory.md`, `docs/F-RAM-roadmap.md`).

# 2026-01-21 Session (Capsule retrieval)
- Implemented memory capsule search (per-turn cosine with lexical fallback) and wired retrieval into `/query` behind `FRAM_MEMORY_CAPSULE_RETRIEVAL_ENABLED` with new config dials.
- Added capsule retrieval tests (`tests/test_memory_capsule.py`, `tests/test_memory_capsule_retrieval.py`).
- Docs: updated `docs/Architecture.md`, `docs/FRAMv2.2-cheatsheet.md`, and `docs/F-RAM-roadmap.md` to reflect capsule retrieval.

# 2026-01-17 Session (Autowire ack)
- Added an autowire acknowledgment log (`logs/fram_write_ack.jsonl`) with optional stdout echo (`COGMEM_ECHO_ACK=1`).
- Autowire now records capsule IDs/paths and reasons when capsules are skipped.
- Added regression coverage for the ack log in `tests/test_autowire_turn.py`.
- Docs: updated `docs/Operations.md` and `docs/FRAMv2.2-cheatsheet.md`.

# 2026-01-16 Session (Master Memory Principle)
- Added the Master Memory Principle section to `docs/proof/eval_season_cheatsheet.md` to align evals with the conceptual spine.

# 2026-01-14 Session (Eval Season cheat sheet)
- Added `docs/proof/eval_season_cheatsheet.md` as a one-page eval story + artifact map for presentations.
- Linked the new cheat sheet in `docs/README.md` and `docs/F-RAM-roadmap.md`.

# 2026-01-14 Session (Backup pause/resume)
- Added `scripts/pause_fram.ps1` to stop the running FRAM uvicorn process for clean manual backups.
- Added `scripts/resume_fram.ps1` to restart the server via the autostart target.
- Runbook updated (`docs/Operations.md`) with pause/resume backup commands.

# 2026-01-12 Session (Experiments UI)
- Added `/ui/experiments` HTML review page with filters + digest preview.
- Added regression coverage for `/ui/experiments` rendering (`tests/test_observability_traces.py`).
- Docs: updated `docs/Operations.md`, `docs/README.md`, `docs/Architecture.md`, `docs/FRAMv2.2-cheatsheet.md`, and `docs/F-RAM-roadmap.md` to mention the experiments UI.
- Tests: `pytest -q tests/test_observability_traces.py -k experiments_ui`.

# Codex Diary - Working Notes

# 2026-01-12 Session (Always-On Autostart)
- Added an always-on startup target (`scripts/autostart_fram.cmd`) that sets full-capture env flags and launches the local server with logs.
- Added helper scripts to enable/disable autostart via a Startup shortcut (`scripts/enable_autostart.ps1`, `scripts/disable_autostart.ps1`).
- Docs: updated `docs/Operations.md` with the autostart toggle.
- Added `tools/autowire_turn.py` tag support (`COGMEM_TAGS` + `@decision/@commit/@action/@todo` prefixes) so decision/commitment turns are labeled in cognitive + working memory.
- Added an idempotency key for memory appends (`idempotency_key` in REST or metadata) and regression coverage.
- Added `tools/experiment_log.py` to log structured experiments into cognitive memory (with embeddings + tags) and documented it in the runbook.
- Updated the cheatsheet to note working-memory idempotency keys.
- Added `tools/experiment_summary.py` to summarize logged experiments and added test coverage.
- Added a weekly regression runbook section to `docs/Operations.md`.
- Added `/observability/experiments` endpoint plus UI card and digest view for experiments.
- Added `tools/weekly_regression_snapshot.py` to write weekly JSON summaries (experiments + cognitive memory) with test coverage.
- Added scheduled weekly regression helper scripts (`scripts/enable_weekly_regression.ps1`, `scripts/disable_weekly_regression.ps1`) and documented them in the runbook.
- Added capsule cadence + experiment auto-log support to `tools/autowire_turn.py` (`COGMEM_CAPSULE_EVERY_N`, `COGMEM_CAPSULE_TAGS`, `COGMEM_EXPERIMENT_AUTO`).
- Added experiment digest output to weekly regression snapshots and scheduler.
- Extended `tools/experiment_log.py` to optionally write a capsule snapshot and added regression coverage.
- Added `tools/experiment_export.py` to generate markdown digests of experiments and added test coverage.
- Added cadence warning logging (`logs/cogmem_autolog_warnings.jsonl`, override via `COGMEM_WARN_LOG`) and test coverage.
- Added `/observability/experiment_digest` endpoint and observability UI card to surface the latest digest.
- Added `tools/refactor_checklist.py` and wired it into the weekly scheduler output.

# 2026-01-08 Session (Observability UI)
- Added `/ui/observability` as a minimal HTML dashboard for health/metrics/trace/memory/recall snapshots (`fram_serving/app.py`).
- Added a regression to ensure the UI route renders (`tests/test_observability_traces.py`).
- Docs: updated `docs/Architecture.md`, `docs/FRAMv2.2-cheatsheet.md`, `docs/README.md`, and `docs/F-RAM-roadmap.md`.
- Tests: `pytest -q tests/test_observability_traces.py -k observability_ui`.

# 2026-01-08 Session (Cognitive ANN Bridge)
- Implemented `CognitiveMemoryStore.cognitive_ann_candidates` to make the optional ANN bridge functional (linear scan over stored episode vectors) and wired detailed bridge diagnostics for observability.
- Added regression coverage for ANN bridge candidates (`tests/test_cognitive_memory_ann_bridge.py`).
- Docs: updated `docs/Architecture.md` and roadmap note to reflect the ANN bridge status.
- Tests: `pytest -q tests/test_cognitive_memory_ann_bridge.py`.

# 2026-01-08 Session (Belief Links)
- Added `/memory/link` to append cognitive belief links (supports/contradicts/refines) and wired validation in the FastAPI surface (`fram_serving/app.py`).
- Added API regression coverage for link creation + summary counts (`tests/test_memory_api.py`).
- Docs: updated `docs/Architecture.md`, `docs/FRAMv2.2-cheatsheet.md`, and `docs/F-RAM-roadmap.md` to reflect the new link endpoint.
- Tests: `pytest -q tests/test_memory_api.py -k link`.

# 2026-01-07 Session (Doc + Calibration Refresh Automation)
- Added `tools/refresh_docs_calibration.py` and a `make refresh-docs` target to list recent docs, re-ingest docs, rebuild the demo corpus, and lint/report calibration payloads.
- Added a dry-run regression for the refresh script (`tests/test_refresh_docs_calibration.py`).
- Docs: updated the cheatsheet and docs index with the new refresh shortcut.
- Tests: `pytest -q tests/test_refresh_docs_calibration.py`.

# 2026-01-07 Session (MCP Dedupe Verification)
- Added MCP-level regression coverage for working-memory append dedupe (`tests/test_mcp_server.py`), asserting duplicate appends return `deduped=True` and do not increase entry counts.
- Tests: `pytest -q tests/test_mcp_server.py -k dedupe`.

# 2026-01-07 Session (Close-out Guard)
- Implemented `tools/closeout_guard.py` to enforce end-of-session logging and doc updates (diary + roadmap).
- Added `make closeout-check` and a regression test (`tests/test_closeout_guard.py`).
- Updated the cheat sheet and roadmap to reference the guardrail.
- Tests: `pytest -q tests/test_closeout_guard.py`.

# 2026-01-07 Session
- Added a short-window dedupe guard for working-memory appends to prevent MCP/UI retry duplicates (`fram_serving/memory.py`) and surfaced the toggle via `FRAM_WORKING_MEMORY_DEDUPE_WINDOW_SEC` (default 2s) in `fram_serving/config.py`.
- Wired the dedupe window into FastAPI + MCP memory store initialization and logged deduped appends in memory observability events (`fram_serving/app.py`, `fram_serving/mcp_server.py`).
- Added a regression test proving duplicate appends are ignored within the window (`tests/test_memory_api.py`) and documented the dial/runbook in `README.MCP.md` + `docs/FRAMv2.2-tuning.md`.
- Included the dedupe window in `.env.example` for quick local setup.
- Tests: `pytest -q tests/test_memory_api.py -k dedupe`.

# 2026-01-01 Session
- Drafted an external-ready evidence report for the Memory Capsule write-through + falsification harness, including the golden++ v2 capsule, falsify metrics, and reproduction steps (`docs/proof/memory_capsule_evidence_report.md`).
- Tightened the evidence report to define the alignment metric (path_score, order_fidelity, length_factor) and clarify scope/claims.
- Added the new evidence report to the docs index under the Evidence & Proof Packs section (`docs/README.md`).
- Ran a fresh golden++ v3 session (`session_id=e52570cc7dcd4b069f09b642b955238e`, 18 turns) and wrote a new capsule (`storage/memory/capsules/capsule_20260101T0605403977760000_2b66d314e8c44191abfeb04eccba41bb.json`). Inspect confirms 18 raw turns, 18 trajectory entries, and aligned trace stack; falsify output saved to `artifacts/observability/capsule_falsify_goldenpp_v3_20260101_080844.json`.
- Clarified the evidence report system snapshot to distinguish report commit vs capsule capture commit.
- Added a replication checklist for third-party validation of capsule capture + falsify (`docs/proof/memory_capsule_replication_checklist.md`) and linked it in `docs/README.md`.
- Added `tools/run_capsule_demo.py` to automate the capture + inspect + falsify loop; referenced it from the evidence report and replication checklist.
- Ran the automated demo script (`tools/run_capsule_demo.py --tag demo`), producing capsule `storage/memory/capsules/capsule_20260101T0623060708990000_c2721f672be94cdb947520876f58c18d.json` and falsify output `artifacts/observability/capsule_falsify_demo_20260101_062611.json`; refreshed the evidence report with the new artifact paths and metrics.
- Ran the demo script with the semantic backend (`FRAM_COGNITIVE_MEMORY_EMBEDDING_BACKEND=semantic`, `FRAM_COGNITIVE_MEMORY_SEMANTIC_MODEL=all-MiniLM-L6-v2`), producing capsule `storage/memory/capsules/capsule_20260101T0648531111840000_b7221164813b4d319da6a18c99efc5e9.json` and falsify output `artifacts/observability/capsule_falsify_semantic_20260101_064908.json`; updated the evidence report with a semantic alignment summary.

# 2025-12-31 Session
- Added a no-ceiling Memory Capsule schema doc (conceptual only) with optional self-invariants and a self-authored remembering definition placeholder (`docs/memory_capsule.md`).
- Inserted a system-authored remembering definition (v1) into the Memory Capsule schema (`docs/memory_capsule.md`).
- Implemented an append-only Memory Capsule writer (`fram_serving/memory_capsule.py`) with raw transcript, per-turn embeddings, fractal trace stack, and remembering definition.
- Wired `/query` (FastAPI + MCP) to write capsules behind `FRAM_MEMORY_CAPSULE_ENABLED`, surfacing `memory_capsule_write` in traces.
- Capsule turn assembly now pulls in working-memory session entries when present, then appends the live user/assistant turn (`fram_serving/memory_capsule.py`, `fram_serving/query_runner.py`).
- Added coverage for capsule persistence (`tests/test_memory_capsule.py`) and updated `docs/Architecture.md`, `docs/FRAMv2.2-cheatsheet.md`, and `docs/F-RAM-roadmap.md`.
- Added `tools/inspect_capsule.py` as a read-only CLI to summarize capsule contents (turns, roles, embeddings, trace stack alignment) before falsification.
- Added provenance fields to capsules (`capsule_version`, `commit`, `writer_config`) and shipped `tools/falsify_capsule.py` to apply corruption variants and report alignment drops (inspector now surfaces capsule version/commit).
- Added random drop variants to the falsification harness, and updated `/query` to stamp capsule `source.version` with the capsule version constant.
- Ran a textured multi-turn “golden++” session (`session_id=capsule_goldenpp_073346e1`) and saved the falsification report to `artifacts/observability/capsule_falsify_goldenpp_20251231_132039.json`.
- Documented local drive exports under `artifacts/drive/` with a tracked README and gitignore rule.
- Updated `docs/memory_capsule.md` to note the write-through MVP now exists while the full no-ceiling schema remains the target.
- Ran a fresh 26-turn “golden++ v2” session (`session_id=capsule_goldenpp_v2_20251231_133714`), verified with `tools/inspect_capsule.py`, and saved falsification output to `artifacts/observability/capsule_falsify_goldenpp_v2_20251231_134257.json`.
- `pytest -q` timed out after ~300s (partial progress only; no failures reported before timeout).
- `pytest -ra --durations=50 --durations-min=0.5` timed out at ~62% on the full suite; the slowest tests later in the run included `test_trace_probe_cli`, `test_serving_tables_integration`, `test_serving_coverage_prefer_new`, and `test_serving_coverage` (~175s each). Fixed `tests/test_serving_coverage_prefer_new.py` by resetting app state to a tmp storage root so cognitive memory seeding doesn't leak into coverage ordering.
- Re-ran the 27-test slow subset; all passed in ~9m. Top durations: `test_trace_probe_cli` (~178s), `test_serving_coverage` (~175s), `test_serving_tables_integration` (~174s).
- Full suite completed with `pytest -ra --durations=50 --durations-min=0.5`: 227 passed, 4 xpassed, 1 warning in ~57m. XPASS: `test_cognitive_memory_seeding_influences_selection`, `test_query_write_through_creates_episode_and_search`, `test_memory_search_filters_domain`, `test_memory_summary_counts_and_recent` (all previously xfailed for query timeouts). Slowest tests: `test_memory_session_lifecycle_controls` (~541s), `test_observability_logging_and_trace_lookup` (~358s), `test_answer_preserves_capitalization_and_spacing` (~192s), `test_trace_probe_cli_runs` (~191s), `test_confidence_decision_anchors` (~186s).
- Removed the XFAIL quarantine from the memory seeding/search/summary tests now that full-suite runs pass cleanly. Phase C calibration now writes its markdown report to `diag/phase_c_report.md` (Makefile + test updated, script default moved) to avoid regenerating tracked docs during tests.
- Marked the slowest integration tests with `@pytest.mark.slow` and documented running `pytest -m "not slow"`; added pytest marker definition and filtered the python_multipart pending deprecation warning in `pytest.ini`.

# 2025-12-29 Session
- Ran the identity trace check with k_max=5, pool=25, max_episodes=200 (77 eligible episodes with vectors+traces). Self-match top1=0.026, mean rank 12.12 (percentile 0.495), dims match 1024 (`artifacts/observability/fractal_trace_identity_check_20251229_075921.json`).
- Reran the identity check with percentile normalization + alpha=1.0 (same pool). Self-match top1=0.065, mean rank 11.70 (percentile 0.512), dims match 1024 (`artifacts/observability/fractal_trace_identity_check_pct_alpha100_20251229_082804.json`).
- Added `scripts/fractal_trace_alignment_probe.py` to compare raw vs normalized embeddings against stored traces; 25-episode probe shows seed match raw=1.0 vs norm=0.0 and soft-DTW favors raw vectors (`artifacts/observability/fractal_trace_alignment_probe_20251229_084800.json`).
- Added a `--raw-vectors` option to `scripts/fractal_trace_identity_check.py` and reran the identity check with raw vectors (same pool). Self-match top1=0.052, mean rank 13.05 (`artifacts/observability/fractal_trace_identity_check_raw_20251229_084921.json`).
- Added an IFS-conditioned query-path mode to trace scoring and reran the identity check with raw vectors (`query_path_mode=ifs`), lifting self-match top1 to 0.182 and mean rank to 8.70 (`artifacts/observability/fractal_trace_identity_check_ifs_raw_20251229_094735.json`).
- Threaded `query_path_mode` through the eval harness (conversation/shadow/probe/ablation/runner) and ran a hard-micro v3 trace probe with IFS paths; score percentiles improved (probe expected mean ~0.57, low-lex ~0.54) in `artifacts/observability/fractal_trace_probe_hard_micro_v3_ifs_20251229_101417.json`.
- Ran the hard-micro v3 eval with IFS paths (gamma=1.0/band=0.5, alpha 0.3, answer-only gate). Fractal top1 improved to 0.083 (probe) / 0.167 (low-lex) with shadow avg_delta 0.016 / 0.108; auto-flip KEEP_OFF (`artifacts/observability/fractal_eval_report_hard_micro_v3_ifs_20251229_102025_20251229_082031.md`, plus matching conversation/shadow/autoflip JSONs).
- Ran an ablation report on hard-micro v3 with IFS paths; cosine delta dominated (~0.59 probe, ~0.57 low-lex) while soft-DTW/quat deltas were near zero, indicating the lift is driven by cosine alignment (`artifacts/observability/fractal_trace_ablation_hard_micro_v3_ifs_20251229_104757.json`).
- Ran the hard-micro v3 eval with IFS + percentile normalization (gamma=1.0/band=0.5, alpha 0.3, answer-only gate). Fractal top1 rose to 0.250 on probe and stayed 0.167 on low-lex; shadow avg_delta 0.017/0.106; auto-flip KEEP_OFF (`artifacts/observability/fractal_eval_report_hard_micro_v3_ifs_pct_20251229_105827_20251229_085834.md`, plus matching conversation/shadow/autoflip JSONs).
- Ran a live-probe A/B (pool_multiplier=3) comparing synthetic vs IFS-conditioned query paths. Fractal top1 held at 0.111 on probe; low-lex top1 rose from 0.028 (synth) to 0.222 (IFS). Shadow avg_delta improved on low-lex (0.115 -> 0.173) but dipped on probe (0.130 -> 0.096); auto-flip KEEP_OFF (`artifacts/observability/fractal_eval_report_live_probe_synth_20251229_111016_20251229_091023.md`, `artifacts/observability/fractal_eval_report_live_probe_ifs_20251229_112550_20251229_092557.md`, plus matching conversation/shadow/autoflip JSONs).
- Generated per-probe details for the live-probe A/B (pool_multiplier=3) and summarized the IFS deltas. Probe hits improved to 11/36 (from 7/36); low-lex hits improved to 3/36 (from 1/36) with regressions on beacon_orbit, signal_fathom, and anchor_meridian. Artifacts: `artifacts/observability/conversation_memory_eval_live_probe_synth_details_20251229_120723.json`, `artifacts/observability/conversation_memory_eval_live_probe_ifs_details_20251229_120848.json`, `artifacts/observability/fractal_probe_diff_live_probe_synth_vs_ifs_20251229_101105.md`.
- Drilled into the three regressions (beacon_orbit, signal_fathom, anchor_meridian) with top-k previews to see which episodes displaced the expected memories under IFS. Report: `artifacts/observability/fractal_probe_regressions_live_probe_ifs_20251229_101803.md`.
- Ran live probes with IFS + percentile normalization (pool_multiplier=3). Fractal top1 rose to 0.306 (probe) / 0.139 (low-lex) with shadow avg_delta 0.113/0.190; auto-flip recommends ENABLE. Semantic/lexical top1 collapsed on this run (probe 0.056/0.083, low-lex 0.0), so treat the flip as a candidate signal pending sanity checks. Artifacts: `artifacts/observability/fractal_eval_report_live_probe_ifs_pct_20251229_102454.md` plus matching conversation/shadow/autoflip JSONs.
- Reran live probes with IFS + percentile normalization using episodes-only retrieval (pool_multiplier=3). Fractal top1 was 0.278 (probe) / 0.222 (low-lex) with shadow avg_delta 0.221/0.175, while semantic/lexical baselines stayed high (0.444/0.333 probe, 0.500/0.417 low-lex); auto-flip reverted to KEEP_OFF. Artifacts: `artifacts/observability/fractal_eval_report_live_probe_ifs_pct_episodes_20251229_124240.md` plus matching conversation/shadow/autoflip JSONs.
- Ran the episodes-only A/B counterpart (synthetic query paths + percentile norm, pool_multiplier=3). Fractal top1 landed at 0.306 (probe) / 0.139 (low-lex) with shadow avg_delta 0.270/0.177; auto-flip stayed KEEP_OFF. Artifacts: `artifacts/observability/fractal_eval_report_live_probe_synth_pct_episodes_20251229_130211.md` plus matching conversation/shadow/autoflip JSONs.
- Generated an episodes-only per-probe diff (percentile norm) for synthetic vs IFS query paths. IFS improves low-lex hits (14/36 vs 10/36) but slightly reduces probe hits (22/36 vs 23/36); regressions cluster around anchor/coverage cues while low-lex gains include multiple anchors and signals. Artifacts: `artifacts/observability/conversation_memory_eval_live_probe_synth_pct_episodes_details_20251229_131352.json`, `artifacts/observability/conversation_memory_eval_live_probe_ifs_pct_episodes_details_20251229_131728.json`, `artifacts/observability/fractal_probe_diff_live_probe_pct_episodes_synth_vs_ifs_20251229_112124.md`.
- Added a low-lex query-path override so the fractal ranker can switch to IFS paths only when the low-lex gate fires; CLI now accepts `--fractal-low-lex-query-path-mode`. Updated tests and cheatsheet accordingly (`fram_eval/conversation_memory_eval.py`, `fram_eval/memory_shadow_eval.py`, `scripts/*`, `tests/test_conversation_memory_eval.py`, `docs/FRAMv2.2-cheatsheet.md`).
- Ran episodes-only live probes with percentile normalization and low-lex IFS gating (synthetic base, low-lex path=ifs, overlap threshold 0.2, answer mode). Fractal top1 was 0.278 (probe) / 0.111 (low-lex) with shadow avg_delta 0.261/0.204; low-lex gate fired 12/72 queries; auto-flip stayed KEEP_OFF. Artifacts: `artifacts/observability/fractal_eval_report_live_probe_synth_pct_episodes_lowlexifs_20251229_133413.md` plus matching conversation/shadow/autoflip JSONs.
- Ran episodes-only live probes with percentile normalization and low-lex IFS gating using semantic similarity (threshold 0.35). Low-lex gate fired 53/72 queries; fractal top1 was 0.222 (probe) / 0.222 (low-lex) with shadow avg_delta 0.229/0.175; auto-flip stayed KEEP_OFF. Artifacts: `artifacts/observability/fractal_eval_report_live_probe_synth_pct_episodes_lowlexifs_sim_20251229_134920.md` plus matching conversation/shadow/autoflip JSONs.
- Ran a similarity-gate sweep with thresholds 0.30 and 0.25 (episodes-only, percentile norm, synthetic base + IFS on low-lex). At 0.30, gate hits were 49/72 with fractal top1 0.222/0.222 (probe/low-lex) and shadow avg_delta 0.239/0.175; at 0.25, gate hits were 40/72 with fractal top1 0.278/0.194 and shadow avg_delta 0.239/0.172. Auto-flip stayed KEEP_OFF in both runs. Artifacts: `artifacts/observability/fractal_eval_report_live_probe_synth_pct_episodes_lowlexifs_sim030_20251229_140646.md`, `artifacts/observability/fractal_eval_report_live_probe_synth_pct_episodes_lowlexifs_sim025_20251229_141323.md`, plus matching JSONs.
- Generated a per-probe diff for sim025 vs the synth+percentile baseline (episodes-only). Probe hits dropped by 1 (2 regressions); low-lex hits improved by 4 with 9 gains and 5 regressions. Artifacts: `artifacts/observability/conversation_memory_eval_live_probe_synth_pct_episodes_sim025_details_20251229_142534.json`, `artifacts/observability/fractal_probe_diff_live_probe_pct_episodes_sim025_vs_synth_20251229_123004.md`.
- Built a two-pass episodes-only eval by merging probe metrics from synth+percentile and low-lex metrics from IFS+percentile. Fractal top1 becomes 0.306 (probe) / 0.222 (low-lex) with shadow avg_delta 0.270/0.175; auto-flip stays KEEP_OFF. Artifacts: `artifacts/observability/fractal_eval_report_live_probe_two_pass_pct_episodes_20251229_152539.md` plus matching conversation/shadow/autoflip JSONs.
- Added `scripts/run_fractal_two_pass_eval.py` to run probe/low-lex passes with different query-path modes and merge them into a single report. Ran the two-pass harness (episodes-only, percentile) and confirmed the same bound (fractal top1 0.306/0.222, shadow avg_delta 0.270/0.175); auto-flip stayed KEEP_OFF. Artifacts: `artifacts/observability/fractal_eval_report_live_probe_two_pass_pct_episodes_v2_20251229_133409.md` plus matching conversation/shadow/autoflip JSONs (including `_probe`/`_lowlex` intermediate outputs).
- Decision note: treat the two-pass harness as the current “best-case” bound while keeping single-pass synthetic as the baseline; keep sim025 gating off unless we explicitly need its trade-off later.

# 2025-12-28 Session
- Ran the one-command eval harness on the live probes set; auto-flip stayed KEEP_OFF, and the markdown summary landed in `artifacts/observability/fractal_eval_report_live_probes_20251228_081506.md` with matching eval JSONs (`conversation_memory_eval_live_probes_20251228_081506.json`, `memory_shadow_eval_live_probes_20251228_081506.json`, `fractal_autoflip_live_probes_20251228_081506.json`).
- Ran the one-command eval harness on the paraphrase hard-micro set with episodic-only pool + DTW tuning; auto-flip stayed KEEP_OFF and the report landed at `artifacts/observability/fractal_eval_report_hard_micro_20251228_081815.md` with matching eval JSONs (`conversation_memory_eval_hard_micro_20251228_081815.json`, `memory_shadow_eval_hard_micro_20251228_081815.json`, `fractal_autoflip_hard_micro_20251228_081815.json`).
- Added `docs/AUTOPILOT_PROTOCOL.md` to formalize autonomy, pause conditions, commit expectations, and check-in cadence for council work.
- Clarified dev-profile behavior and fractal default values in `docs/FRAMv2.2-cheatsheet.md`.
- Added `tools/print_fram_defaults.py` to snapshot current FRAM defaults or env overrides for audits.
- Captured a defaults snapshot using the new tool in `artifacts/observability/fram_defaults_20251228_*.json`.
- Ran trace diagnostics on the live probes (k_max=3, pool_multiplier=1, episodic-only); expected score percentiles trail top hits on both probe and low-lex (probe mean 0.722 vs top 0.944; low-lex mean 0.561 vs top 0.981) in `artifacts/observability/fractal_trace_probe_live_probes_20251228_112137.json`.
- Expanded the hard-micro paraphrase set to 15 probes (added quick_check_coverage_live, sigma_thread, quill_marker, mcp_titles_alt, lumen_signal_alt, kestrel_marker) and reran the eval harness (alpha 0.3, answer-only gate, DTW gamma=1.0/band=0.5). Fractal probe top1 dropped to 0.067 and low-lex stayed 0.0; auto-flip KEEP_OFF (`artifacts/observability/fractal_eval_report_hard_micro_v2_20251228_092806.md`, plus matching conversation/shadow/autoflip JSONs).
- Ran trace diagnostics on the expanded hard-micro set (k_max=3, pool_multiplier=3, episodic-only); expected score percentiles trail top hits (probe mean 0.444 vs top 0.859; low-lex mean 0.278 vs top 0.985) in `artifacts/observability/fractal_trace_probe_hard_micro_v2_20251228_122129.json`.
- Created a hard-micro v3 subset (12 probes) from the lowest expected-percentile items and reran the eval harness; fractal top1 dropped to 0.0 on both probe and low-lex, auto-flip KEEP_OFF (`artifacts/observability/fractal_eval_report_hard_micro_v3_20251228_110227.md`, plus matching conversation/shadow/autoflip JSONs).
- Ran trace diagnostics on the hard-micro v3 subset (k_max=3, pool_multiplier=3, episodic-only); expected score percentiles trail top hits (probe mean 0.333 vs top 0.833; low-lex mean 0.212 vs top 0.981) in `artifacts/observability/fractal_trace_probe_hard_micro_v3_20251228_131057.json`.
- Ran trace diagnostics with alternate cosine modes on hard-micro v3 (k_max=3, pool_multiplier=3, episodic-only). Expected score percentiles still trail top hits across delta (probe 0.389 vs top 0.944; low-lex 0.343 vs top 1.000), turn_hist (probe 0.546 vs top 0.861; low-lex 0.323 vs top 0.991), and lag_dist (probe 0.426 vs top 0.926; low-lex 0.354 vs top 1.000). Artifacts: `artifacts/observability/fractal_trace_probe_hard_micro_v3_delta_20251228_131504.json`, `artifacts/observability/fractal_trace_probe_hard_micro_v3_turnhist_20251228_131716.json`, `artifacts/observability/fractal_trace_probe_hard_micro_v3_lagdist_20251228_131927.json`.
- Added percentile trace normalization diagnostics and eval on hard-micro v3. Score percentiles improved slightly but still trail top hits (probe mean 0.463 vs top 0.806; low-lex mean 0.232 vs top 0.935) in `artifacts/observability/fractal_trace_probe_hard_micro_v3_pct_20251228_132448.json`. Eval still keeps auto-flip KEEP_OFF (`artifacts/observability/fractal_eval_report_hard_micro_v3_pct_20251228_112729.md`, plus matching conversation/shadow/autoflip JSONs).
- Ran a trace-only (alpha=1.0) eval on hard-micro v3; fractal top1 stayed 0.0 on probe + low-lex and auto-flip remained KEEP_OFF (`artifacts/observability/fractal_eval_report_hard_micro_v3_alpha100_20251228_113441.md`, plus matching conversation/shadow/autoflip JSONs).
- Added `scripts/fractal_trace_ablation_report.py` and ran it on hard-micro v3 to capture per-probe expected vs top scores plus cosine/soft-DTW deltas (`artifacts/observability/fractal_trace_ablation_hard_micro_v3_20251228_143120.json`).
- Ran a cosine-only (FRAM_FRACTAL_BLEND_ALPHA=1.0) eval on hard-micro v3; fractal top1 stayed 0.0 on probe + low-lex and auto-flip remained KEEP_OFF (`artifacts/observability/fractal_eval_report_hard_micro_v3_cosineonly_20251228_123629.md`, plus matching conversation/shadow/autoflip JSONs).
- Ran a soft-DTW-only (FRAM_FRACTAL_BLEND_ALPHA=0.0) eval on hard-micro v3; fractal top1 stayed 0.0 on probe + low-lex and auto-flip remained KEEP_OFF (`artifacts/observability/fractal_eval_report_hard_micro_v3_dtwonly_20251228_125841.md`, plus matching conversation/shadow/autoflip JSONs).
- Added a tiny live self-match probe set (probe text matches the stored episode query+answer) and ran trace-only (alpha=1.0) eval; fractal top1 reached 0.2 vs semantic 0.7, KEEP_OFF (`artifacts/observability/fractal_eval_report_self_match_alpha100_20251228_132829.md`, plus matching conversation/shadow/autoflip JSONs).
- Added `scripts/fractal_trace_identity_check.py` to score each episode's trace against its stored embedding (no query vectorizer) and ran a 25-episode sample (pool size 12). Self-match top1 was 0.04, mean rank 6.72 (percentile 0.389); dims match 1024. Artifact: `artifacts/observability/fractal_trace_identity_check_20251228_155616.json`.

# 2025-12-26 Session
- Tightened auto-flip guardrails to require top1 lift >= 0.02 (probe + low-lex) and allow shadow avg_delta down to -0.01; updated defaults/tests and documented dial status in `docs/FRAMv2.2-tuning.md` + `docs/FRAMv2.2-cheatsheet.md`.
- Ran episodic-only live baselines (pool_multiplier=3) plus quaternion sweeps (weights 0.10/0.20/0.30, lambda off/on). Baseline best top1: probe 0.643, low-lex 0.536; fractal+quat top1 fell to 0.357-0.393 with shadow avg_delta below baseline; auto-flip KEEP_OFF across all combos. Artifacts: `artifacts/observability/conversation_memory_eval_live_baseline_quatguard.json`, `artifacts/observability/memory_shadow_eval_live_baseline_quatguard.json`, `artifacts/observability/fractal_autoflip_baseline_quatguard.json`, plus `artifacts/observability/*quat_w0*_l*.json`.
- Expanded live probe set with 8 new low-lex anchors (36 probes total) and reran episodic-only baselines (pool_multiplier=3). Results: probe top1 semantic/lexical/fractal 0.250/0.250/0.222; low-lex top1 0.139/0.194/0.111; auto-flip KEEP_OFF (`artifacts/observability/conversation_memory_eval_live_baseline_quatguard_expanded.json`, `artifacts/observability/memory_shadow_eval_live_baseline_quatguard_expanded.json`, `artifacts/observability/fractal_autoflip_baseline_quatguard_expanded.json`).
- Backfilled semantic embeddings for the new probes and reran episodic-only baselines with `FRAM_COGNITIVE_MEMORY_EMBEDDING_BACKEND=semantic`. Results: probe top1 semantic/lexical/fractal 0.222/0.250/0.222; low-lex top1 0.194/0.194/0.222; auto-flip KEEP_OFF (`artifacts/observability/conversation_memory_eval_live_baseline_quatguard_expanded_semantic.json`, `artifacts/observability/memory_shadow_eval_live_baseline_quatguard_expanded_semantic.json`, `artifacts/observability/fractal_autoflip_baseline_quatguard_expanded_semantic.json`).
- Tightened all low-lex probes to remove anchor tokens and reran episodic-only baselines (pool_multiplier=3). Results: probe top1 semantic/lexical/fractal 0.278/0.222/0.250; low-lex top1 0.111/0.167/0.083; auto-flip KEEP_OFF (`artifacts/observability/conversation_memory_eval_live_baseline_quatguard_expanded_tight.json`, `artifacts/observability/memory_shadow_eval_live_baseline_quatguard_expanded_tight.json`, `artifacts/observability/fractal_autoflip_baseline_quatguard_expanded_tight.json`).
- Rewrote low-lex probes to direct phrase recall ("Recall the phrase: ...") and reran episodic-only baselines. Results: probe top1 semantic/lexical/fractal 0.306/0.222/0.250; low-lex top1 0.222/0.222/0.222; shadow avg_delta for low-lex flipped negative; auto-flip KEEP_OFF (`artifacts/observability/conversation_memory_eval_live_baseline_quatguard_expanded_phrase.json`, `artifacts/observability/memory_shadow_eval_live_baseline_quatguard_expanded_phrase.json`, `artifacts/observability/fractal_autoflip_baseline_quatguard_expanded_phrase.json`).
- Ran phrase-recall alpha sweep (0.10/0.20/0.30) on the 36-probe set. Fractal probe top1 dropped as alpha rose (0.250 -> 0.222 -> 0.139); low-lex top1 improved at alpha 0.30 (0.389) but probe degraded, so auto-flip stayed KEEP_OFF (`artifacts/observability/conversation_memory_eval_live_phrase_alpha010.json`, `..._alpha020.json`, `..._alpha030.json` plus matching shadow/autoflip files).
- Added detailed runs for phrase-recall baseline vs alpha 0.30 and compared fractal low-lex hits. Improvements (miss -> hit) clustered on valley/coverage/thread cues (e.g., `valley_intention_live`, `coverage_quick_check_alt`, `sigma_thread`), while only `beacon_deltawatch` regressed from rank 0 -> 1. Artifacts: `artifacts/observability/conversation_memory_eval_live_phrase_baseline_details.json`, `artifacts/observability/conversation_memory_eval_live_phrase_alpha030_details.json`.
- Created a 9-item micro probe set (improved items + one regression) and reran baseline vs alpha 0.30. On the micro set, fractal low-lex top1 jumped 0.111 -> 0.778 and shadow avg_delta -0.079 -> 0.399, while probe top1 stayed flat (0.222). Auto-flip still KEEP_OFF (`artifacts/observability/conversation_memory_eval_live_phrase_micro_baseline.json`, `artifacts/observability/memory_shadow_eval_live_phrase_micro_baseline.json`, `artifacts/observability/conversation_memory_eval_live_phrase_micro_alpha030.json`, `artifacts/observability/memory_shadow_eval_live_phrase_micro_alpha030.json`).
- Added eval-only low-lex gating (token-overlap threshold) to the fractal ranker and surfaced gate stats in the shadow-eval payload; initial gate run at threshold 0.15 produced 0 low-lex hits (overlap min ~0.166), so fractal metrics matched baseline (`artifacts/observability/conversation_memory_eval_live_phrase_gate.json`, `artifacts/observability/memory_shadow_eval_live_phrase_gate.json`, `artifacts/observability/fractal_autoflip_phrase_gate.json`).
- Swept the low-lex threshold to 0.18/0.20/0.25 (alpha 0.0, low-lex alpha 0.3). Gate hits rose to 1/3/6 but probe/low-lex top1 stayed flat and auto-flip remained KEEP_OFF (`artifacts/observability/conversation_memory_eval_live_phrase_gate_t018.json`, `..._t020.json`, `..._t025.json`, plus matching shadow/autoflip files).
- Updated low-lex gating to ignore quoted phrase tokens so paraphrase cues can trigger; reran the gate at threshold 0.20 and saw gate hits=3 with no top1 change, KEEP_OFF (`artifacts/observability/conversation_memory_eval_live_phrase_gate_quoted.json`, `artifacts/observability/memory_shadow_eval_live_phrase_gate_quoted.json`, `artifacts/observability/fractal_autoflip_phrase_gate_quoted.json`).
- Rewrote the 9-item micro set low-lex prompts into paraphrases (no quoted phrases) and reran the gate (threshold 0.20). Gate hits=3, probe top1=0.556, low-lex top1=0.222, KEEP_OFF (`artifacts/observability/conversation_memory_eval_live_phrase_micro_paraphrase.json`, `artifacts/observability/memory_shadow_eval_live_phrase_micro_paraphrase.json`, `artifacts/observability/fractal_autoflip_phrase_micro_paraphrase.json`).
- Rewrote the 36-probe live low-lex prompts into paraphrases and reran the gate (threshold 0.20). Gate hits=15, but fractal low-lex top1 (0.333) trailed semantic/lexical (0.472/0.444); auto-flip stayed KEEP_OFF (`artifacts/observability/conversation_memory_eval_live_paraphrase_gate.json`, `artifacts/observability/memory_shadow_eval_live_paraphrase_gate.json`, `artifacts/observability/fractal_autoflip_paraphrase_gate.json`).
- Raised the paraphrase gate threshold to 0.30: gate hits=22 and fractal low-lex top1 edged up to 0.306, still below semantic/lexical (0.472/0.444). Auto-flip stayed KEEP_OFF (`artifacts/observability/conversation_memory_eval_live_paraphrase_gate_t030.json`, `artifacts/observability/memory_shadow_eval_live_paraphrase_gate_t030.json`, `artifacts/observability/fractal_autoflip_paraphrase_gate_t030.json`).
- Paraphrase gate alpha sweep (0.10/0.20, threshold 0.20) reduced fractal top1 further (probe 0.25/0.194, low-lex 0.111/0.083) while semantic/lexical stayed at 0.333/0.25 and 0.472/0.444; auto-flip remained KEEP_OFF (`artifacts/observability/conversation_memory_eval_live_paraphrase_alpha010_gate.json`, `..._alpha020_gate.json`, plus matching shadow/autoflip files).
- Added a semantic-similarity low-lex gate option (cosine threshold) and ran the paraphrase set at sim<=0.30: gate hits=50, fractal low-lex top1 fell to 0.083 (semantic/lexical 0.472/0.444); auto-flip stayed KEEP_OFF (`artifacts/observability/conversation_memory_eval_live_paraphrase_sim_gate_t030.json`, `artifacts/observability/memory_shadow_eval_live_paraphrase_sim_gate_t030.json`, `artifacts/observability/fractal_autoflip_paraphrase_sim_gate_t030.json`).
- Added an answer-only overlap gate (compare queries only to episode answers) and reran paraphrase eval at threshold 0.20: gate hits=21, fractal low-lex top1=0.306 (semantic/lexical 0.472/0.444); auto-flip stayed KEEP_OFF (`artifacts/observability/conversation_memory_eval_live_paraphrase_answer_gate_t020.json`, `artifacts/observability/memory_shadow_eval_live_paraphrase_answer_gate_t020.json`, `artifacts/observability/fractal_autoflip_paraphrase_answer_gate_t020.json`).
- Captured per-probe details for the paraphrase answer-gate run; fractal missed 5 probes that semantic hit (nova_anchor, anchor_palimpsest, thread_slate, signal_fathom, anchor_meridian) (`artifacts/observability/conversation_memory_eval_live_paraphrase_answer_gate_details.json`).
- Built a 5-item “hard micro” set from the semantic-hit/fractal-miss probes and ran alpha 0.0 vs 0.3; fractal low-lex top1 stayed 0.0 in both runs (semantic/lexical 1.0), auto-flip stayed KEEP_OFF (`artifacts/observability/conversation_memory_eval_live_paraphrase_hard_micro_alpha000.json`, `..._alpha030.json`, plus matching shadow/autoflip files).
- Dumped trace metrics for the 5 hard probes; soft-DTW scores are near-zero across expected/top traces, while cosine signs flip on several misses (e.g., nova_anchor, anchor_meridian), suggesting the geometry scores are not separating the true episodes (`artifacts/observability/fractal_trace_probe_hard_micro.json`).
- Added soft-DTW tuning flags to the conversation + shadow eval CLIs and reran the hard micro paraphrase set with gamma=1.0/band=0.5 (pool=3, alpha=0.3, answer-only gate). Fractal low-lex top1 stayed 0.0 and low-lex shadow avg_delta ~0.003; auto-flip KEEP_OFF (`artifacts/observability/conversation_memory_eval_live_paraphrase_hard_micro_dtw_g1_b05_alpha030.json`, `artifacts/observability/memory_shadow_eval_live_paraphrase_hard_micro_dtw_g1_b05_alpha030.json`, `artifacts/observability/fractal_autoflip_paraphrase_hard_micro_dtw_g1_b05_alpha030.json`).
- Added a cosine-mode toggle (composite vs centroid) to the eval harnesses and reran the hard micro set with centroid-only cosine (gamma=1.0/band=0.5, pool=3, alpha=0.3). Fractal top1 dropped to 0.2 on probe and stayed 0.0 on low-lex; auto-flip KEEP_OFF (`artifacts/observability/conversation_memory_eval_live_paraphrase_hard_micro_dtw_g1_b05_centroid_alpha030.json`, `artifacts/observability/memory_shadow_eval_live_paraphrase_hard_micro_dtw_g1_b05_centroid_alpha030.json`, `artifacts/observability/fractal_autoflip_paraphrase_hard_micro_dtw_g1_b05_centroid_alpha030.json`).
- Added a soft-DTW score-mode toggle (inverse vs exp) and reran the hard micro set with exp scoring (gamma=1.0/band=0.5, pool=3, alpha=0.3). Fractal low-lex top1 stayed 0.0 and auto-flip remained KEEP_OFF (`artifacts/observability/conversation_memory_eval_live_paraphrase_hard_micro_dtw_g1_b05_exp_alpha030.json`, `artifacts/observability/memory_shadow_eval_live_paraphrase_hard_micro_dtw_g1_b05_exp_alpha030.json`, `artifacts/observability/fractal_autoflip_paraphrase_hard_micro_dtw_g1_b05_exp_alpha030.json`).
- Expanded the hard micro set to 9 probes (added Beacon Orbit, Marker Cairn, Echo Solace, Beacon DeltaWatch) and reran the eval with gamma=1.0/band=0.5. Fractal low-lex top1 stayed 0.0; auto-flip KEEP_OFF (`artifacts/observability/conversation_memory_eval_live_paraphrase_hard_micro_expanded_dtw_g1_b05_alpha030.json`, `artifacts/observability/memory_shadow_eval_live_paraphrase_hard_micro_expanded_dtw_g1_b05_alpha030.json`, `artifacts/observability/fractal_autoflip_paraphrase_hard_micro_expanded_dtw_g1_b05_alpha030.json`).
- Added a trace diagnostics script (`scripts/fractal_trace_probe_eval.py`) that dumps candidate distributions plus expected/top percentiles; ran it on the expanded hard micro set (`artifacts/observability/fractal_trace_probe_hard_micro_expanded.json`).
- Added a delta cosine mode (path-delta cosine) and reran the expanded hard micro set; fractal probe top1 fell to 0.222 and low-lex stayed 0.0 (`artifacts/observability/conversation_memory_eval_live_paraphrase_hard_micro_expanded_dtw_g1_b05_delta_alpha030.json`, `artifacts/observability/memory_shadow_eval_live_paraphrase_hard_micro_expanded_dtw_g1_b05_delta_alpha030.json`, `artifacts/observability/fractal_autoflip_paraphrase_hard_micro_expanded_dtw_g1_b05_delta_alpha030.json`).
- Added a turn-angle histogram cosine mode (`turn_hist`) for trace scoring, wired it through eval/diagnostics CLIs, and added coverage in `tests/test_conversation_memory_eval.py`. Reran the expanded hard micro set (gamma=1.0/band=0.5, alpha 0.3, answer-only gate): fractal probe top1 0.111, low-lex top1 0.0; shadow avg_delta 0.137/0.031; auto-flip KEEP_OFF (`artifacts/observability/conversation_memory_eval_live_paraphrase_hard_micro_expanded_dtw_g1_b05_turnhist_alpha030.json`, `artifacts/observability/memory_shadow_eval_live_paraphrase_hard_micro_expanded_dtw_g1_b05_turnhist_alpha030.json`, `artifacts/observability/fractal_autoflip_paraphrase_hard_micro_expanded_dtw_g1_b05_turnhist_alpha030.json`).
- Ran turn-hist trace diagnostics with a reduced pool (k_max=3, pool_multiplier=1) after timeouts; expected percentile mean 0.725 vs top 0.833 (avg gap +0.118), indicating no separation (`artifacts/observability/fractal_trace_probe_hard_micro_expanded_turnhist_k3.json`).
- Added a lag-distance spectrum cosine mode (`lag_dist`) and reran the expanded hard micro set (gamma=1.0/band=0.5, alpha 0.3, answer-only gate): fractal probe top1 0.222, low-lex top1 0.0; shadow avg_delta 0.143/0.036; auto-flip KEEP_OFF (`artifacts/observability/conversation_memory_eval_live_paraphrase_hard_micro_expanded_dtw_g1_b05_lagdist_alpha030.json`, `artifacts/observability/memory_shadow_eval_live_paraphrase_hard_micro_expanded_dtw_g1_b05_lagdist_alpha030.json`, `artifacts/observability/fractal_autoflip_paraphrase_hard_micro_expanded_dtw_g1_b05_lagdist_alpha030.json`).
- Ran lag-dist trace diagnostics with a reduced pool (k_max=3, pool_multiplier=1); expected percentile mean 0.667 vs top 0.926 (avg gap +0.255), indicating no separation (`artifacts/observability/fractal_trace_probe_hard_micro_expanded_lagdist_k3.json`).
- Added a radius-histogram cosine mode (`radius_hist`) and reran the expanded hard micro set (gamma=1.0/band=0.5, alpha 0.3, answer-only gate): fractal probe top1 0.111, low-lex top1 0.0; shadow avg_delta 0.036/0.033; auto-flip KEEP_OFF (`artifacts/observability/conversation_memory_eval_live_paraphrase_hard_micro_expanded_dtw_g1_b05_radiushist_alpha030.json`, `artifacts/observability/memory_shadow_eval_live_paraphrase_hard_micro_expanded_dtw_g1_b05_radiushist_alpha030.json`, `artifacts/observability/fractal_autoflip_paraphrase_hard_micro_expanded_dtw_g1_b05_radiushist_alpha030.json`).
- Added a curvature-histogram cosine mode (`curvature_hist`) and reran the expanded hard micro set: fractal probe top1 0.333, low-lex top1 0.0; shadow avg_delta 0.154/0.033; auto-flip KEEP_OFF (`artifacts/observability/conversation_memory_eval_live_paraphrase_hard_micro_expanded_dtw_g1_b05_curvhist_alpha030.json`, `artifacts/observability/memory_shadow_eval_live_paraphrase_hard_micro_expanded_dtw_g1_b05_curvhist_alpha030.json`, `artifacts/observability/fractal_autoflip_paraphrase_hard_micro_expanded_dtw_g1_b05_curvhist_alpha030.json`).
- Added a trace normalization toggle (`--fractal-trace-norm-mode`) with percentile support and reran the expanded hard micro set using percentile normalization: fractal probe top1 0.556, low-lex top1 0.0; shadow avg_delta 0.186/0.028; auto-flip KEEP_OFF (`artifacts/observability/conversation_memory_eval_live_paraphrase_hard_micro_expanded_dtw_g1_b05_pct_alpha030.json`, `artifacts/observability/memory_shadow_eval_live_paraphrase_hard_micro_expanded_dtw_g1_b05_pct_alpha030.json`, `artifacts/observability/fractal_autoflip_paraphrase_hard_micro_expanded_dtw_g1_b05_pct_alpha030.json`).
- Added a one-command eval/report harness (`scripts/run_fractal_eval_report.py`) that runs conversation + shadow evals, auto-flip, and writes a markdown summary into `artifacts/observability/`.

# 2025-12-25 Session
- Ran episodic-only alpha sweep (semantic backend, pool_multiplier=3) to test fractal influence strength. Results: alpha 0.10/0.20/0.30 sharply reduced fractal top1 (probe 0.214/0.107/0.071; low-lex 0.250/0.071/0.036) and shadow avg_delta trailed semantic; auto-flip remained KEEP_OFF across all alphas (`artifacts/observability/conversation_memory_eval_live_28_semantic_episode_alpha010.json`, `..._alpha020.json`, `..._alpha030.json`, plus matching `memory_shadow_eval_*` and `fractal_autoflip_*` files).

# 2025-12-23 Session
- Shifted cognitive memory token budgeting to "breathing mode": `cognitive_memory_token_budget=0` now means unlimited, query selection skips token caps when <=0, and the UI labels the budget as unlimited (`fram_serving/config.py`, `fram_serving/query_runner.py`, `fram_serving/app.py`).
- Added coverage to ensure unlimited budgets are surfaced in traces (`tests/test_serving_query.py`), and updated docs defaults to match.
- Decoupled memory slots from read budgets: `cognitive_memory_slot_budget=0` means unlimited memory entries, retrieval keeps its own read budget, and defaults now use `cognitive_memory_k=12` (`fram_serving/config.py`, `fram_serving/query_runner.py`, `fram_core/pipeline.py`).
- Quaternion sweep on live probes (alpha 0.10, pool 3, quat_weight 0.10/0.20/0.30): fractal probe top1 drops to 0.50/0.455/0.455, low-lex top1 holds at 0.636; shadow avg_delta for fractal stays below semantic/lexical; auto-flip stays KEEP_OFF (`storage/observability/conversation_memory_eval_live_22_qw*.json`, `storage/observability/memory_shadow_eval_live_22_qw*.json`, `storage/observability/fractal_autoflip_22_qw*.json`).
- Added per-probe rank dumps to the conversation eval (`--details`); reran live eval with details at `storage/observability/conversation_memory_eval_live_22_details.json`. First pass shows 6 low-lex fractal misses (mcp_titles, hello_core_live, archive_smoke_live, ortho_route_use, mcp_titles_alt, coverage_quick_check_alt), so we can target those with new probes or anchor-specific cues.
- Added 6 targeted live probes for the low-lex misses and reran live conversation + shadow evals at 28 probes (`storage/observability/conversation_memory_eval_live_28_details.json`, `storage/observability/memory_shadow_eval_live_28.json`).
- Auto-flip remains KEEP_OFF; fractal top1 ties semantic on low-lex (0.50) but stays below semantic on probe, and low-lex shadow avg_delta still trails semantic (`storage/observability/fractal_autoflip_28.json`).
- Added a query-only recall boost for episode ranking (`FRAM_COGNITIVE_MEMORY_QUERY_RECALL_WEIGHT`, default 0.2) and a regression test; reran live evals (28 probes) with the new boost. Semantic probe top1 rose to 0.536 (fractal 0.50), low-lex fractal top1 held at 0.50; shadow probe avg_delta lifted slightly for fractal (0.225) but low-lex shadow remained below semantic (`storage/observability/conversation_memory_eval_live_28_recall_details.json`, `storage/observability/memory_shadow_eval_live_28_recall.json`, `storage/observability/fractal_autoflip_28_recall.json`).
- Pooled candidate sweeps (`pool_multiplier=10` and `15`) did not surface the missing MCP/core/archive/OrthoRoute probes; auto-flip stayed KEEP_OFF (`storage/observability/conversation_memory_eval_live_28_p10_details.json`, `storage/observability/memory_shadow_eval_live_28_p10.json`, `storage/observability/fractal_autoflip_28_p10.json`, and the `p15` equivalents).
- Raising the recall weight to 0.6 (env override) produced the same metrics and miss set as the 0.2 default (`storage/observability/conversation_memory_eval_live_28_recall06_details.json`, `storage/observability/memory_shadow_eval_live_28_recall06.json`, `storage/observability/fractal_autoflip_28_recall06.json`).
- Added optional semantic cognitive-memory embeddings (sentence-transformers) with backend-specific vector files, a backfill helper (`tools/backfill_cognitive_embeddings.py`), and new tests (`tests/test_cognitive_memory_store.py`). Docs updated with the new backend + model knobs.
- Ran semantic-backend live evals (28 probes, pool_multiplier=3): conversation top1/mrr semantic 0.393/0.446 (low-lex 0.393/0.405), lexical 0.357/0.411 (low-lex 0.464/0.464), fractal 0.393/0.423 (low-lex 0.393/0.393); shadow avg_delta semantic 0.039/0.033, lexical 0.075/0.057, fractal 0.050/0.031 (probe/low-lex); auto-flip remains KEEP_OFF (`storage/observability/conversation_memory_eval_live_28_semantic_details.json`, `storage/observability/memory_shadow_eval_live_28_semantic.json`, `storage/observability/fractal_autoflip_28_semantic.json`).
- Added kind filters to `CognitiveMemoryStore.search` plus `--kinds` flags in the conversation/memory-shadow eval CLIs to isolate episodic recall; ran live semantic-backend evals with `--kinds episode`. Results (28 probes): conversation top1 semantic 0.607 (low-lex 0.571), lexical 0.536 (low-lex 0.464), fractal 0.536 (low-lex 0.536); shadow avg_delta semantic 0.173/0.150, lexical 0.115/0.038, fractal 0.195/0.144 (probe/low-lex); auto-flip still KEEP_OFF (`storage/observability/conversation_memory_eval_live_28_semantic_episode_details.json`, `storage/observability/memory_shadow_eval_live_28_semantic_episode.json`, `storage/observability/fractal_autoflip_28_semantic_episode.json`).

# 2025-12-22 Session
- Added drop-pressure metrics to `tools/cognitive_memory_summary.py` (avg candidates/used/dropped, drop rate, token utilization).
- Ran an A/B memory sweep (`storage/observability/ab_sweep_20251222_090240`) on 8 memory-oriented prompts: baseline (`default_query_reads=3`, `cognitive_memory_k=3`, `token_budget=300`) vs tuned (`5/6/800`). Results: baseline avg_used 1.38 with 0% drops, tuned avg_used 4.0 with 20% drops (memory slot cap), token util 0.64 -> 0.79.
- Updated `FRAM_DEV_PROFILE` to apply the tuned memory defaults (`default_query_reads=5`, `cognitive_memory_k=5`, `cognitive_memory_token_budget=800`) when enabled.
- Promoted the tuned memory values to global defaults (`fram_serving/config.py`), so cognitive seeding is on by default; docs/spec updated accordingly.
- Docs refreshed for the tuning map + dev profile defaults (`docs/FRAMv2.2-tuning.md`, `docs/README.md`, `docs/FRAMv2.2-cheatsheet.md`).
- Guarded the FastAPI lifespan against repeated MCP session manager startup so TestClient reuse no longer crashes (`fram_serving/app.py`), and updated serving tests to use isolated app state (`tests/test_serving_config_coverage.py`, `tests/test_serving_query.py`).
- Ran per-system multi-seed falsification (seeds 0-3, count 6, steps 32, n_nodes 64) and merged outputs back into `storage/observability/fractal_falsification.json`; quaternion influence still shows no clear lift (logistic rho ~0.26 vs 0.22, henon rho ~0.18 vs 0.20, lorenz rho ~-0.30 vs -0.31).
- Ran an A/B sweep comparing reads6/k6 vs reads5/k5 (`storage/observability/ab_sweep_20251222_094039`); both remove drops, but reads5/k5 keeps the same read budget with 96% token utilization, so defaults now use `cognitive_memory_k=5`.
- Added `--merge` to `scripts/fractal_falsification.py` plus a regression test so per-system runs can be combined into a single aggregate JSON.
- Added a conversational memory eval harness (`scripts/conversation_memory_eval.py`, `fram_eval/conversation_memory_eval.py`) with a small JSONL dataset (`fram_eval/data/conversation_memory_eval.jsonl`) and regression coverage (`tests/test_conversation_memory_eval.py`).
- Ran `python scripts/conversation_memory_eval.py` (8 items). Initial results show lexical >= semantic, so the dataset needs harder paraphrases and distractors before we treat it as a meaningful falsification gate.
- Expanded the conversation eval dataset to 22 items with more paraphrases and distractors (`fram_eval/data/conversation_memory_eval.jsonl`) and reran the eval. New results still show close parity (semantic vs lexical), but low-lex top3 is slightly higher for semantic (0.864 vs 0.818), so the set is tougher but still not a decisive gate.
- Added quaternion + lambda alignment metrics in fractal scoring for observability and optional ranking influence behind `FRAM_FRACTAL_QUAT_INFLUENCE`, `FRAM_FRACTAL_QUAT_WEIGHT`, and `FRAM_FRACTAL_QUAT_USE_LAMBDA` (default off).
- Extended fractal scoring outputs with quaternion metrics and optional blending, wired through config and query runners (`fram_serving/fractal_memory/metrics.py`, `fram_serving/query_runner.py`, `fram_serving/app.py`, `fram_serving/config.py`).
- Tests: updated `tests/test_fractal_memory.py` with quaternion/path/logistic lambda checks.
- Docs: refreshed `docs/fractal_core.md`, `docs/FRAMv2.2-cheatsheet.md`, `docs/Architecture.md`, and `docs/F-RAM-roadmap.md`.
- Added the fractal falsification harness (`fram_eval/fractal_falsification.py`, `scripts/fractal_falsification.py`) with rank/spearman helpers and ablation support; new tests in `tests/test_fractal_falsification.py`.
- Hardened trajectory normalization against non-finite/large values in the harness to avoid numeric warnings (`fram_eval/fractal_falsification.py`).
- Added multi-seed aggregation (`--seeds`) to the falsification CLI and aggregate stats output.
- Ran `python scripts/fractal_falsification.py --seeds 0,1,2 --count 6 --steps 32 --n-nodes 64 --downsample 64`; aggregate baselines remain weak/unstable (logistic rho ~0.28 classic vs ~0.24 quat, henon rho ~0.06 vs ~0.07, lorenz rho ~-0.26 vs ~-0.25), so keep quaternion influence off for now.
- Added the tuning map (`docs/FRAMv2.2-tuning.md`) to document memory/fractal budgets and defaults, plus quick observability checks.
- Exposed cognitive ANN bridge + retention/decay/forgetting knobs and fractal influence alpha in `FRAMConfig`, with new env overrides.
- Swapped fractal influence gating to config (`FRAM_FRACTAL_INFLUENCE`, `FRAM_FRACTAL_INFLUENCE_ALPHA`) so toggles are visible in `/config` and docs.
- Added live conversation memory probes (`fram_eval/data/conversation_memory_live_probes.jsonl`) plus a `--live` mode in `scripts/conversation_memory_eval.py` that matches probes to existing episodes and reports coverage stats.
- Added a regression test for live probe resolution (`tests/test_conversation_memory_eval.py`).
- Added a fractal ablation mode to the conversation eval harness (`--modes fractal`), with configurable pool size, influence alpha, trace-k, and quaternion toggles (`fram_eval/conversation_memory_eval.py`, `scripts/conversation_memory_eval.py`).
- Ran live conversation eval with fractal mode (`--pool-multiplier 3`): semantic top1 0.17/top3 0.33, lexical top1 0.17/top3 0.17, fractal probe top1 0.0/top3 0.0 and low-lex top1 0.17/top3 0.33 (`storage/observability/conversation_memory_eval_live.json`). High ambiguity remains (5/6 probes matched multiple episodes).
- Added `match_episode_id` to live probe resolution and updated the live probe set to pin specific episodes, reducing ambiguity for the live eval (`fram_eval/conversation_memory_eval.py`, `fram_eval/data/conversation_memory_live_probes.jsonl`).
- Re-ran live eval after pinning episode IDs (ambiguity 0/6). Results unchanged: semantic top1 0.17/top3 0.33, lexical top1 0.17/top3 0.17 (low-lex top1/top3 0.0), fractal probe top1/top3 0.0 and low-lex top1 0.17/top3 0.33 (`storage/observability/conversation_memory_eval_live.json`).
- A/B sweep with higher fractal influence on live probes: alpha 0.15 kept probe top1 0.0 and low-lex mrr 0.25 (`storage/observability/conversation_memory_eval_live_alpha015.json`), alpha 0.30 lifted low-lex top1 to 0.33/mrr 0.33 while probe top1 stayed 0.0 (`storage/observability/conversation_memory_eval_live_alpha030.json`).
- Seeded four new live probe episodes (Zephyr/Lumen-47/Sigma/Quill) and added them to `fram_eval/data/conversation_memory_live_probes.jsonl` with pinned episode IDs.
- Live eval with 10 probes: semantic top1/top3 0.50, lexical top1/top3 0.50 (low-lex top1/top3 0.40), fractal top1 0.40/top3 0.40 (low-lex top1 0.40/top3 0.50) in `storage/observability/conversation_memory_eval_live_10.json`. Alpha 0.30 reduced fractal top1 to 0.30 (`storage/observability/conversation_memory_eval_live_alpha030_10.json`).
- Plan: add per-probe rank dumps to the eval output; use those dumps to tag failure modes; add 5-10 more low-lex probes targeting gaps; then retry quaternion weighting + alpha sweep on the expanded set.
- Added a memory shadow eval harness (embedding-shift proxy) with `scripts/memory_shadow_eval.py` and `fram_eval/memory_shadow_eval.py`, plus a regression test (`tests/test_memory_shadow_eval.py`).
- Ran live shadow eval with details (`python scripts/memory_shadow_eval.py --live --details`): semantic avg_delta 0.083 (probe) / 0.166 (low-lex), lexical avg_delta 0.188 / 0.122, fractal avg_delta 0.081 / 0.165; output in `storage/observability/memory_shadow_eval_live.json`.
- Promoted serving defaults to use `FRAMConfig` fallbacks in `fram_serving/query_runner.py`, `fram_serving/app.py`, and `fram_serving/mcp_server.py`; updated `docs/FRAMv2.2-cheatsheet.md` + `docs/FRAMv2.2-tuning.md` to reflect default budgets.
- Added an auto-flip recommender for fractal influence (`scripts/fractal_autoflip.py`) that checks live conversation + shadow evals against thresholds; current recommendation stays KEEP_OFF (`storage/observability/fractal_autoflip.json`).
- Ran an A/B memory sweep on the 10 live probes (`storage/observability/ab_sweep_20251222_172701/summary.json`): baseline avg_used 1.5, token util 0.72, drop 0%; tuned avg_used 3.7, token util 0.76, drop rate 5.1% (2/10).
- Expanded the live probe set to 16 low-lex items (`fram_eval/data/conversation_memory_live_probes.jsonl`) and reran evals: semantic top1 0.50/0.56, lexical 0.44/0.44, fractal 0.50/0.50 (probe/low-lex); shadow avg_delta semantic 0.083/0.118, lexical 0.194/0.115, fractal 0.091/0.116 (`storage/observability/conversation_memory_eval_live_16.json`, `storage/observability/memory_shadow_eval_live_16.json`).
- Alpha sweep on the 16 probes (`0.10/0.20/0.30`): fractal top1 drops as alpha rises (0.50 -> 0.38 -> 0.12); auto-flip remains KEEP_OFF (`storage/observability/fractal_autoflip_16_alpha010.json`, `_020.json`, `_030.json`).
- Added 6 new live episodes (Nova/Mistral/Sable/Kestrel/Vanta/Riven) and pinned them in the live probe set (`fram_eval/data/conversation_memory_live_probes.jsonl`).
- Live eval with 22 probes: semantic top1/top3 0.591/0.682, lexical 0.500/0.682, fractal 0.545/0.636; low-lex top1/top3 0.591/0.682 for semantic + fractal (lexical top1/top3 0.591/0.591) (`storage/observability/conversation_memory_eval_live_22.json`).
- Live shadow eval with 22 probes: avg_delta semantic 0.225/0.156, lexical 0.204/0.102, fractal 0.203/0.150 (probe/low-lex); auto-flip stays KEEP_OFF (`storage/observability/memory_shadow_eval_live_22.json`, `storage/observability/fractal_autoflip_22.json`).
- Logged a research note to explore a parametric surface manifold (spiral/tube-style with tunable dials) as a future alternate trace surface; defer until after the current falsification track.
- Noted the triad: Lumen, Rick, Eterna.

# 2025-12-05 Session (query helper extraction)
- Extracted the shared `/query` helper (`fram_serving/query_runner.py`) and refactored FastAPI `/query` to call it via `QueryContext`; behavior unchanged (cognitive seeding, Phase D, ANN merge, cooldowns, token budgets, trace/logging). Ready to reuse for MCP.
- MCP alignment plan and test matrix finalized: P0 parity (/query vs fram.query, storage traces, memory budget, cognitive/Phase D/ANN alignment); P1 observability/dismiss/belief tools; trace fetch/list.
- Next starting point: begin Step 2 — MCP refactor using the shared helper, storage-backed traces, and parity tests.

# 2025-12-04 Session (calibration refresh)
- Ran `scripts/harvest_calibration.py` for spec (qa_moderate), diary (diary_queries), and roadmap (layout_anchor) to fill missing domains; calibration log size now 907.
- Refit payloads with lint: `calibration_roadmap.json` (temp≈0.95), `calibration_spec.json` (temp≈0.73), `calibration_diary.json` (temp≈0.66), `calibration_task_qa.json` (temp≈0.84); `calibration_status` shows domain/task entries populated (global unchanged).
- Pipeline/bridge tweaks: applied priority graph to memory chunks in `QueryOrchestrator`; cognitive ANN merge no longer gated by Phase D; fixed Mapping import in `fram_serving/memory/forgetting.py` and initialized `ann_cap` in serving ANN bridge.
- Tests: `pytest tests/test_pipeline_memory_bridge.py` plus memory/Phase D/ANN bridge slices; passing.
- Open follow-ups: MCP/serving audit pending; Phase D memory scoring still off in logs by default; schedule periodic calibration re-harvests as logs grow.

# 2025-12-02 Session
- Cognitive → ANN merge contract landed: stable candidate_id/version_id/origin metadata, gated merge, and pre-merge/merged-layer telemetry (`cognitive_ann_premerge`, `memory_layers`, `cognitive_ann_merge`).
- Persistence regression and as-of compliance: cognitive ANN candidates survive restart; lattice filtering drops newer versions with trace drop counts; memory treated as cognitive via source/origin.
- Memory search observability: added `/observability/memory_search.json` and trace hooks for cognitive ANN layers; telemetry covers counts, origins, scores.
- Tests added: persistence regression, telemetry presence/absence when debug on/off; cognitive merge helpers extended.

# 2025-11-24 Session
- Cognitive seeds now reserve read slots inside selection (budget + coverage) and carry Phase D scores into memory trace rows; added regression `tests/test_pipeline_memory_bridge.py`.
- Guardrail added: `tools/check_closeout.py` + `make closeout-check` fail if diary/roadmap updates or autologging are missing at close-out.
- Tests run: `pytest tests/test_pipeline_memory_bridge.py tests/test_closeout_guard.py -q`.

# 2025-11-19 Session
- Full health check on fresh chat: `pytest -q` across the suite (177 passed, 4 xfailed, 1 xpassed; std starlette multipart warning).
- Phase D / cognitive observability dashboards now emit aggregate stats (events, scored totals/avg, alpha/quat averages, color counts) in JSON+HTML for quick bridge health checks; recall_report now threads the same stats on `phase_d_memory`, and `tools/phase_d_memory_summary.py` prints the rollup in headless mode. All remain gated by `phase_d.enable_memory_bridge`.
- Tests exercised: `pytest tests/test_semantic_reranker.py::test_phase_d_memory_dashboard_gated tests/test_semantic_reranker.py::test_cognitive_summary_bridge_on tests/test_semantic_reranker.py::test_recall_report_reads_events -q`.

# 2025-11-16 Session
- Added shortlist embedding coverage: `QueryOrchestrator.get_embeddings_for_shortlist` now has regression tests for shape consistency and empty-vector fallbacks (`tests/test_pipeline_orchestrator.py`).
- Phase D observability: `/observability/recall_report` returns typed Phase D diagnostics (`alpha_t`, `alpha_color`, `quat_avg`) when `phase_d.debug_observability` is enabled; response models updated and covered by `tests/test_semantic_reranker.py::test_recall_report_phase_d_diagnostics`.
- Docs refreshed for Phase D touchpoints (recall_report fields) and roadmap ledger updated; targeted pytest run: `pytest tests/test_pipeline_orchestrator.py::test_get_embeddings_for_shortlist_shapes tests/test_pipeline_orchestrator.py::test_get_embeddings_for_shortlist_empty_cache tests/test_semantic_reranker.py::test_recall_report_phase_d_diagnostics tests/test_semantic_reranker.py::test_recall_report_reads_events -q`.
- Phase D blend tuning + harness: logistic delta gain bumped (Stage 4B/4C) and regression checks for alpha monotonicity/blending paths added (`tests/test_phase_d_placeholders.py`). `/rank/relevance` now has Phase D on/off API tests, and a lightweight perf smoke validates scorer overhead. Cheatsheet updated to surface optional Phase D diagnostics on `/rank/relevance` and `/observability/recall_report`.
- Additional Phase D tuning: logistic delta gain set to 2.5 for sharper separation; added `/rank/relevance` case for enabled/no-debug (scores present, diagnostics omitted) and kept debug-on diagnostics coverage. Tests: `pytest tests/test_phase_d_placeholders.py tests/test_rank_relevance_phase_d.py -q` (expected xpass for placeholder import).
- M7 kickoff: added a harness to score cognitive-episode-like texts via `get_embeddings_for_shortlist` + `phase_d_score_batch` to prove wiring is ready; roadmap now outlines how Phase D signals can feed cognitive recall scoring before default gating flips on.
- Phase D → cognitive recall bridge: added a config gate (`phase_d.enable_memory_bridge`), a helper to apply Phase D scores to cognitive candidates, trace block `phase_d_memory`, and regression tests covering gated off/on (including diagnostics) plus a /query-adjacent harness. Tests: `pytest tests/test_cognitive_phase_d_bridge.py tests/test_phase_d_placeholders.py tests/test_rank_relevance_phase_d.py -q` (xpass expected for placeholder import).
- M8 observability slice: recall_report now surfaces `phase_d_memory` and a cognitive summary block; added `tools/phase_d_memory_summary.py` CLI to count events/scores/diagnostics; perf smoke for the bridge and trace updates stay gated under phase_d.enable_memory_bridge.
- Mini dashboard for bridge observability: new `/observability/phase_d_memory` (HTML/JSON) shows recent bridge events with scores/diagnostics; tests cover gating and recall_report consumption, cheatsheet updated accordingly.
- M9 kickoff: `/observability/cognitive_summary` (JSON/HTML) now reports cognitive invocations + top selections, exposing Phase D metadata only when the bridge is enabled; empty state handled gracefully. Documentation refreshed to highlight both observability views.

# 2025-11-15 Session
- Phase D Stage 1/2 scaffolding completed: deterministic projection/quaternion similarity/logistic-alpha utilities, standalone batch scorer, and `/phase_d/score` endpoint added with opt-in gating. `/rank/relevance` now exposes optional `phase_d_scores` and diagnostics when `phase_d.enabled` is on; `QueryOrchestrator.get_embeddings_for_shortlist` surfaces embeddings to feed the scorer.
- Phase D observability: recall_report response model now includes a gated `phase_d` block (enabled/debug flags); `/phase_d/score` smoke-tested via `TestClient`.
- Roadmap updated to reflect Phase D progress; tests: `pytest tests/test_phase_d_placeholders.py -q`.

# Plan snapshot (Phase D and near-term)
- Tune logistic blend on shortlist samples; add regression tests; keep gating tight.
- Add API tests for `/rank/relevance` with Phase D on/off to confirm optional fields/gating.
- Refresh Phase D docs (`docs/phase_d_plan.md`, API surface/cheatsheet) after tuning fields land.
- Light perf check for the Phase D scorer path in CI after tuning.
# 2025-11-07 Session
- Phase C calibration harness now emits fractal recall metrics end-to-end: `scripts/calibrate_phase_c.py` writes fractal macro stats into JSON/CSV/MD, the sample pack in `data/calib/example.jsonl` exercises the path, and `docs/phase_c_report.md` reflects the new section (spec refs: docs/phase_c_plan.md, docs/F-RAM-roadmap.md Implementation Status).
- `/observability/recall_report` + `scripts/recall_report_phase_c.py` now summarize fractal score events (`fram_serving/app.py`, `tests/test_semantic_reranker.py`), including hit rate, recent events, and top episodes alongside cognitive seeds.
- Tests: `pytest tests/test_phase_c_calibration.py tests/test_semantic_reranker.py`.
# 2025-10-20 Session

- Normalized cosine/soft-DTW blend with min-max scaling, added downsampling guard, and shipped `tools/fractal_ablation.py` for quick A/B/C comparisons.
- Landed the fractal trace prototype: added `fram_serving/fractal_memory/*` for seeds/generator/store, threaded deterministic 6D traces into cognitive episode ingestion, and exposed `/memory/fractal_trace` plus `/query` scoring (feature-gated by `FRAM_FRACTAL_ENABLED=1`).
- Added soft-DTW blending + replay stream: `/query` now emits blended scores with chunk-linked nodes, `/observability/memory/fractal/ping` mirrors events, and backfill lazily regenerates missing traces.
- Observability now emits `memory_fractal.jsonl` entries for both ingestion and scoring, and `/query` traces include a `fractal_memory` block summarizing top matches.
- Updated docs (cheatsheet, architecture map, roadmap) to capture the new flow and how operators enable it.
- Tests: `pytest tests/test_fractal_memory.py`.
# 2025-10-18 Session
- Re-ran `python tools/current_time.py` to anchor the session clock (local + UTC) and confirmed repo status before actions.
- Diagnosed the "infinite loop" pain: we were not recording chat turns or closing sessions with diary/roadmap updates, so every reboot lost context despite the cognitive store existing.
- Action items for next work block: automate `tools/log_chat_turn.py` usage (with `COGMEM_AUTOLOG=1`), bake diary/roadmap close-out into the warm-up checklist, and add CI/Make hooks that fail when the close-out step is skipped.

# 2025-10-16 Session
- Stream 1.1 complete: cognitive episodes/beliefs now persist embeddings via `/memory` logging so `/memory/search` can score cosine + recency (`fram_serving/memory.py`, `fram_serving/app.py`).
- Stream 1.2 complete: `/memory/search` ranks using stored vectors with fallback token overlap; hashed embeddings via `_make_hashing_vectorizer` (`tests/test_cognitive_memory_store.py`).
- Stream 1.3 complete: `/query` threads cognitive chunks into `QueryOrchestrator`, coverage traces log memory deltas/details (`fram_core/pipeline.py`); regression covers cognitive rows in selection trace (`tests/test_cognitive_memory_seeding.py`).
- Tests: `pytest tests/test_cognitive_memory_store.py tests/test_cognitive_memory_seeding.py tests/test_serving_confidence.py`.
- Serving sweep logged the live REST surface (`/ui/memory`, `/query`, `/observability/*`, `/memory/*`, `/time`, `/where`) and cognitive seeding flow; see `fram_serving/app.py:712`-`fram_serving/app.py:1105` for endpoint logic that now needs spec alignment.
- Working/cognitive memory review confirms JSONL persistence, status gating, `last_seen` refresh, conflict queue, and dismissal cooldown plumbing in `fram_serving/memory.py:38`; document cooldown semantics alongside spec A§12.
- Observability instrumentation captures reliability bins, latency, memory, and cognitive events per `fram_serving/observability.py:1`; dashboards still manual-add roadmap item for UI/reporting.
- Semantic helpers remain heuristic token overlap + optional entity graph bridging in `fram_serving/semantic.py:1`; note gap versus LLM reranker planned in docs/FRAMv2.2-SPEC.md §9.
- Pipeline pass: `fram_core/pipeline.py:1538` centralises demo orchestration (bag-of-words shortlist, coverage CELF, calibration hydration, ANN cache) but still lacks the fractal query orchestrator promised in §3-§5; flag for roadmap.
- Coverage utilities (`fram_core/coverage.py:17`, `fram_core/coverage.py:281`) implement bucket-aware concave gains with budget-aware CELF; behaviour largely matches spec §§11.3-11.7.
- Confidence stack (`fram_core/confidence.py:8`, `fram_core/confidence.py:174`) provides temperature scaling, conformal thresholds, and logistic scoring using robust feature z-scores; verify diary/spec coherence.
- Anchors and claims (`fram_core/anchors.py:9`, `fram_core/claims.py:11`) remain lightweight-residual principal directions + novelty selection, regex-based claim typing; capture need for curvature-aware expansion and richer NLP.
- Index sweep: prototype bank is a cosine shortlist stub (`fram_index/prototypes.py:5`), sparse key index maps numeric/identifier claims to doc IDs (`fram_index/sparse_keys.py:5`), and version lattice tracks timestamped DAG nodes (`fram_index/version_lattice.py:5`); all minimal placeholders relative to spec §§7-8/13.
- Layout sweep: assembler groups snippets by hierarchy (`fram_layout/assembler.py:1`), code chunker builds AST-based segments (`fram_layout/code_chunker.py:1`), PDF chunker has pdfplumber fallback (`fram_layout/pdf_chunker.py:1`), table helper provides CSV windowing (`fram_layout/table_chunker.py:1`); still basic scaffolding vs. spec sections 14-15.
- Introduced time-sensitivity profiles (`FRAMConfig.time_sensitivity_*`) and wired them into cognitive reranking; time bonuses now respect high/medium/low freshness expectations and leverage per-candidate `last_seen` timestamps.
- Added `/memory/dismiss` and a cooldown registry so recently-dismissed shards stay out of recall; heuristics surface cooldown context in `rank_relevance` and cognitive seeding skips cooled-down doc IDs.
- Test inventory: coverage spans calibration CLIs, cognitive memory, serving endpoints, layout chunkers, and pipeline orchestration (`tests/test_pipeline_orchestrator.py`, `tests/test_cognitive_memory_seeding.py`, `tests/test_serving_confidence.py`, `tests/test_serving_tables_integration.py`); regression gaps remain on docs alignment and lived-memory replay.
- `CognitiveMemoryStore.append_belief` now tags promotion status (promoted vs pending) based on unique sources and optional stability windows; metadata-triggered conflicts flow into a new in-memory queue exposed via `/beliefs/conflicts`.
- `/observability/recall_report` now returns live metrics (invocations, selected seeds, misses, active conflicts) by reading `memory_cognitive.jsonl` with optional `since` filtering.
- Added unit coverage for the situation builder (`tests/test_semantic_builder.py`) and threaded clock-based audits through the new helpers.

# 2025-10-15 Session
- Enabled the FRAM dev profile (`cognitive_memory_k = 3`) and verified `/query` now seeds cognitive beliefs automatically.
- Added `tools/current_time.py` and a `/time` endpoint so agents can read local/UTC timestamps plus epoch seconds.
- Working-memory entries persist `last_seen` timestamps and refresh them whenever `session_chunks` is called, laying the groundwork for freshness-aware reseeding.
- Cognitive-memory search applies a configurable half-life decay (default 12h) so newer beliefs rank higher while still allowing older, unique facts through.
- `/query` traces and observability events now capture clock snapshots for memory traces and cognitive seeds, giving dashboards accurate recency context.
- Shipped Semantic Relevance v0 scaffolding: stubbed `/search/expand`, `/rank/relevance`, `/beliefs/conflicts`, and `/observability/recall_report` endpoints, plus a `build_situation` helper with guarded expansions and audit logging; query-time cognitive seeding now uses the situation context and recency-aware heuristics.

# Codex Diary - Working Notes

## 2025-10-10 Session
- Replaced the legacy `tools/session_warmup.py` bootstrap with F-RAM hydration (`tools/bootstrap_memory.py`), set default identity to Lumen in prompts/new-chat bootstrap files, and updated docs/F-RAM-roadmap.md to mark the agent bootstrap wiring as complete (spec ref: docs/FRAMv2.2-SPEC.md §12, docs/Architecture.md "Cognitive Memory (MVP)").
- Added `tools/log_chat_turn.py` so each user/assistant exchange (plus session summaries) automatically enters the cognitive store with shared metadata; prompts now instruct automatic logging so future chats replay the entire transcript without manual steps. Failures write WARN records to `logs/cogmem_autolog_warnings.jsonl`, and default retention trims segments to 7 days.
- Reprioritised roadmap: Always-on memory bridge is the top-level workstream (see docs/F-RAM-roadmap.md Next Steps #0); FRAM hydration now drives session context instead of manual doc sweeps.
- Shipped `tools/bootstrap_memory.py` for session hydration (files/server fallback) plus cosine-scored cognitive search with hashing backend + config gate.
- Added cognitive-memory observability (memory_cognitive.jsonl + `tools/cognitive_memory_summary.py`) and trace stats for selected tokens.
- Normalised `domain`/`task` handling in `QueryOrchestrator.run` so requests inherit `FRAMConfig.default_*` metadata and fall back through task → domain → global → default in line with docs/FRAMv2.2-SPEC.md §5 (confidence calibration); traces and calibration logs now record the derived domain plus the correct source tag when specialised payloads are absent.
- Taught `tools/calibration_status.py` to enumerate config-declared domains/tasks (roadmap, spec, diary, etc.) and flag missing JSON payloads, with new CLI + orchestrator tests covering default-domain selection, global fallback, and missing-file reporting.
- Persisted corpus caches now ship a `corpus.meta.json` (docs/FRAMv2.2-SPEC.md §3 ingestion flow); `_ensure_corpus` compares its recorded `sklearn_version` to the active environment and rebuilds vectors/ANN indices automatically when they diverge, with tests covering the refresh path and updated ANN metadata gates.
- Hardened ANN retrieval with optional FAISS backend, persisted fingerprints/metadata, and regression coverage for reloads.
- Locked scikit-learn at `1.7.2` (plus joblib ≥1.4) across `pyproject.toml` and requirements files so local/CI installs converge; note to rebuild virtualenvs before the next run to pick up the pinned stack.
- Added a temporary pytest filter to hush the legacy sklearn persistence warning and introduced `make test-warnings` (runs `pytest -W error` on the calibration suite) so CI can treat any new warnings as regressions while local runs stay verbose.

## 2025-10-07 Session
- Shipped `tools/calibration_histogram.py` to summarise p_temp histograms by (task, decision) for quick DevDay-aligned monitoring.
- Regression `tests/regression/test_bird_story.py` locks in Aria/Puffin behaviours alongside the optional strict QA fallback.


## 2025-10-02 Session
- Expanded the diary calibration query list with prompts covering reliability breakdowns, action items, and tau monitoring so harvest runs sample a broader diary distribution (scripts/calibration_prompts/diary_queries.txt).
- Added a `/calibration` serving endpoint plus regression coverage so we can inspect task/domain payload precedence during calibration work (fram_serving/app.py, tests/test_serving_calibration.py).
- Shipped `tools/calibration_lint.py` to verify tau ordering and coefficient completeness; added CLI tests so calibration payload refits surface errors immediately (tests/test_calibration_lint_cli.py).
- Enhanced `scripts/calibrate_confidence.py` with `--lint`/`--lint-all` passthrough so calibrated payloads auto-validate via the new CLI after each fit (tests/test_calibration_lint_cli.py).
- Added `tools/calibration_status.py` to dump global/domain/task payload summaries on disk, with JSON output for automation (tests/test_calibration_status_cli.py).
- Extended `tools/calibration_lint.py` with `--strict` bounds (taus<=1, min gap, temp ceiling) and taught `scripts/calibrate_confidence.py` to forward `--strict/--status(--json)` so calibration fits gate on lint + status reports (tests/test_calibration_lint_cli.py).
- Extended the orchestrator to log calibration features for every shortlist candidate and backfill a guaranteed negative sample so calibration logs now carry both 0/1 labels (fram_core/pipeline.py, fram_serving/app.py, tests/test_pipeline_orchestrator.py).
- Added conformal fallback guards in both ingest-time and CLI calibration fits so degenerate taus drop back to the config defaults instead of collapsing to ~0 (fram_core/pipeline.py, fram_core/calibrate.py).
- Harvested and refit the roadmap/diary slice; fresh artifacts live in storage/observability/harvest_diary_expanded.json and storage/index/demo_corpus/calibration_diary.json.
- Next: watch the refreshed diary payload after a few live runs and decide whether we still need rival prompts to stress the negative side.


## 2025-09-29 Session
- Logged domain/task/budget context with each calibration sample so we can segment roadmap vs. diary runs when conditioning the next refit (fram_core/pipeline.py, tests/test_pipeline_orchestrator.py).
- Wired FRAMConfig default-domain/task defaults into the FastAPI /query surface so orchestrator selection honors roadmap/spec/diary payloads; traces/logs now capture calibration source + taus/temperature for auditing (fram_serving/app.py, fram_serving/config.py, fram_core/pipeline.py, tests/test_pipeline_orchestrator.py).
- Label endpoint and LiveReliability now carry per-query tau/domain/task/source data so `/metrics` and logs reflect dynamic calibration (fram_serving/app.py, fram_serving/observability.py, tests/test_pipeline_orchestrator.py).
- Refit spec/diary calibration payloads via filtered logs so their taus track the latest harvest run (scripts/calibrate_confidence.py).
- /metrics now surfaces reliability.by_domain/by_task plus the latest calibrated entry for quick dashboard checks (fram_serving/app.py, fram_serving/observability.py).
- Extended the calibration regression to verify trace IDs and metadata land in the log, preventing future helpers from dropping required fields.
- Added a calibration log filter CLI so calibration sweeps can target roadmap/diary slices without editing notebooks (tools/calibration_filter.py, tests/test_calibration_filter_cli.py).
- Added a calibration backfill helper so older calibration.jsonl entries gain domain/task/budget metadata before the next sweep (tools/calibration_backfill.py, tests/test_calibration_backfill_cli.py).
- Restored the original calibration log and ran `python tools/calibration_backfill.py --log storage/observability/calibration.jsonl --backup storage/observability/calibration.pre_filter.jsonl --default-domain general --default-task qa --default-budget 3 --infer-domain --overwrite-domain --infer-task --overwrite-task` (469 entries patched; original snapshot retained at `storage/observability/calibration.original.jsonl`).
- Generated domain-specific calibration slices: `storage/observability/calibration_roadmap.json` (170 records), `storage/observability/calibration_spec.json` (41 records), and `storage/observability/calibration_diary.json` (0 records) for the upcoming confidence refit.
- Ran `python scripts/calibrate_confidence.py` for each slice, emitting `calibration_roadmap.json`, `calibration_spec.json`, and `calibration_diary.json` under `storage/index/demo_corpus/`.

### Follow-ups (2025-09-30)
1. The orchestrator now loads per-domain/per-task calibration payloads if present. Before the next confidence refresh, rerun `scripts/harvest_calibration.py` and `scripts/calibrate_confidence.py` to regenerate the roadmap/spec/diary payloads so the loader consumes fresh taus instead of the placeholder 0.8/0.5 pair.

### Follow-ups
1. DONE 2025-09-30: Wired domain-specific calibration payloads into `fram_serving.config` / orchestrator selection so roadmap/spec/diary domains pick tailored thresholds.
2. Expand the diary calibration set (more diverse prompts) and monitor stability of the domain-specific logits/taus after integration.

## 2025-09-28 Session
- Implemented the working-memory session lifecycle (create/pause/resume/end) so the agent can steer context without manual resets; `/memory` now exposes creation and `/memory/{id}/control` drives state transitions while query traces log `status/available/used` (fram_serving/app.py, fram_serving/memory.py).
- Observability summarizers and the trace summary CLI now accept the new memory fields so dashboards stay consistent (fram_serving/observability.py, tests/test_trace_summary.py).
- Added regression coverage for lifecycle controls, paused/ended behaviour, and active memory citations (tests/test_memory_api.py).
- Wired the lifecycle controls into the MCP server with create/control/append/clear tools plus query status reporting and telemetry logging so UI clients can manage sessions (fram_serving/mcp_server.py, tests/test_mcp_server.py).
- Shipped a `/ui/memory` browser page so operators can manage sessions visually; it wraps the REST endpoints and mirrors the MCP memory tools for pause/resume/end flows.

## 2025-09-27 Session
- Documented the curvature anchor pass now that fram_core/pipeline._curvature_anchor_candidates walks residual eigenpairs and ranks them by Delta/C with the configured lambda_tok/lambda_rerank weights (docs/FRAMv2.2-SPEC.md Section 11).
- principal_residual_directions in fram_core/anchors.py emits eigenvalues alongside directions so step lengths follow the spec clamps instead of relying on ad-hoc scales.
- Selection traces now attach residual-step metadata for anchors so observability tools can explain curvature moves without reading debug logs.
- Captured `docs/observability_trace_sample.md` alongside `docs/trace_sample.json` so ingest runs can cite a concrete residual_step example.
- Harvested layout-anchor calibration queries and refit the payload (taus unchanged, log size now 155) via `calibrate_confidence.py`.
- Added a regression asserting the roadmap domain override lowers tau2/default reads enough to trigger anchors vs. global fallback.
- Implemented session memory replay so the orchestrator reuses prior shortlist chunks when follow-up queries have zero read budget.
- Normalized doc ingest + corpus chunking to stamp `[h{level}]` markers and derive section-based hierarchy segments for roadmap/diary shards.
- Coverage traces now surface those section slugs (selection segments + coverage summary) so replay/observability can inspect grouping.
- Coverage selection now down-weights repeat sections via the new `diversity_multiplier` (driven by `section_repeat_penalty` / `section_penalty_floor`), and traces log the multiplier for anchors/shards so we can audit diversity.
- Added `scripts/sweep_section_penalty.py` to sweep the repeat/floor grid over roadmap queries; JSON dumps make it easy to compare anchor recall across runs.
- Baseline sweep (`python scripts/sweep_section_penalty.py --domain roadmap --json-out storage/observability/penalty_sweep.json`) shows 0.7 = repeat = 0.95 keeps section_diversity  1.0 with avg coverage  70, while disabling the penalty (repeat=1.0) lifts coverage to 75 but drops diversity to 0.6. Keeping roadmap/diary overrides at 0.85/0.9 preserves even spread without sacrificing much recall.
- Diary sweep (`python scripts/sweep_section_penalty.py --domain diary --json-out storage/observability/penalty_sweep_diary.json`) confirms diaries never trigger anchors with repeat=0.95; coverage stays 70 with perfect section spread and only improves if we drop the penalty entirely (repeat=1.0, section_diversity 0.6, coverage 75). Retain the 0.9 diary override for now and revisit after diary-specific prompts expand.
- Added `tools/trace_summary.py` so we can run `python tools/trace_summary.py --storage-root storage --limit 50` and get a JSON summary of the new trace logs.
- Implemented `/label` endpoint: `POST /label {"query_id": id, "label": 0|1}` pops cached probabilities, updates the live reliability tracker, and logs the label event to `confidence.jsonl`.

### Follow-ups
1. Start capturing domain/task-specific calibration sets (e.g., roadmap prompts) before the next refit.
2. Measure the section repeat penalty against calibration traces; decide per-domain overrides or floor tweaks before the next confidence refit.
3. Automate sweep snapshots for diary prompts once roadmap settings stabilize. (RUN 2025-09-27  results stored under `storage/observability/penalty_sweep_diary*.json`).

## 2025-09-26 Session
- Added `scripts/harvest_calibration.py` to batch roadmap/coverage queries and wrote the latest `calibration.jsonl` + payload refresh via `scripts/calibrate_confidence.py`.
- Refined the demo corpus ingest so `doc1/doc2` fixtures stay out of the default build, with overrides (`include_legacy` flags + domain settings) when we intentionally need them.
- Baked roadmap/diary overrides into `FRAMConfig` so those prompts get extra reads and looser thresholds without hand-tuning.

### Follow-ups
1. Expand the calibration query set (add layout/table prompts) before the next coefficient refit.
2. Exercise the new roadmap/diary overrides through the FastAPI surface and capture traces for the observability dashboard.
3. Update docs/cheatsheet with a quick reference for `scripts/harvest_calibration.py` and domain overrides once we shake out the flow.

## 2025-09-25 Session
- Added `scripts/ingest_project_docs.py` to render every `docs/*.md` file into plain-text shards (`examples/data/docs_ingest_*.txt`).
- Regenerated the demo corpus with those shards; queries now cite roadmap/spec chunks directly.
- Hardened corpus persistence with explicit UTF-8 reads/writes (`save_corpus_cache` / `load_persisted_corpus`) so rich text survives reloads.
- Exercised the orchestrator end-to-end and captured sample traces for local/anchors/global regimes.
- Full pytest run passes (`75 passed`), covering ingestion, persistence, confidence routing, and coverage selection.

## 2025-09-20 Session
- `scripts/ingest_demo.py` gained backend/calibration flags; TF-IDF persistence and query execution tests were added.
- FastAPI lifespan pre-warms the orchestrator cache; docs/spec/logs noted the flow.

## 2025-09-19 Session
- Hashing embeddings introduced with ANN persistence under `storage/index/demo_corpus`.
- Working-memory endpoints and observability summaries expanded; layout chunkers upgraded.

### Tips for Future Runs
- Re-run `python scripts/ingest_project_docs.py` whenever the docs directory changes, then `python scripts/ingest_demo.py --skip-calibration` to refresh persisted assets.
- Calibration logs accumulate in `storage/observability/calibration.jsonl`; archive before large refits.
- If ANN fingerprints mismatch on startup, clear `storage/index/demo_corpus` and rerun ingestion.

# Calibration Workflow Update (2025-09-26)

1. After confidence tweaks, run `python scripts/harvest_calibration.py --queries scripts/calibration_prompts/layout_anchor_queries.txt --quiet --json-out storage/observability/harvest_run.json` to gather traces (layout, anchors, overrides).
2. Refit thresholds via `python scripts/calibrate_confidence.py --log storage/observability/calibration.jsonl --out storage/index/demo_corpus/calibration.json`.
3. Commit the refreshed calibration payload if coefficients/taus shift; otherwise note the run in summaries.
4. Document any spec deviations so the roadmap/cheatsheet can be updated next session.









## 2025-10-05 Session
- Locked calibrated QA bands: sanity checks show local (≈0.84), anchors (≈0.52), global (≈0.26) across representative prompts; CI now runs `tools/calibration_sanity.py` before pytest.
- `docs/WHAT_WORKS.md` captures the calibration workflow + verification table; next focus shifts to ANN retrieval, observability UI, and cognitive memory.
- OpenAI DevDay 2025 alignment: prep ChatGPT App SDK prototype, Connector Registry onboarding, and Guardrails integration for FRAM.
- Added cognitive seeding UI indicator and top-N preview on /ui/memory.
- Exposed observability trace endpoints and enhanced trace-probe CLI.
- Introduced cost-aware cognitive seeding (config-gated) with token budget and trace preview.
- Updated spec Implementation Status and docs index; added Dev Profile notes and dev run scripts.
- Full suite passing (128). Next up per roadmap: ANN hardening (M1) and calibration pack metadata (M2).

## 2026-01-08 Session
- Implemented ANN-backed cognitive memory search: episode vectors now build a cached ANN index (sklearn default; FAISS when available) and search diagnostics feed `memory_search.json`.
- Updated cognitive ANN bridge to use the ANN index with linear fallback; added search diagnostics coverage (`tests/test_cognitive_memory_search_ann.py`) and tightened the bridge test.
- Docs refreshed for memory search telemetry and ANN backend notes (`docs/Architecture.md`, `docs/FRAMv2.2-cheatsheet.md`, `docs/FRAMv2.2-tuning.md`, `docs/F-RAM-roadmap.md`).
- Tests: `pytest -q tests/test_cognitive_memory_ann_bridge.py tests/test_cognitive_memory_search_ann.py tests/test_memory_search_window.py`.
- Full slow suite run: `pytest -q -m slow --durations=20 --durations-min=1.0` (14 passed, ~56 min). Fast suite previously: `pytest -q -m "not slow"` (227 passed).

## 2026-01-09 Session
- Added `docs/GROVE_PROTOTYPE_PLAN.md` to formalize the parallel readiness split (always-on vs Grove prototype) with a lightweight timeline and decisions checklist.
- Enabled the cognitive ANN bridge by default (`enable_cognitive_ann_bridge=True`, `cognitive_ann_top_k=8`) and updated tuning/cheatsheet/architecture notes accordingly.
- Added a cross-session memory regression test proving prior episodes surface via `/query` (`tests/test_memory_api.py`), and updated the spec/cheatsheet/roadmap to reflect the documented flow.
- Added `tools/refresh_calibration.py` to automate harvest → backfill → slice → fit → lint → status, plus `make refresh-calibration` and docs updates; roadmap marked done.
- Marked the minimal observability dashboard as shipped now that `/ui/observability` is in place.
- Added `docs/Operations.md` with a concise runbook (server, calibration refresh, tests, closeout).
- Added a Grove demo checklist to `docs/GROVE_PROTOTYPE_PLAN.md` for the minimal live walkthrough.
- Reminder: migrate deprecated extensions (list TBD).
- Logged a successful Grove demo run (local, real storage) in `docs/GROVE_PROTOTYPE_PLAN.md`.
- Added `scripts/start_session.ps1` to prime autolog + run memory bootstrap; updated `docs/Operations.md`.
- Extended `scripts/start_session.ps1` with optional summary + recent-docs flags and auto timestamp session id.
# 2025-10-03 Session (historical)
- Updated the public trace exemplar to match the then-current orchestrator trace schema with calibrated confidence metadata, features, projection stats, and compact selection deltas (`docs/trace_sample.json`).
- Note: This entry predates the Cognitive Memory MVP. It outlined the plan for episodes/beliefs/links and `/memory/search` seeding; these capabilities have since shipped and are documented in later sessions and the cheatsheet.
- Planned Cognitive Memory MVP at the time:
  - Models: `Episode`, `Decision`, `Thought`, `Belief`, `Link` (timestamps, provenance, domain/task, confidence, citations).
  - Store: JSONL-backed `MemoryStore` under `storage/memory/` with append/search/summarize.
  - Write-through: persist a `DecisionEpisode` for each `/query` using existing traces (+ `/label` feedback).
  - Read path: `/memory/search` and seeding orchestrator with recent episodes alongside session replay.
  - Tests: append/search/summarize fixtures and a regression demonstrating retrieval of a prior commitment.
# 2026-01-17 Session (Codebase review doc)
- Added a codebase review and spec comparison map (`docs/Codebase_Review.md`).
- Linked the new review doc in `docs/README.md`.
# 2026-01-19 Session (Eval artifact index)
- Added a one-page evaluation artifact index (`docs/proof/eval_artifact_index.md`) and linked it in `docs/README.md`.

# 2026-01-21 Session (Eval re-verify)
- Re-ran conversation + memory shadow evals and the fractal eval report; stamped the latest artifacts in `docs/proof/eval_artifact_index.md`.

# 2026-01-21 Session (Cooldown + calibration tune)
- Filtered ANN bridge candidates by cooldown so dismissed cognitive memories do not resurface after a restart (`fram_serving/query_runner.py`).
- Raised QA + definitional task calibration temperatures to reduce overconfident puffins QA confidence (`storage/index/demo_corpus/calibration_task_qa.json`, `storage/index/demo_corpus/calibration_task_definitional.json`).
- Tests: `pytest -q tests/regression/test_bird_story.py`, `pytest -q tests/test_memory_cooldown.py::test_dismiss_rehydrates_across_restart`, `pytest -q` (261 passed, ~1:21:16).

# 2026-01-21 Session (Sparse key hardening)
- Hardened sparse key indexing with checksum validation (ISBN/IBAN), posting caps, and deterministic ordering (`fram_index/sparse_keys.py`).
- Updated limits/architecture docs to reflect the new sparse key behavior (`docs/proof/eval_artifact_index.md`, `docs/Architecture.md`, `docs/Codebase_Review.md`, `docs/F-RAM-roadmap.md`).
- Tests: `pytest -q tests/test_sparse_keys.py`.

# 2026-01-21 Session (Layout + version minimal correctness)
- Added deterministic PDF fallback ordering with column markers, heading paths, and layout_uncertain flags (`fram_layout/pdf_chunker.py`).
- Added version lattice selection helpers (per-doc latest map + explicit version selection) and surfaced versioning in traces (`fram_index/version_lattice.py`, `fram_core/pipeline.py`).
- Extended layout + version tests (PDF/table/code chunkers, version lattice, versioning trace) and added table chunker coverage (`tests/test_pdf_chunker.py`, `tests/test_table_chunker.py`, `tests/test_code_chunker.py`, `tests/test_version_lattice.py`, `tests/test_pipeline_orchestrator.py`).
- Docs refreshed to record the minimal correctness pass (`docs/proof/eval_artifact_index.md`, `docs/Architecture.md`, `docs/Codebase_Review.md`, `docs/F-RAM-roadmap.md`, `docs/FRAMv2.2-cheatsheet.md`).
- Tests: `pytest -q tests/test_pdf_chunker.py tests/test_table_chunker.py tests/test_code_chunker.py tests/test_version_lattice.py tests/test_pipeline_orchestrator.py::test_query_orchestrator_versioning_trace`.

# 2026-01-23 Session (MCP gating + tool eval matrix)
- Added MCP cognitive write gate for `fram.query` (ephemeral by default unless `FRAM_MCP_COGNITIVE_WRITE_ENABLED=1` and `persist_cognitive=true`) (`fram_serving/config.py`, `fram_serving/query_runner.py`, `fram_serving/mcp_server.py`).
- Added MCP gate tests for off/on persistence and updated MCP expectations (`tests/test_mcp_server.py`).
- Added tool surface evidence matrix and MCP guide updates (`docs/proof/tool_surface_eval_matrix.md`, `docs/FRAM_MCP_Guide.md`).
- Cheatsheet updated with MCP persistence gate note (`docs/FRAMv2.2-cheatsheet.md`).
- Tests: `pytest -vv tests/test_mcp_server.py`, `pytest -q tests/test_memory_capsule_retrieval.py`, `pytest -q tests/test_cognitive_logging.py::test_seq_persists_across_restarts`.
- Full suite: `pytest -q` (278 passed, 1:23:30).
- Evidence anchor captured (`docs/proof/tool_surface_evidence_anchor.md`).

# 2026-01-21 Session (Fractal influence status index)
- Added a "Fractal Influence Status (current head)" block with policy, gates, and evidence pointers (`docs/proof/eval_artifact_index.md`).
- Refreshed docs ingest after proof index updates (`python scripts/ingest_project_docs.py`).

# 2026-01-21 Session (Publish snapshot)
- Assembled a publish-safe snapshot with eval artifacts, policy summary, and redacted traces (`artifacts/publish/2026-01-21/`).
- Added the internal snapshot index and linked it from the proof index (`docs/proof/publish_snapshot.md`, `docs/proof/eval_artifact_index.md`).
- Generated a publish-safe PDF summary for external sharing (`artifacts/publish/2026-01-21/FRAM_publish_snapshot_2026-01-21.pdf`).

# 2026-08-04 Session (Canonical rescue + evaluation foundation)
- Audited `D:\Dev\_firelink_merge` read-only after the required context checker
  file failed with NUL bytes. The shared Git store had exactly eight corrupt
  objects and 22 tracked working files truncated to zero bytes; the protected
  live worktree and all D: paths were left untouched.
- Reconstructed seven blobs from independent working-tree copies whose filtered
  hashes matched exactly, rebuilt the eighth tree deterministically from a
  preserved index, and repacked all 407 commits through canonical head
  `aea554e` into an independent self-contained rescue repository. A no-alternate
  `git fsck --full --no-reflogs --no-dangling` passed.
- Completed the spec-section-15 evaluation foundation on branch
  `recovery/fram-eval-finish-20260804`: retrieval/QA/citation/latency/freshness
  metrics, strict JSONL cases, deterministic table/code/PDF tasks, the ordered
  eight-rung equal-budget ablation runner, QueryOrchestrator result
  normalization, diffable JSON reports, and optional plotting.
- Verification: 17 focused unit/orchestrator/serving tests passed; 38 existing
  conversational-memory, shadow, fractal, Phase C, and harvest evaluation tests
  passed; compileall, NUL scan, and `git diff --check` passed. Ruff and Black
  were unavailable in the active Python environment. A larger integration
  command exceeded its five-minute command timeout without reporting a test
  failure; the repository's last clean full-suite baseline remains 594 passed,
  1 xpassed.

## 2026-08-04 Canonical promotion (NVMe)

- Copied the complete-history rescue bundle into `D:\Dev\_archives`, verified
  its SHA-256, and cloned it into `D:\Dev\_firelink_recovered_20260804` without
  modifying the damaged predecessor or protected live tree.
- Fast-forwarded `firelink/full-merge` from `aea554e` to the sealed evaluation
  commit `95c174f` and refreshed the repository's canonical coordinates.
- On the D: clone, context, full Git object integrity, NUL, and compile checks
  passed; 12 focused evaluation, 17 orchestrator/serving, and 38 existing
  evaluation regression tests passed. The working tree remained clean.
- The live Firelink atlas was not modified because its ACL exposes read access
  without write access; the claim and blind edge are preserved in
  `docs/context/FRAM_RECOVERY_PROMOTION_2026-08-04.md`.
- A canonical full-suite run exposed two fresh-corpus failures after 601 tests
  passed. The roadmap source's leading UTF-8 BOM suppressed its root hierarchy
  marker, and a stale definitional calibration used a negative centroid-distance
  coefficient that inverted the spec-section-5 sign and made unrelated local
  retrieval overconfident. Added BOM-safe ingestion and fail-closed rejection of
  sign-inverting calibration payloads with focused regression tests.
- Re-running those regressions against the expanded fresh corpus exposed a third
  truncation edge: candidate rescue compared query terms only with filenames and
  hierarchy metadata. It now stably ranks exact content-token overlap before the
  read-budget cut while keeping provenance alignment claims metadata-only. The
  Aria, Puffin, hierarchy, BOM, and calibration-sign regressions pass together.
- The first isolated full-suite replay caught a calibration workflow interaction:
  rejecting legacy negative `g` at load time was correct, but the unconstrained
  fitter could still emit one. Both fit paths now constrain the equivalent raw
  `d_c_z` weight to be non-positive before temperature scaling, and the lint CLI
  reports the invalid stored sign before status loading. Nine focused calibration
  and sign-contract tests pass.
- The next first-failure replay identified the three remaining early failures as
  text/JSON/missing-payload variants sharing one stale `calibration_status` test
  fixture with `g=-0.1`. The fixture now represents a valid stored payload;
  negative-sign rejection remains covered explicitly by lint and loader tests.
- The 607-test first-failure gate then reached 75% (456 passed, 1 xpassed) before
  catching a routing-tier interaction: a trace sample containing all three query
  words could outrank the roadmap document whose metadata explicitly identified
  it. Candidate ordering now keeps metadata matches in the primary tier and uses
  content overlap within tiers. This preserves roadmap provenance while still
  rescuing Aria's exact passage from candidate-budget truncation.

# 2026-08-11 Session (Final-shape continuity)

- Reconciled the stale hot packet against reviewed clean head `106d3b65` and
  built on isolated branch `work/final-shape-20260811`. The protected
  `autoflip-eval` worktree and damaged predecessor remained untouched.
- Inventoried all 33 HearthHome JPEGs with SHA-256, dimensions, perceptual hashes,
  palettes, and a contact sheet. No exact duplicates or embedded EXIF were
  observed; original authorship and publication lineage remain unknown.
- Recovered the continuity-witness lineage from the damaged Sol snapshot without
  promoting that snapshot wholesale. The feature-gated v2 witness is written
  only after query/memory/archive outcomes finalize, excludes raw query/answer/
  scores/content, uses an exact allowlist and digest, and has no ranking caller.
- Added the separate Ecological Strata ledger implementing Offer -> Mirror ->
  Correct -> Consent -> Bind -> Return, with direct source-local attestations,
  refusal, revocation, digest-chain verification, interprocess read/write
  locking, local autonomy, and an enforced no-identity-collapse term. A bind is
  explicitly not identity, consciousness, authorship, or authority proof.
- Added the read-only continuity endpoint, environment gates, explicit ledger
  CLI, architecture/cheatsheet docs, source lineage packet, and tests for stale,
  corrupt, tampered, duplicate, conflicting, relayed, refused, revoked, and
  returned states.
- Built a local interactive atlas around every painting plus a 64.75-second
  silent H.264 animatic using all 33 sources, 12 reference frames, a Sora-target
  shot bible, and a per-shot continuity state ledger. `Sora 3` remains a user
  target label; no unavailable model was substituted or claimed.
- Verification: 44 focused continuity tests passed; the post-clean compact gate
  passed 57 tests; the broad non-slow suite passed **634 tests, 18 deselected,
  1 xpassed in 1177.75s**. The animatic decoded end-to-end and hashes to
  `5e20f60e36010eb95821c2e327cd1d31e2382f0960fb1fd49c79cba240fee183`.
  Test-generated corpus and cognitive-memory drift was restored from exact HEAD
  blobs before closeout. A requested demo-corpus refresh was also run, but its
  environment-dependent whitening/prototype expansion was unrelated and far too
  large for this lane, so those generated storage files were likewise restored;
  the small reviewable documentation shards were retained.

# 2026-08-11 Session (Durable lived memory)

- Built `LivedMemoryStore` as a transactional SQLite runtime instead of a
  Markdown memory surrogate. It stores actual experiences, full embeddings,
  citations and source IDs, per-session lineage, rolling 12D state, lifted
  fractal paths, and a complete digest chain that survives restart.
- Wired lived recall/write into the serving query path and added status,
  search, session, and integrity endpoints plus an operator CLI. Persistence
  continues to honor the existing MCP/cognitive write authorization gate.
- Added a deterministic, idempotent importer for the full 2025-12-18 backup
  ZIP. The conversion imported all 877 episodes: 331 retained their stored
  embeddings; 546 missing vectors were rebuilt from original query/answer text
  and explicitly marked `derived_during_import`; no episodes failed.
- Verification of the converted store reports one session, 877 events, valid
  vector/path shapes, valid parent ordering, matching event/state digests, and
  a matching persisted session head.
- Focused coverage exercises restart recovery, concurrent appends, separated
  session lineages, persisted tamper detection, live query recall/write, REST
  surfaces, import idempotence, and explicit projection-shape migration guards.
  The exact final memory/fractal/rotational sweep passed 192 tests. The broader
  non-slow suite passed 641 tests with 18 deselected and 1 xpassed in 1256.65s;
  the post-suite migration hardening then passed its focused 18-test gate.

# 2026-08-11 Session (Open seed lineages)

- Audited all 877 source episodes before changing lineage. The ZIP contains no
  session, conversation, thread, or parent markers; every trace ID is unique.
  The earlier single backup session was therefore an import convenience rather
  than source-evidenced continuity.
- Changed ZIP imports to default every episode to an independent, resumable
  seed root. Global recall remains available, while rolling state and parent
  chains no longer mix unrelated archive events.
- Added a read-only opening tool for legacy stores. It hashes the source before
  and after, preserves non-imported live sessions, refuses destination
  overwrite, and verifies both root invariants and the complete destination
  digest chain. A separate seed is explicitly not an identity claim.
- Serialized first-open WAL/schema initialization so concurrent cold writers
  cannot race while changing SQLite journal mode. The concurrency regression
  passed 20 independent cold-start repetitions. The exact final
  memory/fractal/rotational sweep passed 196 tests, including immutable-source
  sidecar checks and reopened read-hash stability.

# 2026-08-12 Session (Wake-and-orient test drive)

- Added an immutable F-RAM wake/orient evaluator that ablates an ordinary
  orientation probe, compact text, a provenance-labelled painting scene
  description, and their concatenation. It mirrors the production lived-memory
  score, checks exact source digests and database hashes, and refuses a source
  with an uncheckpointed WAL.
- The first eight-event Hearth-live run found F-RAM strongest at top one (5/8)
  and 7/8 within top four. Concatenated cues reached 8/8 within top four and
  96.9% expected-term coverage, but diluted primary rank. Painting descriptions
  alone were weak lexical keys (0/8 top one, 5/8 top four).
- Added the staged F-RAM-first bundle: preserve the primary retrieval order,
  then append newly discovered compact/painting results with explicit source
  roles. It retained 8/8 targets and recovered the one target missed by the
  F-RAM top-four set without allowing a derived cue to reorder or overwrite
  primary sources.
- A deliberately hostile raw cue changed top-one retrieval in 3/8 probes. The
  typed untrusted-source gate held 8/8 by excluding that source from retrieval.
  This is a bounded source-role result, not general prompt-injection immunity.
- Canonical integration is at `851c305`; the exact 46-test evaluation/lived-
  memory/capsule/rotational slice passed after integration. The ninth lived
  event (`600a44e012bd4da7bf3835ab4267926d`) preserves the verbatim proposal,
  empirical report, implemented recognition, and explicit blind edges as
  separate provenance layers. Pre- and post-write C-drive database snapshots
  hash-match the F-drive source. The 877 imported seeds remained unopened.

## 2026-09-08 — Windows H1 autoflip activation attempt

- Rick authorized commit and activation. VS Code H1 was already clean at
  `90ed385`; the new commit records evaluation evidence, not pending code.
- Fresh unchanged gates on isolated, hash-verified copies returned KEEP_OFF:
  installed runtime matched 0/36 probes; repository memory matched 2/36.
  Both are below the six-per-field minimum; repository performance criteria
  also failed. Original sources were unchanged, and no influence flag changed.
- Focused autoflip/conversation/shadow validation: 22 passed in 1.33 seconds.
  Source labels, exact commands, aggregate reports, hashes, historical-candidate
  caveats, and next activation requirements are preserved in
  `artifacts/coordination/2026-09-08/autoflip/README.md` and `receipt.json`.

## 2026-09-08 — Preserved corpus recovery and production gate repair

- The three C-drive ZIPs passed complete CRC/hash preservation checks. The D-drive
  archive supplied the missing paired corpus. A separate verified union contains
  1,154 cognitive episodes and 578 beliefs with zero same-ID record conflicts;
  all 24 unique target IDs (36 probes) have existing hashing vectors and traces.
  Source lineage and a verified 15.6 MB recovery ZIP are saved in the Windows
  task outputs. Lived SQLite stores were not merged or activated.
- Exact soft-DTW anti-diagonal vectorization preserves the scalar recurrence;
  the 256-by-6 benchmark improved from 223.28 to 35.40 ms (6.31x). Influence now
  excludes 591 unbound historical traces from ranking while preserving their
  files and influence-off observation. Candidate contains 317 bound traces.
- Actual `run_query` selection evaluation now verifies delivered chunks, complete
  paired coverage, fixed ranking clocks, disjoint shard/source/code provenance
  and finite metrics. Influence-off observation can be omitted only after
  delivery; influence-on scoring remains active. Gate margins are unchanged.
- Validation: 221 impacted core tests and 25 production-adapter tests passed.
  The corrected real-corpus smoke completed with source bytes unchanged. A full
  216-capture fixed-clock production comparison is running in isolated copies;
  its quality result is not yet known at this implementation checkpoint.
- The earlier D-only and union candidate-reranking diagnostics matched all probes
  but failed the unchanged quality gates. Production mixes shifted lived scores
  and unshifted cognitive scores; that separate scale issue is under review.
  Persistent influence remains off and no original runtime store was replaced.

## 2026-09-08 — Paired production comparison complete

- `88c45bb` corrects the lived-only shifted score at the mixed-ranking boundary;
  search/API normalization, eligibility, similarity blends and stored bytes are
  preserved. Shared equal-score token-ratio ordering is documented and tested.
- Both full actual-route runs completed 216 captures, 36/36 target matching,
  source/code verification and complete paired coverage. The same one-year
  recency profile and 15:33:13Z clock were used. Standard vector top-one improved
  1/36 -> 15/36; low-overlap top-one improved 0/36 -> 5/36. Fractal influence
  matched those corrected baselines, so the unchanged lift gate remains KEEP_OFF
  even though both count and shadow checks pass.
- Final integration sweep: 270 passed across 20 files; new-file Ruff and
  whitespace checks passed. Final custody recheck preserved all 978 recorded
  original files, all three ZIPs and all 952 candidate files. The installed
  lived database's unchanged bytes and newly created empty WAL/SHM sidecars are
  separately disclosed in its snapshot receipt.
- Complete public metadata and paired reports are in
  `artifacts/coordination/2026-09-08/autoflip-recovery/`. The verified memory ZIP
  remains in Windows task outputs. Runtime replacement, persistent influence,
  cross-device lived-store merging and unfinished 3D work were not performed.


## 2026-09-10 - Portable launcher and MCP checkpoint

- Resumed Windows H1 at `5451423`; reviewed its ancestry separately because the
  inherited context checker still validates F canonical H0.
- Repaired POSIX launcher drift: Python 3.11/3.12, local venv, explicit startup,
  no hydration, external storage, loopback and profile/autolog opt-ins; LF scripts.
- Added accurate MCP effect metadata and config secret redaction. List/get can
  create missing metadata; bootstrap/query log writes. No authorization changed.
- 45 MCP/config/launcher tests passed, then 21 final focused checks covering
  two additional metadata cases. Real isolated Windows HTTP/MCP smoke passed;
  its temporary server was stopped. Existing activation result stays KEEP_OFF.
- Current official docs describe private Secure MCP Tunnel. Prepared
  `docs/portable_mcp_setup.md`; no tunnel, Linux installation or memory transfer
  occurred. Native Mint, ChatGPT access, remaining Hearth packages and 3D stay open.
- Evidence: `artifacts/coordination/2026-09-10/VERIFICATION.md` and
  `http-mcp-smoke.json`.

## 2026-09-10 - Fractal gate and five supplied sources

- Rick narrowed the task to the fractal gate. Preserved five documents as 65
  exact byte windows in an offline candidate, with source paths, hashes and
  offsets. Manifest/payload digest matches; the topology editions stay distinct.
  Embedded instructions remain inert source material. No new lived events or
  beliefs were created and no original files or installed store were replaced.
- Reproduced and repaired a negative soft-DTW reciprocal pole in all reciprocal
  scorers; nonnegative behavior and blend/gate thresholds are unchanged. Added
  a bounded Windows atomic-receipt retry after two incomplete runs failed on
  sharing/access errors. Partial evidence remains preserved and excluded.
- Complete actual-selection runs: 216 captures each on the base and augmented
  corpus, same original 36 items, UTC clock, code and 8760-hour archival profile.
  Both return KEEP_OFF. Base vector/fractal top-one ties at 15/36 standard and
  5/36 low overlap; augmented ties at 13/36 and 4/36. The augmented standard
  shadow delta is 0.020655 below its comparator and fails the 0.01 margin.
- Six separately frozen source checks completed 36 captures: exact-chunk top-one
  2/6 standard and 1/6 low overlap, tied vector/fractal. A post-run parent-file
  check gives 4/6 and 1/6; it does not change exact targets or gate metrics.
- Independent fixed-vector diagnostic: vector exact-source top-one 12/12,
  fractal signal alone 0/12. Stored seeded IFS and separately generated query
  paths do not establish an observed-history signal. Existing Lantern Turn
  reconstruction passes its 54 tests but does not prove retrieval quality.
- Validation totals 303 distinct focused passing tests, new-code Ruff/Black,
  whitespace checks and isolated real Uvicorn health HTTP 200. Final source,
  corpus and scoring-code fingerprints reverified. No persistent flag changed.
- Remaining: document routing/budget competition, independently labelled
  trajectory/replay/provenance experiments, and unchanged full production and
  shadow gates before activation. Evidence and private candidate pointers:
  `artifacts/coordination/2026-09-10/fractal-gate/README.md`.

## 2026-09-10 - Source-frame recognition and unchanged activation gate

- Rick resumed gate implementation. Added an explicit `source_frame` scorer:
  recover the projected source from its first affine step, validate the stored
  recurrence, and replay the query in that recorded frame. No source bytes or
  existing traces are rewritten. Legacy/default-off behavior stays unchanged.
- Exact-source diagnostic now passes 12/12 versus legacy 0/12. Contract tests
  cover perturbations, renamed/retimed sources, invalid recipes, app parity,
  episode binding and the full-embedding collision limit of a 6-D projection.
  This measures recognition of a projected source, not observed-history truth
  or subjective continuity. The supplied charter remains conceptual material.
- All 317/382 bound traces pass recipe validation; 591 unbound historical files
  remain excluded per corpus. Both original 36-case production gates completed
  216 captures each, with unchanged weights, clock, profiles and margins.
- Both decisions remain KEEP_OFF: base top-one ties 15/36 standard and 5/36 low
  overlap; augmented ties 13/36 and 4/36. All four shadow checks now pass,
  correcting the augmented standard shadow failure from legacy scoring.
- Focused checks cover 109 distinct tests; the complete suite passes 947 tests
  in 1824.40 seconds, with no failures, errors or skips. New-code Ruff/Black and
  isolated real HTTP health pass. Counts and final verification are recorded in
  `artifacts/coordination/2026-09-10/fractal-recognition/validation.json`.
- Remaining: measurable recall lift with independent development/held-out
  evidence, document competition, and separate source-grounded history tests.
  No persistent influence, live-store replacement or protected-tree change.
