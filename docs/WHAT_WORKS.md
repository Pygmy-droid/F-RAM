# What Works (2025-10-10)

## Firelink recovery baseline (2026-07-27)

- The canonical assembled build is isolated on `firelink/full-merge`; the live
  `autoflip-eval` worktree and its uncommitted recovery files remain untouched.
- Phase D/G behavior, persisted cognitive ANN recall, version-manifest/as-of
  enforcement, lifecycle, storage, restored observability routes, and legacy
  memory imports coexist on one line.
- Visual evidence can be inventoried losslessly and rendered into deterministic
  contact sheets while retaining duplicate paths and AppleDouble sidecars.
- The Hopf map is available as a pure proof-track geometry primitive. It does
  not influence serving or retrieval defaults.
- Validated Hopf horizontal transport, principal holonomy, and the exact
  paired-Givens S1 fiber action now live in bounded proof modules. The
  fixed-shell Aizawa field has an analytic two-pole result; no topology claim
  is wired into runtime behavior.
- The recovered Chaos Playground contract now has an executable deterministic
  Python core: four-system registry, logistic diagnostics, declared
  `RotationalEncodingV1`, Mandelbrot/Julia kernels, and versioned scene JSON.
  Opus's exact 64,584-byte browser artifact is committed and visibly verified:
  all four canvases paint, 18 controls load without console errors, and scene
  memory completes save → shelve → restore. A shared golden fixture binds its
  default logistic readouts to the canonical Python simulator. The historical
  March formula remains unrecovered.
- Rotational-lift capsules can record an ordered Givens product while preserving
  the legacy single-plane path. A versioned Chaos evidence adapter now applies
  a real row window, records active indices and the parent digest, and reports
  selected-scope re-entry. This remains proof/evaluation code and does not
  affect serving or retrieval defaults.
- New sessions bootstrap from a sub-8-KiB hot packet and verify required
  coordinates, strict ancestry, and watched-path freshness; immutable Firelink
  snapshots can be created at closeout.
- Power-trip runtime records and historical observability files are preserved
  with provenance rather than mixed silently into generated runtime storage.
- Details, verification evidence, and operating boundaries:
  `docs/FIRELINK_CLOSEOUT_2026-07-27.md`.

## Calibration guard rails

- `fram_core/confidence.py`: logits now clip to +/-20 and the returned probability is bounded to `[0.001, 0.999]`.
- `fram_core/pipeline.py` `_fit_logistic_regression`: clamps feature columns (Δ_z, ρ_pos, d_c_z) to +/-10, keeps `mhd`/`fresh` in `[0, 1]`, and limits weight/bias updates to +/-5 with stronger L2. This stops the sigmoid from collapsing.
- `fram_core/calibrate.py`: enforces `tau1 >= config.tau1` and `tau2 <= config.tau2` so fitted thresholds never undercut the documented defaults (0.8 / 0.5).

## Prompt sweeps

- High-confidence definitional prompts: `scripts/calibration_prompts/definitional_queries.txt`
- Softer/near-miss prompts: `scripts/calibration_prompts/definitional_soft_queries.txt`
- Ambiguous low-confidence prompts: `scripts/calibration_prompts/definitional_low_conf_queries.txt`
- QA moderate prompts (new/expanded): `scripts/calibration_prompts/qa_moderate_queries.txt`

Harvest commands used today (domain `general`):

```bash
$env:PYTHONPATH=(Get-Location).Path; python scripts/harvest_calibration.py --queries scripts/calibration_prompts/definitional_queries.txt --task qa --quiet
$env:PYTHONPATH=(Get-Location).Path; python scripts/harvest_calibration.py --queries scripts/calibration_prompts/definitional_queries.txt --task definitional --quiet
$env:PYTHONPATH=(Get-Location).Path; python scripts/harvest_calibration.py --queries scripts/calibration_prompts/definitional_soft_queries.txt --task definitional --quiet
$env:PYTHONPATH=(Get-Location).Path; python scripts/harvest_calibration.py --queries scripts/calibration_prompts/definitional_low_conf_queries.txt --task qa --quiet
$env:PYTHONPATH=(Get-Location).Path; python scripts/harvest_calibration.py --queries scripts/calibration_prompts/definitional_low_conf_queries.txt --task definitional --quiet
$env:PYTHONPATH=(Get-Location).Path; python scripts/harvest_calibration.py --queries scripts/calibration_prompts/qa_moderate_queries.txt --task qa --quiet
```

