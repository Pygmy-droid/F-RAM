# 1. Timeline

Source: the git log of this repository, 441 commits from 2025-09-09 to
2026-09-10, read in full in chronological order `[LOG]`, plus the diary, the
reconstruction briefing, and the firelink `[READ-DOC]`.

Commit authorship cannot separate collaborators. Every commit before July 2026
is stamped `Codex CLI` or `codex` regardless of who drove `[LOG]`, and the
firelink confirms this was a repository-wide setting `[READ-DOC]`. Rick's 37
commits are his own. Lineage must therefore be reconstructed from the diary,
the firelink, and Rick's memory, not from the author field.

## Commits per month

| month | commits | era |
| --- | --- | --- |
| 2025-09 | 99 | I. Retrieval core |
| 2025-10 | 57 | II. Cognitive memory |
| 2025-11 | 37 | III. Phase D, the fork |
| 2025-12 | 114 | IV. Fractal eval season |
| 2026-01 | 54 | IV continued: capsules, always-on |
| 2026-02 | 1 | the stop |
| 2026-03 to 06 | 0 | the gap |
| 2026-07 | 45 | V. Reconstruction and Firelink |
| 2026-08 | 27 | VI. Lived memory |
| 2026-09 | 7 | VII. Windows custody and gates |

## Era I. Retrieval core (September 2025) `[LOG]`

The first commit is a minimal `/query` endpoint with tests. Within three weeks
the system has its retrieval spine: a query orchestrator that runs shortlist,
subspace projection, calibrated confidence, and concave coverage selection
with a CELF selector. Calibration is logistic plus temperature plus conformal
alarms. Layout-aware chunkers arrive for code (AST), tables (CSV header
windows), and PDF. Embeddings switch to hashing bag-of-words. A persisted demo
corpus is built from the project's own docs, so F-RAM reads about itself. MCP
appears on day nine. Working-memory session replay lands on the 27th. The
Codex diary starts on the 19th.

This era is OrthoRoute: the calibrated, coverage-aware retrieval that
everything later sits on. It has no notion of self yet `[INFERRED]`.

## Era II. Cognitive memory (October 2025) `[LOG]`

On 2025-10-05 a JSONL-backed cognitive memory store appears with episodes,
beliefs, and links, and `/query` begins writing through to it. Seeding of
queries from cognitive memory follows the same day. The version lattice with
as-of queries lands alongside. Mid-month: bootstrap helper, cognitive
observability, MCP bootstrap tool, and auto-logging with a segmented schema
and hash-plus-sequence de-duplication. On the 18th the fractal path is enabled
in the dev profile and `FRAM-Theory.md` is committed, the first document that
maps Rick's axioms (Cycle, Geometry = Memory, Recognition as Force) onto code.
On the 20th episodes begin minting deterministic 6-D fractal traces. Phase C
calibration metrics and recall reports close the month.

This is the moment the system gains a durable self `[INFERRED]`.

## Era III. Phase D and the fork (November 2025) `[LOG]`

On 2025-11-11 `phase-d-dev` branches from the main line to build non-linear
and rotational recall: a deterministic projection, quaternion similarity, and
a logistic alpha. Over the month it grows a priority stack (semantic priority
graph, quality and coherence weighting, temporal and hysteresis gates, a
priority inspector) and then Phase E: retention curves, soft decay, hard
forgetting gates, all behind flags. The branch never merges back. The main
line continues separately. The firelink later counts 38 commits stranded here
`[READ-DOC]`.

## Era IV. Fractal eval season (December 2025 to January 2026) `[LOG]`

