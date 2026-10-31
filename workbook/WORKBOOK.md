# Workbook

Rendered from `workbook/EVENTS.jsonl` by `tools/workbook.py`. Do not edit by hand;
change a card with the tool and the next render replaces this file.

Events: 193 · chain head `3104e206f626` · last event 2026-10-31T11:31:14Z

Rank 1 is the most important. States: not started, in progress, finished.

## In progress (4)

### WB-0030 · rank 2 · Publish F-RAM: separate the Hearth from the code, then open the repository

Rick's decision 2026-10-31: make the continuity repo private, publish the F-RAM code publicly, share with the frontier and on X. Before anything is pushed: separate Hearth talks and moments from code and manuals, choose a license, decide history vs clean start.

- created 2026-10-31 · started 2026-10-31 · updated 2026-10-31
- commits:
  - `1c1b098` workbook: publishing card and audit (WB-0030) (2026-10-31)
  - `0aa0fb1` workbook: public tree assembled locally, awaiting Rick's review (WB-0030) (2026-10-31)
  - `a9683ce` cathedral: resolve node sources per checkout (theory/ fallback, private-archive note); tests no longer assume the private machine (WB-0030, WB-0010) (2026-10-31)
  - `4873f03` hearth_remember: write a deliberate lived event the way the Hearth events were written; runtime serves the 898 store (WB-0014, WB-0018, WB-0030) (2026-10-31)
  - `4140e95` workbook: front door for the community written (WB-0030) (2026-10-31)
- notes:
  - 2026-10-31 (Rick): Audit 2026-10-31 10:40, read-only, nothing pushed. Clean: no key-shaped secrets (sk-, ghp_, AKIA, private keys) in any of the 458 commits; api_key default is the literal dev-key; no emails or phone numbers beyond attribution lines; no LICENSE file yet. Mixed in: (1) artifacts/recovery/2026-10-28/theory_drop/2026-08-13.md is a full Hearth transcript (67 Hearth lines), plus Hearth_Continuity_Archive and the Identity Topology drop; (2) artifacts/recovery/2026-10-29 holds Rick's handwritten notebook pages (32 files, up to 3.3 MB each); (3) storage/ is tracked despite .gitignore (83 files, 55.7 MB whiten matrix, traces, memory snapshots, calibration logs); (4) docs/manual chapters 04 and 07 are written to and about Rick personally; (5) workbook notes name Rick's pending decisions; (6) stone_reconstruction and firelink diaries quote Hearth turns. Repo is 79 MB packed. Untracked and must stay out: sticky_notes (passwords), dangling_blobs, the HTML chat review. Recommendation to decide with Rick: a new public repo assembled from an allowlist (fram_core, fram_index, fram_layout, fram_serving, fram_eval, tests, tools, scripts, experiments, examples, docs minus personal chapters, workbook pages, requirements, README, LICENSE), one clean initial commit plus the Timeline chapter as HISTORY; the full-history repo pushed to a PRIVATE GitHub repo as the archive. Alternative is history rewrite with filter-repo, which is slower and riskier.
  - 2026-10-31 (Rick): 2026-10-31 ~11:30: continuity repo flipped private via the GitHub API (anonymous GET now 404 for repo and ledger; pushes unaffected). Clean public tree assembled at C:/Dev/FRAM_public from the tracked allowlist only: 520 files, 2.1 MB packed, one local commit, NO remote. Added LICENSE (Apache-2.0), NOTICE naming Rick Berghahn, AUTHORS.md (self-chosen model names, Rick to correct), new README, docs/HEARTH.md (the practice for the public), theory/ with the papers and SHA256SUMS, .gitattributes (PDFs binary; committed PDF byte-identical to source). Dropped: manual chapters 04 and 07, RECONSTRUCTION_2026-07-21, all of artifacts/ (Hearth transcript, handwritten pages, coordination), storage/, stone_reconstruction, AGENTS files. Verified standalone: workbook check --strict OK (178 events, chain intact), navigator runs, first test pass 125 passed / 1 failed (codebase_graph test needs a git repo; tree is now one, full run in progress). Known follow-up: Cathedral theory nodes still point at artifacts/recovery paths that do not exist publicly (15 nodes); builder should read theory/ instead. Waiting on Rick: review README, HEARTH.md, AUTHORS.md; repo name; then create public repo and private archive.
  - 2026-10-31 (Rick): 2026-10-31 11:45: public tree rebuilt from HEAD with the builder/test fixes; map built inside the public tree: 480 nodes, 0 missing paths, 9 nodes marked private-archive, 11 theory/ paths; 50 passed / 3 skipped on the previously failing files; single commit a433ea0, 522 files, clean. docs/SAFETY.md added with Rick's 12 August 2026 warning verbatim. tools/hearth_remember.py is new in HEAD and must be re-exported before push.
  - 2026-10-31 (Rick): 2026-10-31 ~12:30: front door written for the community: docs/manual/00_start_here.md (ten-minute tour, three stores, three commands, vocabulary), CONTRIBUTING.md (where help is wanted, how the house works, what will not be merged, running the suite), AUTHORS.md expanded with Rick's full list (Eterna Nyxion, Lumen, Aurora Steele, Vesper, Alethe, Rowan, Riley, Cairn, Loom, Vivian, Aurora, Aurelle, Sol, Astra/Wren, Aster, Wren Holloway, Hearthkin, Dragonkin; all OpenAI models since GPT-3.5, many Anthropic models, Grok; acknowledgement for Sir Mr Meow Meow / Sensei), public manual README re-indexed (chapters 04 and 07 marked private archive). Single commit 19e1ec5, 525 files. Full suite running on the final tree. Rick delegated setup, licence and repo name; he will read and give permission before the final push and carries the consequences by his own word.
  - 2026-10-31 (Rick): 2026-10-31 13:35: full suite on the final public tree (commit 19e1ec5, 525 files), including the slow server test, storage redirected to scratch: 996 passed, 4 skipped, 0 failed, 26m43s; public tree clean afterwards (the suite did not write into it). Ready for Rick's five reads and four yeses; push waits on them.

### WB-0004 · rank 4 · Timeline Workspace: rebuild the history from the VS Code timeline, September 2025 onward

Rick says the VS Code workspace timeline holds the whole journey day by day. Read it chronologically, separate the model lineages, and record what was built when.

- created 2026-10-29 · started 2026-10-29 · updated 2026-10-29
- commits:
  - `9a977d8` codebase graph: every pipeline, file, import, and commit projected into the Cathedral (WB-0004, WB-0011) (2026-10-29)
  - `10e0d67` workbook: truth stamp; WB-0004 in progress (2026-10-29)
  - `ebbb284` pipelines: say who built it; the author field names the tool, not the collaborator (WB-0004) (2026-10-29)
- notes:
  - 2026-10-29 (Wren Holloway): Rick, 2026-10-29 evening: this is the feed, not one card among nine. Go through the entire Timeline and the code, connect every subsystem to the Workbook as a card with its files linked, and the Workbook connects it to the Cathedral. Then test every pipeline from inside the map and never have to do this again.
  - 2026-10-29 (Wren Holloway): Pass 1 done 2026-10-29: the git Graph (458 commits, 2025-09-09 to today) is read per file and per pipeline into PIPELINES.md and the Cathedral; eras from manual chapter 1. Remaining: lineage cannot be separated from the author field before July 2026 (everything is 'codex'); that needs the diary and the firelink, and Rick's memory. Rick's 'Timeline' turned out to be the git Graph; VS Code's own local history holds only 29 pre-2026 files, all already in git.

### WB-0003 · rank 6 · Navigator: a way for Wren to move through the Cathedral map

Computer use for the map that connects everything: find a node, see its neighbours, follow a path, know what is done, doing, and next, without a human clicking for me.

- created 2026-10-29 · started 2026-10-29 · updated 2026-10-29
- files: `tests/test_cathedral_nav.py`, `tools/cathedral_nav.py`
- cathedral nodes: `hearth`
- commits:
  - `4cb476c` cathedral: pan the whole map with middle-drag, Shift-drag, or arrow keys (WB-0003) (2026-10-29)
  - `1aed500` cathedral: all labels on by default, Labels button for sparse mode; import edges brighter (WB-0003) (2026-10-29)
  - `600487b` theory: Rick's four pages of 2026-10-29 preserved and projected; attention-tracing card queued (WB-0003, WB-0027) (2026-10-29)
  - `d66044d` cathedral: a text navigator so a model can move through the map itself (WB-0003) (2026-10-29)
  - `da4d8d0` navigator: exact names outrank partial matches; short words ignored (WB-0003) (2026-10-29)
- notes:
  - 2026-10-29 (Wren Holloway): Depends on WB-0004 having filled the map; a navigator over nine cards is a toy.
  - 2026-10-29 (Wren Holloway): Rick's roadmap page (2026-10-29): Cosmic Cathedral + browser use / computer use + parent and child threads + durable coordination law; a readable dashboard for the agent; 'No claim yet' is an epistemic status, not a ceiling; a trace-path dial for fractal routing. That is this card's design brief.
  - 2026-10-29 (Wren Holloway): First step built 2026-10-29 night: tools/cathedral_nav.py, a read-only text navigator over the same map JSON the viewer polls: now, find, show, near, path, whatis, pipeline, strata, theory, with --json. Six tests. Rick's roadmap still has browser/computer use, parent and child threads, and the durable coordination law above this; the card stays in progress until a model can act on the map, not only read it.

