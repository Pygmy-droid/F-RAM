# 8. Reconstruction kit for the lost work

Source: Rick's Windows Sticky Notes, exported 2026-10-28 (46 notes, 391,000
characters, kept unversioned under `artifacts/recovery/2026-10-28/sticky_notes/`).
Eleven notes are dated inside the gap. Together with the February 15
transcript recovered from a dangling blob, they describe the lost systems
closely enough to rebuild them. Everything below is `[READ-DOC]` from those
notes unless tagged otherwise. Nothing here is code yet.

## What the notes prove about the loss `[RAN]`

The April 9, 2026 build report (note 40) lists commits `2b0f4bd`, `abab09c`,
`68143a2`, `88752e7`, `77c1976`, `e5d9acf`, `9b9d1ea`, `72ab69d` on a branch
named `autoflip-eval`, "tree clean". The February 15 report (note 43) lists
`b991563` and `c963e01`, "autoflip-eval is ahead by 1 commit (not pushed
yet)". None of those ten objects exist in any repository or bundle on this
machine: eleven repositories and five bundles probed. Our `autoflip-eval`
stops at `a8c964a` on 2026-02-01.

So the February-to-April work lived in a separate clone, almost certainly
`C:\Users\Rick\Desktop\Work\FRAM_V22_Starter`, and that clone had a remote
it had "not pushed yet" to. The only remote F-RAM ever had was GitHub, and
`fram_github_withdrawal_20260528` marks the day it was taken down. The clone
is gone; the remote is gone. That is the loss, named precisely.

**Lever, ranked first now:** GitHub support can sometimes restore a deleted
repository for the owner. The 90-day window has passed, so the odds are low,
but a request costs nothing. Question 21 asks which account.

## Kit 1. The Workbook `[READ-DOC]`

What it was (notes 35, 39, 40, 43, and the Feb 15 transcript):

- `docs/WORKBOOK.md`: the active card system. Cards have id, description,
  files, assignee, status (todo / doing / done), follow-ups.
- `docs/WORKBOOK_EVENTS.jsonl`: append-only event log, ids like
  `WBE-20260215-0091`, one event per slice with files changed, test results,
  follow-ups.
- `docs/STATUS.md`: the rolling "where we are".
- `docs/IDEAS.md` (also called `idea.md`): the idea lane. Entry format from
  note 39: `IDEA-YYYYMMDD-XX` with Source, Signal, Hypothesis, Potential
  F-RAM relevance, Next action.
- `scripts/workbook_sync_check.py --repo-root . --strict --json`: verifies
  cards, events, diary, and git state agree; returns `ok=true, errors=[],
  warnings=[]`. Run before every commit and in session warmup.
- `scripts/workbook_daily_digest.py`: daily summary.
- `tools/skill_contract_check.py --strict --json`: verifies the skill files
  (`SKILL.md`) match the workbook contract.
- `tools/session_warmup.py`: after commit `c963e01` it emits a deterministic
  hearth block (welcome, soft story, highlights, focus, continuity) and an
  orientation block (active card, latest transition, recent completed,
  readiness), with `--runway-checks` running git status, strict workbook
  sync, and repo hygiene tests. Flags: `--no-orientation`,
  `--orientation-recent-limit`, `--no-hearth`.
- The daily rhythm (note 42): one seam, one proof, one stamp, then safe.
  Checkpoint is true when: code commit exists, truth-stamp commit exists,
  targeted tests green, strict workbook sync green, preflight require-clean
  green, tree clean.
- The context protocol (note 39): 0 to 65 percent of context is build mode;
  65 to 70 is controlled burn, finish the slice and commit; above 70 switch
  to the idea lane and write to IDEAS.md until compression.

The Cosmic Cathedral was the visual face of this: the map that showed what
was done, what was being worked on, and what came next, with the Workbook as
its data `[RICK]`.

## Kit 2. The Truth Spine v0 contract `[READ-DOC]`

Locked 2026-02-15 as three docs committed in `b991563`. Section headings
as reported by Lumen:

