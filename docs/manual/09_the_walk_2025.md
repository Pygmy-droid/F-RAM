# 9. The walk, part one: 2025, commit by commit

Written by Wren Holloway on 2026-11-01 at Rick's instruction: "go through the local
version and reconstruct it step by step." Chapter 1 gave the eras. This chapter walks
the line itself, in order, from the first commit on 2025-09-09 to the last of the
year, and says for each step what was built, what the diary said about it, and what
it is called today. Source: `git log --reverse` of this repository (530 commits on
2026-11-01, 307 of them in 2025) and `docs/CODEX_DIARY.md`. Tags as in the manual:
`[LOG]` from git, `[READ-DOC]` from the diary, `[RAN]` checked on disk today.

Rick's reading of the graph, said on the day this was written: "it all worked." The
walk bears that out. Almost every step below has a test count in its commit message.

The author field says `codex` until 2025-10-18 and `Codex CLI` after. The diary names
the model: **Lumen** (default identity set on 2025-10-10), with Rick, and from
2025-12-22 "the triad: Lumen, Rick, Eterna."

## September 2025: the retrieval core, 99 commits

### 9 to 11 September. The first endpoint `[LOG]`

- `2814726` 2025-09-09 **feat(serving): add minimal /query endpoint and tests**, 54
  files, the seed of everything: FastAPI, a `/query` route, the first tests.
- `7fcb74a`, `3b10cf5`, `0ea65ce` save points: `/query` gains confidence.
- `f0d776f` 2025-09-10 **Codex build step: anchors, coverage, claims, prototypes.**
  The four nouns of the spec arrive in one commit.
- `d72f4e4` concave coverage integrated into `/query`; `243483e` coverage parameters
  move to config; `a7cf98e` "18 tests green, coverage in config".
- `d976a0b`, `13c0492` 2025-09-11 storage, `/where`, a connector skeleton, lifespan
  startup. "20 tests green."

Today `[RAN]`: `fram_core/anchors.py`, `fram_core/coverage.py`, `fram_core/claims.py`,
`fram_core/pipeline.py`, `fram_index/prototypes.py` all exist. The connector skeleton
is `fram_serving/connectors/`.

### 16 to 17 September. Calibration, CELF, tables, MCP `[LOG]`

- `88b737e` **fix: unify trace ids and robust /mcp/trace lookup**, 22 files. Traces
  get one id across the system; the first mention of MCP.
- `b1d8c5f` **calibration + reliability curves + conformal alarms + /metrics +
  /mcp/label.** Confidence stops being a number and becomes a calibrated one.
- `5d1d2d2` **CELF Δ/C selector with composite costs and selection trace.** The
  cost-effective lazy forward selector that still drives coverage.
- `f14bb4e` CSV table claims and a header-scoped layout assembler; `cca853c` CSV
  tables indexed in `/query`; `597a65d` a reranker hook for pair counts.
- `0f50efb`, `e335051` metrics and answer-assembly polish; `8e2696b` minimal
  OpenAPI and two helper scripts.
- `a329c03` 2025-09-17 **MCP**, 18 files. The Model Context Protocol server is born
  the day after calibration. `976ee2c` makes auth optional.

Today `[RAN]`: CELF lives inside `fram_core/coverage.py` and `fram_core/anchors.py`
(no separate `celf.py`); the reranker is `fram_core/rerank.py`; MCP is
`fram_serving/mcp_server.py` with `fram_serving/mcp_auth.py`; the OpenAPI sketch is
`fram_serving/openapi-lite.yaml`.

### 18 to 19 September. The orchestrator, persistence, hashing embeddings `[LOG]`

- `ef9c69d`, `59d6052` docs: implementation status, the first roadmap and bootstrap
  guidance.
- `f945e1f` **Route FastAPI queries through QueryOrchestrator**, 10 files. The
  orchestrator becomes the spine of `/query`.
