# F-RAM Claim and Handoff Template

## CLAIM

```text
CLAIM <id>
timestamp:
owner:
base commit:
branch:
worktree:
scope:
exact write paths/globs:
preserved invariants:
seam/overlap reviewer:
exit gate:
status: ACTIVE
```

Re-read the Firelink tail immediately before starting and immediately before
committing. One active writer owns a path.

## CHECKPOINT

```text
CHECKPOINT <claim-id>
commit:
changed paths:
test command/result:
dirty status:
new recognition/decision:
blind edge:
next step:
```

Append a checkpoint only after a coherent commit. Never hand off loose edits.
A blocked lane may use an explicitly labeled WIP commit on its own branch with
the failing evidence; never place a broken WIP commit on canonical.

## HANDOFF

```text
HANDOFF <claim-id>
source frame (base -> commit):
target frame / expected cherry-pick base:
touched paths:
behavioral delta:
evidence anchors:
assumptions:
lossy or omitted fields:
explicit blind edge:
seam risks:
classification: recognition-grade | hypothesis-grade | integration-grade
status: DONE | BLOCKED | RELEASED
```

Claims do not expire solely by time. Before marking one stale, the lead checks
the owner/process and appends the reason.