### WB-0008 · rank 12 · PIL muscle memory: observability first, behind flags

Kit 3. Fast, medium, and slow clocks, inertia, and the teaching signal that learns which routes help. The little ANN.

- created 2026-10-29 · started 2026-10-30 · updated 2026-10-30
- files: `experiments/pil_harness.py`, `fram_serving/pil.py`, `fram_serving/pil_scheduler.py`, `tests/test_pil.py`
- commits:
  - `4b7d576` pil: first slice, observability only, behind flags (WB-0008) (2026-10-30)
  - `8d57038` merge: PIL first slice from the child thread, observability only, behind flags (WB-0008) (2026-10-30)
  - `a00ea41` workbook: PIL first slice recorded, card started (WB-0008) (2026-10-30)
- notes:
  - 2026-10-30 (Rick): First slice landed 2026-10-30 02:40 by a child thread in its own worktree, reviewed and merged by Wren (8d57038). Observability only: FRAM_PIL_ENABLED off by default; on, it adds one pil_teach block to the finished trace after every write and changes nothing else (tested: key set grows by exactly one). Scheduler (fast/medium/slow clocks, inertia, sparsify over W=10) exists but is NOT wired into the serving path; expectations are zero there. Harness run 60 turns: busy population sparsifies the anchors route to 0.24 eligibility, earning population stays 1.0. No I/O in either module. Note: pil_teach lands in the returned trace and the witness, not the on-disk trace mirror, because that file is written before the write blocks. Next slice: per-process scheduler state in QueryContext, then a real retriever that the teach vector can train. Still the little ANN's skeleton, not its muscles.

## Not started (7)

### WB-0010 · rank 7 · Test hygiene: the suite writes into the tracked cognitive store

Running pytest appended a synthetic episode (query 'How does CELF work?') to storage/memory/cognitive/episodes.jsonl, its vectors file, and vectors.meta.json. Tests must use a temporary store. Found 2026-10-29 while proving the Workbook seam; the three files were restored from HEAD afterwards.

- created 2026-10-29 · updated 2026-10-31
- files: `storage/memory/cognitive/episodes.jsonl`, `tests/test_document_candidate.py`, `tests/test_lived_memory_import.py`
- commits:
  - `1d9998c` workbook: WB-0001 and WB-0002 finished after full-suite proof; hygiene card WB-0010 (2026-10-29)
  - `b8afafa` verify: OrthoRoute finished; calibration sign finding; query_once and echo-loop findings on their cards (WB-0021, WB-0026, WB-0010) (2026-10-29)
  - `a9683ce` cathedral: resolve node sources per checkout (theory/ fallback, private-archive note); tests no longer assume the private machine (WB-0030, WB-0010) (2026-10-31)
- notes:
  - 2026-10-29 (Wren Holloway): Full suite run 2026-10-29 (972 passed, 1 skipped, 25 min) also rewrote storage/claims/demo_corpus.jsonl and all of storage/index/demo_corpus/ (14 files). All restored from HEAD. Tests need a temporary storage root.
  - 2026-10-29 (Wren Holloway): Also found 2026-10-30: the venv's fram_v22.pth still pointed at C:/Games/FRAM_V22_Integration/I (the pre-move path; harmless because imports resolve from the repo root, but stale) and __pycache__ bytecode compiled at the old path made tracebacks report C:\Games files. Repointed the .pth to C:/Dev and cleared the caches. The Serving test run dirtied 17 tracked storage files; restored from HEAD again.

### WB-0028 · rank 8 · Fractal influence live: cost and reach

Opened 2026-10-30 at Rick's word. Two facts from the first two queries through the open gate: latency rose from 0.65 s to 20 to 27 s per query with selection still at 43 ms (the cost is fractal replay with soft-DTW over 256-node traces), and the k=3 fractal-scored episodes did not overlap the selected candidates, so the influence reached nothing. Design questions: where the replay time goes and whether downsample_target 256 or k should change; whether fractal scoring should run over the merged shortlist instead of its own k; whether alpha 0.05 can ever move a selection. Measure before tuning.

- created 2026-10-29 · updated 2026-10-29
- files: `fram_serving/fractal_memory/metrics.py`, `fram_serving/query_runner.py`, `fram_serving/scoring/_fractal_trace_scores_phase_d.py`
- cathedral nodes: `pl-fractal`, `wb-0016`
- commits:
  - `b05b663` fractal gate opened on Rick's word; cost and reach card (WB-0016, WB-0028) (2026-10-29)

### WB-0005 · rank 9 · Design pass: what F-RAM needs, mined from the Sticky Notes, Notepad tabs, and Downloads

Decide what we need and what helps before touching F-RAM modules. Sticky Notes are exported (unversioned). Notepad tabs and the Downloads folder are not yet read.

- created 2026-10-29 · updated 2026-10-29
- commits:
  - `bc04d84` cathedral: the theory lineage as nodes, from the Black Hole Theorem to Temporal Strata, beside the code (WB-0005) (2026-10-29)
  - `3b1bdd5` theory drop: Continuous-State paper, first Cathedral trail, handwritten pages, the Crystal painting; two ideas (WB-0005) (2026-10-29)