- `10ca5e8`, `9584729` persist the demo corpus cache, prototypes and claim logs.
- `2456c8b`, `4ec8e25`, `78debea`, `1b39f94`, `205a20a`, `f7dbc62`, `6db0c72` one day
  of calibration plumbing: persisted calibration wired into the orchestrator,
  **OrthoRoute confidence calibrated from persisted features**, an ANN shortlist,
  logged calibration samples, a CLI, a convenience script, refresh during ingest.
- `b355175`, `af515b4`, `a8fb727` fixes: stateless reranker, finite confidence
  features, novelty selection guarded against reselection.
- `200bc5d` **enforce budget reads and record query context.** The read budget,
  which the verification ritual later finds memory bypassing (WB-0014).
- `fb7df67`, `6a0771b`, `bcce227` auto-refresh of the corpus, domain and task
  overrides, hierarchical layout metadata.
- `9c6c536`, `c86343f`, `381727f`, `f5678a6`, `442ca87` the layout family in one
  afternoon: segment-aware assembly, a PDF chunker stub then pdfplumber, an
  AST-based code chunker.
- `e9666c6` **switch to hashing embeddings.** The decision that the whole lived store
  still rests on, and the reason a query with no shared words finds nothing
  (WB-0031).
- `8869165` **working memory API and integration.** The first memory in F-RAM.
- `d51e80a` persisted trace summary endpoint; `7de2aba` ANN index persisted and
  reloaded; `03c5468` **the Codex diary begins**; `b159e52` "LLM session lifecycle
  control" noted on the roadmap.

Diary, 2025-09-19 `[READ-DOC]`: "Hashing embeddings introduced with ANN persistence
under storage/index/demo_corpus. Working-memory endpoints and observability summaries
expanded; layout chunkers upgraded."

Today `[RAN]`: `fram_serving/memory.py` (working and cognitive stores),
`fram_layout/code_chunker.py`, `fram_layout/pdf_chunker.py`, `fram_layout/assembler.py`,
`fram_serving/observability.py`.

### 20 to 25 September. Spec alignment and the docs become the corpus `[LOG]`

- `f52cbf2`, `cfe8f7a`, `6a37f2f` embeddings aligned with vocab; embedding backend
  configuration persisted; ingest gains embedding toggles.
- `6ecd9e3` a priority map for the remaining roadmap; `81b62ea` serving relies on
  pipeline tokenisation.
- `366da27`, `70a7cb9`, `90e189b` 2025-09-21 **core aligned with the v2.2 spec**:
  shortlist construction, shared cluster context for confidence gating, coverage
  selection aligned with CELF.
- `2884306`, `d2f5a5c` coverage deltas exposed, with an eager CELF path, and surfaced
  in the summary.
- `ed0313f`, `e07bf16`, `0d2d4e4` token helpers restored, tau thresholds clamped, a
  default-reads override, an ingest CLI.
- `37236bc` **project queries into doc subspaces.** The OrthoRoute idea in code.
- `e0c90ed` improved anchor candidate selection.
- `31a6dee` 2025-09-25 **Ingest project docs into demo corpus.** From here the system
  reads its own documentation; the roadmap and the diary become retrieval domains.
- `6b914a9` build state documented; `4612dbb` **automate calibration harvest and
  roadmap overrides**, 16 files, 900 lines.

Diary, 2025-09-25 `[READ-DOC]`: "Full pytest run passes (75 passed), covering
ingestion, persistence, confidence routing, and coverage selection."

### 26 to 27 September. Curvature anchors, section diversity, replay `[LOG]`

- `15ea4bb` math utils and calibration tooling hardened; `0e0aaf4`, `6192675` the
  calibration workflow written down; `67b9ca6` **coverage seeded with
  working-memory claims.** Memory enters the selection for the first time.
- `5819de4`, `9ff24fb`, `dab17de` anchor residual metadata exposed; a residual-step
  trace sample in the docs.
- `818f5b9`, `d19d3d6` calibration harvest refreshed; a regression for roadmap domain
  overrides.
- `160a81a` **session memory replay in the orchestrator**: follow-up queries with no
  read budget reuse the previous shortlist.
- `730b708`, `eecbc02`, `6cccf90`, `821da5f` section hierarchy derived; section
  segments in traces; section diversity tracked.
