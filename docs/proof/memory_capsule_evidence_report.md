# Memory Capsule Evidence Report (External-Ready)

Date: 2026-01-01

## Scope

This report covers the Memory Capsule write-through MVP and its falsification
results. It documents what the capsule captures, how integrity was checked,
and how corruption variants degrade alignment. It does not claim access to
internal attention/KV tensors, and it does not claim retrieval quality or
user-facing recall performance. This report is derived from the stored
artifacts listed below and was not re-run for this write-up.

Primary references:
- `docs/memory_capsule.md` (capsule goals and schema)
- `docs/fractal_core.md` (trace semantics and explicit non-claims)
- `docs/FRAMv2.2-SPEC.md` (implementation status)

## System Snapshot

- Repo HEAD (capture run): `33f5408276997a74dddebd0671ce02f8fdf5065f`
- Capsule capture commit (recorded in capsule): `33f5408276997a74dddebd0671ce02f8fdf5065f`
- Capsule version: `capsule-mvp-1`
- Trace version: `fractal-trace-v0`
- Embedding backend: `hashing`
- Embedding dim: `1024`
- Feature flag: `FRAM_MEMORY_CAPSULE_ENABLED=1`

## Evidence Artifacts

- Capsule: `storage/memory/capsules/capsule_20260101T0623060708990000_c2721f672be94cdb947520876f58c18d.json`
- Inspect output (CLI): `python tools/inspect_capsule.py storage/memory/capsules/capsule_20260101T0623060708990000_c2721f672be94cdb947520876f58c18d.json`
- Falsify report (JSON): `artifacts/observability/capsule_falsify_demo_20260101_062611.json`

Semantic backend run (same demo sequence):
- Capsule: `storage/memory/capsules/capsule_20260101T0648531111840000_b7221164813b4d319da6a18c99efc5e9.json`
- Inspect output (CLI): `python tools/inspect_capsule.py storage/memory/capsules/capsule_20260101T0648531111840000_b7221164813b4d319da6a18c99efc5e9.json`
- Falsify report (JSON): `artifacts/observability/capsule_falsify_semantic_20260101_064908.json`

Full test suite snapshot (latest recorded):
- `pytest -ra --durations=50 --durations-min=0.5`
- Result: `227 passed, 4 xpassed, 1 warning` (runtime ~56m55s)
- Warning: `python_multipart` PendingDeprecationWarning (starlette formparsers)

## Capture Procedure (Golden++)

1. Enable capsule writer:
   - `FRAM_MEMORY_CAPSULE_ENABLED=1`
2. Create a working-memory session:
   - `POST /memory` to create a session id.
3. Append a textured multi-turn set into the session:
   - Include a correction, contradiction, commitment, tone shift, and anchor.
4. Run `/query` once with `memory_session` set:
   - The capsule is written to `storage/memory/capsules/`.
5. Inspect and falsify:
   - `python tools/inspect_capsule.py <capsule>`
   - `python tools/falsify_capsule.py <capsule> --json`

## Integrity Checks (Inspect Capsule)

From `tools/inspect_capsule.py`:
- `raw_turns`: 18
- `trajectory_count`: 18
- `trace_stack_count`: 18
- `alignment.raw_vs_trajectory`: True
- `alignment.trajectory_vs_trace_stack`: True
- `roles`: alternating `user`/`assistant` across the 18 turns
- `meta_counts`: `entry_id=16`, `last_seen=16`

These checks confirm the capsule captured the full turn set and that
trajectory and trace stack are aligned 1:1 with the transcript.

## Falsification Results (Alignment Degradation)

Alignment metric used by `tools/falsify_capsule.py`:
- `path_score`: cosine between the query embedding and a weighted trajectory
  signature (position + role weights).
- `order_fidelity`: cosine between baseline and variant delta signatures,
  mapped to [0,1].
- `length_factor`: `variant_turns / baseline_turns`.
- `combined_score = path_score * order_fidelity * length_factor`.
- `bag_score` is reported (mean of top-k turn scores) but is not used in
  `combined_score`.

Baseline combined score: `0.48775517711979854` (baseline order_fidelity and
length_factor are 1.0)