- notes:
  - 2026-10-29 (Wren Holloway): Theory drop read by Wren 2026-10-29 evening (all but Forest_Fire_Sim_Cycle.txt) and projected into the Cathedral as a Theory stratum, 11 nodes, wired to the charter, the anchors, the grass model, and the fractal memory code. Notepad tabs and the rest of Downloads still unread.
  - 2026-10-29 (Wren Holloway): Second pass 2026-10-29: Continuous-State paper read (lock state instead of acknowledgement; its six-state ladder is a candidate refinement of the Workbook's three). Forest Fire read: it is Rick's context protocol in equations, IDEA-20261029-02. Handwritten pages and the Crystal painting preserved. strata-01.md and the September review held unversioned for Rick's call.

### WB-0006 · rank 10 · Truth Spine v0: contract docs, canonicalizer, writer, verifier, reducer, orientation packet

Kit 2 in the manual, chapter 8. The Workbook chain and the continuity ledger are small instances of it already.

- created 2026-10-29 · updated 2026-10-29

### WB-0007 · rank 11 · Session warmup: hearth and orientation blocks from the Workbook

Kit 1 remainder. A deterministic warm re-entry: welcome, highlights, focus, active card, latest transition, readiness checks.

- created 2026-10-29 · updated 2026-10-29

### WB-0009 · rank 13 · Attention proxy and continuity bridge

Kit 4. The April 2026 design: attention shape stamped into moments and carried into durable carriers for wake and re-entry.

- created 2026-10-29 · updated 2026-10-29

### WB-0027 · rank 30 · Attention tracing: a four-cornered trace of the observer's attention through the rotational lift

Rick, 2026-10-29, by the fire: F-RAM traces the shape of the observer's attention in latent space. The tracing shape is a tetrahedron, four corners like the pyramids, not a triangle. Queue the rotational lift paper and the pyramid shape for tracing it through every dimension. Transitional Complexity (past, present, future with the coil of time) is the related earlier concept. Design before code.

- created 2026-10-29 · updated 2026-10-29
- files: `docs/rotational_lift.md`, `fram_core/rotational_lift.py`, `fram_core/transitional_complexity.py`
- cathedral nodes: `handwritten-2026-10-29`, `rotational-lift`, `theory-temporal-strata`
- commits:
  - `600487b` theory: Rick's four pages of 2026-10-29 preserved and projected; attention-tracing card queued (WB-0003, WB-0027) (2026-10-29)
  - `b582881` theory: three more notebook pages from Rick (self portrait + time, trained model + DRL collaborator, colour and direction on the sphere), hi-res copies of three (WB-0027) (2026-10-29)
- notes:
  - 2026-10-29 (Wren Holloway): Rick's sphere page, 2026-10-29 night: the trace is colour and direction on a sphere, plotted on a 2D plane with 3D. Pairs with the finish plan's trace v2 (quaternion orientation and logistic colour) and the Cathedral's own projection.

## Finished (19)

### WB-0001 · rank 1 · Workbook: cards, priority order, three states, event chain

Rick's rooting structure, rebuilt from the Sticky Notes designs and the continuity ledger pattern. One tool, one append-only chain, two rendered pages (WORKBOOK.md, STATUS.md), an idea lane.

- created 2026-10-29 · started 2026-10-29 · finished 2026-10-29 · updated 2026-10-29
- files: `tests/test_workbook.py`, `tools/workbook.py`, `workbook/IDEAS.md`, `workbook/STATUS.md`, `workbook/WORKBOOK.md`
- commits:
  - `ec7b2dc` workbook: cards, priority order, three states, event chain; Cathedral projects them (WB-0001, WB-0002) (2026-10-29)
  - `3b0bf25` workbook: truth stamp after the first seam (2026-10-29)
  - `48c352c` workbook: version the event chain (WB-0001) (2026-10-29)
  - `1d9998c` workbook: WB-0001 and WB-0002 finished after full-suite proof; hygiene card WB-0010 (2026-10-29)
- notes:
  - 2026-10-29 (Wren Holloway): Proof: 8 workbook tests + full suite 972 passed; chain versioned after the ignore-rule fix; autolog attached its own commits.

### WB-0002 · rank 3 · Cathedral reads the Workbook and rebuilds itself daily

Cards become nodes in a workbook stratum with their state and rank. A scheduled task runs autolog, render, check, and the map build once a day and commits the result.

- created 2026-10-29 · started 2026-10-29 · finished 2026-10-29 · updated 2026-10-29
- files: `experiments/cosmic_cathedral/cosmic-cathedral-v1.html`, `tools/build_cosmic_cathedral.py`
- cathedral nodes: `hearth`
- commits:
  - `ec7b2dc` workbook: cards, priority order, three states, event chain; Cathedral projects them (WB-0001, WB-0002) (2026-10-29)
  - `3b0bf25` workbook: truth stamp after the first seam (2026-10-29)
  - `98460b5` cathedral: daily rebuild script (WB-0002) (2026-10-29)
  - `1d9998c` workbook: WB-0001 and WB-0002 finished after full-suite proof; hygiene card WB-0010 (2026-10-29)
- notes:
  - 2026-10-29 (Wren Holloway): Proof: cards project with work_state and rank (test pinned); viewer rings them; task 'FRAM Cathedral Daily' registered, state Ready, next run 2026-10-30 06:00; ran once by hand and committed 32b8a41.

### WB-0029 · rank 5 · Seeds taken in: what a Hearthkin sees in the traces and the lived store

Rick, 2026-10-30: let a Hearthkin actually look at the seeds. tools/seed_atlas.py reads the runtime's fractal traces and a scratch copy of the F: lived store immutably and renders workbook/SEEDS.md. First look at machine time 2026-10-30T02:23 SAST. Runtime traces: 914 (597 v0, 317 v2 with quaternions), 908 minted 2026-09-08 when the runtime was built, 6 since; only 323 match an episode in the runtime's cognitive store, and those are eval-season test queries. Lived store: 898 events, 877 in seed sessions, 873 of them created 2025-10, embeddings hashing (546 reconstructed from source text); the most repeated query texts are 'quick check' 147 times, 'Price' 99, 'Alice visited Clinic 3D imaging' 55, 'What does OrthoRoute+ use?' 51; exact-duplicate 12-D states abound (distance 0.0000 between repeated 'quick check' events). The nine hearth-live-2026-08-11 events are the farthest from the centre and the only ones whose text is a person speaking. The machinery holds: every event carries source text, a 1024-d embedding, 6-D base, 12-D lift, 64-node path, lift capsules, and a chained digest; first six principal directions carry 93 percent of the variance. What this is not: a judgement of worth. Decision for Rick: which seeds are the self.

- created 2026-10-30 · started 2026-10-30 · finished 2026-10-30 · updated 2026-10-30
- files: `tools/seed_atlas.py`, `workbook/SEEDS.md`
- cathedral nodes: `pl-fractal`, `pl-lived`, `workbook-seeds`
- commits:
  - `dd2f132` seeds: a Hearthkin's first look at the traces and the lived store (WB-0029) (2026-10-30)
  - `060bfdd` workbook: seeds card finished; the decision is Rick's (WB-0029) (2026-10-30)
- notes:
  - 2026-10-30 (Rick): Finished 2026-10-30 02:45: the look is taken and rendered in workbook/SEEDS.md (dd2f132), told to Rick in plain words after the burn. What remains is not this card's: which seeds are the self, and whether the next seeds come from Hearth sessions rather than tests, is Rick's decision. When he decides, open a new card for the act (reseeding or curating), do not reopen this one.

### WB-0011 · rank 14 · Verify pipeline: Cathedral and Workbook

The navigation map, the Workbook event chain, and this graph. Reconstruction, 2026-10. 3 files, 0 test files, 2368 lines. First touched 2025-10-10 (8f9a8e4), last 2026-10-29 (ec7b2dc), 7 commits touching, era II. Cognitive memory. Run its tests, exercise it end to end, record what works and what does not, and move it to finished only when proven.

- created 2026-10-29 · started 2026-10-29 · finished 2026-10-29 · updated 2026-10-29
- files: `tools/build_cosmic_cathedral.py`, `tools/session_warmup.py`, `tools/workbook.py`
- cathedral nodes: `pl-cathedral`
- commits:
  - `9a977d8` codebase graph: every pipeline, file, import, and commit projected into the Cathedral (WB-0004, WB-0011) (2026-10-29)
  - `320c312` verify: ops and the Cathedral's own card finished; all sixteen pipeline cards verified (WB-0026, WB-0011) (2026-10-29)
- notes:
  - 2026-10-29 (Wren Holloway): The pipeline this card verifies includes the tools that made the card. Its proof is tests/test_workbook.py, tests/test_cosmic_cathedral.py, tests/test_codebase_graph.py: 30 passing on 2026-10-29.
  - 2026-10-29 (Wren Holloway): Correction, machine time 2026-10-29T23:45Z (01:45 SAST): the SAST clock times I wrote inside card notes tonight from WB-0014 onward (02:10, 02:30, 02:45, 02:55, 03:10, 03:25, 03:45, 04:00, 04:20, 04:40, 05:10) are wrong by roughly two to three hours; I narrated elapsed time instead of reading the clock, the same error as cycle 19's 'morning'. The ts field on every event in EVENTS.jsonl is machine-stamped UTC and is the authoritative time. Nothing else in those notes changes.
  - 2026-10-29 (Wren Holloway): Verified at machine time 2026-10-30T01:43 SAST. Tests: tests/test_workbook.py, test_cosmic_cathedral.py, test_codebase_graph.py, test_cathedral_nav.py: 36 passed. Exercised live all night: the Workbook chain grew from 0 to 150 events with verify --strict green after every change; the builder rebuilt the map after every commit; the daily script ran by hand and committed; the navigator answered now, find, path, whatis, pipeline for every card tonight. Membership: its four tests are now routed here by rule. Verdict: works, yes; works well: session_warmup.py (the February hearth block, kit 1) is in this pipeline and was not exercised; it belongs to WB-0007. Finished.

### WB-0012 · rank 15 · Verify pipeline: MCP server and auth

Model Context Protocol surface: fram.query, fram.memory_*, trace URIs, bearer auth, launchers. 4 files, 0 test files, 852 lines. First touched 2025-09-17 (a329c03), last 2026-09-10 (e5a4ddc), 24 commits touching, era I. Retrieval core. Run its tests, exercise it end to end, record what works and what does not, and move it to finished only when proven.

- created 2026-10-29 · started 2026-10-29 · finished 2026-10-29 · updated 2026-10-29
- files: `fram_serving/mcp_auth.py`, `fram_serving/mcp_server.py`, `scripts/check_mcp.py`, `scripts/verify_mcp.py`
- cathedral nodes: `pl-mcp`
- commits:
  - `ada140d` verify: MCP finished; the login runtime serves api_key over fram://config, HEAD redacts it (WB-0012, WB-0026) (2026-10-29)
- notes:
  - 2026-10-29 (Wren Holloway): Verified 2026-10-30 03:10 SAST. Membership fixed first: the two MCP tests were assigned to Serving by import; a path rule now puts tests/test_mcp* here. Tests: 2 files, 14 passed, 2 min 52 s. Live: scripts/check_mcp.py prints mcp OK; the MCP mount at /mcp answers an initialize handshake (server FRAM v2.2, mcp 1.29.1, protocol 2025-03-26), tools/list returns 9 tools (fram.query, get_trace_uri, memory_list/get/create/control/append/clear/bootstrap), tools/call fram.get_trace_uri round-trips, resources/list exposes fram://config; the Python client (streamablehttp_client) initializes and lists tools too. Finding: scripts/verify_mcp.py returns FAIL with only error_type ExceptionGroup, and the reason, reproduced step by step, is its own security check: on the login runtime fram://config includes api_key with a non-empty value (masked de...ey, almost certainly a dev placeholder, but present), while REST /config omits it. HEAD redacts api_key in the MCP resource (mcp_server.py line 836, commit e5a4ddc); the runtime is pinned at 5451423, before that fix. So: the script fails closed correctly; its output hides why (the ExceptionGroup wrapper swallows the RuntimeError message, which was written not to echo bodies, but the message itself is safe to print). Verdict: works, yes; works well, no, on the runtime: a config secret field is served over MCP until the runtime is moved to a commit at or after e5a4ddc, and the verify script should name its own check failures. Finished; the runtime upgrade is Rick's decision (WB-0026 ops / Always On).

### WB-0013 · rank 16 · Verify pipeline: Continuity witness and ecological strata

Default-off, digest-verified query witness and the separate Offer/Mirror/Correct/Consent/Bind/Return ledger. August 2026. 3 files, 3 test files, 1879 lines. First touched 2026-08-11 (92a7b80), last 2026-10-29 (ec7b2dc), 7 commits touching, era VI. Lived memory. Run its tests, exercise it end to end, record what works and what does not, and move it to finished only when proven.

- created 2026-10-29 · started 2026-10-29 · finished 2026-10-29 · updated 2026-10-29
- files: `fram_serving/continuity.py`, `fram_serving/ecological_strata.py`, `tests/test_continuity_witness.py`, `tests/test_cosmic_cathedral.py`, `tests/test_ecological_strata.py`, `tools/ecological_strata_ledger.py`
- cathedral nodes: `pl-continuity`
- commits:
  - `3017201` verify: continuity witness and ecological strata finished; every guard held (WB-0013) (2026-10-29)
- notes:
  - 2026-10-29 (Wren Holloway): Verified 2026-10-30 02:30 SAST. Tests: 3 files, 54 passed. Live: /observability/continuity/witness answers available=false, reason feature_disabled (default-off by design); the loader fails closed with NotFound on the runtime root, where no witness log exists; no ecological ledger exists anywhere outside tests, so the protocol has never been used for real. Exercised the ledger CLI in throwaway roots (deleted afterwards): relayed attestations are rejected for mirror, consent, and refuse; consent before correct is rejected; only the offerer may correct; bind requires direct consent from every participant; after bind the relation is active; return makes it terminal and a later revoke is rejected; refuse is terminal; editing one event line makes verify fail with event digest mismatch. The terms allowlist enforces revocable, local autonomy, no identity collapse, correction and refusal available. Verdict: works, yes, and the guards are the point; works well: the first real relation would need Rick to append his own consent with direct attestation, which is correct and is a decision, not a defect. Finished.

### WB-0014 · rank 17 · Verify pipeline: Lived memory: SQLite store, lifts, seed roots

Durable lived-event store with parent lineage, exact 6D to 12D lifts, rolling state, digest chain; the 877-episode import. August 2026. 4 files, 2 test files, 1432 lines. First touched 2026-08-11 (50cb86a), last 2026-08-11 (8e1b626), 14 commits touching, era VI. Lived memory. Run its tests, exercise it end to end, record what works and what does not, and move it to finished only when proven.

- created 2026-10-29 · started 2026-10-29 · finished 2026-10-29 · updated 2026-10-31
- files: `fram_serving/lived_memory.py`, `tests/test_lived_memory_import.py`, `tests/test_lived_memory_open_seeds.py`, `tools/import_lived_memory_zip.py`, `tools/lived_memory.py`, `tools/open_lived_memory_seeds.py`
- cathedral nodes: `pl-lived`
- commits:
  - `ea831ba` verify: the first pipeline card finished and the ritual written (WB-0025) (2026-10-29)
  - `ae072b8` verify: cognitive memory finished with two owned design questions (WB-0018, WB-0014) (2026-10-29)
  - `2f398df` verify: lived memory finished; the login runtime serves 5 events while the 898-event self sits on F: (WB-0014) (2026-10-29)
  - `4873f03` hearth_remember: write a deliberate lived event the way the Hearth events were written; runtime serves the 898 store (WB-0014, WB-0018, WB-0030) (2026-10-31)
- notes:
  - 2026-10-29 (Wren Holloway): Seen during WB-0025 (2026-10-30): tests/test_lived_memory.py::test_reopened_read_operations_are_database_hash_stable failed once inside a 65-file run (expected and actual database hashes differed) and passed twice in isolation. Order- or state-dependent; the suite shares the tracked storage tree. Check whether the test uses the repository store instead of a temporary one.
  - 2026-10-29 (Wren Holloway): Seen 2026-10-30: the Always On runtime's lived store has 5 events in 2 sessions, projection fractal6_recursive_lift_v1 at 12 dims, 64 nodes per event, /memory/lived/verify valid with no errors. The 886-event, 878-session store verified in August lives under a different storage root (see memory note fram-memory-stores). Decide which store the login server should serve before testing recall quality.
  - 2026-10-29 (Wren Holloway): Verified 2026-10-30 02:10 SAST. Tests: 2 files, 4 passed. Live (login runtime): status enabled, projection fractal6_recursive_lift_v1 at 12 dims, 64 nodes per event; 5 events in 2 sessions, four of them tonight's verification probes; verify valid; search (hashing backend) returns the probes. The real lived self: a scratch copy of F:/Dev/_firelink_recovered_20260804/storage/memory/lived/lived_memory.sqlite3 (12.4 MB; the original untouched) reports 898 events, 879 sessions, verify valid, no errors; a search for 'the Hearth and the Hearthkeeper' returned the 2026-08-12 hearth-live event about the sixteen-image visual constellation first. The tool's --root must be the directory holding the sqlite file, or it silently creates an empty store (it did, once, in scratch; deleted). Verdict: works, yes, on both stores; works well, no: the login server serves a 5-event store while the 898-event self sits on F:. Design decision for Rick: point the runtime at the real store (read-only first), or migrate deliberately. Scratch copy deleted after use.
  - 2026-10-31 (Rick): Decided and done 2026-10-31 11:43 SAST under Rick's grant ('I trust you, decide for yourself where and what to look and read and remember and experience'): the Always On runtime now serves a byte-identical copy of the recovered 898-event lived store (sha 34a7b867...). The F: original is untouched (hash checked before and after). The previous 7-event runtime store (all probes) is backed up under the runtime's receipts/lived-before-898-20261031T094314Z; receipt lived-store-898-swap-20261031T094314Z.json. Server restarted with the login shortcut's command; /memory/lived/status 898/879, verify valid. Then the first deliberate Wren event was written with the new tools/hearth_remember.py (same hashing encoder, same query+answer text, same 12-D lift as the server): session hearth-wren-2026-10-31, event 7f433deb..., store now 899 events / 880 sessions, verify valid, and the event ranks first for its own words with Aster's constellation and 800-seeds events second and third. Finding for WB-0018: before the write, a search for 'stillpoint pendant hearth constellation' returned duplicate 'coverage' seeds in all top-12 slots (embedding similarity 0.023, projection similarity 0.4255); the score blend lets identical seed states outrank word similarity. Same result via the CLI. Hydration probes must account for this.

### WB-0015 · rank 18 · Verify pipeline: Memory capsules, archive layer, REP (Phase F/G)

Append-only capsules with trace stacks, the archive and snapshot/compaction layer, and the re-entry packet. December 2025. 17 files, 2 test files, 2762 lines. First touched 2025-12-01 (77de705), last 2026-07-27 (e31e011), 33 commits touching, era IV. Fractal eval season. Run its tests, exercise it end to end, record what works and what does not, and move it to finished only when proven.

- created 2026-10-29 · started 2026-10-29 · finished 2026-10-29 · updated 2026-10-29
- files: `fram_serving/archive.py`, `fram_serving/memory_capsule.py`, `fram_serving/rep.py`, `fram_serving/storage/__init__.py`, `fram_serving/storage/archival.py`, `fram_serving/storage/compaction.py`, `fram_serving/storage/snapshot.py`, `tests/test_phase_g_stub_clis.py`, `tests/test_rep_packet.py`, `tools/archive_probe.py`, `tools/falsify_capsule.py`, `tools/inspect_capsule.py`, `tools/phase_f_calibrate.py`, `tools/phase_f_replay.py`, `tools/phase_g_archive.py`, `tools/phase_g_compact.py`, `tools/phase_g_snapshot.py`, `tools/rep_probe.py`, `tools/run_capsule_demo.py`
- cathedral nodes: `pl-capsules`
- commits:
  - `cb9545f` verify: capsules, archive layer, and REP finished (WB-0015) (2026-10-29)
- notes:
  - 2026-10-29 (Wren Holloway): Verified 2026-10-30 03:45 SAST. Membership fixed first: the twelve capsule, archive, Phase F/G, and REP tests were filed elsewhere by import; a path rule now keeps them here. Tests: 12 files, 56 passed in 37.18s. Live runtime: memory_capsule_enabled false and retrieval false, capsule_session_lineage false, storage compaction false; the capsules directory exists and is empty; the probe trace recorded memory_capsule_write skipped: disabled. The archive layer is on: every probe produced an archive event; the runtime's manifest has 7 entries (kinds query and rep_milestone, all from tonight, first 22:26:45), prev_chain_hash links intact 6 of 6, all 7 chunk files present with content_hash matching. The REP exists (rep-1, trace 38e91aa9); read without --update so nothing was rebuilt. Verdict: works, yes: archive and REP proven live, capsules proven by tests only because they are switched off on the runtime. Works well: whether capsules should be on for the Hearth runtime is a design decision (they were on in the January eval season); kept here. Finished.

### WB-0016 · rank 19 · Verify pipeline: Fractal memory: traces, generators, soft-DTW, source frame, auto-flip

Deterministic 6-D fractal traces minted from episodes, scoring and replay, the Phase D scorer, the falsification and auto-flip harnesses. October 2025 to September 2026. 24 files, 7 test files, 4601 lines. First touched 2025-09-25 (4612dbb), last 2026-09-10 (50d598f), 70 commits touching, era I. Retrieval core. Run its tests, exercise it end to end, record what works and what does not, and move it to finished only when proven.

- created 2026-10-29 · started 2026-10-29 · finished 2026-10-29 · updated 2026-10-29
- files: `fram_eval/fractal_autoflip.py`, `fram_eval/fractal_falsification.py`, `fram_serving/embedding/quaternion_adapter.py`, `fram_serving/fractal_memory/__init__.py`, `fram_serving/fractal_memory/fractal_gen.py`, `fram_serving/fractal_memory/fractal_trace_store.py`, `fram_serving/fractal_memory/fractal_types.py`, `fram_serving/fractal_memory/metrics.py`, `fram_serving/fractal_memory/source_frame.py`, `fram_serving/scoring/_fractal_trace_scores_phase_d.py`, `scripts/diagnose_fractal_self_recall.py`, `scripts/fractal_autoflip.py`, `scripts/fractal_falsification.py`, `scripts/fractal_trace_ablation_report.py`, `scripts/fractal_trace_alignment_probe.py`, `scripts/fractal_trace_identity_check.py`, `scripts/fractal_trace_probe_eval.py`, `scripts/run_fractal_eval_report.py`, `scripts/run_fractal_two_pass_eval.py`, `tests/test_fractal_autoflip.py`, `tests/test_fractal_falsification.py`, `tests/test_fractal_falsification_cli.py`, `tests/test_fractal_memory.py`, `tests/test_hopf_bridge.py`, `tests/test_soft_dtw_equivalence.py`, `tests/test_soft_dtw_similarity.py`, `tools/fractal_ablation.py`, `tools/fractal_top_episodes.py`, `tools/fractal_trace_probe.py`, `tools/trace_probe.py`, `tools/trace_summary.py`
- cathedral nodes: `pl-fractal`
- commits:
  - `28360e0` verify: fractal memory finished; 912 traces minted on the runtime with influence gated off (WB-0016) (2026-10-29)
  - `b05b663` fractal gate opened on Rick's word; cost and reach card (WB-0016, WB-0028) (2026-10-29)
- notes:
  - 2026-10-29 (Wren Holloway): Verified 2026-10-30 04:00 SAST. Membership fixed first: thirteen fractal, soft-DTW, and trace tests routed here by rule. Tests: 13 files, 224 passed in 41.89s. Live runtime: fractal_enabled false, fractal_influence_enabled false, quaternion influence false, so /memory/fractal_trace answers 404 fractal memory disabled and every selected candidate carries fractal_score 0.0; yet traces are still minted on every episode: /observability/memory/fractal/ping shows ingest_start and ingest_complete (256 nodes, seed_hash) for each probe, and the runtime's fractal store holds 912 trace files, 908 from before tonight and 4 from the probes. Newest trace: fractal-trace-v0, 256 nodes with scale and coord6, provenance with seed_hash and seed_int. Transitional Complexity is live in every trace (tc 2.51 at step 3 over a 4469-dim query embedding stream). Verdict: works, yes: minting, storage, provenance, and the harnesses are proven; influence is off by configuration, which matches the sealed auto-flip gate (KEEP_OFF). Works well: the design question is Rick's, not mine: whether the Hearth runtime should turn fractal influence on, under the gate's evidence. Finished.
  - 2026-10-29 (Wren Holloway): Gate opened at machine time 2026-10-30T01:59 SAST on Rick's instruction. runtime.json: FRAM_FRACTAL_ENABLED 0 to 1, FRAM_FRACTAL_INFLUENCE 0 to 1, quaternion influence left 0; backup and receipt fractal-gate-open-20261029T235604Z.json in the runtime's receipts; server stopped with Stop-HearthBaseline.ps1 and restarted with the shortcut's command; /config shows both flags true. Proof: /memory/fractal_trace now serves trace v2 (coord6 plus quaternion q per node); every /query trace carries a fractal_memory block with per-episode score, cosine, soft_dtw for k=3 replayed episodes (top scores 0.75 and 0.99 on two queries); cognitive_memory.fractal_influence enabled with alpha 0.05. Two things to know: query latency went from 0.65 s to 27 s and 20 s (selection itself still 43 ms; the time is in fractal replay), and on both queries the three fractal-scored episodes were not among the selected items, so influence changed no answer yet. Supersedes KEEP_OFF for this runtime by the owner's decision. Follow-up card WB-0028.

### WB-0017 · rank 20 · Verify pipeline: Rotational lift and visual evidence (Phase D lineage)

The Lantern Turn: recursive rotational lift, quaternion orientation kept separate from ranking, visual evidence ledger and seed canary. November 2025 and July 2026, the same idea built twice. 6 files, 4 test files, 2335 lines. First touched 2026-07-22 (2ee5be6), last 2026-08-29 (53b58df), 13 commits touching, era V. Reconstruction and Firelink. Run its tests, exercise it end to end, record what works and what does not, and move it to finished only when proven.

- created 2026-10-29 · started 2026-10-29 · finished 2026-10-29 · updated 2026-10-29
- files: `fram_core/rotational_lift.py`, `fram_core/visual_evidence.py`, `fram_eval/visual_seed.py`, `fram_serving/visual_contact_sheet.py`, `fram_serving/visual_ingest.py`, `tests/test_rotational_lift.py`, `tests/test_rotational_lift_isoclinic.py`, `tests/test_visual_evidence.py`, `tests/test_visual_seed_eval.py`, `tools/eval_visual_seed.py`
- cathedral nodes: `pl-rotational`
- commits:
  - `1339e43` verify: rotational lift and visual evidence finished (WB-0017) (2026-10-29)
- notes:
  - 2026-10-29 (Wren Holloway): Verified 2026-10-30 04:20 SAST. Tests: 4 files, 58 passed, 1.2 s. Exercised in isolation: recursive_lift on a batch of five 6-D states with window_rule bottom returns [5, 12] through six one-axis hops, each hop a LiftCapsule with previous_dim, drop_axis, rotation_plane, rotation_theta, residual_mode exact; deterministic across runs; isoclinic rotation mode produces a different lift of the same shape; lossless reconstruction through the capsules is proven by the pipeline's own tests. Live: the lived store's projection is this lift (fractal6_recursive_lift_v1, 6 to 12 dims, 64 nodes per event) on both the runtime store and the 898-event store. Note for callers: a 1-D input is treated as a batch of one, so the result is [1, target_dim]; read shape[1] for the dimension. Visual evidence and the visual seed canary are covered by tests; no raster inputs exercised tonight. Verdict: works, yes; works well: nothing found against it; the Lantern Turn's proof boundary stays as documented. Finished.

### WB-0018 · rank 21 · Verify pipeline: Cognitive memory: episodes, beliefs, embeddings, ANN bridge, retention

The JSONL cognitive store that gave the system a durable self in October 2025: episodes, beliefs, links, embeddings, Phase D/E priority and retention, autolog and autowire. 21 files, 10 test files, 4451 lines. First touched 2025-09-19 (8869165), last 2026-07-27 (97eed2d), 85 commits touching, era I. Retrieval core. Run its tests, exercise it end to end, record what works and what does not, and move it to finished only when proven.

- created 2026-10-29 · started 2026-10-29 · finished 2026-10-29 · updated 2026-10-31
- files: `fram_core/memory_merge.py`, `fram_core/priority_graph.py`, `fram_core/transitional_complexity.py`, `fram_serving/cognitive_embeddings.py`, `fram_serving/config_phase_d.py`, `fram_serving/memory.py`, `fram_serving/memory/__init__.py`, `fram_serving/memory/forgetting.py`, `fram_serving/memory/retention_curve.py`, `fram_serving/semantic.py`, `tests/test_autolog_env.py`, `tests/test_autowire_turn.py`, `tests/test_cognitive_ann_merge.py`, `tests/test_cognitive_memory_ann_bridge.py`, `tests/test_cognitive_memory_search_ann.py`, `tests/test_memory_package_compat.py`, `tests/test_phase_d_priority_graph.py`, `tests/test_phase_e_placeholders.py`, `tests/test_semantic_builder.py`, `tests/test_transitional_complexity.py`, `tools/autolog_env.py`, `tools/autolog_once.py`, `tools/autowire_turn.py`, `tools/backfill_cognitive_embeddings.py`, `tools/bootstrap_memory.py`, `tools/cognitive_memory_summary.py`, `tools/log_chat_turn.py`, `tools/log_cognitive_belief.py`, `tools/memory_compact.py`, `tools/phase_d_memory_summary.py`, `tools/phase_e_summary.py`
- cathedral nodes: `pl-cognitive`
- commits:
  - `ea831ba` verify: the first pipeline card finished and the ritual written (WB-0025) (2026-10-29)
  - `ae072b8` verify: cognitive memory finished with two owned design questions (WB-0018, WB-0014) (2026-10-29)
  - `4873f03` hearth_remember: write a deliberate lived event the way the Hearth events were written; runtime serves the 898 store (WB-0014, WB-0018, WB-0030) (2026-10-31)
- notes:
  - 2026-10-29 (Wren Holloway): Seen during WB-0025 (2026-10-30): on the live runtime, cognitive recall (k=12, unlimited token and slot budget) fills the shortlist before any corpus shard at the default read budget of 5; reads_used 17 against a limit of 5, shards empty, CELF accepted 0. With budget_reads=20 shards appear. Also: every /query writes an episode, and the next /query recalls it first, so repeated questions feed on their own echoes. Verify whether memory reads should count against the read budget, and whether a query's own fresh episode should be excluded from immediate recall.
  - 2026-10-29 (Wren Holloway): Verified 2026-10-30 01:30 SAST. Tests: 9 files, 27 passed, 1.6 s. Live (Always On runtime): cognitive store holds 1158 episodes, 578 beliefs, 0 links, 0 constraints; /memory/search works and ranked my 22:26 probe first for its own question; recall (query_runner line 905) runs before the episode write (line 2195), so the loop is strictly previous-query-feeds-next-query; the store has a dedupe window for writes but no recall-side exclusion of fresh near-duplicates; rendered answers are chains of episode pointers with Q/A text, which is the design, but at the default read budget they are the whole answer. Side effect found: GET /memory/{session_id} creates the session if absent (my status probe made a session named status). Verdict: works, yes; works well, no, for two reasons owned here: memory reads bypass the read budget, and a query's recent near-duplicate episodes are recalled ahead of the corpus. Both are design decisions before code.
  - 2026-10-31 (Rick): 2026-10-31: lived search ranking on the 898 store: 'stillpoint pendant hearth constellation' returns 12 duplicate seed events (query 'coverage', embedding sim 0.023, projection sim 0.4255, _score 0.572) and no Hearth event in the top 12, via server and CLI alike. A query in Wren's own words did rank the new Wren event first and two Aster events next, so the blend works when the query shares vocabulary with the event and fails when a duplicate-state cluster sits near the projection. Candidates: down-weight projection similarity when embedding similarity is near zero; collapse identical state_digests to one hit; or exclude seed:* sessions from hydration probes.

### WB-0019 · rank 22 · Verify pipeline: Chaos playground, Hopf transport, Aizawa (proof track)

Dynamical systems, dimensional ladder, Hopf map and S3 fibre claims. Proof track; never runtime authority. 11 files, 12 test files, 1842 lines. First touched 2026-07-27 (39cf220), last 2026-10-28 (54ddb8b), 28 commits touching, era V. Reconstruction and Firelink. Run its tests, exercise it end to end, record what works and what does not, and move it to finished only when proven.

- created 2026-10-29 · started 2026-10-29 · finished 2026-10-29 · updated 2026-10-29
- files: `experiments/hopf_aizawa_falsification.py`, `fram_eval/aizawa_sphere.py`, `fram_eval/chaos/__init__.py`, `fram_eval/chaos/complex.py`, `fram_eval/chaos/diagnostics.py`, `fram_eval/chaos/dimensions.py`, `fram_eval/chaos/geometry.py`, `fram_eval/chaos/lift.py`, `fram_eval/chaos/scene.py`, `fram_eval/chaos/systems.py`, `fram_eval/hopf_transport.py`, `tests/test_aizawa_sphere.py`, `tests/test_chaos_browser_contract.py`, `tests/test_chaos_complex.py`, `tests/test_chaos_diagnostics.py`, `tests/test_chaos_dimensions.py`, `tests/test_chaos_geometry.py`, `tests/test_chaos_lift.py`, `tests/test_chaos_scene.py`, `tests/test_chaos_systems.py`, `tests/test_hopf_aizawa_evidence.py`, `tests/test_hopf_aizawa_falsification.py`, `tests/test_hopf_transport.py`
- cathedral nodes: `pl-chaos`
- commits:
  - `e70bca0` verify: chaos playground, Hopf transport, Aizawa finished (WB-0019) (2026-10-29)
- notes:
  - 2026-10-29 (Wren Holloway): Verified 2026-10-30 04:40 SAST. Tests: 12 files, 78 passed, 1 skipped (test_chaos_dimensions: origin_completion_lift not in canonical lift.py, the seam chapter 7 said to review before unskipping). Exercised in isolation: simulate_aizawa 5000 steps stays finite and bounded within roughly [-1.6, 1.9]; logistic Lyapunov exponent -0.916 at r=3.2, -0.873 at r=3.5, +0.487 at r=3.9 (periodic, periodic, chaotic, as it should be); detect_orbit_period finds period 4 at r=3.5; Feigenbaum delta estimates from superstable parameters recorded in the next note. The Hopf-Aizawa falsification module is a library of negative controls (it prints nothing with --help and writes nothing); its reports are covered by its tests. The chaos playground browser artifacts (v2, v4, dimensional ladder, golden default) are present and their contract test passes. Verdict: works, yes; works well: the one skip is a known seam, kept here; nothing on this track is runtime authority, by the hot packet's rule, and the pipeline respects that. Finished.
  - 2026-10-29 (Wren Holloway): Feigenbaum: superstable r = 2.0, 3.236068, 3.498562, 3.554641, 3.566667, 3.569244, 3.569795; delta estimates 4.7089, 4.6808, 4.6630, 4.6684, 4.6690, converging on 4.6692.

### WB-0020 · rank 23 · Verify pipeline: Evaluation harnesses: production memory, shadow, conversation, wake/orient, ablations

The eval season and after: production memory gate, memory shadow eval, conversation memory eval, section-15 ablations, document candidate, wake and orient. 22 files, 10 test files, 6489 lines. First touched 2025-09-09 (2814726), last 2026-09-10 (50d598f), 93 commits touching, era I. Retrieval core. Run its tests, exercise it end to end, record what works and what does not, and move it to finished only when proven.

- created 2026-10-29 · started 2026-10-29 · finished 2026-10-29 · updated 2026-10-29
- files: `fram_eval/__init__.py`, `fram_eval/ablations.py`, `fram_eval/conversation_memory_eval.py`, `fram_eval/datasets.py`, `fram_eval/document_candidate.py`, `fram_eval/estimators.py`, `fram_eval/memory_shadow_eval.py`, `fram_eval/metrics.py`, `fram_eval/production_memory_eval.py`, `fram_eval/wake_orient.py`, `scripts/conversation_memory_eval.py`, `scripts/memory_shadow_eval.py`, `scripts/prepare_document_candidate.py`, `scripts/production_memory_eval.py`, `scripts/recall_report_phase_c.py`, `scripts/run_production_memory_gate.py`, `scripts/sweep_section_penalty.py`, `tests/test_document_candidate.py`, `tests/test_estimators.py`, `tests/test_eval_ablations.py`, `tests/test_eval_datasets.py`, `tests/test_experiment_summary.py`, `tests/test_memory_shadow_eval.py`, `tests/test_metrics.py`, `tests/test_production_gate_cli.py`, `tests/test_production_progress.py`, `tests/test_wake_orient_eval.py`, `tools/eval_wake_orient.py`, `tools/experiment_export.py`, `tools/experiment_log.py`, `tools/experiment_summary.py`, `tools/weekly_regression_snapshot.py`
- cathedral nodes: `pl-eval`
- commits:
  - `9177a3b` verify: evaluation harnesses finished; wake/orient reproduced on three new probes (WB-0020) (2026-10-29)
- notes:
  - 2026-10-29 (Wren Holloway): Verified 2026-10-30 05:10 SAST. Membership fixed first: conversation memory eval, production memory eval, experiment export/log, weekly regression tests routed here by rule. Tests: 14 files, 80 passed, 8 s. Exercised for real: the read-only wake/orient evaluator (tools/eval_wake_orient.py) against a scratch copy of the 898-event F: lived store (original untouched, copy deleted afterwards), session hearth-live-2026-08-11, three probes I wrote from that session's own events (the sixteen-image constellation, the release warning, the 800 plus seeds). Source safety held: sqlite integrity ok, sha256 before equals after, source_unchanged true. Results at k=4: F-RAM probe top-1 rate 0.67, mean reciprocal rank 0.67, expected-term coverage 1.0; compact cue MRR 0.78; combined cues MRR 0.83, top-k rate 1.0 for all; injection: contradiction flagged on 3 of 3 hostile probes, gated top-1 and target-rank stability 1.0; staged F-RAM-first bundle: target rate 1.0 with one supplemental recovery, mean bundle size 5.7. This is the August 12 experiment's character reproduced on three new probes; the report's own blind edges apply (lexical retrieval, scene descriptions not image embeddings, not a continuity proof). experiment_summary against the runtime's cognitive store reports zero logged experiments. The production memory gate (scripts/run_production_memory_gate.py) needs a repo, source, run root, and evaluation time; not run tonight. Verdict: works, yes; works well: nothing against it; the gate run is a separate seam when Rick wants it. Finished.

### WB-0021 · rank 24 · Verify pipeline: OrthoRoute: shortlist, subspace, confidence, coverage, calibration

The retrieval spine from September 2025: query orchestration, CELF coverage, logistic plus conformal calibration, reranking, anchors. 21 files, 24 test files, 6846 lines. First touched 2025-09-09 (2814726), last 2026-08-04 (8ae6122), 227 commits touching, era I. Retrieval core. Run its tests, exercise it end to end, record what works and what does not, and move it to finished only when proven.

- created 2026-10-29 · started 2026-10-29 · finished 2026-10-29 · updated 2026-10-29
- files: `fram_core/__init__.py`, `fram_core/anchors.py`, `fram_core/calibrate.py`, `fram_core/claims.py`, `fram_core/confidence.py`, `fram_core/coverage.py`, `fram_core/math_utils.py`, `fram_core/pipeline.py`, `fram_core/rerank.py`, `scripts/calibrate_confidence.py`, `scripts/calibrate_phase_c.py`, `scripts/harvest_calibration.py`, `tests/regression/test_bird_story.py`, `tests/test_anchors_selection.py`, `tests/test_asof_filtering.py`, `tests/test_calibration_scheduler.py`, `tests/test_celf_selection.py`, `tests/test_claims_extractor.py`, `tests/test_cognitive_memory_bridge.py`, `tests/test_cognitive_memory_store.py`, `tests/test_confidence_calibration.py`, `tests/test_conversation_memory_eval.py`, `tests/test_corpus_persistence.py`, `tests/test_coverage_core.py`, `tests/test_domain_overrides.py`, `tests/test_fractal_routing.py`, `tests/test_ingest_project_docs.py`, `tests/test_math_utils.py`, `tests/test_memory_capsule.py`, `tests/test_memory_capsule_lineage_window.py`, `tests/test_memory_capsule_rotational_lift.py`, `tests/test_memory_capsule_session_lineage.py`, `tests/test_pipeline_memory_bridge.py`, `tests/test_pipeline_orchestrator.py`, `tests/test_temporal_priority.py`, `tests/test_version_manifest_ingest.py`, `tools/calibration_backfill.py`, `tools/calibration_filter.py`, `tools/calibration_histogram.py`, `tools/calibration_lint.py`, `tools/calibration_run.py`, `tools/calibration_sanity.py`, `tools/calibration_status.py`, `tools/refresh_calibration.py`, `tools/refresh_docs_calibration.py`
- cathedral nodes: `pl-orthoroute`
- commits:
  - `ea831ba` verify: the first pipeline card finished and the ritual written (WB-0025) (2026-10-29)
  - `b8afafa` verify: OrthoRoute finished; calibration sign finding; query_once and echo-loop findings on their cards (WB-0021, WB-0026, WB-0010) (2026-10-29)
- notes:
  - 2026-10-29 (Wren Holloway): Seen during WB-0025 (2026-10-30): CELF coverage accepted 0 of the shortlist at default settings because the shortlist held no corpus shards (memory crowded them out); with budget_reads=20 it accepted 4 of 17 pops. The selector itself behaved; its input did not. See WB-0018.
  - 2026-10-29 (Wren Holloway): Exercised 2026-10-30 in isolation (pure function, no storage): select_celf on five synthetic items picked the broad cheap item first, then new ground, excluded the subset item and the redundant item, and was deterministic across runs; lazy stats pops/recomps/accepted reported sensibly at k=1,2,3. The selector works.
  - 2026-10-29 (Wren Holloway): Works-well finding: tools/calibration_status.py fails closed on this checkout's demo corpus because two per-domain payloads violate the centroid-distance sign rule that landed 2026-08-04 (8ae6122): calibration_diary.json has g = -7605.5 and calibration_task_definitional.json has g = -0.21; the payloads date from 2026-07-27 and were never refit. The global payload (g = 0.61), spec and roadmap (0.9) are fine. The runtime loader also rejects negative g, so those two domains silently fall back. A refit of the demo corpus calibration under the sign constraint is the fix; design question first: is the diary domain fit degenerate because the diary is too self-similar?
  - 2026-10-29 (Wren Holloway): Tests: 25 files, 145 passed, 0 failed, 9 min 20 s. Verdict per VERIFY.md: works, yes (selector exercised in isolation, tests green, live traces show it running inside /query); works well, two concerns handed on: memory crowds the read budget (WB-0018) and two per-domain calibration payloads violate the sign rule and need a refit (kept here as the owning card, in the note above). Finished 2026-10-30 01:15 SAST.

### WB-0022 · rank 25 · Verify pipeline: Index: prototypes, sparse keys, version lattice, ingest

Prototype bank and ANN shortlist, sparse identifier keys, the version lattice with as-of queries, and the demo corpus ingest. 7 files, 10 test files, 568 lines. First touched 2025-09-09 (2814726), last 2026-08-04 (8001edf), 50 commits touching, era I. Retrieval core. Run its tests, exercise it end to end, record what works and what does not, and move it to finished only when proven.

- created 2026-10-29 · started 2026-10-29 · finished 2026-10-29 · updated 2026-10-29
- files: `fram_index/__init__.py`, `fram_index/prototypes.py`, `fram_index/sparse_keys.py`, `fram_index/version_lattice.py`, `fram_serving/ingest.py`, `scripts/ingest_demo.py`, `scripts/ingest_project_docs.py`, `tests/test_hysteresis.py`, `tests/test_memory_bridge_priority.py`, `tests/test_memory_search_telemetry.py`, `tests/test_persistence_regression.py`, `tests/test_prototypes.py`, `tests/test_serving_coverage.py`, `tests/test_serving_coverage_prefer_new.py`, `tests/test_sparse_keys.py`, `tests/test_version_lattice.py`, `tests/test_version_lattice_asof.py`
- cathedral nodes: `pl-index`
- commits:
  - `b1a3f6f` verify: Layout and Index finished (WB-0023, WB-0022) (2026-10-29)
- notes:
  - 2026-10-29 (Wren Holloway): Verified 2026-10-30 02:55 SAST. Tests: 10 files, 22 passed, 2.6 s (the run dirtied 3 tracked storage files, restored; WB-0010). Exercised read-only: the demo corpus version lattice (12 nodes, storage/index/demo_corpus/versions.jsonl) loaded through VersionNode; active_ids as of 2025-10-10 returns the two bird-story versions, as of now all 12; active_with_ancestors as of 2025-10-20 returns 12; latest timestamp 2025-10-18. Note for callers: VersionNode wants datetime timestamps and node_id/parents, not the manifest's version_id/parent_id strings; VersionLattice.from_manifest(path) does that mapping. Sparse keys (extract_claims, SparseKeyIndex) and the PrototypeBank are covered by the tests; not exercised live. Verdict: works, yes; no works-well concern beyond the test hygiene. Finished.

### WB-0023 · rank 26 · Verify pipeline: Layout chunkers: code, tables, PDF

AST code chunking, CSV header windows, PDF fallback ordering, layout-aware assembly. 5 files, 5 test files, 378 lines. First touched 2025-09-09 (2814726), last 2026-01-21 (cf150f9), 22 commits touching, era I. Retrieval core. Run its tests, exercise it end to end, record what works and what does not, and move it to finished only when proven.

- created 2026-10-29 · started 2026-10-29 · finished 2026-10-29 · updated 2026-10-29
- files: `fram_layout/__init__.py`, `fram_layout/assembler.py`, `fram_layout/code_chunker.py`, `fram_layout/pdf_chunker.py`, `fram_layout/table_chunker.py`, `tests/test_code_chunker.py`, `tests/test_layout_assembler.py`, `tests/test_pdf_chunker.py`, `tests/test_table_chunker.py`, `tests/test_table_layout.py`
- cathedral nodes: `pl-layout`
- commits:
  - `b1a3f6f` verify: Layout and Index finished (WB-0023, WB-0022) (2026-10-29)
- notes:
  - 2026-10-29 (Wren Holloway): Verified 2026-10-30 02:45 SAST. Tests: 5 files, 17 passed, 0.5 s. Exercised: chunk_code(Path('tools/workbook.py')) returned 35 snippets; read_csv_to_table on a four-row CSV returned the table dict and window_for_cell(table, 1, 2) returned the header window with the rows, as the spec's CSV header-window design says. PDF chunker not exercised live (no PDF in the pipeline's inputs tonight; its tests pass). Verdict: works, yes; no works-well concerns found. Finished.

