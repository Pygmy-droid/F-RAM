# Firelink full-lineage integration closeout

Date: 2026-07-27  
Canonical branch: `firelink/full-merge`  
Canonical worktree: `D:\Dev\_firelink_merge`

## Outcome

The recovered F-RAM lineages now have one canonical integration branch. The
merge keeps the newer serving and memory work while restoring the Phase D,
Phase E, Phase G, version-lattice, storage, observability, and proof artifacts
that existed only in older branches, archives, or uncommitted state.

The protected working branch at
`D:\Dev\FRAM_V22_Starter\fram_v22_starter` remains separate. Its branch,
uncommitted files, imported visuals, and recovered folders were not rewritten
or cleaned during this integration.

## Integrated seams

- Phase D priority, retention, hysteresis, quaternion scoring, and memory
  bridge behavior coexist with the newer pipeline.
- Cognitive ANN candidates merge with document candidates only when cognitive
  candidates actually exist; otherwise the established coverage order remains
  unchanged.
- Explicit version selection, latest-version lookup, manifests, ancestry, and
  as-of filtering share one version lattice.
- Serving exposes the restored observability route family, memory lifecycle,
  Phase D scoring, storage, configuration, and query behavior.
- The `fram_serving.memory` package transparently delegates legacy module
  attributes while preserving newer submodules.
- Phase E and calibration command-line tools bootstrap the repository when run
  directly by absolute path.
- Five historical observability JSONL files are preserved as tracked evidence
  under `artifacts/phase_history/`; live `/storage/` policy remains runtime
  oriented.
- Snapshot and backup provenance trees remain in place and are excluded from
  pytest recursion.

## Visual evidence

The Visual Evidence Ledger recovered through Opus is now part of canonical
source. It provides:

- lossless path-level inventory;
- byte-signature format detection and dimensions;
- SHA-256 content identities and duplicate groups without dropping duplicate
  paths;
- explicit AppleDouble metadata-sidecar classification;
- auditable JSONL/summary outputs; and
- deterministic contact sheets with a path-complete observation index.

The recovered real-corpus run reported 455/455 files indexed: 243 pixel
visuals, 212 AppleDouble sidecars, 244 unique contents, 211 exact duplicates,
zero unverified files, and complete status.

See `docs/VISUAL_EVIDENCE.md`.

## Geometry proof track

`fram_serving.embedding.quaternion_adapter.hopf_map` now supplies the canonical
`h(q) = q i q^-1` map from S3 to S2 as a pure, unused-by-default primitive.
Tests pin its S1 fibers, unit output, declared quaternion convention, and
`q`/`-q` invariance.

Validated proof modules now provide the declared right-S1 action, horizontal
transport, principal holonomy modulo `2π`, exact paired-Givens fiber bridge,
and a fixed-shell Aizawa tangent field with an analytic two-pole result. The
ambient R3 flow and fixed-shell field remain distinct; numerical zero finding
is corroboration, not a completeness or recurrence proof.

This still does not assert that a four-coordinate embedding projection is a
global S3 chart, that a dropped Euclidean residual is an S1 phase, or that any
runtime path is intended to live on S3.

See `docs/proof/hopf_aizawa_bridge.md`.

## Chaos reconstruction

The visual contract now has an executable deterministic Python core under
`fram_eval/chaos/`: adapters for the four canonical systems, logistic
diagnostics and bounded Feigenbaum estimates, an explicitly new
`RotationalEncodingV1`, Mandelbrot/Julia escape kernels, and versioned scene
memory. Golden and legacy-identity tests pin the mathematical contract.

Opus's reconstructed Playground v2 is now preserved exactly under
`experiments/chaos_playground/`. The 64,584-byte authored source has SHA-256
`227C350BFC930ACC17FFD3309D5AFB5F9EA1EA0876DEE82497746B33B0EF44B5`;
`.gitattributes` prevents checkout line-ending conversion. A visible Edge run
painted the helix, bifurcation, Mandelbrot, and Julia canvases with nontrivial
color variance, loaded 18 controls, produced no console errors, and completed
the save → shelve → restore memory cycle.

`golden-default-v1.json` binds the browser's default logistic Lyapunov,
last-state, period, and cascade display to the canonical Python simulator and
diagnostics. The original March 2026 formula is still not claimed recovered.

The supplied recursive-lift payload produced two bounded changes. Capsules can
now record an ordered Givens product while the legacy single-plane default
remains unchanged. Independent scoring confirmed that paired rotation does not
repair the off-S3 landing: norm deviation is identical and the remapped base
stays near chance. Separately,
`fram_eval.chaos.lift.windowed_lift_trajectory` now applies a real row window
and emits active indices, a parent digest, a capsule chain, and selected-scope
re-entry evidence. It is not attention, compression, Hopf transport, or a
runtime behavior change.

## Recovered runtime evidence

Unique power-trip records were archived outside tracked source at:

```text
D:\Dev\_archives\FRAM_power_trip_recovery_202512
```

The archive manifest records per-file SHA-256 hashes and the following unique
counts compared with the protected live worktree:

- 20 cognitive episodes;
- 20 cognitive vectors;
- 84 calibration records;
- 10 confidence records;
- 10 latency records;
- 11 cognitive-memory observability records; and
- 58 fractal-memory observability records.

The annotated rescue tag is `rescued/power-trip-stash-2025-12`. No raw stash
was applied wholesale, cache binaries were not promoted, and the archive stays
outside the source branch.

## Safety and operating boundary

- Keep `autoflip-eval` and its uncommitted recovery files untouched until Rick
  explicitly chooses a migration strategy.
- Treat `firelink/full-merge` as the assembled build, not as permission to
  overwrite the live branch.
- Keep optional/research behavior gated; the Hopf primitive is proof-track
  only.
- Preserve backup zips and snapshot trees because they contain provenance and,
  in at least one case, source that Git did not retain.
- Regenerated corpus/index files are runtime artifacts. Restore them after test
  runs unless a deliberate corpus refresh is being committed.

## Verification notes

The integration was verified in ordered partitions with immediate regression
repair at each failure boundary. The highest-risk
`tests/test_pipeline_orchestrator.py` seam passed 34 tests in 409.33 seconds;
the final post-refresh partition passed 108 tests in 192.03 seconds. Focused
ledger, Hopf, closeout, routing, lifecycle, versioning, ANN persistence, memory
compatibility, and direct-run CLI suites are green.

Corpus construction can spend tens of seconds in `numpy.linalg.svd`. The same
behavior reproduces on the untouched live branch, so it is a known performance
cost rather than an integration regression.
