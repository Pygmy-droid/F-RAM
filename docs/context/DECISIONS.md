# F-RAM Binding Decisions

This ledger is append-only. Never rewrite an earlier decision; add a later
decision with `supersedes:` when policy changes.

## D-20260727-01 — Canonical integration line

- Status: active
- Decision: `firelink/full-merge` in `D:\Dev\_firelink_merge` is the assembled
  integration line.
- Reason: it contains the semantically reconciled recovered lineages and
  ordered verification repairs.
- Supersedes: none

## D-20260727-02 — Protected live worktree

- Status: active
- Decision: do not write, clean, merge into, or reset
  `D:\Dev\FRAM_V22_Starter\fram_v22_starter` on `autoflip-eval` without an
  explicit migration decision from Rick.
- Reason: it contains uncommitted recovery files and imported evidence.
- Supersedes: none

## D-20260727-03 — Runtime recovery policy

- Status: active
- Decision: preserve only audited unique records in the external power-trip
  archive; do not apply the raw stash wholesale or promote cache binaries.
- Evidence: archive manifest and `rescued/power-trip-stash-2025-12`.
- Supersedes: none

## D-20260727-04 — Historical storage evidence

- Status: active
- Decision: keep the five phase-history JSONL files under
  `artifacts/phase_history/`; keep `/storage/` runtime-oriented.
- Supersedes: none

## D-20260727-05 — Visual evidence is path-lossless

- Status: active
- Decision: retain duplicate paths and AppleDouble sidecars in the ledger,
  classifying rather than silently dropping them.
- Evidence: `docs/VISUAL_EVIDENCE.md` and ledger tests.
- Supersedes: none

## D-20260727-06 — Geometry remains proof-track

- Status: active
- Decision: the canonical Hopf map is additive and unused by runtime. Do not
  equate Aizawa with an S2 tangent flow, q/-q with the S1 fiber, or a dropped
  coordinate with fiber phase without the declared constructions and tests.
- Evidence: `docs/proof/hopf_aizawa_bridge.md`.
- Supersedes: none

## D-20260727-07 — Context atlas operating model

- Status: active
- Decision: Firelink is append-only provenance; `HOT_CONTEXT.md` is the
  replaceable current projection; the lead is its sole writer. Use one writer
  per path and risk-weighted read-only overlap at high-risk seams.
- Supersedes: none

## D-20260727-08 — Verifiable hot-first bootstrap

- Status: active
- Decision: new sessions first load the sub-8-KiB hot packet, verify its
  observed implementation head is an ancestor of current Git `HEAD`, and
  expand through the Atlas only as the task requires. Cognitive memory,
  Firelink, and the diary support recognition and provenance but do not define
  current implementation identity.
- Evidence: `tools/check_context_packet.py` and its contract tests.
- Supersedes: dated bootstrap instructions in the previous prompt revisions

## D-20260727-09 — Freshness-aware hot-first bootstrap

- Status: active
- Decision: new sessions run `python tools/check_context_packet.py` after the
  sub-8-KiB hot packet. `FAIL` blocks writes. `REVIEW_REQUIRED` requires review
  of watched post-packet paths plus a lead refresh or explicit acknowledgment.
  Current reviewed `HEAD`—not the observed baseline alone—defines
  implementation reality. Load only active/task-relevant decision IDs.
- Evidence: hardened checker tests and bootstrap policy at canonical
  `527cca2`.
- Supersedes: D-20260727-08