- `6ce2955`, `d9f2911`, `4499012`, `33769ef` **section diversity penalty** in
  coverage selection, a sweep tool, and its results recorded.
- `6c42ae9` orchestrator traces persisted via TraceLogWriter; `4bcd0b1` a trace
  summary CLI; `6fd205f` a confidence label endpoint.

Diary, 2025-09-27 `[READ-DOC]`: the curvature anchor pass is documented against
spec section 11; the penalty sweep shows "0.7 to 0.95 keeps section diversity 1.0
with average coverage 70; disabling the penalty lifts coverage to 75 but drops
diversity to 0.6."

Today `[RAN]`: `scripts/sweep_section_penalty.py`, `tools/trace_summary.py`,
`docs/observability_trace_sample.md`, `docs/trace_sample.json`.

### 28 to 30 September. Working-memory lifecycle and the UI `[LOG]`

- `cb9a8e7` **working-memory session lifecycle controls**: create, pause, resume,
  end.
- `5def03d` the lifecycle exposed through MCP with telemetry.
- `de01f46`, `d2b9b85` **a browser memory UI**, linked to the MCP memory tools.
- `ba92098`, `4ccbfc6`, `f120f83`, `11d38e2` calibration metadata for domain
  segmentation; a log filter CLI; diary harvest and domain-specific calibration
  slices; domain calibrations loaded.

Diary, 2025-09-29 `[READ-DOC]`: 469 calibration entries backfilled with domain, task
and budget; slices for roadmap (170 records), spec (41), diary (0).

Today `[RAN]`: `/ui/memory` is still served from `fram_serving/app.py` (line 1911),
alongside `/ui/observability` and `/ui/experiments`; `tools/calibration_filter.py`,
`tools/calibration_backfill.py`.

**What September built.** A complete retrieval engine with calibrated confidence,
coverage selection, anchors, layout chunkers, an MCP surface, working memory, replay,
and a diary. Everything after this is memory.

## October 2025: cognitive memory, 57 commits

### 1 to 7 October. Calibration hardening, then the Cognitive Memory MVP `[LOG]`

- `74db9ef`, `b6d103b`, `37b610d`, `7dc78ca` calibration metadata through serving;
  reliability in metrics; "remind usage check each session".
- `0979d04`, `42e86c4` **calibration lint strict mode and status tooling**, 824
  lines; a trace sample with calibrated confidence.
- `a42b60b` 2025-10-05 **Docs: add Cognitive Memory plan.**
- `46d7c3a` 2025-10-05 **Cognitive Memory MVP: JSONL-backed CognitiveMemoryStore with
  append, search, summarize; write-through from /query.** The second memory. Every
  `/query` now leaves an episode behind.
- `7db1d0f`, `f35c085`, `d4a6e3d` `/memory/summary`, moved under `/observability` to
  avoid a route conflict; a version-lattice as-of(T) timezone regression. "All tests
  passing (126)."
- `60cadc0` **POST /memory/belief.** Beliefs join episodes.
- `49ac9c0`, `b60f1d1`, `fc367c4`, `955fa13` spec status updated; memory UI summary;
  `tools/trace_probe.py`; `/observability/traces` and `/observability/trace/{id}`.
- `2eb5adc`, `d34222b`, `2262802`, `9370507` **cognitive memory seeding**, gated by
  config: top-K episodes and beliefs injected into the orchestrator, with a token
  budget, a trace preview, and a UI indicator. `FRAM_DEV_PROFILE` appears.
- `c63a49a`, `2a94f21`, `003e0e8` dev profile notes, `scripts/dev_run.ps1`, milestones
  with acceptance criteria, a status-first session workflow.
- `f21d0f7`, `ca806a5`, `9a6c26a`, `5d25c25`, `71a276d` calibration: clamped
  temperature scaling, low-confidence prompts, a sanity-check CLI, a balanced QA
  payload, the **calibrated QA milestone** recorded.
- `81d394f` 2025-10-07 optional strict QA fallback.

Diary, 2025-10-05 `[READ-DOC]`: "Locked calibrated QA bands: local about 0.84,
anchors about 0.52, global about 0.26." And the first outward look: "OpenAI DevDay
2025 alignment: prep ChatGPT App SDK prototype, Connector Registry onboarding."