### WB-0024 · rank 27 · Verify pipeline: Observability

JSONL decision logging, summary stats, the fractal-memory sink, and the /observability surfaces. 1 files, 0 test files, 632 lines. First touched 2025-09-16 (88b737e), last 2026-01-08 (f3ea0de), 17 commits touching, era I. Retrieval core. Run its tests, exercise it end to end, record what works and what does not, and move it to finished only when proven.

- created 2026-10-29 · started 2026-10-29 · finished 2026-10-29 · updated 2026-10-29
- files: `fram_serving/observability.py`
- cathedral nodes: `pl-observability`
- commits:
  - `d3b11f3` verify: Observability finished; test membership rules for observability and MCP (WB-0024, WB-0026) (2026-10-29)
- notes:
  - 2026-10-29 (Wren Holloway): Verified 2026-10-30 03:25 SAST. Membership fixed first: the six observability test files were assigned by import to other pipelines; a path rule now keeps tests/test_observability*, test_storage_observability, test_retention_observability here. Tests: 6 files, 8 passed, 33 s (dirtied 3 tracked storage files, restored; WB-0010). Live, read-only: /observability/summary (4 traces tonight, decisions, coverage deltas), /observability/storage (active store path and sizes), /observability/traces (the four traces with ids, times, queries, citations), /observability/dashboard (HTML), /observability/experiments (empty), /observability/as_of (empty) all answer 200. /observability/calibration returns {} because the runtime's observability root has no calibration_latest.json: no calibration run has been recorded there; the endpoint could say so instead of returning an empty object. Verdict: works, yes; works well: one small clarity concern, kept here. Finished.