Strong corruption variants show large drops:
- `permute_dims`: `0.044896225666874075` (drop `0.4428589514529245`)
- `random_trace`: `0.03401995492853862` (drop `0.45373522219125995`)
- `shuffle_order`: `0.33131679904876576` (drop `0.15643837807103278`)

Targeted drop-k is monotonic (expected pattern):
- `drop_k_1`: `0.2589673994194528` (drop `0.22878777770034575`)
- `drop_k_2`: `0.22235504285746546` (drop `0.2654001342623331`)
- `drop_k_3`: `0.18521367237414638` (drop `0.30254150474565217`)

Random drop-k is not monotonic (expected to be noisier):
- `drop_k_random_1`: `0.4045106319838428`
- `drop_k_random_2`: `0.2445378667784395`
- `drop_k_random_3`: `0.4267295499867812`

Role noise and light trace noise are less destructive:
- `role_noise`: `0.5141860139443489` (drop `-0.026430836824550386`)
- `trace_noise`: `0.39316586170584295` (drop `0.0945893154139556`)

Verdict (from report):
- `drop_k_monotonic_targeted = True`
- `drop_k_monotonic_random = False`
- `largest_drop_variant = random_trace`
- `largest_drop_is_strong_corruption = True`

Interpretation:
- Alignment is sensitive to structural corruption (permute dims, random trace,
  shuffle order) and targeted drops, which is the expected falsification
  pattern for a real geometric signal.
- Role metadata is not a primary alignment driver in this metric (expected).

## Semantic Backend Run (Alignment Summary)

Baseline combined score: `0.6313268462116094`

Strong corruption variants show large drops:
- `permute_dims`: `-0.002439210931066179` (drop `0.6337660571426755`)
- `random_trace`: `0.05793851867558064` (drop `0.5733883275360288`)
- `shuffle_order`: `0.34589832425361083` (drop `0.28542852195799856`)

Targeted drop-k is monotonic:
- `drop_k_1`: `0.4883795408963318` (drop `0.1429473053152776`)
- `drop_k_2`: `0.4229818950800911` (drop `0.2083449511315183`)
- `drop_k_3`: `0.37548948616088806` (drop `0.25583736005072133`)

Random drop-k remains noisy:
- `drop_k_random_1`: `0.519921413776628`
- `drop_k_random_2`: `0.46668960836326884`
- `drop_k_random_3`: `0.5237662266716063`

Role noise is minimal:
- `role_noise`: `0.6242654473552164` (drop `0.007061398856393009`)

Interpretation:
- The same falsification patterns hold under the semantic backend, with
  stronger baseline alignment and stronger penalties for structural corruption.

## What This Does and Does Not Claim

Does:
- Demonstrate that the capsule stores full turns plus a trajectory and trace
  stack, aligned per turn.
- Show that corrupting geometry degrades alignment in predictable ways.

Does not:
- Claim access to internal attention/KV tensors.
- Claim end-user recall quality or retrieval lift.
- Claim a retrieval surface for capsules (write-through only).
- Replace external replication and peer review.

## Reproduction (Minimal)

Start server (PowerShell):
```powershell
$env:FRAM_MEMORY_CAPSULE_ENABLED=1
uvicorn fram_serving.app:app --reload --port 8000
```

Create session:
```powershell
curl -s -X POST http://127.0.0.1:8000/memory -H "Content-Type: application/json" -d "{}"
```

Append 5-10 turns:
```powershell
curl -s -X POST http://127.0.0.1:8000/memory/<session_id> -H "Content-Type: application/json" -d "{\"text\":\"Turn 1: correction ...\"}"
```

Run /query with memory_session:
```powershell
curl -s -X POST http://127.0.0.1:8000/query -H "Content-Type: application/json" -d "{\"text\":\"Summarize the correction, contradiction, commitment, and anchors.\",\"memory_session\":\"<session_id>\"}"
```

Inspect + falsify:
```powershell
python tools/inspect_capsule.py storage/memory/capsules/<capsule_id>.json
python tools/falsify_capsule.py storage/memory/capsules/<capsule_id>.json --json
```

Optional automation:
```powershell
python tools/run_capsule_demo.py
```

## External Validation Next Steps

- Re-run the capture/falsify loop on fresh sessions and share the reports.
- Repeat with a different embedding backend (semantic) to see if alignment
  curves are stable across embedding sources.
- Ask a third party to run the reproduction steps and compare the drop curves.
