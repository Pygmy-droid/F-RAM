# Grove Prototype Plan (Parallel Readiness)

This plan formalizes the parallel readiness approach for the Grove application:
keep the always-on F-RAM track moving while preparing a clean, separable prototype
without artificial deadline pressure.

## Status (Jan 2026)

Conceptual only. No branching or prototype cuts until the core engine (especially ANN memory) is settled.

## Framing

We already submitted the Grove application. The close date is not our deadline.
The practical constraint is being ready to travel on short notice if accepted.
That means calm, parallel preparation:

- Always-on F-RAM: keep the full research workspace healthy and moving.
- Grove prototype: prepare a clean demo surface in parallel.

No hard freeze. No demo theater. Just steady, sensible readiness.

## What "parallel readiness" means (in practice)

- Two tracks, one cadence:
  - Track A (Always-on): continue primary development in this repo.
  - Track B (Prototype): prepare a small, clean surface that can be shown quickly.
- Minimal coupling:
  - Prototype work should not block or slow the always-on track.
  - Any risky changes stay in always-on until stable.
- Small checkpoints:
  - Short, test-backed diffs on both tracks.
  - Regular sync points so the prototype stays fresh.

## Prototype scope (initial)

Core behaviors to demonstrate (Grove-ready):
- `/query` end-to-end flow with citations.
- `/memory` create/append/search.
- `/ui/observability` quick view.
- Memory capsule write-through (`FRAM_MEMORY_CAPSULE_ENABLED=1`).

Defaults:
- Fractal influence stays OFF by default.
- Minimal env overrides in the demo.

## Grove demo checklist (when activated)

Use this as the minimal, repeatable live walkthrough.

1) Start the server
   - PowerShell: `scripts/dev_run.ps1` or `FRAM_DEV_PROFILE=1` + `uvicorn fram_serving.app:app --reload --host 127.0.0.1 --port 8000`
   - Enable capsules: `FRAM_MEMORY_CAPSULE_ENABLED=1`
2) Create a memory session
   - `POST /memory` → capture session id
3) Append 3–5 turns
   - include: a correction, a commitment, and a tone shift
4) Run one `/query` with `memory_session`
   - confirm citations and memory trace show selected items
5) Open the UI
   - `GET /ui/memory?session=<id>`
   - `GET /ui/observability`
6) Confirm capsule write
   - Inspect latest capsule file (or use `python tools/inspect_capsule.py <path>`)

Pass condition: memory session entries are used in `/query`, capsule write is OK, and UIs render.

## Demo run log

- 2026-01-09 (local, real storage): session `76d3029ed058449cbeee6376e0ab19bc`, capsule `storage/memory/capsules/capsule_20260109T1605489377950000_ddebf3d3b57b4eb883fceaba5afc706b.json`, `/ui/memory` + `/ui/observability` 200 OK, capsule write OK.

## Split strategy (recommended)

Phase 1: Branch-based split (fast)
- Create a `grove-prototype` branch.
- Strip to demo surface and clean run instructions.
- Keep always-on on the main working branch.

Phase 2: Optional repo split (cleaner)
- If Grove needs a separate repo, mirror the branch into a new repo.
- Preserve commit history for provenance.

## Timeline (flexible, steady)

Day 0-1: Scope freeze
- Confirm must-show endpoints and demo script.
- List any "do-not-ship" items for the prototype.

Day 2-3: Prototype branch
- Create branch and apply prototype-only trims.
- Add a clean quickstart + demo walkthrough.

Day 4: Validation
- Run the full test suite on the prototype branch.
- Produce one clean demo artifact (optional).

Day 5: Snapshot
- Finalize the prototype branch with a stable README.
- Tag the commit for easy recall (e.g., `grove-ready-YYYYMMDD`).

## Decisions to confirm

1) Split method: branch now, repo later (recommended).
2) Must-show endpoints: confirm list or add/remove.
3) Artifacts: include a tiny demo artifact or keep artifact-free.

Once confirmed, we will:
- Create the branch.
- Apply the minimal changes.
- Document the quickstart and demo steps.