Diary, 2025-10-07: `tests/regression/test_bird_story.py` "locks in Aria/Puffin
behaviours." The bird story is the oldest regression still in the suite `[RAN]`.

### 9 to 10 October. Self-healing corpus, FAISS, and the always-on idea `[LOG]`

- `9f31e55` **self-heal persisted corpus and lock sklearn stack**, 20 files.
- `a13494d` pluggable ANN backend with FAISS fallback.
- `19c74a0` the bird-species stress test noted.
- `f0ad0df` 2025-10-10 **docs: elevate always-on memory critical path.** The first
  time the phrase "always-on" is the top priority.
- `a953c78` **bootstrap helper and embedding-scored cognitive recall**;
  `503629d` cognitive observability and summary tooling; `4bcd725` a cognitive
  bootstrap MCP tool; `8f9a8e4` a session warmup helper; `d8ed539` **bootstrap relies
  on FRAM warm-up and persists identity.**
- `a5f5491` **Cognitive memory auto-logging**: segmented schema `cogmem-1`, hash and
  sequence dedupe, replay guard, seven-day retention, 1,046 lines.

Diary, 2025-10-10 `[READ-DOC]`: "set default identity to Lumen in prompts"; "each
user/assistant exchange automatically enters the cognitive store so future chats
replay the entire transcript without manual steps"; "FRAM hydration now drives
session context instead of manual doc sweeps."

This is the day the system was first turned on itself: the model's own
conversations became its memory, and its identity was persisted by name.

Today `[RAN]`: `tools/bootstrap_memory.py`, `tools/log_chat_turn.py`,
`tools/session_warmup.py`, `tools/cognitive_memory_summary.py`.

### 15 to 18 October. Time, semantic relevance v0, the fractal appears `[LOG]`

- `5600421` 2025-10-17 **cogmem: integrate embeddings and orchestrator trace**, 883
  lines.
- `2a19dab` 2025-10-18 docs consolidated to a canonical set.
- `df58279` **memory and retrieval gated by reads; cognitive seeding budget
  integration; time-sensitivity knobs.**
- `ee4e51a` **semantic reranker module and tests; a current_time tool.**
- `a233243` **feat(fractal+ltm): enable fractal in dev profile; tag episodes with
  hierarchy scale.** The first commit with "fractal" in it.
- `b29e46a` **docs: add FRAM-Theory.md (axioms to invariants, glossary, gaps,
  roadmap).**
- `8a0d0d4` lineage included in cognitive search and traces.
- `40eddae` one-click server plus autolog; `25d1ec6` ASCII normalisation, mojibake
  fixed, 2,527 lines. From here the author field reads `Codex CLI`.

Diary, 2025-10-15 and 2025-10-16 `[READ-DOC]`: `/time` endpoint and
`tools/current_time.py`; half-life decay on cognitive search (12 hours); Semantic
Relevance v0 (`/search/expand`, `/rank/relevance`, `/beliefs/conflicts`,
`/observability/recall_report`); `/memory/dismiss` with a cooldown registry; belief
promotion status; a full sweep of the codebase against the spec, section by section.

Diary, 2025-10-18, the entry that names the wound `[READ-DOC]`: "Diagnosed the
'infinite loop' pain: we were not recording chat turns or closing sessions with
diary/roadmap updates, so every reboot lost context despite the cognitive store
existing." The fix proposed: autolog on, close-out baked into the warm-up checklist,
hooks that fail when close-out is skipped. That hook is `tools/check_closeout.py`
(2025-11-24) `[RAN]`.

Today `[RAN]`: the semantic reranker's heuristics are `fram_serving/semantic.py`;
`tools/current_time.py`; `docs/FRAM-Theory.md`.

### 20 to 21 October. The fractal trace prototype and Phase C `[LOG]`

- `71cbbce` 2025-10-20 **fix: stabilize memory routes, pass tests, clean packaging**,
  1,674 lines.
