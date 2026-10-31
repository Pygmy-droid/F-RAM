# Production cognitive-selection gate

The candidate-reranking conversation harness and `run_query` select different
pools. Production adds situation expansion, beliefs, the configured cognitive
ANN bridge, lived recall, global trace normalization and selection budgets.
This adapter implements the retrieval/ablation evidence contract in
`FRAMv2.2-SPEC.md` section 15 using actual `run_query` memory selection.

The adapter captures chunks delivered to an empty knowledge orchestrator and
cross-checks IDs against full cognitive telemetry. Recall and the existing
snippet-similarity proxy use the same capture. This evaluates memory selection,
not generated answers. Queries use fresh contexts without session/cooldown
history. Phase-D, capsules and hard forgetting are rejected.

## Inputs and reproducibility

Supply a stable offline `memory/` tree containing `cognitive/`, relevant trace
directories and an optional consistent `lived/` SQLite backup. Nonempty source
WALs are rejected. The adapter hashes source bytes, copies to a new disposable
root, verifies the copy and verifies the source again at completion. It does not
merge lived stores. Set scratch paths before importing F-RAM so module-level
initialization cannot target a live store.

```powershell
$env:FRAM_STORAGE_ROOT = 'C:\scratch\fram-gate-bootstrap'
$env:COGMEM_STORAGE_ROOT = 'C:\scratch\fram-gate-bootstrap\memory\cognitive'
$env:COGMEM_AUTOLOG = '0'
$env:FRAM_DEV_PROFILE = '0'
$env:FRAM_FRACTAL_INFLUENCE = '0'
python -B -m scripts.production_memory_eval `
  --source-memory-root 'C:\offline\memory' `
  --scratch-root 'C:\scratch\fram-gate-new' `
  --fractal-enabled --max-items 1 `
  --evaluation-time '2026-09-08T15:30:00+00:00' --skip-off-observation
```

The default one-item smoke cannot authorize activation. A full gate uses the
whole dataset, both probe fields and all three modes. `--config` takes explicit
FRAMConfig JSON. `--half-life-hours` declares a candidate recency policy; the
runtime default is unchanged. Semantic mode uses the configured vectorizer
(hashing by default), not necessarily a language embedding model. The lexical
comparator disables the base vectorizer and its ANN path while retaining lived
recall.

Use one timezone-aware `--evaluation-time` across paired runs: source timestamps
stay intact while recency clocks remain comparable. `--skip-off-observation`
omits only influence-off fractal observation after final chunks are delivered.
An earlier call invalidates the optimization. Influence-on scoring stays active.
This option does not validate skipped replay telemetry.

Separate-process shards use the same full dataset, configuration, timestamp and
observation policy with disjoint `--item-offset` / `--max-items` slices.
`merge_production_reports` requires complete ranges and matching source, code,
profile and dataset fingerprints, then recomputes aggregates from captures.
Never average shard percentages. `strict_production_gate` requires all expected
targets, queries and vectors, exact paired capture sets and finite metrics before
applying unchanged minimum-count, top-one-lift and shadow thresholds.

Public reports contain IDs, hashes, scores and aggregates. Raw queries and chunks
stay in local `private-captures.jsonl`; typed claims preserve their fields and
type names. Atomic progress/error receipts preserve attempted, selected and
persisted query counts even if serialization fails. Partial/failed runs cannot
authorize activation.

## Accompanying production corrections

- Influence-enabled trace scoring admits only exact seed IDs resolving to current
  episode records. Historical unbound files remain preserved, and influence-off
  observation retains them. One episode-file scan avoids repeated store scans.
  Valid-trace scoring and gate thresholds are unchanged.
- Soft-DTW computes independent anti-diagonal cells with NumPy while retaining
  the original recurrence, cost matrix, band semantics and edge behavior. Parity
  tests compare the scalar reference across shapes, bands, gamma and rankings.
  No approximate distance or dependency is introduced.

A pass applies to the complete supplied dataset, corpus, code and explicit
profile. It does not install a store, set a persistent flag, establish cross-device
parity or validate absent document/session/lived-memory coverage.

## Explicit document candidate and repeatable full run

`scripts.prepare_document_candidate` adds explicitly named UTF-8 documents to a
new copy of an offline hashing-vector memory tree. It preserves exact source
bytes (including BOMs and line endings), partitions them into reversible byte
windows, and retains a separate source path, digest and offsets for each record.
Overlapping editions remain distinct. The receipt verifies all original inputs
and the copied base. Existing destinations and input/output overlap are rejected.

The records use the episode storage schema with `record_kind=document-import`,
`self_lived=false` and `instruction_authority=none`. Import time is explicit;
event time is not inferred. Neither beliefs nor lived events are created. Hashing
vectors and synthetic IFS traces are derived data, not the source or a lived
trajectory. A source snapshot plus all byte windows can reconstruct the source;
the vector or fractal trace alone cannot.

```powershell
python -B -m scripts.prepare_document_candidate `
  --base-memory 'C:\offline\memory' --destination 'C:\scratch\document-candidate' `
  --sources 'C:\sources\note.md' 'C:\sources\transcript.md' `
  --imported-at ([DateTimeOffset]::UtcNow.ToString('o'))

