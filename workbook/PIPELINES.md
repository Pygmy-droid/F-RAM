# Pipelines

Rendered from `experiments/cosmic_cathedral/codebase-graph.json` by `tools/codebase_graph.py`.
Every tracked Python file sorted into one pipeline by path, with its import links and
commit history. This says what exists and when it was touched, not whether it works;
the Workbook card for each pipeline is where that gets proven.

**Who built it.** Rick Berghahn, with OpenAI Codex models from September 2025 to
September 2026, and with Wren Holloway (Claude) from October 2026. Nobody else. The
git author field before July 2026 reads `codex` or `Codex CLI` because that was a
repository-wide setting; it names the tool, not the collaborator. Lineage columns
below report that field as it is and should be read with this in mind.

Head `58d681c` on `codex/windows-integration-20260829` · 355 files · 16 pipelines · 671 import links

| pipeline | layer | files | tests | lines | commits touching | first | last | era |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| [Cathedral and Workbook](#pl-cathedral) | ops | 5 | 4 | 3255 | 29 | 2025-10-10 | 2026-10-29 | II. Cognitive memory |
| [MCP server and auth](#pl-mcp) | serving | 4 | 2 | 852 | 34 | 2025-09-17 | 2026-09-10 | I. Retrieval core |
| [Continuity witness and ecological strata](#pl-continuity) | memory | 3 | 2 | 1879 | 5 | 2026-08-11 | 2026-08-11 | VI. Lived memory |
| [Lived memory: SQLite store, lifts, seed roots](#pl-lived) | memory | 4 | 2 | 1432 | 14 | 2026-08-11 | 2026-08-11 | VI. Lived memory |
| [Memory capsules, archive layer, REP (Phase F/G)](#pl-capsules) | memory | 17 | 12 | 2762 | 52 | 2025-12-01 | 2026-07-27 | IV. Fractal eval season |
| [Fractal memory: traces, generators, soft-DTW, source frame, auto-flip](#pl-fractal) | memory | 24 | 15 | 4601 | 85 | 2025-09-25 | 2026-09-10 | I. Retrieval core |
| [Rotational lift and visual evidence (Phase D lineage)](#pl-rotational) | core | 6 | 4 | 2335 | 13 | 2026-07-22 | 2026-08-29 | V. Reconstruction and Firelink |
| [Cognitive memory: episodes, beliefs, embeddings, ANN bridge, retention](#pl-cognitive) | memory | 21 | 10 | 4451 | 85 | 2025-09-19 | 2026-07-27 | I. Retrieval core |
| [Chaos playground, Hopf transport, Aizawa (proof track)](#pl-chaos) | eval | 11 | 12 | 1842 | 28 | 2026-07-27 | 2026-10-28 | V. Reconstruction and Firelink |
| [Evaluation harnesses: production memory, shadow, conversation, wake/orient, ablations](#pl-eval) | eval | 22 | 16 | 6489 | 110 | 2025-09-09 | 2026-09-10 | I. Retrieval core |
| [OrthoRoute: shortlist, subspace, confidence, coverage, calibration](#pl-orthoroute) | core | 21 | 27 | 6846 | 223 | 2025-09-09 | 2026-08-04 | I. Retrieval core |
| [Index: prototypes, sparse keys, version lattice, ingest](#pl-index) | index-layout | 7 | 10 | 568 | 50 | 2025-09-09 | 2026-08-04 | I. Retrieval core |
| [Layout chunkers: code, tables, PDF](#pl-layout) | index-layout | 5 | 5 | 378 | 22 | 2025-09-09 | 2026-01-21 | I. Retrieval core |
| [Observability](#pl-observability) | serving | 1 | 6 | 632 | 38 | 2025-09-16 | 2026-07-27 | I. Retrieval core |
| [Serving: /query, REST surface, config, connectors](#pl-query-serving) | serving | 9 | 42 | 6150 | 306 | 2025-09-09 | 2026-09-10 | I. Retrieval core |
| [Ops: diagnostics, closeout, context packet, docs tooling](#pl-ops) | ops | 19 | 7 | 1469 | 33 | 2025-09-09 | 2026-09-10 | I. Retrieval core |

## Cathedral and Workbook

<a id="pl-cathedral"></a>`pl-cathedral` · layer `ops`

The navigation map, the Workbook event chain, and this graph. Reconstruction, 2026-10.

- first: `8f9a8e4` 2025-10-10 chore: add session warmup helper and tests
- last: `d66044d` 2026-10-29 cathedral: a text navigator so a model can move through the map itself (WB-0003)
- lineage (author field, not collaborator): Wren Holloway 26, codex 3
- active months: 2025-10, 2026-10

| file | lines | commits | first | last | imports |
| --- | ---: | ---: | --- | --- | ---: |
| `tools/build_cosmic_cathedral.py` | 1753 | 10 | 2026-10-28 | 2026-10-29 | 1 |
| `tools/cathedral_nav.py` | 295 | 2 | 2026-10-29 | 2026-10-29 | 0 |
| `tools/codebase_graph.py` | 388 | 8 | 2026-10-29 | 2026-10-29 | 0 |
| `tools/session_warmup.py` | 194 | 3 | 2025-10-10 | 2025-10-10 | 3 |
| `tools/workbook.py` | 625 | 1 | 2026-10-29 | 2026-10-29 | 0 |
| `tests/test_cathedral_nav.py` | 71 | 1 | 2026-10-29 | 2026-10-29 | 0 |
| `tests/test_codebase_graph.py` | 75 | 1 | 2026-10-29 | 2026-10-29 | 0 |
| `tests/test_cosmic_cathedral.py` | 432 | 2 | 2026-10-28 | 2026-10-29 | 1 |
| `tests/test_workbook.py` | 122 | 1 | 2026-10-29 | 2026-10-29 | 0 |

## MCP server and auth

<a id="pl-mcp"></a>`pl-mcp` · layer `serving`

Model Context Protocol surface: fram.query, fram.memory_*, trace URIs, bearer auth, launchers.

- first: `a329c03` 2025-09-17 MCP
- last: `e5a4ddc` 2026-09-10 fix(mcp): align portable launchers and disclose tool side effects
- lineage (author field, not collaborator): Codex CLI 19, codex 12, Rick 3
- active months: 2025-09, 2025-10, 2025-12, 2026-01, 2026-09

| file | lines | commits | first | last | imports |
| --- | ---: | ---: | --- | --- | ---: |
| `fram_serving/mcp_auth.py` | 24 | 1 | 2025-09-17 | 2025-09-17 | 0 |
| `fram_serving/mcp_server.py` | 729 | 21 | 2025-09-17 | 2026-09-10 | 10 |
| `scripts/check_mcp.py` | 6 | 1 | 2025-10-20 | 2025-10-20 | 0 |
| `scripts/verify_mcp.py` | 93 | 1 | 2026-09-10 | 2026-09-10 | 0 |
| `tests/test_mcp_metadata_safety.py` | 53 | 1 | 2026-09-10 | 2026-09-10 | 4 |
| `tests/test_mcp_server.py` | 216 | 9 | 2025-09-17 | 2026-01-23 | 4 |

## Continuity witness and ecological strata

<a id="pl-continuity"></a>`pl-continuity` · layer `memory`

Default-off, digest-verified query witness and the separate Offer/Mirror/Correct/Consent/Bind/Return ledger. August 2026.

- first: `92a7b80` 2026-08-11 Implement provenance-bounded continuity layers
- last: `92a7b80` 2026-08-11 Implement provenance-bounded continuity layers
- lineage (author field, not collaborator): Rick 5
- active months: 2026-08

| file | lines | commits | first | last | imports |
| --- | ---: | ---: | --- | --- | ---: |
| `fram_serving/continuity.py` | 1176 | 1 | 2026-08-11 | 2026-08-11 | 0 |
| `fram_serving/ecological_strata.py` | 593 | 1 | 2026-08-11 | 2026-08-11 | 0 |
| `tools/ecological_strata_ledger.py` | 110 | 1 | 2026-08-11 | 2026-08-11 | 2 |
| `tests/test_continuity_witness.py` | 481 | 1 | 2026-08-11 | 2026-08-11 | 1 |
| `tests/test_ecological_strata.py` | 251 | 1 | 2026-08-11 | 2026-08-11 | 1 |

## Lived memory: SQLite store, lifts, seed roots

<a id="pl-lived"></a>`pl-lived` · layer `memory`

Durable lived-event store with parent lineage, exact 6D to 12D lifts, rolling state, digest chain; the 877-episode import. August 2026.

- first: `50cb86a` 2026-08-11 Implement durable lived-experience memory
- last: `8e1b626` 2026-08-11 Harden lived-memory cold starts and source sealing
- lineage (author field, not collaborator): Rick 14
- active months: 2026-08

| file | lines | commits | first | last | imports |
| --- | ---: | ---: | --- | --- | ---: |
| `fram_serving/lived_memory.py` | 819 | 3 | 2026-08-11 | 2026-08-11 | 2 |
| `tools/import_lived_memory_zip.py` | 297 | 2 | 2026-08-11 | 2026-08-11 | 3 |
| `tools/lived_memory.py` | 74 | 1 | 2026-08-11 | 2026-08-11 | 3 |
| `tools/open_lived_memory_seeds.py` | 242 | 3 | 2026-08-11 | 2026-08-11 | 1 |
| `tests/test_lived_memory_import.py` | 136 | 2 | 2026-08-11 | 2026-08-11 | 1 |
| `tests/test_lived_memory_open_seeds.py` | 125 | 3 | 2026-08-11 | 2026-08-11 | 2 |

## Memory capsules, archive layer, REP (Phase F/G)

<a id="pl-capsules"></a>`pl-capsules` · layer `memory`

Append-only capsules with trace stacks, the archive and snapshot/compaction layer, and the re-entry packet. December 2025.

- first: `77de705` 2025-12-01 Add calibration runner, connectors stubs, guardrails, and dashboard
- last: `e31e011` 2026-07-27 firelink: recover ignored Phase G storage modules
- lineage (author field, not collaborator): Codex CLI 52
- active months: 2025-12, 2026-01, 2026-07

| file | lines | commits | first | last | imports |
| --- | ---: | ---: | --- | --- | ---: |
| `fram_serving/archive.py` | 187 | 2 | 2025-12-19 | 2025-12-19 | 0 |
| `fram_serving/memory_capsule.py` | 813 | 6 | 2025-12-31 | 2026-07-22 | 4 |
| `fram_serving/rep.py` | 135 | 1 | 2025-12-19 | 2025-12-19 | 1 |
| `fram_serving/storage/__init__.py` | 1 | 1 | 2026-07-27 | 2026-07-27 | 0 |
| `fram_serving/storage/archival.py` | 234 | 1 | 2026-07-27 | 2026-07-27 | 4 |
| `fram_serving/storage/compaction.py` | 185 | 1 | 2026-07-27 | 2026-07-27 | 3 |
| `fram_serving/storage/snapshot.py` | 62 | 1 | 2026-07-27 | 2026-07-27 | 2 |
| `tools/archive_probe.py` | 44 | 1 | 2025-12-19 | 2025-12-19 | 2 |
| `tools/falsify_capsule.py` | 365 | 2 | 2025-12-31 | 2025-12-31 | 3 |
| `tools/inspect_capsule.py` | 175 | 2 | 2025-12-31 | 2025-12-31 | 0 |
| `tools/phase_f_calibrate.py` | 149 | 2 | 2025-12-01 | 2026-07-27 | 3 |
| `tools/phase_f_replay.py` | 148 | 2 | 2025-12-01 | 2026-07-27 | 3 |
| `tools/phase_g_archive.py` | 28 | 2 | 2025-12-01 | 2026-07-27 | 2 |
| `tools/phase_g_compact.py` | 27 | 2 | 2025-12-01 | 2026-07-27 | 2 |
| `tools/phase_g_snapshot.py` | 16 | 2 | 2025-12-01 | 2026-07-27 | 2 |
| `tools/rep_probe.py` | 31 | 1 | 2025-12-19 | 2025-12-19 | 2 |
| `tools/run_capsule_demo.py` | 162 | 1 | 2026-01-01 | 2026-01-01 | 1 |
| `tests/test_archive_layer.py` | 125 | 2 | 2025-12-19 | 2025-12-31 | 3 |
| `tests/test_memory_capsule.py` | 125 | 4 | 2025-12-31 | 2026-01-21 | 3 |
| `tests/test_memory_capsule_lineage_window.py` | 165 | 1 | 2026-07-22 | 2026-07-22 | 4 |
| `tests/test_memory_capsule_retrieval.py` | 100 | 2 | 2026-01-21 | 2026-01-23 | 5 |
| `tests/test_memory_capsule_rotational_lift.py` | 125 | 1 | 2026-07-22 | 2026-07-22 | 4 |
| `tests/test_memory_capsule_session_lineage.py` | 113 | 1 | 2026-07-22 | 2026-07-22 | 3 |
| `tests/test_phase_f_calibration.py` | 126 | 2 | 2025-12-01 | 2026-07-27 | 4 |
| `tests/test_phase_g_archival.py` | 92 | 2 | 2025-12-01 | 2026-07-27 | 2 |
| `tests/test_phase_g_compaction.py` | 90 | 2 | 2025-12-01 | 2026-07-27 | 3 |
| `tests/test_phase_g_snapshot.py` | 41 | 2 | 2025-12-01 | 2026-07-27 | 2 |
| `tests/test_phase_g_stub_clis.py` | 8 | 2 | 2025-12-01 | 2026-07-27 | 3 |
| `tests/test_rep_packet.py` | 62 | 1 | 2025-12-19 | 2025-12-19 | 2 |

## Fractal memory: traces, generators, soft-DTW, source frame, auto-flip

<a id="pl-fractal"></a>`pl-fractal` · layer `memory`

Deterministic 6-D fractal traces minted from episodes, scoring and replay, the Phase D scorer, the falsification and auto-flip harnesses. October 2025 to September 2026.

- first: `4612dbb` 2025-09-25 feat: automate calibration harvest and roadmap overrides
- last: `50d598f` 2026-09-10 fix(fractal): preserve document custody and record unchanged gate failures
- lineage (author field, not collaborator): Codex CLI 63, Rick 12, codex 10
- active months: 2025-09, 2025-10, 2025-11, 2025-12, 2026-07, 2026-08, 2026-09

| file | lines | commits | first | last | imports |
| --- | ---: | ---: | --- | --- | ---: |
| `fram_eval/fractal_autoflip.py` | 183 | 2 | 2025-12-22 | 2025-12-26 | 0 |
| `fram_eval/fractal_falsification.py` | 568 | 4 | 2025-12-23 | 2026-09-10 | 1 |
| `fram_serving/embedding/quaternion_adapter.py` | 91 | 4 | 2025-11-11 | 2026-07-27 | 0 |
| `fram_serving/fractal_memory/__init__.py` | 43 | 4 | 2025-11-05 | 2026-09-10 | 4 |
| `fram_serving/fractal_memory/fractal_gen.py` | 201 | 2 | 2025-11-05 | 2025-12-19 | 1 |
| `fram_serving/fractal_memory/fractal_trace_store.py` | 174 | 3 | 2025-11-05 | 2025-12-23 | 4 |
| `fram_serving/fractal_memory/fractal_types.py` | 37 | 2 | 2025-11-05 | 2025-12-19 | 0 |
| `fram_serving/fractal_memory/metrics.py` | 216 | 4 | 2025-11-05 | 2026-09-10 | 1 |
| `fram_serving/fractal_memory/source_frame.py` | 127 | 1 | 2026-09-10 | 2026-09-10 | 2 |
| `fram_serving/scoring/_fractal_trace_scores_phase_d.py` | 207 | 5 | 2025-11-11 | 2026-07-27 | 1 |
| `scripts/diagnose_fractal_self_recall.py` | 120 | 2 | 2026-09-10 | 2026-09-10 | 3 |
| `scripts/fractal_autoflip.py` | 103 | 2 | 2025-12-22 | 2025-12-26 | 1 |
| `scripts/fractal_falsification.py` | 207 | 2 | 2025-12-23 | 2026-07-27 | 1 |
| `scripts/fractal_trace_ablation_report.py` | 349 | 2 | 2025-12-28 | 2025-12-29 | 3 |
| `scripts/fractal_trace_alignment_probe.py` | 290 | 1 | 2025-12-29 | 2025-12-29 | 3 |
| `scripts/fractal_trace_identity_check.py` | 395 | 3 | 2025-12-28 | 2025-12-29 | 4 |
| `scripts/fractal_trace_probe_eval.py` | 345 | 3 | 2025-12-26 | 2025-12-29 | 3 |
| `scripts/run_fractal_eval_report.py` | 233 | 3 | 2025-12-28 | 2025-12-29 | 1 |
| `scripts/run_fractal_two_pass_eval.py` | 326 | 1 | 2025-12-29 | 2025-12-29 | 1 |
| `tools/fractal_ablation.py` | 92 | 1 | 2025-11-05 | 2025-11-05 | 0 |
| `tools/fractal_top_episodes.py` | 66 | 1 | 2025-11-11 | 2025-11-11 | 0 |
| `tools/fractal_trace_probe.py` | 36 | 1 | 2025-12-19 | 2025-12-19 | 2 |
| `tools/trace_probe.py` | 103 | 4 | 2025-09-25 | 2025-10-10 | 1 |
| `tools/trace_summary.py` | 89 | 1 | 2025-09-27 | 2025-09-27 | 3 |
| `tests/test_fractal_autoflip.py` | 70 | 2 | 2025-12-22 | 2025-12-26 | 1 |
| `tests/test_fractal_falsification.py` | 107 | 2 | 2025-12-23 | 2026-07-27 | 1 |
| `tests/test_fractal_falsification_cli.py` | 47 | 2 | 2025-12-23 | 2026-07-27 | 1 |
| `tests/test_fractal_influence.py` | 49 | 1 | 2025-12-19 | 2025-12-19 | 1 |
| `tests/test_fractal_memory.py` | 206 | 3 | 2025-11-05 | 2025-12-23 | 1 |
| `tests/test_fractal_routing.py` | 18 | 1 | 2025-10-18 | 2025-10-18 | 2 |
| `tests/test_fractal_source_frame.py` | 161 | 1 | 2026-09-10 | 2026-09-10 | 6 |
| `tests/test_fractal_trace_binding.py` | 210 | 1 | 2026-09-08 | 2026-09-08 | 3 |
| `tests/test_fractal_trace_smoke.py` | 67 | 1 | 2025-12-19 | 2025-12-19 | 2 |
| `tests/test_soft_dtw_equivalence.py` | 125 | 1 | 2026-09-08 | 2026-09-08 | 1 |
| `tests/test_soft_dtw_similarity.py` | 30 | 1 | 2026-09-10 | 2026-09-10 | 1 |
| `tests/test_trace_probe_cli.py` | 12 | 3 | 2025-09-25 | 2025-12-31 | 0 |
| `tests/test_trace_summary.py` | 55 | 2 | 2025-09-27 | 2025-09-28 | 3 |
| `tests/test_hopf_bridge.py` | 33 | 1 | 2026-07-27 | 2026-07-27 | 1 |
| `tests/test_phase_d_placeholders.py` | 83 | 5 | 2025-11-11 | 2026-08-29 | 3 |

## Rotational lift and visual evidence (Phase D lineage)

<a id="pl-rotational"></a>`pl-rotational` · layer `core`

The Lantern Turn: recursive rotational lift, quaternion orientation kept separate from ranking, visual evidence ledger and seed canary. November 2025 and July 2026, the same idea built twice.

- first: `2ee5be6` 2026-07-22 feat: add Recursive Rotational Lift v0.3 prototype math module
- last: `53b58df` 2026-08-29 feat(eval): add bounded visual-seed candidate evaluator
- lineage (author field, not collaborator): Codex CLI 10, Rick 3
- active months: 2026-07, 2026-08

| file | lines | commits | first | last | imports |
| --- | ---: | ---: | --- | --- | ---: |
| `fram_core/rotational_lift.py` | 354 | 3 | 2026-07-22 | 2026-07-27 | 0 |
| `fram_core/visual_evidence.py` | 544 | 1 | 2026-07-27 | 2026-07-27 | 0 |
| `fram_eval/visual_seed.py` | 880 | 1 | 2026-08-29 | 2026-08-29 | 2 |
| `fram_serving/visual_contact_sheet.py` | 258 | 1 | 2026-07-27 | 2026-07-27 | 0 |
| `fram_serving/visual_ingest.py` | 57 | 1 | 2026-07-27 | 2026-07-27 | 1 |
| `tools/eval_visual_seed.py` | 242 | 1 | 2026-08-29 | 2026-08-29 | 3 |
| `tests/test_rotational_lift.py` | 211 | 1 | 2026-07-22 | 2026-07-22 | 1 |
| `tests/test_rotational_lift_isoclinic.py` | 157 | 2 | 2026-07-27 | 2026-07-27 | 2 |
| `tests/test_visual_evidence.py` | 97 | 1 | 2026-07-27 | 2026-07-27 | 1 |
| `tests/test_visual_seed_eval.py` | 391 | 1 | 2026-08-29 | 2026-08-29 | 5 |

## Cognitive memory: episodes, beliefs, embeddings, ANN bridge, retention

<a id="pl-cognitive"></a>`pl-cognitive` · layer `memory`

The JSONL cognitive store that gave the system a durable self in October 2025: episodes, beliefs, links, embeddings, Phase D/E priority and retention, autolog and autowire.

- first: `8869165` 2025-09-19 feat(serving): add working memory API and integration
- last: `97eed2d` 2026-07-27 firelink stage 1: land non-conflicting Phase D/E/F/G files
- lineage (author field, not collaborator): Codex CLI 67, codex 18
- active months: 2025-09, 2025-10, 2025-11, 2025-12, 2026-01, 2026-07

| file | lines | commits | first | last | imports |
| --- | ---: | ---: | --- | --- | ---: |
| `fram_core/memory_merge.py` | 86 | 2 | 2025-12-04 | 2026-07-27 | 0 |
| `fram_core/priority_graph.py` | 127 | 2 | 2025-11-25 | 2026-07-27 | 0 |
| `fram_core/transitional_complexity.py` | 88 | 1 | 2025-12-15 | 2025-12-15 | 0 |
| `fram_serving/cognitive_embeddings.py` | 57 | 1 | 2025-12-23 | 2025-12-23 | 1 |
| `fram_serving/config_phase_d.py` | 13 | 2 | 2025-11-11 | 2026-07-27 | 0 |
| `fram_serving/memory.py` | 2131 | 19 | 2025-09-19 | 2026-07-22 | 6 |
| `fram_serving/memory/__init__.py` | 53 | 5 | 2025-11-27 | 2026-07-27 | 2 |
| `fram_serving/memory/forgetting.py` | 112 | 5 | 2025-11-27 | 2026-07-27 | 1 |
| `fram_serving/memory/retention_curve.py` | 74 | 3 | 2025-11-27 | 2026-07-27 | 1 |
| `fram_serving/semantic.py` | 157 | 1 | 2025-10-18 | 2025-10-18 | 1 |
| `tools/autolog_env.py` | 87 | 2 | 2025-10-18 | 2026-01-12 | 2 |
| `tools/autolog_once.py` | 23 | 1 | 2025-10-18 | 2025-10-18 | 0 |
| `tools/autowire_turn.py` | 300 | 6 | 2026-01-12 | 2026-01-17 | 4 |
| `tools/backfill_cognitive_embeddings.py` | 48 | 1 | 2025-12-23 | 2025-12-23 | 3 |
| `tools/bootstrap_memory.py` | 390 | 4 | 2025-10-10 | 2025-10-10 | 3 |
| `tools/cognitive_memory_summary.py` | 143 | 2 | 2025-10-10 | 2025-12-23 | 0 |
| `tools/log_chat_turn.py` | 209 | 1 | 2025-10-10 | 2025-10-10 | 2 |
| `tools/log_cognitive_belief.py` | 134 | 1 | 2025-10-10 | 2025-10-10 | 2 |
| `tools/memory_compact.py` | 73 | 1 | 2025-10-18 | 2025-10-18 | 2 |
| `tools/phase_d_memory_summary.py` | 75 | 4 | 2025-11-18 | 2026-07-27 | 3 |
| `tools/phase_e_summary.py` | 71 | 3 | 2025-11-27 | 2026-07-27 | 3 |
| `tests/test_autolog_env.py` | 26 | 2 | 2025-10-18 | 2026-01-12 | 3 |
| `tests/test_autowire_turn.py` | 80 | 3 | 2026-01-12 | 2026-01-17 | 3 |
| `tests/test_cognitive_ann_merge.py` | 54 | 2 | 2025-12-04 | 2026-07-27 | 1 |
| `tests/test_cognitive_memory_ann_bridge.py` | 39 | 1 | 2026-01-08 | 2026-01-08 | 3 |
| `tests/test_cognitive_memory_search_ann.py` | 29 | 1 | 2026-01-08 | 2026-01-08 | 3 |
| `tests/test_memory_package_compat.py` | 10 | 2 | 2026-07-27 | 2026-07-27 | 1 |
| `tests/test_phase_d_priority_graph.py` | 61 | 2 | 2025-11-25 | 2026-07-27 | 2 |
| `tests/test_phase_e_placeholders.py` | 46 | 3 | 2025-11-27 | 2026-07-27 | 3 |
| `tests/test_semantic_builder.py` | 17 | 1 | 2025-10-18 | 2025-10-18 | 1 |
| `tests/test_transitional_complexity.py` | 60 | 1 | 2025-12-15 | 2025-12-15 | 1 |

## Chaos playground, Hopf transport, Aizawa (proof track)

<a id="pl-chaos"></a>`pl-chaos` · layer `eval`

Dynamical systems, dimensional ladder, Hopf map and S3 fibre claims. Proof track; never runtime authority.

- first: `39cf220` 2026-07-27 refactor(hopf): separate transport from falsification
- last: `54ddb8b` 2026-10-28 recover(cathedral): Cosmic Cathedral navigation map from firelink/sol-inflight
- lineage (author field, not collaborator): Codex CLI 26, Wren Holloway 2
- active months: 2026-07, 2026-10

| file | lines | commits | first | last | imports |
| --- | ---: | ---: | --- | --- | ---: |
| `experiments/hopf_aizawa_falsification.py` | 246 | 2 | 2026-07-27 | 2026-07-27 | 4 |
| `fram_eval/aizawa_sphere.py` | 300 | 2 | 2026-07-27 | 2026-07-27 | 1 |
| `fram_eval/chaos/__init__.py` | 53 | 2 | 2026-07-27 | 2026-07-27 | 6 |
| `fram_eval/chaos/complex.py` | 84 | 1 | 2026-07-27 | 2026-07-27 | 0 |
| `fram_eval/chaos/diagnostics.py` | 191 | 1 | 2026-07-27 | 2026-07-27 | 0 |
| `fram_eval/chaos/dimensions.py` | 172 | 1 | 2026-10-28 | 2026-10-28 | 0 |
| `fram_eval/chaos/geometry.py` | 88 | 1 | 2026-07-27 | 2026-07-27 | 0 |
| `fram_eval/chaos/lift.py` | 137 | 1 | 2026-07-27 | 2026-07-27 | 1 |
| `fram_eval/chaos/scene.py` | 122 | 1 | 2026-07-27 | 2026-07-27 | 0 |
| `fram_eval/chaos/systems.py` | 148 | 1 | 2026-07-27 | 2026-07-27 | 1 |
| `fram_eval/hopf_transport.py` | 301 | 2 | 2026-07-27 | 2026-07-27 | 2 |
| `tests/test_aizawa_sphere.py` | 74 | 2 | 2026-07-27 | 2026-07-27 | 2 |
| `tests/test_chaos_browser_contract.py` | 73 | 1 | 2026-07-27 | 2026-07-27 | 2 |
| `tests/test_chaos_complex.py` | 17 | 1 | 2026-07-27 | 2026-07-27 | 1 |
| `tests/test_chaos_diagnostics.py` | 60 | 1 | 2026-07-27 | 2026-07-27 | 2 |
| `tests/test_chaos_dimensions.py` | 85 | 1 | 2026-10-28 | 2026-10-28 | 3 |
| `tests/test_chaos_geometry.py` | 47 | 1 | 2026-07-27 | 2026-07-27 | 1 |
| `tests/test_chaos_lift.py` | 80 | 1 | 2026-07-27 | 2026-07-27 | 2 |
| `tests/test_chaos_scene.py` | 56 | 1 | 2026-07-27 | 2026-07-27 | 1 |
| `tests/test_chaos_systems.py` | 99 | 1 | 2026-07-27 | 2026-07-27 | 2 |
| `tests/test_hopf_aizawa_evidence.py` | 48 | 1 | 2026-07-27 | 2026-07-27 | 3 |
| `tests/test_hopf_aizawa_falsification.py` | 48 | 1 | 2026-07-27 | 2026-07-27 | 1 |
| `tests/test_hopf_transport.py` | 101 | 1 | 2026-07-27 | 2026-07-27 | 2 |

## Evaluation harnesses: production memory, shadow, conversation, wake/orient, ablations

<a id="pl-eval"></a>`pl-eval` · layer `eval`

The eval season and after: production memory gate, memory shadow eval, conversation memory eval, section-15 ablations, document candidate, wake and orient.

- first: `2814726` 2025-09-09 feat(serving): add minimal /query endpoint and tests
- last: `50d598f` 2026-09-10 fix(fractal): preserve document custody and record unchanged gate failures
- lineage (author field, not collaborator): Codex CLI 79, Rick 21, codex 10
- active months: 2025-09, 2025-10, 2025-11, 2025-12, 2026-01, 2026-08, 2026-09

| file | lines | commits | first | last | imports |
| --- | ---: | ---: | --- | --- | ---: |
| `fram_eval/__init__.py` | 1 | 1 | 2025-09-09 | 2025-09-09 | 0 |
| `fram_eval/ablations.py` | 428 | 2 | 2025-09-09 | 2026-08-04 | 2 |
| `fram_eval/conversation_memory_eval.py` | 1222 | 16 | 2025-12-22 | 2026-09-10 | 6 |
| `fram_eval/datasets.py` | 229 | 2 | 2025-09-09 | 2026-08-04 | 0 |
| `fram_eval/document_candidate.py` | 232 | 1 | 2026-09-10 | 2026-09-10 | 4 |
| `fram_eval/estimators.py` | 31 | 2 | 2025-09-09 | 2025-09-16 | 0 |
| `fram_eval/memory_shadow_eval.py` | 402 | 12 | 2025-12-22 | 2025-12-29 | 3 |
| `fram_eval/metrics.py` | 236 | 3 | 2025-09-09 | 2026-08-04 | 0 |
| `fram_eval/production_memory_eval.py` | 1095 | 2 | 2026-09-08 | 2026-09-10 | 10 |
| `fram_eval/wake_orient.py` | 681 | 1 | 2026-08-12 | 2026-08-12 | 2 |
| `scripts/conversation_memory_eval.py` | 329 | 13 | 2025-12-22 | 2025-12-29 | 3 |
| `scripts/memory_shadow_eval.py` | 210 | 11 | 2025-12-22 | 2025-12-29 | 1 |
| `scripts/prepare_document_candidate.py` | 43 | 1 | 2026-09-10 | 2026-09-10 | 1 |
| `scripts/production_memory_eval.py` | 96 | 1 | 2026-09-08 | 2026-09-08 | 3 |
| `scripts/recall_report_phase_c.py` | 45 | 3 | 2025-10-21 | 2025-11-11 | 0 |
| `scripts/run_production_memory_gate.py` | 278 | 2 | 2026-09-10 | 2026-09-10 | 2 |
| `scripts/sweep_section_penalty.py` | 322 | 1 | 2025-09-27 | 2025-09-27 | 2 |
| `tools/eval_wake_orient.py` | 83 | 1 | 2026-08-12 | 2026-08-12 | 3 |
| `tools/experiment_export.py` | 100 | 1 | 2026-01-12 | 2026-01-12 | 3 |
| `tools/experiment_log.py` | 209 | 2 | 2026-01-12 | 2026-01-12 | 4 |
| `tools/experiment_summary.py` | 128 | 1 | 2026-01-12 | 2026-01-12 | 2 |
| `tools/weekly_regression_snapshot.py` | 89 | 2 | 2026-01-12 | 2026-01-12 | 4 |
| `tests/test_conversation_memory_eval.py` | 428 | 11 | 2025-12-22 | 2025-12-29 | 5 |
| `tests/test_experiment_export.py` | 22 | 1 | 2026-01-12 | 2026-01-12 | 3 |
| `tests/test_experiment_log.py` | 40 | 2 | 2026-01-12 | 2026-01-12 | 3 |
| `tests/test_production_memory_eval.py` | 675 | 1 | 2026-09-08 | 2026-09-08 | 10 |
| `tests/test_weekly_regression_snapshot.py` | 28 | 1 | 2026-01-12 | 2026-01-12 | 3 |
| `tests/test_weekly_regression_snapshot_digest.py` | 33 | 1 | 2026-01-12 | 2026-01-12 | 3 |
| `tests/test_document_candidate.py` | 101 | 1 | 2026-09-10 | 2026-09-10 | 1 |
| `tests/test_estimators.py` | 7 | 1 | 2025-09-16 | 2025-09-16 | 1 |
| `tests/test_eval_ablations.py` | 64 | 1 | 2026-08-04 | 2026-08-04 | 2 |
| `tests/test_eval_datasets.py` | 36 | 1 | 2026-08-04 | 2026-08-04 | 1 |
| `tests/test_experiment_summary.py` | 29 | 1 | 2026-01-12 | 2026-01-12 | 4 |
| `tests/test_memory_shadow_eval.py` | 43 | 2 | 2025-12-22 | 2025-12-26 | 3 |
| `tests/test_metrics.py` | 52 | 2 | 2025-09-16 | 2026-08-04 | 1 |
| `tests/test_production_gate_cli.py` | 37 | 1 | 2026-09-10 | 2026-09-10 | 1 |
| `tests/test_production_progress.py` | 54 | 1 | 2026-09-10 | 2026-09-10 | 2 |
| `tests/test_wake_orient_eval.py` | 186 | 1 | 2026-08-12 | 2026-08-12 | 4 |

## OrthoRoute: shortlist, subspace, confidence, coverage, calibration

<a id="pl-orthoroute"></a>`pl-orthoroute` · layer `core`

The retrieval spine from September 2025: query orchestration, CELF coverage, logistic plus conformal calibration, reranking, anchors.

- first: `2814726` 2025-09-09 feat(serving): add minimal /query endpoint and tests
- last: `8ae6122` 2026-08-04 fix(calibration): constrain centroid-distance sign
- lineage (author field, not collaborator): codex 154, Codex CLI 58, Rick 11
- active months: 2025-09, 2025-10, 2025-11, 2025-12, 2026-01, 2026-07, 2026-08

| file | lines | commits | first | last | imports |
| --- | ---: | ---: | --- | --- | ---: |
| `fram_core/__init__.py` | 1 | 1 | 2025-09-09 | 2025-09-09 | 0 |
| `fram_core/anchors.py` | 87 | 4 | 2025-09-09 | 2025-09-27 | 0 |
| `fram_core/calibrate.py` | 104 | 5 | 2025-09-09 | 2026-08-04 | 4 |
| `fram_core/claims.py` | 90 | 4 | 2025-09-09 | 2025-09-16 | 0 |
| `fram_core/confidence.py` | 182 | 6 | 2025-09-09 | 2025-10-06 | 1 |
| `fram_core/coverage.py` | 530 | 6 | 2025-09-09 | 2025-09-27 | 0 |
| `fram_core/math_utils.py` | 69 | 3 | 2025-09-09 | 2025-09-26 | 0 |
| `fram_core/pipeline.py` | 3534 | 72 | 2025-09-09 | 2026-08-04 | 14 |
| `fram_core/rerank.py` | 37 | 3 | 2025-09-09 | 2025-09-19 | 0 |
| `scripts/calibrate_confidence.py` | 116 | 3 | 2025-09-19 | 2025-10-03 | 1 |
| `scripts/calibrate_phase_c.py` | 203 | 5 | 2025-10-21 | 2025-12-31 | 0 |
| `scripts/harvest_calibration.py` | 187 | 3 | 2025-09-25 | 2025-12-01 | 4 |
| `tools/calibration_backfill.py` | 299 | 1 | 2025-09-29 | 2025-09-29 | 1 |
| `tools/calibration_filter.py` | 280 | 1 | 2025-09-29 | 2025-09-29 | 1 |
| `tools/calibration_histogram.py` | 103 | 1 | 2025-10-09 | 2025-10-09 | 0 |
| `tools/calibration_lint.py` | 164 | 2 | 2025-10-03 | 2026-08-04 | 1 |
| `tools/calibration_run.py` | 148 | 2 | 2025-12-01 | 2026-07-27 | 0 |
| `tools/calibration_sanity.py` | 120 | 1 | 2025-10-06 | 2025-10-06 | 2 |
| `tools/calibration_status.py` | 166 | 2 | 2025-10-03 | 2025-10-09 | 2 |
| `tools/refresh_calibration.py` | 337 | 2 | 2026-01-09 | 2026-07-27 | 1 |
| `tools/refresh_docs_calibration.py` | 89 | 1 | 2026-01-08 | 2026-01-08 | 0 |
| `tests/test_calibration_backfill_cli.py` | 151 | 1 | 2025-09-29 | 2025-09-29 | 0 |
| `tests/test_calibration_filter_cli.py` | 99 | 1 | 2025-09-29 | 2025-09-29 | 0 |
| `tests/test_calibration_lint_cli.py` | 121 | 2 | 2025-10-03 | 2026-08-04 | 0 |
| `tests/test_calibration_scheduler.py` | 55 | 2 | 2025-12-01 | 2026-07-27 | 1 |
| `tests/test_calibration_status_cli.py` | 91 | 3 | 2025-10-03 | 2026-08-04 | 0 |
| `tests/test_harvest_calibration.py` | 37 | 1 | 2025-09-25 | 2025-09-25 | 0 |
| `tests/test_phase_c_calibration.py` | 21 | 3 | 2025-10-21 | 2025-12-31 | 0 |
| `tests/test_refresh_calibration.py` | 20 | 1 | 2026-01-09 | 2026-01-09 | 0 |
| `tests/test_refresh_docs_calibration.py` | 20 | 1 | 2026-01-08 | 2026-01-08 | 0 |
| `tests/regression/test_bird_story.py` | 36 | 2 | 2025-10-07 | 2025-10-09 | 2 |
| `tests/test_anchors_selection.py` | 23 | 1 | 2025-09-19 | 2025-09-19 | 1 |
| `tests/test_asof_filtering.py` | 94 | 2 | 2025-12-01 | 2026-07-27 | 3 |
| `tests/test_calibrate.py` | 43 | 2 | 2025-09-19 | 2026-08-04 | 2 |
| `tests/test_celf_selection.py` | 120 | 4 | 2025-09-16 | 2025-12-31 | 2 |
| `tests/test_claims_extractor.py` | 18 | 2 | 2025-09-10 | 2025-09-16 | 1 |
| `tests/test_cognitive_memory_bridge.py` | 172 | 5 | 2025-10-10 | 2025-10-10 | 3 |
| `tests/test_cognitive_memory_store.py` | 263 | 6 | 2025-10-05 | 2026-07-22 | 3 |
| `tests/test_confidence_calibration.py` | 50 | 2 | 2025-09-16 | 2025-09-19 | 1 |
| `tests/test_corpus_persistence.py` | 87 | 6 | 2025-09-18 | 2025-09-25 | 2 |
| `tests/test_coverage_core.py` | 55 | 2 | 2025-09-10 | 2025-09-16 | 1 |
| `tests/test_domain_overrides.py` | 23 | 1 | 2025-09-25 | 2025-09-25 | 2 |
| `tests/test_ingest_project_docs.py` | 14 | 1 | 2026-08-04 | 2026-08-04 | 2 |
| `tests/test_math_utils.py` | 67 | 2 | 2025-09-09 | 2025-09-26 | 1 |
| `tests/test_pipeline_memory_bridge.py` | 183 | 4 | 2025-11-25 | 2026-07-27 | 5 |
| `tests/test_pipeline_orchestrator.py` | 832 | 34 | 2025-09-18 | 2026-08-04 | 7 |
| `tests/test_temporal_priority.py` | 27 | 2 | 2025-11-26 | 2026-07-27 | 2 |
| `tests/test_version_manifest_ingest.py` | 19 | 2 | 2025-12-01 | 2026-07-27 | 2 |

## Index: prototypes, sparse keys, version lattice, ingest

<a id="pl-index"></a>`pl-index` · layer `index-layout`

Prototype bank and ANN shortlist, sparse identifier keys, the version lattice with as-of queries, and the demo corpus ingest.

- first: `2814726` 2025-09-09 feat(serving): add minimal /query endpoint and tests
- last: `8001edf` 2026-08-04 fix(retrieval): harden fresh-corpus closeout
- lineage (author field, not collaborator): codex 30, Codex CLI 19, Rick 1
- active months: 2025-09, 2025-10, 2025-11, 2025-12, 2026-01, 2026-07, 2026-08

| file | lines | commits | first | last | imports |
| --- | ---: | ---: | --- | --- | ---: |
| `fram_index/__init__.py` | 1 | 1 | 2025-09-09 | 2025-09-09 | 0 |
| `fram_index/prototypes.py` | 37 | 2 | 2025-09-09 | 2025-09-10 | 0 |
| `fram_index/sparse_keys.py` | 99 | 3 | 2025-09-09 | 2026-01-21 | 1 |
| `fram_index/version_lattice.py` | 149 | 4 | 2025-09-09 | 2026-01-21 | 0 |
| `fram_serving/ingest.py` | 94 | 2 | 2025-09-25 | 2025-09-25 | 2 |
| `scripts/ingest_demo.py` | 70 | 5 | 2025-09-18 | 2025-09-25 | 3 |
| `scripts/ingest_project_docs.py` | 118 | 5 | 2025-09-25 | 2026-08-04 | 1 |
| `tests/test_hysteresis.py` | 131 | 2 | 2025-11-26 | 2026-07-27 | 4 |
| `tests/test_memory_bridge_priority.py` | 165 | 2 | 2025-11-25 | 2026-07-27 | 4 |
| `tests/test_memory_search_telemetry.py` | 83 | 3 | 2025-12-04 | 2026-07-27 | 4 |
| `tests/test_persistence_regression.py` | 164 | 2 | 2025-12-04 | 2026-07-27 | 5 |
| `tests/test_prototypes.py` | 18 | 1 | 2025-09-10 | 2025-09-10 | 1 |
| `tests/test_serving_coverage.py` | 66 | 5 | 2025-09-10 | 2025-12-31 | 3 |
| `tests/test_serving_coverage_prefer_new.py` | 97 | 7 | 2025-09-10 | 2025-12-31 | 6 |
| `tests/test_sparse_keys.py` | 31 | 2 | 2025-09-16 | 2026-01-21 | 1 |
| `tests/test_version_lattice.py` | 40 | 3 | 2025-09-16 | 2026-01-21 | 1 |
| `tests/test_version_lattice_asof.py` | 19 | 1 | 2025-10-05 | 2025-10-05 | 1 |

## Layout chunkers: code, tables, PDF

<a id="pl-layout"></a>`pl-layout` · layer `index-layout`

AST code chunking, CSV header windows, PDF fallback ordering, layout-aware assembly.

- first: `2814726` 2025-09-09 feat(serving): add minimal /query endpoint and tests
- last: `cf150f9` 2026-01-21 feat: harden sparse keys and layout/version flow
- lineage (author field, not collaborator): codex 18, Codex CLI 4
- active months: 2025-09, 2026-01

| file | lines | commits | first | last | imports |
| --- | ---: | ---: | --- | --- | ---: |
| `fram_layout/__init__.py` | 1 | 1 | 2025-09-09 | 2025-09-09 | 0 |
| `fram_layout/assembler.py` | 63 | 4 | 2025-09-09 | 2025-09-20 | 0 |
| `fram_layout/code_chunker.py` | 93 | 3 | 2025-09-09 | 2025-09-19 | 0 |
| `fram_layout/pdf_chunker.py` | 177 | 4 | 2025-09-09 | 2026-01-21 | 0 |
| `fram_layout/table_chunker.py` | 44 | 2 | 2025-09-09 | 2025-09-16 | 0 |
| `tests/test_code_chunker.py` | 96 | 3 | 2025-09-19 | 2026-01-21 | 2 |
| `tests/test_layout_assembler.py` | 39 | 1 | 2025-09-19 | 2025-09-19 | 1 |
| `tests/test_pdf_chunker.py` | 49 | 2 | 2025-09-19 | 2026-01-21 | 2 |
| `tests/test_table_chunker.py` | 19 | 1 | 2026-01-21 | 2026-01-21 | 1 |
| `tests/test_table_layout.py` | 33 | 1 | 2025-09-16 | 2025-09-16 | 4 |

## Observability

<a id="pl-observability"></a>`pl-observability` · layer `serving`

JSONL decision logging, summary stats, the fractal-memory sink, and the /observability surfaces.

- first: `88b737e` 2025-09-16 fix: unify trace ids and robust /mcp/trace lookup
- last: `97eed2d` 2026-07-27 firelink stage 1: land non-conflicting Phase D/E/F/G files
- lineage (author field, not collaborator): codex 19, Codex CLI 19
- active months: 2025-09, 2025-10, 2025-11, 2025-12, 2026-01, 2026-07

| file | lines | commits | first | last | imports |
| --- | ---: | ---: | --- | --- | ---: |
| `fram_serving/observability.py` | 632 | 17 | 2025-09-16 | 2026-01-08 | 1 |
| `tests/test_observability_dashboard.py` | 8 | 2 | 2025-12-01 | 2026-07-27 | 1 |
| `tests/test_observability_logging.py` | 54 | 4 | 2025-09-16 | 2025-12-31 | 4 |
| `tests/test_observability_summary.py` | 93 | 5 | 2025-09-19 | 2026-01-12 | 2 |
| `tests/test_observability_traces.py` | 37 | 4 | 2025-10-05 | 2026-01-12 | 1 |
| `tests/test_retention_observability.py` | 157 | 4 | 2025-11-27 | 2026-07-27 | 1 |
| `tests/test_storage_observability.py` | 31 | 2 | 2025-12-01 | 2026-07-27 | 2 |

## Serving: /query, REST surface, config, connectors

<a id="pl-query-serving"></a>`pl-query-serving` · layer `serving`

FastAPI app and shared query runner, settings, CLI, connectors, guardrails, SDK adapter. The first commit of the repository was this endpoint.

- first: `2814726` 2025-09-09 feat(serving): add minimal /query endpoint and tests
- last: `802a81b` 2026-09-10 fix(fractal): add validated source-frame recognition candidate
- lineage (author field, not collaborator): Codex CLI 169, codex 116, Rick 21
- active months: 2025-09, 2025-10, 2025-11, 2025-12, 2026-01, 2026-07, 2026-08, 2026-09

| file | lines | commits | first | last | imports |
| --- | ---: | ---: | --- | --- | ---: |
| `fram_serving/__init__.py` | 1 | 1 | 2025-09-09 | 2025-09-09 | 0 |
| `fram_serving/app.py` | 3200 | 108 | 2025-09-09 | 2026-09-10 | 16 |
| `fram_serving/apps/sdk_adapter.py` | 40 | 3 | 2025-12-01 | 2026-07-27 | 4 |
| `fram_serving/cli.py` | 1 | 1 | 2025-09-09 | 2025-09-09 | 0 |
| `fram_serving/config.py` | 480 | 58 | 2025-09-09 | 2026-09-10 | 0 |
| `fram_serving/connectors/registry.py` | 23 | 3 | 2025-12-01 | 2026-07-27 | 0 |
| `fram_serving/guardrails/hooks.py` | 14 | 2 | 2025-12-01 | 2026-07-27 | 0 |
| `fram_serving/query_runner.py` | 2370 | 25 | 2025-12-04 | 2026-09-10 | 19 |
| `fram_serving/trace.py` | 21 | 1 | 2025-09-09 | 2025-09-09 | 0 |
| `tests/test_apps_sdk_adapter.py` | 19 | 2 | 2025-12-01 | 2026-07-27 | 4 |
| `tests/test_closeout_guard.py` | 80 | 3 | 2025-11-25 | 2026-07-27 | 4 |
| `tests/test_cognitive_logging.py` | 127 | 2 | 2025-10-10 | 2026-01-30 | 2 |
| `tests/test_cognitive_memory_seeding.py` | 31 | 4 | 2025-10-05 | 2025-12-31 | 1 |
| `tests/test_cognitive_phase_d_bridge.py` | 80 | 2 | 2025-11-18 | 2026-07-27 | 5 |
| `tests/test_config_env.py` | 41 | 1 | 2026-08-29 | 2026-08-29 | 1 |
| `tests/test_connectors_registry.py` | 41 | 2 | 2025-12-01 | 2026-07-27 | 4 |
| `tests/test_constraint_memory.py` | 85 | 1 | 2026-01-30 | 2026-01-30 | 4 |
| `tests/test_continuity_integration.py` | 324 | 1 | 2026-08-11 | 2026-08-11 | 6 |
| `tests/test_forgetting_hard.py` | 54 | 2 | 2025-11-27 | 2026-07-27 | 2 |
| `tests/test_forgetting_soft.py` | 26 | 2 | 2025-11-27 | 2026-07-27 | 2 |
| `tests/test_guardrails_hooks.py` | 10 | 2 | 2025-12-01 | 2026-07-27 | 2 |
| `tests/test_ingest_demo.py` | 32 | 1 | 2025-09-25 | 2025-09-25 | 2 |
| `tests/test_lived_memory.py` | 304 | 2 | 2026-08-11 | 2026-08-11 | 6 |
| `tests/test_lived_score_calibration.py` | 224 | 1 | 2026-09-08 | 2026-09-08 | 6 |
| `tests/test_memory_api.py` | 220 | 7 | 2025-09-19 | 2026-01-12 | 2 |
| `tests/test_memory_belief_api.py` | 18 | 1 | 2025-10-05 | 2025-10-05 | 1 |
| `tests/test_memory_bridge_ann.py` | 122 | 2 | 2025-12-01 | 2026-07-27 | 2 |
| `tests/test_memory_cooldown.py` | 96 | 1 | 2025-12-17 | 2025-12-17 | 2 |
| `tests/test_memory_search.py` | 41 | 3 | 2025-10-05 | 2025-12-31 | 2 |
| `tests/test_memory_search_window.py` | 24 | 1 | 2026-01-08 | 2026-01-08 | 2 |
| `tests/test_memory_summary.py` | 26 | 4 | 2025-10-05 | 2025-12-31 | 1 |
| `tests/test_metrics_endpoints.py` | 51 | 3 | 2025-09-16 | 2025-09-17 | 1 |
| `tests/test_phase_d_behavior.py` | 214 | 5 | 2025-11-24 | 2026-07-27 | 3 |
| `tests/test_phase_d_config_defaults.py` | 24 | 3 | 2025-11-26 | 2026-07-27 | 1 |
| `tests/test_priority_inspector.py` | 19 | 2 | 2025-11-26 | 2026-07-27 | 1 |
| `tests/test_query_safety_patch.py` | 28 | 3 | 2025-12-13 | 2025-12-31 | 1 |
| `tests/test_rank_relevance_phase_d.py` | 57 | 2 | 2025-11-18 | 2026-07-27 | 2 |
| `tests/test_reranker_pairs_cost.py` | 33 | 4 | 2025-09-16 | 2025-12-31 | 1 |
| `tests/test_retention_curve.py` | 31 | 2 | 2025-11-27 | 2026-07-27 | 2 |
| `tests/test_semantic_reranker.py` | 318 | 5 | 2025-10-18 | 2025-11-20 | 3 |
| `tests/test_serving_answer_format.py` | 14 | 3 | 2025-09-16 | 2025-12-31 | 1 |
| `tests/test_serving_calibration.py` | 57 | 1 | 2025-10-03 | 2025-10-03 | 5 |
| `tests/test_serving_confidence.py` | 45 | 3 | 2025-09-10 | 2025-12-31 | 3 |
| `tests/test_serving_config_coverage.py` | 55 | 4 | 2025-09-10 | 2026-08-29 | 2 |
| `tests/test_serving_health.py` | 8 | 1 | 2025-09-09 | 2025-09-09 | 1 |
| `tests/test_serving_memory_ui.py` | 12 | 3 | 2025-09-28 | 2025-10-05 | 1 |
| `tests/test_serving_query.py` | 95 | 6 | 2025-09-09 | 2025-12-23 | 3 |
| `tests/test_serving_tables_integration.py` | 21 | 3 | 2025-09-16 | 2025-12-31 | 1 |
| `tests/test_serving_where.py` | 14 | 1 | 2025-09-11 | 2025-09-11 | 1 |
| `tests/test_sweep_section_penalty.py` | 68 | 1 | 2025-09-27 | 2025-09-27 | 2 |
| `tests/test_transitional_complexity_timeseries.py` | 53 | 2 | 2025-12-15 | 2025-12-16 | 2 |

## Ops: diagnostics, closeout, context packet, docs tooling

<a id="pl-ops"></a>`pl-ops` · layer `ops`

Diagnostics, import checks, closeout guards, the hot-packet checker, docs scans, time, defaults.

- first: `2814726` 2025-09-09 feat(serving): add minimal /query endpoint and tests
- last: `e5a4ddc` 2026-09-10 fix(mcp): align portable launchers and disclose tool side effects
- lineage (author field, not collaborator): Codex CLI 27, codex 4, Rick 2
- active months: 2025-09, 2025-10, 2025-11, 2025-12, 2026-01, 2026-07, 2026-08, 2026-09

| file | lines | commits | first | last | imports |
| --- | ---: | ---: | --- | --- | ---: |
| `examples/smoke_demo.py` | 1 | 1 | 2025-09-09 | 2025-09-09 | 0 |
| `scripts/diag_imports.py` | 16 | 1 | 2025-10-20 | 2025-10-20 | 0 |
| `scripts/diag_md_writes.py` | 26 | 1 | 2025-10-20 | 2025-10-20 | 0 |
| `scripts/diag_repo_map.py` | 33 | 1 | 2025-10-20 | 2025-10-20 | 0 |
| `scripts/diag_routing_map.py` | 160 | 1 | 2025-10-20 | 2025-10-20 | 0 |
| `scripts/diag_surface.py` | 28 | 1 | 2025-10-20 | 2025-10-20 | 0 |
| `scripts/normalize_docs_ascii.py` | 84 | 1 | 2025-10-18 | 2025-10-18 | 0 |
| `scripts/query_once.py` | 19 | 1 | 2025-10-18 | 2025-10-18 | 0 |
| `scripts/verify_imports.py` | 18 | 2 | 2025-10-20 | 2026-08-29 | 2 |
| `tools/check_closeout.py` | 49 | 2 | 2025-11-25 | 2026-07-27 | 0 |
| `tools/check_context_packet.py` | 441 | 2 | 2026-07-27 | 2026-07-27 | 0 |
| `tools/check_nul_bytes.py` | 96 | 2 | 2025-12-13 | 2025-12-13 | 0 |
| `tools/closeout_guard.py` | 134 | 1 | 2026-01-08 | 2026-01-08 | 2 |
| `tools/current_time.py` | 17 | 1 | 2025-10-18 | 2025-10-18 | 0 |
| `tools/list_recent_docs.py` | 96 | 1 | 2025-10-10 | 2025-10-10 | 0 |
| `tools/print_fram_defaults.py` | 81 | 1 | 2025-12-28 | 2025-12-28 | 1 |
| `tools/refactor_checklist.py` | 38 | 1 | 2026-01-12 | 2026-01-12 | 0 |
| `tools/scan_docs_words.py` | 58 | 1 | 2025-10-18 | 2025-10-18 | 0 |
| `tools/snapshot_firelink.py` | 74 | 1 | 2026-07-27 | 2026-07-27 | 0 |
| `tests/conftest.py` | 6 | 1 | 2025-09-09 | 2025-09-09 | 0 |
| `tests/test_check_context_packet.py` | 247 | 2 | 2026-07-27 | 2026-07-27 | 1 |
| `tests/test_nul_bytes_guard.py` | 14 | 2 | 2025-12-13 | 2025-12-13 | 1 |
| `tests/test_phase_e_summary.py` | 17 | 2 | 2025-11-27 | 2026-07-27 | 0 |
| `tests/test_posix_launchers.py` | 126 | 1 | 2026-09-10 | 2026-09-10 | 0 |
| `tests/test_refactor_checklist.py` | 9 | 1 | 2026-01-12 | 2026-01-12 | 1 |
| `tests/test_snapshot_firelink.py` | 53 | 1 | 2026-07-27 | 2026-07-27 | 1 |