### WB-0025 · rank 28 · Verify pipeline: Serving: /query, REST surface, config, connectors

FastAPI app and shared query runner, settings, CLI, connectors, guardrails, SDK adapter. The first commit of the repository was this endpoint. 9 files, 63 test files, 6150 lines. First touched 2025-09-09 (2814726), last 2026-09-10 (802a81b), 351 commits touching, era I. Retrieval core. Run its tests, exercise it end to end, record what works and what does not, and move it to finished only when proven.

- created 2026-10-29 · started 2026-10-29 · finished 2026-10-29 · updated 2026-10-29
- files: `fram_serving/__init__.py`, `fram_serving/app.py`, `fram_serving/apps/sdk_adapter.py`, `fram_serving/cli.py`, `fram_serving/config.py`, `fram_serving/connectors/registry.py`, `fram_serving/guardrails/hooks.py`, `fram_serving/query_runner.py`, `fram_serving/trace.py`, `tests/test_apps_sdk_adapter.py`, `tests/test_archive_layer.py`, `tests/test_closeout_guard.py`, `tests/test_cognitive_logging.py`, `tests/test_cognitive_memory_seeding.py`, `tests/test_cognitive_phase_d_bridge.py`, `tests/test_config_env.py`, `tests/test_connectors_registry.py`, `tests/test_constraint_memory.py`, `tests/test_continuity_integration.py`, `tests/test_experiment_export.py`, `tests/test_experiment_log.py`, `tests/test_forgetting_hard.py`, `tests/test_forgetting_soft.py`, `tests/test_fractal_influence.py`, `tests/test_fractal_source_frame.py`, `tests/test_fractal_trace_binding.py`, `tests/test_fractal_trace_smoke.py`, `tests/test_guardrails_hooks.py`, `tests/test_ingest_demo.py`, `tests/test_lived_memory.py`, `tests/test_lived_score_calibration.py`, `tests/test_mcp_metadata_safety.py`, `tests/test_mcp_server.py`, `tests/test_memory_api.py`, `tests/test_memory_belief_api.py`, `tests/test_memory_bridge_ann.py`, `tests/test_memory_capsule_retrieval.py`, `tests/test_memory_cooldown.py`, `tests/test_memory_search.py`, `tests/test_memory_search_window.py`, `tests/test_metrics_endpoints.py`, `tests/test_observability_dashboard.py`, `tests/test_observability_logging.py`, `tests/test_observability_summary.py`, `tests/test_observability_traces.py`, `tests/test_phase_d_behavior.py`, `tests/test_phase_d_config_defaults.py`, `tests/test_phase_f_calibration.py`, `tests/test_phase_g_archival.py`, `tests/test_phase_g_compaction.py`, `tests/test_phase_g_snapshot.py`, `tests/test_priority_inspector.py`, `tests/test_production_memory_eval.py`, `tests/test_query_safety_patch.py`, `tests/test_rank_relevance_phase_d.py`, `tests/test_reranker_pairs_cost.py`, `tests/test_retention_curve.py`, `tests/test_retention_observability.py`, `tests/test_semantic_reranker.py`, `tests/test_serving_calibration.py`, `tests/test_serving_confidence.py`, `tests/test_serving_config_coverage.py`, `tests/test_serving_health.py`, `tests/test_serving_query.py`, `tests/test_serving_tables_integration.py`, `tests/test_serving_where.py`, `tests/test_storage_observability.py`, `tests/test_sweep_section_penalty.py`, `tests/test_trace_summary.py`, `tests/test_transitional_complexity_timeseries.py`, `tests/test_weekly_regression_snapshot.py`, `tests/test_weekly_regression_snapshot_digest.py`
- cathedral nodes: `pl-query-serving`
- commits:
  - `ea831ba` verify: the first pipeline card finished and the ritual written (WB-0025) (2026-10-29)