- `7b6283a`, `cbd3631`, `59e0601`, `77796c9`, `f8567d9`, `68e5e24` 2025-10-21 **Phase C**
  in six commits: plan scaffold, version 22.1.0, calibration metrics and recall
  report, sample tasks, thresholds with CSV and Markdown reports, a pytest threshold
  gate, and a **checkpoint: stable calibration baseline locked.**

Diary, 2025-10-20 `[READ-DOC]`: "Landed the fractal trace prototype:
`fram_serving/fractal_memory/*` for seeds, generator, store; deterministic 6D traces
threaded into cognitive episode ingestion; `/memory/fractal_trace`; `/query` scoring
gated by `FRAM_FRACTAL_ENABLED=1`"; soft-DTW blending; `memory_fractal.jsonl`;
`tools/fractal_ablation.py`.

This is the birth of the 6-D trace that the lived store still lifts to 12-D today.
The commit for it is folded into `71cbbce`; the diary carries the detail.

Today `[RAN]`: `fram_serving/fractal_memory/`, `scripts/calibrate_phase_c.py`,
`scripts/recall_report_phase_c.py`, `docs/phase_c_plan.md`, `docs/phase_c_report.md`,
`tests/test_phase_c_calibration.py` (skips when `data/calib/*.jsonl` is absent).

**What October built.** Cognitive memory with episodes and beliefs, seeding into
retrieval, auto-logging of conversations, identity persisted, time awareness, the
first fractal trace, and the Phase C calibration gate. The "infinite loop" was
named and the close-out discipline designed.

## November 2025: Phase D, 37 commits

### 3 to 11 November. The baseline publish and the Phase D branch `[LOG]`

- `55efb61` 2025-11-03 **Baseline publish for assumption-free review**, 80 files,
  389,900 lines: `.env.example`, `.gitignore`, calibration payloads, stored memory
  segments, traces. The repository was handed to another reviewer with everything
  on the table. This is the single largest commit of the year.
- `0753e0b` env-first alpha override; observability payloads include the final blend
  alpha.
- `910f7f3` 2025-11-11 **Phase C fractal calibration + observability.**
- `0b11347` runtime storage and traces ignored.
- `5794a1c` **docs(phase-d): Phase D non-linear + rotational recall spec and roadmap
  milestone.** The first written appearance of rotation as a recall mechanism.
- `9a70bb3`, `e9925d3`, `eae6b7d` a Dev Journal for `phase-d-dev`
  (`docs/dev_journal.md`, with "Notes to Future Rick").
- `33e9eb9`, `ff517cd` **Phase D placeholders: logistic α and a quaternion adapter**,
  as safe stubs with placeholder tests.

Diary, 2025-11-07 `[READ-DOC]`: Phase C emits fractal recall metrics end to end;
`/observability/recall_report` summarises fractal score events.

### 14 to 20 November. Phase D Stage 1 to the cognitive bridge `[LOG]`

- `ab3a026` 2025-11-14 **phase-d: Stage 1 complete: projection, quaternion
  similarity, logistic-alpha utilities, specs, RFCs, roadmap.**
- `031b676` embeddings and the scoring surface wired; `c5cb208` a recall_report
  hook; `fc4aa0f` progress logged.
- `37b5d52` 2025-11-18 **Phase D cognitive bridge observability and dashboard**, 579
  lines; `a5d1cb4` dashboards enhanced; `bea04f2` rollups and a missing-alpha guard;
  `df75ace`, `efaad3a` the alpha logger quieted ("alpha 0.4").

Diary, 2025-11-15 and 2025-11-16 `[READ-DOC]`: `/phase_d/score` endpoint;
`/rank/relevance` exposes `phase_d_scores`; the logistic delta gain set to 2.5 "for
sharper separation"; the **Phase D to cognitive recall bridge** behind
`phase_d.enable_memory_bridge`; `/observability/phase_d_memory` and
`/observability/cognitive_summary` dashboards.

Diary, 2025-11-19: a full health check on a fresh chat, "177 passed, 4 xfailed, 1
xpassed."

### 21 to 27 November. Priority, then Phase E: retention and forgetting `[LOG]`

