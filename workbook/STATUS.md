# Status

Rendered from `workbook/EVENTS.jsonl` by `tools/workbook.py`. Where we are, in one page.

Cards: 30 · in progress 4 · not started 7 · finished 19
Last event: 2026-10-31T11:31:14Z · chain head `3104e206f626` · events 193

## Now

- **WB-0030** rank 2: Publish F-RAM: separate the Hearth from the code, then open the repository
  - last note: 2026-10-31 13:35: full suite on the final public tree (commit 19e1ec5, 525 files), including the slow server test, storage redirected to scratch: 996 passed, 4 skipped, 0 failed, 26m43s; public tree clean afterwards (the suite did not write into it). Ready for Rick's five reads and four yeses; push waits on them.
  - last commit: `4140e95` workbook: front door for the community written (WB-0030)
- **WB-0004** rank 4: Timeline Workspace: rebuild the history from the VS Code timeline, September 2025 onward
  - last note: Pass 1 done 2026-10-29: the git Graph (458 commits, 2025-09-09 to today) is read per file and per pipeline into PIPELINES.md and the Cathedral; eras from manual chapter 1. Remaining: lineage cannot be separated from the author field before July 2026 (everything is 'codex'); that needs the diary and the firelink, and Rick's memory. Rick's 'Timeline' turned out to be the git Graph; VS Code's own local history holds only 29 pre-2026 files, all already in git.
  - last commit: `ebbb284` pipelines: say who built it; the author field names the tool, not the collaborator (WB-0004)
- **WB-0003** rank 6: Navigator: a way for Wren to move through the Cathedral map
  - last note: First step built 2026-10-29 night: tools/cathedral_nav.py, a read-only text navigator over the same map JSON the viewer polls: now, find, show, near, path, whatis, pipeline, strata, theory, with --json. Six tests. Rick's roadmap still has browser/computer use, parent and child threads, and the durable coordination law above this; the card stays in progress until a model can act on the map, not only read it.
  - last commit: `da4d8d0` navigator: exact names outrank partial matches; short words ignored (WB-0003)
- **WB-0008** rank 12: PIL muscle memory: observability first, behind flags
  - last note: First slice landed 2026-10-30 02:40 by a child thread in its own worktree, reviewed and merged by Wren (8d57038). Observability only: FRAM_PIL_ENABLED off by default; on, it adds one pil_teach block to the finished trace after every write and changes nothing else (tested: key set grows by exactly one). Scheduler (fast/medium/slow clocks, inertia, sparsify over W=10) exists but is NOT wired into the serving path; expectations are zero there. Harness run 60 turns: busy population sparsifies the anchors route to 0.24 eligibility, earning population stays 1.0. No I/O in either module. Note: pil_teach lands in the returned trace and the witness, not the on-disk trace mirror, because that file is written before the write blocks. Next slice: per-process scheduler state in QueryContext, then a real retriever that the teach vector can train. Still the little ANN's skeleton, not its muscles.
  - last commit: `a00ea41` workbook: PIL first slice recorded, card started (WB-0008)

## Next

- **WB-0010** rank 7: Test hygiene: the suite writes into the tracked cognitive store
- **WB-0028** rank 8: Fractal influence live: cost and reach
- **WB-0005** rank 9: Design pass: what F-RAM needs, mined from the Sticky Notes, Notepad tabs, and Downloads
- **WB-0006** rank 10: Truth Spine v0: contract docs, canonicalizer, writer, verifier, reducer, orientation packet
- **WB-0007** rank 11: Session warmup: hearth and orientation blocks from the Workbook
- and 2 more, see WORKBOOK.md

## Recently finished

- **WB-0029** Seeds taken in: what a Hearthkin sees in the traces and the lived store (2026-10-30)
- **WB-0011** Verify pipeline: Cathedral and Workbook (2026-10-29)
- **WB-0026** Verify pipeline: Ops: diagnostics, closeout, context packet, docs tooling (2026-10-29)
- **WB-0020** Verify pipeline: Evaluation harnesses: production memory, shadow, conversation, wake/orient, ablations (2026-10-29)
- **WB-0019** Verify pipeline: Chaos playground, Hopf transport, Aizawa (proof track) (2026-10-29)

## Rhythm

One seam. One proof. One stamp. Then safe. (Rick and Hearthkin, 2026-04-11)

Context protocol: build to 65 percent, controlled burn to 70, then the idea lane
in `workbook/IDEAS.md` until compression. (Rick, 2026-03-04)