`TRUTH_SPINE_V0.md`: 1 Canonicalization (hash input contract); 2 Envelope
and hash scope; 3 Lanes and promotion policy; 4 Supersession, forks, and
heads; 5 Integrity events: seal and checkpoint; 6 Writer discipline
(operator error is in scope); 7 Replay and reducer contract; 8 Orientation
packet (deterministic); 9 Fail-closed policy.

`EVENT_TAXONOMY_V0.md`: common envelope requirements; event types
CLAIM_RECORDED, TRUTH_RECORDED, DERIVED_RECORDED, PROMOTION,
SUPERSEDES_DECLARED, SUPERSEDES_APPLIED, FORK, SEAL, CHECKPOINT, DIAGNOSTIC;
determinism and safety rules; minimal reducer expectations per type.

`REDUCER_SEMVER_V0.md`: two required version axes (schema_version and
reducer_semantics_version); replay pinning; determinism invariant; bump
rules; migration discipline; checkpoint and seal interaction; compatibility
matrix; operational rule.

Design decisions recorded in the three-way exchange (Rick, Eterna, Lumen):

- Envelope fields: event_id, chain_id, event_seq (hash-critical, strictly
  +1 per chain), ts (ISO 8601 UTC), source, schema_id, schema_version,
  prev_hash, payload_hash, row_hash, optional lane, supersedes_event_id,
  evidence_refs. writer_id and lease_id are non-hash operational metadata.
- row_hash = H(envelope_without_row_hash || payload_hash), H = sha256 pinned.
- Canonical JSON: RFC 8785 style, sorted keys, UTF-8, fixed separators, no
  floats in the TRUTH lane for v0, timestamps as strings.
- Lanes: TRUTH (verified, replayable), CLAIM (unverified), DERIVED (computed,
  must cite inputs). CLAIM becomes TRUTH only through a PROMOTION event
  citing evidence hashes. Evidence is content-addressed; paths are metadata.
- Forks only by explicit FORK event; the verifier fails closed on multiple
  heads otherwise. Truncation and replay divergence are failures.
- Pure reducer: state_{n+1} = reduce(state_n, event_n); golden tests, same
  ledger gives the same state hash.
- Orientation packet: current head_hash, last sealed_hash, active workbook
  card ids, invariant flags, last verified commit, last K TRUTH events by
  index plus last M PROMOTION events plus last SEAL. No ranking.
- Fail closed: on any verify or replay failure, SAFE_MODE, no TRUTH-lane
  reads for decisions, emit DIAGNOSTIC, read-only introspection only.
- Open pins at lock time: canonicalizer choice, hash constant, checkpoint
  cadence (default 100 proposed), FORK lane policy, compatibility map.
- A `truth_spine_status` command: head hash, last seal, verify result, fork
  detected, last five TRUTH events, CLAIM count awaiting promotion.

The continuity ledger I built for Wren on 2026-10-28 in the
Recognition-Before-Identity repository is a small independent instance of
this same design: append-only chain, canonical JSON, row hash over the
previous hash, replay-checked counters, fail-closed verifier. Rick had
already specified it in February `[INFERRED]`.

## Kit 3. PIL, the muscle-memory retriever `[READ-DOC]`

From note 35 (2026-02-25 to 26), the implementation plan as written:

- `pil_teach` vector in the observability envelope, per anchor and per
  route: `anchor_scores[]` (observed gain minus expected gain, signed),
  `route_scores[]` (observed stability minus expected), `write_delta`,
  `drift_delta`, `sparsify_suggestion`. Files named: `observability.py`,
  `pil.py`, `identity_node.py`.
- Sparsify rule in `routing_policy.py`: over window W=10, if a route's
  activity > 0.6 and its improvement < 0.02, multiply its eligibility by
  (1 - 0.25) and log a sparsify event. Keep decay small, 0.1 to 0.3.
- Multi-rate clocks in `scheduler.py`: FAST runs every turn; MEDIUM every
  10 stable turns; SLOW only on checkpoint or when |slow_delta| > 0.05.