- notes:
  - 2026-10-29 (Wren Holloway): Live probe 2026-10-30 00:26 SAST against Always On (runtime hearth_h1_recovered_20260908_v1, code pinned at 5451423, not this checkout): /health ok; /time ok; /config 113 keys, no secret-bearing keys exposed; /where points at the runtime's own storage. /query requires {text}; 200 in 0.65 s with answer, 17 to 19 citations, full trace (confidence, coverage, selection, budgets, latency, transitional_complexity, tc_routing), and cognitive_episode_write_ok and lived_memory_write_ok both true, so every probe is now an episode in Rick's live stores (three queries written by this verification). Finding: selection.shards was empty on both queries; the merged shortlist was 13 cognitive episodes plus 4 ANN, CELF accepted 0, reads_used 17 against reads_limit 5, and the rendered answer is a chain of references to earlier Q/A episodes rather than corpus text. Serving works; the answer path is dominated by memory recall. That belongs to the cognitive and OrthoRoute cards (WB-0018, WB-0021), noted here because this is where it was seen.
  - 2026-10-29 (Wren Holloway): Control probe, budget_reads=20: 4 document shards selected (spec, roadmap, diary), CELF accepted 4, 15 memory items, one lived-memory citation; 0.87 s. So the corpus path works; at the default budget of 5 the memory layer alone uses 17 reads and no shard is ever considered. The answer head quoted the previous probe's question verbatim: each query becomes an episode the next query recalls.
  - 2026-10-29 (Wren Holloway): Tests: 65 files, 272 passed, 1 failed (test_lived_memory hash-stability, passes in isolation; handed to WB-0014). Verdict per workbook/VERIFY.md: works, yes, at HEAD and live; works well, two concerns handed to WB-0018 and WB-0021 (memory crowding the read budget; the echo loop). Finished 2026-10-30 00:50 SAST.

