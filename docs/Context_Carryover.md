# Carrying F-RAM Context Across Agents

No agent should load the whole repository, chronology, and collaboration log
into one context window. Use three layers with different update rules.

## 1. Hot current state

Start with `docs/context/HOT_CONTEXT.md`. It stays below 8 KiB and contains only:

- canonical branch, commit, and worktree;
- protected surfaces;
- current mission and binding invariants;
- active claims and exact write surfaces;
- next gates and known blind edges; and
- pointers to the smallest cold sources that can answer deeper questions.

The lead is the sole writer. Refresh it when the canonical HEAD changes, a
claim opens or closes, a failure changes a gate, or user direction changes.

The packet records the implementation head it observed, not its own final
commit hash (a tracked file cannot contain its own content-addressed Git hash).
At bootstrap, verify rather than trust:

```powershell
python tools/check_context_packet.py
git status --short
```

The checker enforces required safety fields/sections, verifies the declared
canonical branch/worktree and protected no-write worktree, and proves strict
`observed head -> packet commit -> current canonical HEAD` ancestry.

- `OK` (exit 0): the packet is structurally valid and no watched path changed
  after its commit.
- `FAIL` (exit 1): schema, coordinates, provenance, or ancestry are invalid.
- `REVIEW_REQUIRED` (exit 2): the packet is structurally valid, but watched
  paths changed after its commit. Do not write until the lead refreshes the
  packet or explicitly acknowledges the reviewed range.

Watched paths are documented in `tools/check_context_packet.py` and cover the
runtime/source/test/tool/script/experiment trees; dependency and build files;
the bootstrap/context/policy surfaces; proof docs; and current
roadmap/diary/architecture summaries. Cold files outside that set may land
without forcing a packet refresh.

Current canonical `HEAD`, after ancestry verification and review of intervening
commits, defines implementation reality. The observed head is the packet's
pre-commit baseline, not the final authority.

## 2. Indexed cold context

Use `docs/context/ATLAS_INDEX.md` to route a question to code/tests, evaluation
artifacts, binding decisions, summaries, theory, or history. Read only what the
question requires.

Implementation identity comes from code and tests at reviewed current canonical
`HEAD`. Historical recognition is valuable evidence but cannot silently
outrank current implementation.

`docs/context/DECISIONS.md` is append-only and therefore intentionally
unbounded. The hot packet projects active decision IDs; open only those
sections, their supersession chain, or task-relevant decisions routed by the
Atlas. Never load the full ledger as a mandatory bootstrap step, and never
rewrite old reasoning.

## 3. Append-only provenance

Firelink, the diary, reconstruction maps, and archived evidence preserve the
path by which the project changed. Firelink is a wear log, not the hot bootstrap
packet. Consume only events newer than the hash/line anchor in `HOT_CONTEXT.md`
unless a question requires older history.

At closeout or before rotating Firelink, store an immutable copy and manifest
under:

```text
artifacts/firelink/<YYYY-MM-DD>/<HHMM>-<canonical-shortsha>/
```

The manifest records source path, SHA-256, byte and line counts, canonical HEAD,
and last event. Create it with:

```powershell
python tools/snapshot_firelink.py C:\Users\Rick\Desktop\firelink.md
```

The command refuses to overwrite an existing checkpoint.

## Claims and handoffs

Use `docs/context/HANDOFF_TEMPLATE.md`.

- One active writer owns each path.
- High-risk seams receive a read-only overlapping reviewer.
- A claim declares ownership; a handoff also records source/target frames,
  preserved invariants, evidence, lossy fields, and blind edges.
- Never hand off loose edits. Green work gets a normal lane commit. Broken work
  stays on its lane branch as an explicitly labelled WIP checkpoint with
  failing evidence.
- Claims do not expire merely because a slow test is running.

## Runtime memory is complementary

Cognitive-memory bootstrap and REP are semantic re-entry tools. They may point
to the hot packet but do not replace Git verification or become the coordination
source of truth. Repository state, lane ownership, and safety boundaries remain
source-controlled.