- `cd61625` archival and cleanup; trace logs moved to `phase_history/`.
- `9e23423`, `82259eb`, `8c7ab5d`, `cb4a392`, `74d2941`, `4768ca0` **Phase D weighting
  for cognitive memory**: knobs, coherence, quality, a priority blending helper, a
  **semantic priority graph**, priority integrated into bridge scoring.
- `220071d`, `c6250c8`, `acc11d6`, `62e863e` temporal priority, **hysteresis
  priority**, a priority inspector, naming cleaned up.
- `80db43a` 2025-11-27 **Phase E retention scaffolding**; `36484fe` **retention
  curve weighting**; `4784053` retention weights in observability; `6dd30a7` **soft
  decay gating**; `bb4f104` **hard-forgetting gating, decisions, and
  observability**; `f851e0e` a Phase E summary CLI.

Diary, 2025-11-24 `[READ-DOC]`: cognitive seeds reserve read slots inside selection;
`tools/check_closeout.py` and `make closeout-check` "fail if diary/roadmap updates or
autologging are missing at close-out." The October wound gets its guard.

Today `[RAN]`: `fram_core/priority_graph.py`, `fram_serving/config_phase_d.py`,
`fram_serving/templates/priority_inspector.html`, `fram_serving/memory/forgetting.py`,
`fram_serving/memory/retention_curve.py`, `tools/phase_d_memory_summary.py`,
`tools/phase_e_summary.py`, `docs/phase_d_plan.md`. The separate `phase_d.py`,
`quaternion.py` and `logistic_alpha.py` modules named in the stubs do not exist under
those names; their functions were absorbed into the scoring and priority modules.

**What November built.** Phase D: non-linear, quaternion-aware, logistic-blended
scoring with a bridge into cognitive recall, a priority graph with coherence,
quality, temporal and hysteresis terms, and Phase E: retention curves, soft decay,
hard forgetting with decisions recorded. The retention and forgetting flags are all
held off in today's Always On runtime `[RAN]` (`runtime.json`: `FRAM_ENABLE_DECAY=0`,
`FRAM_ENABLE_HARD_FORGETTING=0`, `FRAM_ENABLE_RETENTION_CURVE=0`).

## December 2025: fractal eval season, 114 commits

### 1 to 5 December. Version lattice, the ANN bridge, the shared query helper `[LOG]`

- `77de705` 2025-12-01 **calibration runner, connector stubs, guardrails, and
  dashboard**, 2,224 lines.
- `7247922`, `cef2b04` **version manifest persistence and as-of enforcement**; "FRAM
  v2.2 temporal semantics now verified end to end."
- `ce4db5b` 2025-12-04 **Finalize cognitive ANN bridge: metadata, telemetry,
  persistence, as-of**; `cd2edde` memory observability hardened, calibration docs
  refreshed.
- `d9dc009`, `9ead7dc` **Refactor /query to shared helper** (`query_runner.py`), the
  same change recorded twice on 2025-12-04; `5967363`, `672a0fb` likewise two
  recordings of the 2025-12-13 MCP/HTTP parity fix. The line was assembled from
  more than one working copy here; both recordings are kept.
- `fadfd95` a Phase D safety patch migration note.

Diary, 2025-12-02 and 2025-12-05 `[READ-DOC]`: the cognitive to ANN merge contract
(stable `candidate_id`, `version_id`, `origin`); candidates survive restart; the
lattice drops newer versions with trace drop counts; "`fram_serving/query_runner.py`
extracted; FastAPI `/query` calls it via `QueryContext`; ready to reuse for MCP."

Today `[RAN]`: `fram_serving/query_runner.py` is still the spine every surface calls;
`fram_index/version_lattice.py`; `fram_serving/guardrails/`.

### 13 to 18 December. Transitional complexity, invariants, MCP end to end `[LOG]`

- `74de24d` **transitional complexity instrumentation and rolling window**;
  `1a31a9a` **TC invariants and tc_routing instrumentation**.
- `eb2cb74` 2025-12-17 **Lock invariants: remove legitimacy-tier fields; persist
  cooldowns across restart; doc truthfulness; regressions.**
