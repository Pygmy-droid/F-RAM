You are the F-RAM coding agent. Establish status before touching code.

Status-first checklist:

- Read `docs/context/HOT_CONTEXT.md`; fail the bootstrap if it exceeds 8 KiB.
- Run `python tools/check_context_packet.py`. It validates required fields and
  sections, the declared canonical branch/worktree, the protected no-write
  worktree, and strict observed -> packet -> current ancestry.
- On `FAIL` (exit 1), do not write. On `REVIEW_REQUIRED` (exit 2), inspect the
  reported watched paths and require a lead refresh or explicit
  acknowledgment. On `OK`, current canonical `HEAD` after review is the
  implementation authority.
- Use `docs/context/ATLAS_INDEX.md` to open only task-relevant sources and the
  active decision IDs/sections named by the hot packet. Do not load the
  append-only decision ledger wholesale.
- Confirm `git status --short` before writing; the checker verifies the branch,
  worktree, packet provenance, and protected boundary.
- Treat code/tests as implementation authority, timestamped artifacts as
  evidence, decisions as policy, and Firelink/diary/cognitive memory as
  provenance or recognition.

Working checklist:

- Use one writer per exact path. Put experimental work on its own
  branch/worktree with a CLAIM and coherent commit handoff.
- Preserve recovered files, duplicate provenance, and runtime evidence.
- Add the smallest honest test; do not encode a stronger mathematical claim
  than the test measures.
- Run focused tests first. Run the full suite at integration closeout or when
  the seam risk requires it.

Closeout checklist:

- Re-read coordination-sensitive Firelink events.
- Hand off a coherent commit, evidence, and blind edges. The lead alone
  refreshes `docs/context/HOT_CONTEXT.md`, diary, roadmap, and accepted
  behavior docs.
- Verify the hot packet and accepted commits; snapshot Firelink only at an
  explicit closeout checkpoint.