$receipt = Get-Content 'C:\scratch\document-candidate\receipt.json' -Raw | ConvertFrom-Json
python -B -m scripts.run_production_memory_gate `
  --repo $PWD.Path --source $receipt.memory_root `
  --run-root 'C:\scratch\document-gate' --workers 4 `
  --half-life-hours 8760 --evaluation-time $receipt.imported_at
```

The full-run supervisor uses 1-4 local processes, one native math thread per
worker, a bounded timeout, atomic progress receipts and strict report merging.
It stops only its own workers on failure and retains partial evidence. Omit
`--half-life-hours` to use the runtime default; 8760 is an explicit archival
evaluation profile, not a new default. Windows receipt replacement retries
transient access/sharing errors for at most 1.27 seconds, then fails visibly.

`--dataset` supports separate source-recall diagnostics. Freeze their questions
and exact source targets before inspecting retrieval outcomes. Source-authored
checks are supplementary; never pool them into, replace, or dilute the existing
36-case gate. Keep private files, candidate copies and raw captures outside Git.

## Soft-DTW score domain and the remaining signal question

Soft-DTW can be negative even for identical paths. The old `1/(1+d)` score had
a pole at -1 and could rank a perturbation above its identical source. The
shared score conversion now retains the old reciprocal exactly for `d >= 0`
and uses `2 - 1/(1-d)` for negative values. This is a continuous decreasing
score transform, not a probability or a nonnegative divergence. Nonfinite
costs yield no evidence. Production, the legacy API scorer and the reciprocal
evaluation path share it. No blend weights or gate margins changed.

The current generator makes deterministic, seeded contractive IFS traces from
single embeddings. Production compares them with `build_query_path`'s separately
generated path. The synthetic diagnostic
`python -m scripts.diagnose_fractal_self_recall --scratch-root <new-path>`
measures the fractal signal alone using 12 fixed orthogonal source vectors.
It does not measure blended production recall or supply activation evidence.
The 2026-09-10 result is 0/12 exact-source top-one for fractal versus 12/12 for
vector cosine; all measured costs are positive. Thus the negative-cost fix
does not address that structural mismatch.

The supplied Lantern Turn sketch already has reconstruction implementations in
`fram_core/rotational_lift.py` and `fram_eval/chaos/lift.py`; see
`docs/rotational_lift.md`. Exact reconstruction is a separate contract from
useful retrieval. The topology paper supplies hypotheses for future tests:
same endpoint/different history, correction/provenance swaps, and matched-token
replay ablations. Those require source-grounded trajectory data, independent
labels and a separately frozen benchmark before any serving change. Generated
IFS traces must not be relabelled as those observed trajectories.

## Optional source-frame recognition candidate (2026-09-10)

`FRAM_FRACTAL_SCORING_MODE=source_frame` selects the same-frame candidate;
`legacy` remains the default. The diagnostic accepts `--scoring-mode` with
these values. The unchanged twelve-source diagnostic returns 12/12 with the
candidate and 0/12 with legacy scoring. This is a synthetic recognition result,
not an activation result. Evidence and production results are recorded in
`artifacts/coordination/2026-09-10/fractal-recognition/`.

For recorded affine maps `x_t = A_t x_(t-1) + b_t`, the candidate solves the
first step for `x_0`, checks every subsequent stored coordinate against the
recorded recurrence, and replays the projected query with exactly those maps.
Only supported recipe seeds, finite coordinates and 2-4096 contiguous nodes
are admitted. It never repairs a trace in place. Existing episode binding
filtering runs before normalization; rejected records cannot consume influence.

Each generator matrix is scaled orthogonal, `A_t = s_t R_t`. The replay cost is

```
d = sum_t ||q_t - x_t||^2
    / sum_t product_(j<=t) s_j^2
    / (||q_0||^2 + ||x_0||^2)
  = ||q_0 - x_0||^2 / (||q_0||^2 + ||x_0||^2)
```

The scorer combines parent cosine and `1/(1+d)` with the existing min-max
normalization and 0.4 blend. Influence weight remains 0.05. Its telemetry names
`source_frame_distance` and `contraction_normalized_aligned_replay`; it supplies
no soft-DTW metric. Quaternion influence is unsupported and raises an error.
Near-zero projected source/query signals abstain. Recipe validation establishes
internal coordinate consistency, not source authenticity. Missing or replaced
external provenance is not authenticated by the recurrence check.

The equality above is also the limit of this design: it measures a stored 6-D
projection, not independent trajectory information. Distinct full embeddings
can collide in that projection; an explicit nullspace test preserves this
boundary. Observed history, source truth, subjective continuity and identity
are not established by synthetic replay.

The full supervisor now forwards `--config <path>` to every shard and records
its SHA-256. The frozen candidate profile is
`artifacts/coordination/2026-09-10/fractal-recognition/candidate-profile.json`.
Both original-corpus and supplied-document runs use the original 36 cases,
paired fields/modes, fixed clock and unchanged strict activation checks.
No weight or threshold is fitted to their outcomes.