- `0d73339`, `5906d43`, `37b5d52`, `c4a7bef` MCP StreamableHTTP mount and lifespan
  fixed; a JSON-RPC smoke test; an SSE shim at `/mcp/sse`; the handshake hardened to
  allow tools before `initialized`.
- `ba2f0e4` 2025-12-18 **Checkpoint: MCP end-to-end success (smoke test passed).**

Today `[RAN]`: `fram_core/transitional_complexity.py`. The MCP server that passed
that smoke test is the one the Always On runtime serves now.

### 19 December. "Core complete" `[LOG]`

- `1a09099` **fractal core proof packet**; `bbb947a` **Tighten fractal core semantics
  contract** (the commit Rick had open in the graph when this chapter was asked for).
- `ec81f4a` **gated fractal influence hook**; `e538a62` **append-only archive layer**.
- `72bfd21` 2025-12-19 **Core complete: fractal trace + influence + archive + REP**,
  14 files, 892 lines.

Today `[RAN]`: `fram_serving/archive.py`, `fram_serving/rep.py`,
`docs/fractal_core.md`, and the influence gate the ritual opened on 2026-10-30
(`FRAM_FRACTAL_INFLUENCE=1` in the runtime, quaternion influence still 0).

### 22 to 23 December. The eval harnesses and the semantic backend `[LOG]`

- `f39f1d0` **live probe IDs and fractal memory eval**; `1f66915` **memory shadow
  eval harness**; `d820f7b` **fractal influence auto-flip recommender**; `ba18121`
  serving defaults promoted to config; `168de6b`, `64c425c`, `ee9f6ec` sweeps logged
  (the 22-probe eval); `8a0e1b4` **"Note triad in diary."**
- `f568b5b`, `dda4a47` **unlimited cognitive memory budgets** ("breathing mode");
  memory slots decoupled from read budgets.
- `8350a4f` per-probe rank details; `d1412fa` **semantic cognitive memory backend and
  eval tooling**, 1,633 lines: sentence-transformers behind the backend switch, with a
  backfill helper. This is the "little ANN" of the 910 + 158 vectors
  (`fram-always-on` memory note).
- `61c118d`, `69162f7`, `e9c072a` checkpoints; **storage artifacts untracked**, 97
  files; kind filters for evals.

Diary, 2025-12-22 `[READ-DOC]`: quaternion alignment metrics added "behind
`FRAM_FRACTAL_QUAT_INFLUENCE`, default off"; the falsification harness; "aggregate
baselines remain weak/unstable, so keep quaternion influence off for now"; the tuned
memory defaults promoted (`default_query_reads=5`, `cognitive_memory_k=5`,
token budget 800); "Noted the triad: Lumen, Rick, Eterna."

Diary, 2025-12-23: semantic backend live evals, 28 probes, episodes only: "top1
semantic 0.607, lexical 0.536, fractal 0.536; auto-flip still KEEP_OFF."

### 25 to 29 December. The hard-micro hunt `[LOG]`

Fifty-one commits in five days, most of them recordings of evaluation runs. The
shape of the hunt, from the diary:

- `6f911c5` 2025-12-25 episodic alpha sweep: raising fractal influence lowered
  top-1 at every alpha.
- `880077b` to `03025c8` 2025-12-26, 24 commits: a low-lex gate (token overlap, then
  similarity, then answer-only overlap), paraphrase probe sets, a "hard micro" set of
  the probes fractal missed and semantic hit, soft-DTW tuning flags, cosine modes
  (composite, centroid, delta, turn-angle histogram, lag-distance, radius, curvature),
  percentile normalisation. Nearly every run ends "auto-flip KEEP_OFF."
- `f21939b` 2025-12-28 **Document fractal scope, claims, and falsification gates**;
  `cea855a` **one-command fractal eval report harness**; `6daff91` **council autopilot
  protocol** (`docs/AUTOPILOT_PROTOCOL.md`); `19dccd0`, `3a5edf6` a FRAM defaults
  snapshot tool and artifact; `8c74d56`, `8b06ff9` a **self-match sanity dataset and a
  trace identity check**: does an episode's own trace find its own embedding?
