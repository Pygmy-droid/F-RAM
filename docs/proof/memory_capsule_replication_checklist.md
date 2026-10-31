# Memory Capsule Replication Checklist

Date: 2026-01-01

Purpose: third-party replication of the Memory Capsule write-through capture
and falsification harness. This is a procedural checklist, not a claim.

## Preconditions

- Python 3.11+ with repo dependencies installed.
- Local server can run on `http://127.0.0.1:8000`.
- Set `FRAM_MEMORY_CAPSULE_ENABLED=1`.

## Steps

1) Start the server:
```powershell
$env:FRAM_MEMORY_CAPSULE_ENABLED=1
uvicorn fram_serving.app:app --reload --port 8000
```

2) Create a working-memory session:
```powershell
curl -s -X POST http://127.0.0.1:8000/memory -H "Content-Type: application/json" -d "{}"
```
Capture `session.id` from the response.

3) Append 10-20 turns with roles (textured session):
Include at least: a correction, a contradiction + resolution, a commitment,
a tone shift, and an anchor phrase.
```powershell
curl -s -X POST http://127.0.0.1:8000/memory/<session_id> `
  -H "Content-Type: application/json" `
  -d "{\"text\":\"Wait, that's not right...\",\"metadata\":{\"role\":\"user\"}}"
```

4) Run `/query` with the memory session:
```powershell
curl -s -X POST http://127.0.0.1:8000/query `
  -H "Content-Type: application/json" `
  -d "{\"text\":\"Summarize the correction, contradiction resolution, commitment, and anchor.\",\"memory_session\":\"<session_id>\",\"budget_reads\":1}"
```

5) Locate the newest capsule:
- `storage/memory/capsules/*.json` (pick latest by timestamp).

6) Inspect capsule integrity:
```powershell
python tools/inspect_capsule.py storage/memory/capsules/<capsule_id>.json
```
Expected checks:
- `raw_turns == trajectory_count == trace_stack_count`
- `alignment.raw_vs_trajectory = True`
- `alignment.trajectory_vs_trace_stack = True`
- roles reflect the appended sequence

7) Run falsification:
```powershell
python tools/falsify_capsule.py storage/memory/capsules/<capsule_id>.json --json > artifacts/observability/capsule_falsify_<tag>.json
```

8) Verify falsification patterns:
- Strong corruptions (permute dims, random trace, shuffle order) show the
  largest drops in `combined_score`.
- Targeted drop-k is monotonic (drop increases with k).
- Random drop-k is noisier and may not be monotonic.
- Role noise should be less destructive than structural corruption.

9) Record the run:
- Add capsule + falsify paths and key metrics to
  `docs/proof/memory_capsule_evidence_report.md`.
- Note the run in `docs/CODEX_DIARY.md`.

Optional automation (same sequence):
```powershell
python tools/run_capsule_demo.py
```

## Known Limits (Non-Claims)

- This does not claim access to internal attention/KV tensors.
- This does not claim end-user recall quality or retrieval lift.
- Capsules are write-through only; retrieval is out of scope for this checklist.