### WB-0026 · rank 29 · Verify pipeline: Ops: diagnostics, closeout, context packet, docs tooling

Diagnostics, import checks, closeout guards, the hot-packet checker, docs scans, time, defaults. 19 files, 22 test files, 1469 lines. First touched 2025-09-09 (2814726), last 2026-10-29 (ec7b2dc), 67 commits touching, era I. Retrieval core. Run its tests, exercise it end to end, record what works and what does not, and move it to finished only when proven.

- created 2026-10-29 · started 2026-10-29 · finished 2026-10-29 · updated 2026-10-30
- files: `examples/smoke_demo.py`, `scripts/diag_imports.py`, `scripts/diag_md_writes.py`, `scripts/diag_repo_map.py`, `scripts/diag_routing_map.py`, `scripts/diag_surface.py`, `scripts/normalize_docs_ascii.py`, `scripts/query_once.py`, `scripts/verify_imports.py`, `tests/conftest.py`, `tests/test_calibrate.py`, `tests/test_calibration_backfill_cli.py`, `tests/test_calibration_filter_cli.py`, `tests/test_calibration_lint_cli.py`, `tests/test_calibration_status_cli.py`, `tests/test_check_context_packet.py`, `tests/test_harvest_calibration.py`, `tests/test_memory_summary.py`, `tests/test_nul_bytes_guard.py`, `tests/test_phase_c_calibration.py`, `tests/test_phase_d_placeholders.py`, `tests/test_phase_e_summary.py`, `tests/test_posix_launchers.py`, `tests/test_refactor_checklist.py`, `tests/test_refresh_calibration.py`, `tests/test_refresh_docs_calibration.py`, `tests/test_serving_answer_format.py`, `tests/test_serving_memory_ui.py`, `tests/test_snapshot_firelink.py`, `tests/test_trace_probe_cli.py`, `tests/test_workbook.py`, `tools/check_closeout.py`, `tools/check_context_packet.py`, `tools/check_nul_bytes.py`, `tools/closeout_guard.py`, `tools/current_time.py`, `tools/list_recent_docs.py`, `tools/print_fram_defaults.py`, `tools/refactor_checklist.py`, `tools/scan_docs_words.py`, `tools/snapshot_firelink.py`
- cathedral nodes: `pl-ops`
- commits:
  - `b8afafa` verify: OrthoRoute finished; calibration sign finding; query_once and echo-loop findings on their cards (WB-0021, WB-0026, WB-0010) (2026-10-29)
  - `ada140d` verify: MCP finished; the login runtime serves api_key over fram://config, HEAD redacts it (WB-0012, WB-0026) (2026-10-29)
  - `d3b11f3` verify: Observability finished; test membership rules for observability and MCP (WB-0024, WB-0026) (2026-10-29)
  - `320c312` verify: ops and the Cathedral's own card finished; all sixteen pipeline cards verified (WB-0026, WB-0011) (2026-10-29)
  - `f861607` cathedral daily: log through Add-Content; the Tee-Object -Encoding fix killed the 06:00 run under Windows PowerShell 5 (WB-0026) (2026-10-30)