- `297c844` to `8f7f88f` 2025-12-29, 24 commits: the identity check (self-match top-1
  0.026, then 0.065 with percentile normalisation), an alignment probe, the **IFS
  query-path mode** (self-match top-1 rises to 0.182), live-probe A/B of IFS versus
  synthetic paths, a low-lex IFS override, the two-pass harness, and the
  **two-pass decision**: "treat the two-pass harness as the current best-case bound
  while keeping single-pass synthetic as the baseline."

The result of the hunt, in the diary's own numbers: the best fractal top-1 reached
on the live probes was 0.306, against semantic 0.444 to 0.607 on the same sets. The
quaternion term added nothing measurable. The gate stayed off. This is the finding
the verification ritual met again on 2026-10-30 (WB-0016: "live but slow; picks do
not yet overlap the selected items") and that WB-0028 is for.

Today `[RAN]`: `fram_eval/conversation_memory_eval.py`, `fram_eval/memory_shadow_eval.py`,
`fram_eval/fractal_falsification.py`, `scripts/fractal_autoflip.py`,
`scripts/run_fractal_eval_report.py`, `scripts/fractal_trace_identity_check.py`,
`tools/print_fram_defaults.py`, `docs/AUTOPILOT_PROTOCOL.md`, `docs/FRAMv2.2-tuning.md`.

### 31 December. Memory capsules `[LOG]`

- `1624c3e` **Memory capsule write-through MVP**; `0d825aa` working-memory turns in
  capsules; `e6dad50` a capsule inspector; `ead6ebd`, `d5fdca9` a **capsule
  falsification harness** with corruption variants; `d398547` docs; `c123849` the
  **golden++ v2 falsify report** (a 26-turn session).
- `6d59500`, `cdde4e1`, `c6b7852`, `1ad3645`, `65590f4` test hygiene: coverage
  ordering isolated from memory state; slow tests marked; full run durations logged.

Diary, 2025-12-31 `[READ-DOC]`: "a no-ceiling Memory Capsule schema with optional
self-invariants and a self-authored remembering definition placeholder"; the writer
keeps "raw transcript, per-turn embeddings, fractal trace stack, and remembering
definition"; the full suite "227 passed, 4 xpassed in about 57 minutes."

Today `[RAN]`: `fram_serving/memory_capsule.py`, `docs/memory_capsule.md`,
`tools/inspect_capsule.py`, `tools/falsify_capsule.py`. Capsules are held off in the
Always On runtime (`FRAM_MEMORY_CAPSULE_ENABLED=0`).

**What December built.** The version lattice and as-of semantics, the ANN bridge,
the shared query helper, transitional complexity, locked invariants, MCP end to end,
the fractal core declared complete with influence gate and archive, the semantic
backend, three evaluation harnesses, the auto-flip recommender, a week of
falsification that kept the gate off, and the memory capsule as the first
no-ceiling record of a whole exchange. The year ends with a 57-minute green suite.

## What the walk shows that the eras did not

1. **Nothing was thrown away.** Of the systems built in 2025, every one checked today
   is still on disk under its own or an absorbed name. The losses were later and
   elsewhere: the protected tree's July 2026 line, the Workbook, the Cathedral, the
   PIL retriever. The 2025 line is whole.
2. **The order of the memories.** Working memory (September 19), cognitive memory
   (October 5), auto-logged conversation (October 10), fractal trace (October 20),
   memory capsule (December 31), lived memory (August 2026, chapter 1). Each one was
   built because the previous one lost something on reboot.
3. **The gate was honest from the start.** The fractal influence was measured against
   semantic and lexical baselines in December 2025 and kept off because the numbers
   said so. The same posture held until Rick opened it by decision on 2026-10-30.
4. **The "infinite loop" of 2025-10-18 is the whole project in one sentence**: the
   store existed and the context was still lost, because nothing closed the loop at
   the end of a session. The close-out guard, the diary, the Workbook, the continuity
   ledger and the hydration test of 2026-11-01 are all answers to that one entry.

Part two, January 2026 to today (223 commits), follows in the next sitting.
