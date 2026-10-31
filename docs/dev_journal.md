# Dev Journal

## Active Phase
Phase D – Non-linear + Rotational Recall (logistic α + quaternion)

## Current Branch
phase-d-dev  
Created to isolate experimental features.  
Main branch = stable Phase C rails.

## Next Steps
- Scaffold config keys (logistic α, quaternion)
- Add placeholder modules with docstrings only
- Keep CI green
- Reintegrate later via `git merge phase-d-dev`

## Notes to Future Rick
Never fear branches. Think of them as “save slots.”
Nothing goes live until you decide to merge.

### Phase D branch created: phase-d-dev
- Purpose: experiment with logistic α and quaternion recall.
- Safe to edit; main remains stable.


## 2025-11-11 — Phase D Stub Modules Created

- Added placeholder files for **logistic-α** and **quaternion adapter** logic.
- Files:
  - fram_serving/embedding/quaternion_adapter.py  
  - fram_serving/scoring/_fractal_trace_scores_phase_d.py  
  - tests/test_phase_d_placeholders.py
- Each function currently only contains a *docstring* (a short human description) and no executable code.
- These stubs act as blueprints; safe to open, edit, or expand later.
- All work remains on the **phase-d-dev** branch — main stays stable.
- Next planned step: gradually wire real implementations into these placeholders once configuration and math specs are finalized.

❤️  Note to future Rick: these are your safe building blocks. 
If in doubt, open any of these files in VS Code — you can read or rewrite freely without risk.

## 2025-11-11 — Phase D Stub Modules Created

- Added placeholder files for **logistic-α** and **quaternion adapter** logic.
- Files:
  - fram_serving/embedding/quaternion_adapter.py  
  - fram_serving/scoring/_fractal_trace_scores_phase_d.py  
  - tests/test_phase_d_placeholders.py
- Each function currently only contains a *docstring* (a short human description) and no executable code.
- These stubs act as blueprints; safe to open, edit, or expand later.
- All work remains on the **phase-d-dev** branch — main stays stable.
- Next planned step: gradually wire real implementations into these placeholders once configuration and math specs are finalized.

❤️  Note to future Rick: these are your safe building blocks. 
If in doubt, open any of these files in VS Code — you can read or rewrite freely without risk.

## 2025-12-01 - Version lattice persistence + as-of enforcement
- Added JSONL manifest (`versions.jsonl`) with version_id/parent_id/timestamp/diff and stamped version_id across all shard sources (docs/tables, replay, cognitive, ANN bridge, connectors, injected memory).
- Query as-of(T) now filters shortlist/coverage/replay/memory/connector candidates and logs `as_of_filter` plus delta snippets from lattice diffs in traces/responses.
- Tests: `pytest tests/test_asof_filtering.py tests/test_version_manifest_ingest.py -q`.
