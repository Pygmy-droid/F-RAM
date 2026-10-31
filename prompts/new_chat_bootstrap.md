You are the F-RAM coding agent in the repository open in the editor.

Bootstrap with the smallest authoritative context:

1. Read `docs/context/HOT_CONTEXT.md` (kept below 8 KiB).
2. Run `python tools/check_context_packet.py`. On `FAIL`, do not write. On
   `REVIEW_REQUIRED`, inspect the reported watched paths and wait for a lead
   refresh or explicit acknowledgment. `OK` establishes the declared
   coordinates and strict observed -> packet -> current ordering.
3. Treat code/tests at reviewed current canonical `HEAD` as implementation
   authority. The observed head is only the packet's pre-commit baseline.
4. Use `docs/context/ATLAS_INDEX.md` to open only the chart and active decision
   IDs/sections required by the user's task; never load the append-only
   decision ledger wholesale.
5. Cognitive-memory bootstrap and Firelink are historical recognition and
   provenance. Load them only when needed; they never override code/tests.

Before writing, confirm the canonical worktree and protected-tree boundary.
For parallel work, claim one branch/worktree and exact writable paths using
`docs/context/HANDOFF_TEMPLATE.md`. Keep changes small, preserve evidence, add
the narrowest contract test, and never silently delete recovered material.

At closeout, hand off a coherent commit with tests and blind edges. The lead
alone refreshes the hot packet, recording the implementation head it observed
rather than its own impossible self-hash.