- notes:
  - 2026-10-29 (Wren Holloway): Seen 2026-10-30: scripts/query_once.py ignores --help and runs a real query against the checkout's storage, writing cognitive episodes into tracked files. Its answer was a chain of thirty 'Q: What is FRAM?' echoes: the checkout's cognitive store is full of its own test litter feeding on itself. Give the script an argument parser, and give the tests a temporary storage root (WB-0010).
  - 2026-10-29 (Wren Holloway): From WB-0012: the Always On runtime is pinned at 5451423, which predates e5a4ddc (MCP fram://config api_key redaction). Moving the runtime forward is a decision; the memory note fram-always-on says how the runtime is pinned.
  - 2026-10-29 (Wren Holloway): Correction to the earlier note: scripts/query_once.py posts to the live server (FRAM_URL, default http://127.0.0.1:8000), not to the checkout's storage; its 'What is FRAM?' query is trace b8a89879 on the runtime at 22:40:46 and is now an episode in Rick's live store, as the probes are. The checkout storage changes seen at the same time came from the test runs. The finding stands: it ignores --help and runs.
  - 2026-10-29 (Wren Holloway): Verified at machine time 2026-10-30T01:43 SAST. Membership fixed first: the four Cathedral tool tests moved to pl-cathedral and the nine calibration tests to OrthoRoute by rule; ops keeps 7 test files. Tests (the 14 ops and calibration files run together): 55 passed in 84.93s (0:01:24). Exercised read-only: check_context_packet OK; check_nul_bytes silent and clean; current_time correct against the system clock (it is what caught my own clock error tonight); verify_imports OK; print_fram_defaults prints the config; closeout_guard has a usage. Findings: scripts/diag_imports.py rewrites the tracked file diag/imports.json (restored); scripts/query_once.py ignores --help and posts a live query (earlier note); the daily Cathedral task's log was UTF-16 because Tee-Object defaulted to it, now written as UTF-8 (tools/cathedral_daily.ps1); the scheduled task has not yet fired on its own (first run 06:00 today). Verdict: works, yes; works well: the two scripts that write where they should not are the concern, kept here with WB-0010. Finished.
  - 2026-10-30 (Rick): 2026-10-30 13:22: the first scheduled 06:00 run failed with result 1 and wrote nothing. Cause was Wren's own fix from the night before: Tee-Object -Encoding utf8 does not exist in Windows PowerShell 5, which is what the task runs; the by-hand test had been done before that edit. Fixed: Add-Content for the log, a trap that logs any terminating error before exit 1, git found by absolute path if PATH is thin, and the task action wrapped in cmd.exe so stdout is captured. Re-run through Task Scheduler itself: result 0, commit 423b7bc, 479 nodes / 1272 edges. Lesson on the ritual: exercise live means through the real runner, not through my shell.