Fits:

```bash
$env:PYTHONPATH=(Get-Location).Path; python scripts/calibrate_confidence.py --log storage/observability/calibration.jsonl --out storage/index/demo_corpus/calibration.json
$env:PYTHONPATH=(Get-Location).Path; python scripts/calibrate_confidence.py --log storage/observability/calibration_task_definitional.jsonl --out storage/index/demo_corpus/calibration_task_definitional.json
```

## Sanity checks

- `tools/calibration_sanity.py` prints decision/p_temp for the bundled prompts and exits non-zero if any entry hits the floor/ceiling. Wire it into CI like so:

  ```bash
$env:PYTHONPATH=(Get-Location).Path; python tools/calibration_sanity.py --floor 0.05 --ceiling 0.95
$env:PYTHONPATH=(Get-Location).Path; python tools/calibration_sanity.py --task definitional --floor 0.05 --ceiling 0.95
  ```

- Histogram CLI: `python tools/calibration_histogram.py --bins 10` summarises p_temp distribution by (task, decision).

## Verification snapshot (reads=3)

| Query | Task | Decision | p_temp | Calibration source |
| --- | --- | --- | --- | --- |
| What is FRAM? | qa | local | 0.84 | global |
| What did I work on today? | qa | local | 0.84 | global |
| What are the next milestones? | qa | local | 0.81 | global |
| How does CELF work? | qa | anchors | 0.52 | global |
| Which features are done? | qa | anchors | 0.52 | global |
| What is FRAM? | definitional | local | 0.81 | task:definitional |
| What did I work on today? | definitional | local | 0.81 | task:definitional |
| What are the next milestones? | definitional | anchors | 0.74 | task:definitional |
| How does CELF work? | definitional | global | 0.26 | task:definitional |
| Which features are done? | definitional | global | 0.26 | task:definitional |

## Next steps

- Continue adding mid-confidence QA prompts so anchors/global decisions stay balanced.
- Hook `tools/calibration_sanity.py` into CI before pytest to catch saturated payloads early (Makefile `test` target already does this).

## Phase D safety patch migration (2025-12-13)

- `/query` and MCP `fram.query` now share `fram_serving/query_runner.py`, so budget handling (including `budget` alias) and trace fields stay in parity.
- Repo guard: `tools/check_nul_bytes.py` is wired into pre-commit (`check-nul-bytes`) and `make nul-check`; use `--fix` if a paste introduced hidden NULs in `docs/` or `prompts/`.



## Observability tips (Phase D bridge)

- Use `python tools/phase_d_memory_summary.py --json` or `GET /observability/recall_report` to inspect `phase_d_memory.stats` (events, scored totals/avg, alpha/quaternion means, color counts, `missing_alpha`). With debug off, `alpha_*` may be absent; enable `phase_d.debug_observability` for diagnostics.
- Perf sanity (dev, cold start, hashing corpus): `/query` averaged ~55.2s with the bridge off vs ~57.3s with it on (single query; dominated by orchestrator warm-up). Expect smaller steady-state deltas; rerun after caches warm.

## Release and Warnings

- Pluggable ANN now prefers FAISS when available (fallback to sklearn); metadata fingerprints drive self-healing reloads across runs.
- Version bumped to 0.1.0 with pinned scikit-learn 1.7.2 / joblib>=1.4 for deterministic persisted artifacts.
- Added pytest warning filters plus make test-warnings to keep calibration suites warning-free.