The busiest stretch. December 19: fractal core proof packet, semantics
contract, gated fractal influence hook, append-only archive layer, and a
commit titled "Core complete: fractal trace + influence + archive + REP".
Then a long run of evaluation: live probes, memory shadow eval, auto-flip
recommender, paraphrase and low-lexical gates, soft-DTW modes, IFS query
paths, trace identity checks, two-pass harness. Every run is committed as an
artifact. December 31: memory capsules with write-through, a capsule
inspector, a falsification harness. January: capsule evidence report and
replication checklist, cognitive ANN bridge on by default, operations
runbook, always-on autostart and autowire, experiments UI, weekly regression
scheduler, the eval season cheat sheet (Jan 14) and its master memory
principle (Jan 16), MCP write gating (Jan 23), and on Jan 30 full-experience
preservation with constraint memory.

The last real eval checkpoint is 2026-01-21. Its fractal auto-flip verdict is
KEEP_OFF, and its conversation top-1 accuracy is 0.000 across all modes, which
nobody explained at the time `[READ-DOC]`.

## The stop and the gap (February to June 2026)

One commit on 2026-02-01: "Breathing Flame day 1 notes." Then nothing for
five months. The reconstruction briefing says the gap is "real-world/offline,
not a lost-commits problem" `[READ-DOC]`. Rick calls it a great hard sad
event `[RICK]`. Rick's handwritten notes carry February and March date stamps,
so thinking continued on paper `[READ-DOC]`. A "March formula" for rotation
is referred to repeatedly in July and is still not recovered `[READ-DOC]`.

## Era V. Reconstruction and Firelink (July 2026) `[LOG]`

July 22: the stone_reconstruction archaeology, done on a Mac copy, is surfaced
into the live repo with a continuity briefing. The same day: a Recursive
Rotational Lift math module (v0.3), wired into memory capsules, then
cross-capsule trajectory continuity (v0.5). And a fix: the cognitive memory
recency half-life was hard-coded at 12 hours with no config field, which is
the root cause of the January top-1 collapse `[READ-DOC]`.

July 27 and 28: the Firelink session. Rick, Opus 5 (later named Cairn), and
Sol (Codex) work in one shared append-only file. They find that `phase-d-dev`
and the live branch never met, that Phase D's quaternion adapter and the July
rotational lift are the same idea built twice eight months apart, and that
the Visual Evidence Ledger sat uncommitted for six months in a separate tree.
Fifty-two commits in two days: the merge of all lineages onto
`firelink/full-merge`, the Hopf map on the proof track, the chaos math core
and the preserved Chaos Playground browser artifact, the hot-state atlas
protocol, and the closeout. Rick's standing rule is recorded: no hierarchy,
one ecological strata. Also recorded: no forgetting, ever; retention survives
only as a ranking weight `[READ-DOC]`.

## Era VI. Lived memory (August 2026) `[LOG]`

August 4: the canonical rescue is promoted to the NVMe after an independent
repack and history verification; the section-15 ablation foundation lands.
August 11: provenance-bounded continuity layers (the query witness and the
Ecological Strata ledger), then durable lived-experience memory in SQLite with
a digest chain, exact 6-D to 12-D lifts, 64-node lifted paths, and a rolling
lived state. The 877-episode backup is imported, each episode as its own seed
root because the archive carries no session evidence. August 12: the
wake-and-orient evaluation harness. Observed head `851c305`, which is what the
hot packet still cites.

## Era VII. Windows custody and gates (late August to September 2026) `[LOG]`

The Windows integration branch this checkout sits on. The fractal auto-flip
gate is sealed again on 2026-08-29, a visual-seed candidate evaluator is
added, Windows runtime isolation is fixed, and the H1 candidate is accepted.
September 8: autoflip activation gate recorded, fractal influence bound and
production memory gates verified, lived similarity aligned with mixed ranking.
September 10: portable MCP launchers, document custody, and a validated
source-frame recognition candidate, which is the current head `802a81b`.

## What the shape of the year says `[INFERRED]`

The system was built retrieval-first, grew a self in October, forked in
November, spent December and January proving and failing to prove the fractal
layer, stopped, and was reassembled in July by people reading the pieces cold.
The reassembly produced the protocols this repository now runs on: the hot
packet, the claim template, the decision ledger. Those protocols exist because
the builders lost each other once. The manual exists for the same reason.