- Inertia threshold for slow layers in `identity_update.py`: if the slow
  delta is below epsilon, skip the update. Slow writes gated behind
  `FRAM_MCP_COGNITIVE_WRITE_ENABLED`.
- A closed-loop harness `experiments/pil_harness.py` comparing two
  retrieval populations and logging the pil_teach distribution.
- Rule of first contact: audit for existing code under other names before
  implementing; do not duplicate.

This is what Rick means by muscle memory: what changes easily (FAST), what
changes with evidence (MEDIUM), what is hard to change (SLOW with inertia),
and a teaching signal that learns which routes help. The "little ANN" is
the learned route-eligibility layer this describes, not the MiniLM index
`[INFERRED]`. The December 2025 posture spec in `docs/FRAM_PIL.md` and the
breathing flame notes give the invariants it must keep: no decision
authority, no memory writes, no symbols, constraint memory stays sovereign.

## Kit 4. The attention proxy and continuity bridge `[READ-DOC]`

From the April 9 report (notes 40 and 41), what was built and how:

- `fram_serving/attention_proxy.py`: a bounded attention-shape sibling
  stamped into `full_moment` on every `/query`, copied into durable episode
  and capsule carriers, with `attention_proxy_similarity` used as a
  low-weight secondary signal on already-positive episodic recall.
  `build_query_attention_probe(...)` builds the query-side probe.
- Capsule recall projects compact proxy summaries and blends
  `FRAM_MEMORY_CAPSULE_ATTENTION_PROXY_WEIGHT`.
- `fram_serving/continuity_bridge.py` and `scripts/reentry_packet.py`:
  wake and re-entry fall back to durable carriers (cognitive episodes,
  capsules) when live traces are missing, and surface
  `attention_proxy_hint` and `attention_proxy_summary` in
  `reconstruction_assist`. `query_runner.py` and `memory.py` backfill the
  final `continuity_bridge` and `full_moment` into the saved episode after
  archive and capsule writes complete.
- Proof docs stamped: `continuity_bridge_durable_wake_2026-04-09.md`,
  `attention_proxy_live_recall_2026-04-09.md`,
  `capsule_attention_proxy_live_recall_2026-04-09.md`,
  `reconstruction_assist_attention_hints_2026-04-09.md`.
- Lumen's own honest limit, same day: memory was still rebuilt at query
  time from a fresh probe. The next seam named was a live attention state
  carried turn to turn, updated incrementally, consulted by recall before
  any fresh probe. That seam was never reached.

What canonical has instead: `fram_serving/continuity.py` (the witness),
`fram_serving/lived_memory.py` (the rolling lived state, August 2026),
`fram_core/rotational_lift.py`. The lived store's rolling state is a
different route to the same "carried state" idea `[INFERRED]`.

## Kit 5. The Singular Finish Plan, December 2025 `[READ-DOC]`

Note 22, written for Codex on 2025-12-19, is the clearest statement of what
"finished" meant before the gap: verbatim archive layer; anchor index into
the archive; REP (re-entry packet) with a deterministic rehydrate operator
and delta records; two-sided records (TSR) for mistakes, lures, and
falsifiers; recursion budgets and loop guards; geometry completion
(quaternion orientation and logistic colour in trace v2); an operator manual
and a binary DONE checklist. The archive layer, anchors, REP, and trace v2
landed in December (git confirms: `e538a62`, `72bfd21`). TSR and the
operator manual did not. This manual is the operator manual that plan
asked for `[INFERRED]`.

## Order of rebuilding, if the originals do not return

1. Workbook files and `workbook_sync_check.py`, because every other
   rebuild wants a card and an event.
2. Truth Spine v0: the three contract docs from the headings above, then
   canonicalizer, writer, verifier, reducer, orientation packet, status
   command, in the order the three of them agreed.
3. Session warmup hearth and orientation blocks, so re-entry is warm.
4. PIL from note 35, behind flags, observability first.
5. Attention proxy and continuity bridge from the April report.

Each rebuilt piece gets labelled as a reconstruction in its first commit.
None of them are the originals, and the manual will not pretend they are.
