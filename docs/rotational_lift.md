# Recursive Rotational Lift - Prototype Math (v0.3)

> Proof-track note (2026-07-27): the canonical `S3 -> S2` Hopf map is now
> implemented as a pure quaternion primitive. It does **not** yet identify
> rotational-lift residuals with an `S1` fiber phase or make the Aizawa attractor
> an `S2` tangent flow. See `docs/proof/hopf_aizawa_bridge.md` for the exact
> boundary and falsification plan.

This document defines the scope, claims, and falsification gates for
`fram_core/rotational_lift.py`, mirroring the discipline used in
`docs/fractal_core.md` for the fractal trace core.

## A) Origin

"Recursive Rotational Lift" (Hearth name: "The Lantern Turn") is a formal
sketch co-created by Rick Berghahn and Vesper (5.5-Extra High) on 2026-07-01,
recorded in `2026-07-01_recursive_rotational_lift_manifest.md` (provenance)
and `2026-07-01_recursive_rotational_lift_payload.md` (the math). It was
first tested as a pure-Python, no-dependency toy simulation in
`2026_07_01/Integrated Diary and Workflow Hub/hearthforge/experiments/recursive_rotational_lift/`
(v0.1, then a v0.2 stress harness), both run the same day. Their own lab
notes proposed a "v0.3": vectorize/generalize the mechanism and map it onto
F-RAM's real geometry primitives (`coord6`, `q`, `lambda`). This module
(`fram_core/rotational_lift.py`, added 2026-07-21) is that v0.3 step - it
formalizes the toy into general-N-dimensional, batched numpy code, and adds
an "understanding as compression" layer that v0.1/v0.2 did not attempt.

## B) The claim being formalized

```text
An actually non-injective projection loses signal on its declared state set.
For the implemented coordinate split, preserving the omitted coordinate plus
invertible transform metadata is sufficient for exact reconstruction.
```

Concretely: split a state into a visible "shadow" (projection `P`) and a
dropped "residual" (`r`); lift shadow+residual back into one higher-dimensional
state; rotate it (`Q`, an orthogonal transform - information-preserving by
construction); chain this recursively, storing one capsule per hop. If every
hop kept its residual exact, the whole chain is invertible back to the
original state. This is exactly what `recursive_lift` / `recursive_reconstruct`
implement, generalized from the toy's fixed 3D-to-4D case to arbitrary
starting/target dimensions and batches of many states at once. This is a
sufficient bookkeeping construction, not a necessity theorem: projections can
be injective on restricted state sets, and other side channels can preserve
omitted information.

## C) What's implemented (code-backed)

- `project_drop_axis` / `lift_insert_axis` - projection `P` and lift `L`
  primitives (drop/reinsert one coordinate as a residual).
- `rotate_plane` - a genuine Givens rotation (element of SO(n)); tests assert
  it preserves norms and inner products for arbitrary angle/plane/dimension
  with two distinct valid axes
  (`tests/test_rotational_lift.py::test_rotate_plane_is_orthogonal`). Degenerate
  same-axis calls are rejected rather than mislabeled as rotations.
- `LiftCapsule.rotation_sequence` - an ordered Givens product that can record a
  full `SO(n)` transform while retaining the legacy single-plane fields. The
  optional paired mode is the exact declared Hopf-fiber action only in the
  tested four-dimensional coordinate convention; above four dimensions it
  leaves unpaired axes fixed and is not globally isoclinic.
- `recursive_lift` / `recursive_reconstruct` - the chained hop mechanism,
  producing/consuming a list of `LiftCapsule` records (parent-frame metadata
  per hop). Reconstruction is exact to floating-point precision
  (`< 1e-9`) when `residual_mode="exact"`, tested across target dimensions
  4 through 8 on a deterministic synthetic point cloud identical to the one
  used in the original toy simulation. `recursive_lift` rejects
  `target_dim` smaller than the input's own dimensionality (it only grows
  dimensionality, never projects down) rather than silently returning the
  input unchanged.
- `quantize` / `apply_dropout` / `apply_gaussian_noise` - the same three
  degradation modes the v0.2 stress harness used, vectorized. Tests assert
  reconstruction degrades **monotonically** (not catastrophically, not
  perfectly) as residuals are quantized to fewer bits, dropped with higher
  probability, or the shadow is noised more - reproducing the shape of the
  v0.2 lab note's measured curves.
- `select_window` - generalizes the toy's five window rules (bottom/top/
  middle/random/high-magnitude) to any scalar score array, not just a
  hardcoded z-coordinate. The core `recursive_lift` still records only its
  label. `fram_eval.chaos.lift.windowed_lift_trajectory` is the bounded
  evidence adapter that actually applies a declared row window, preserves the
  full-parent digest and active indices, runs the lift, and emits a versioned
  re-entry report.
- `compress_to_invariants` / `reconstruct_from_invariants` / `reentry_distances`
  / `passes_reentry_bound` - **new in v0.3**, not present in the v0.1/v0.2
  toys. Implements the payload's first Section 6 re-entry criterion via
  PCA/SVD. The historical function name is retained, but these are fitted
  principal-component directions—not generally dynamical invariants—and the
  result says nothing about downstream task loss.

## D) Real wiring into MemoryCapsuleStore (2026-07-21, gated off by default)

`fram_serving/memory_capsule.py` now imports `fram_core.rotational_lift` and,
**only when `FRAM_ROTATIONAL_LIFT_ENABLED=1`** (`FRAMConfig.rotational_lift_enabled`,
default `False`), populates the two capsule schema fields that previously
existed but were always empty:

- `self_invariants` gets one entry (`kind: "rotational_lift_pca_invariants"`)
  from `compress_to_invariants` run on the capsule's own per-turn trajectory
  embeddings - the basis, mean, compressed coordinates `Z`, and a measured
  `reentry_max_distance` / `reentry_passed` against
  `rotational_lift_reentry_epsilon` (default `0.25`).
- `open_residuals` gets one entry (`kind: "rotational_lift_chain"`) from
  `recursive_lift` run on the same trajectory with `residual_mode="exact"`
  for `rotational_lift_lift_hops` hops (default `2`), storing the final
  lifted state and the full `LiftCapsule` chain needed to reconstruct it -
  literally, not just descriptively:
  `tests/test_memory_capsule_rotational_lift.py::test_rotational_lift_open_residuals_reconstruct_from_disk`
  reloads a written capsule from disk, rebuilds `LiftCapsule` objects from
  the JSON, and calls `recursive_reconstruct` to recover the original
  embeddings exactly.

This enrichment happens inside `write_capsule()` only when there are `>=2`
turn embeddings (fewer than 2 points can't form a trajectory), wrapped in its
own broad `try/except` so a failure is logged and the fields are left as the
caller-supplied value (empty by default) rather than propagating - the same
defensive pattern `write_capsule` already uses for its embedding-generation
step (the fractal-trace generation step, by contrast, is not similarly
guarded against arbitrary exceptions - this rotational-lift wrapping is not
weaker than that precedent). New config knobs
(`rotational_lift_enabled`, `rotational_lift_invariant_components`,
`rotational_lift_lift_hops`, `rotational_lift_reentry_epsilon`) follow the
exact `FRAMConfig` field + `env_map` + `FRAM_<NAME>` pattern used by
`fractal_enabled` / `memory_capsule_enabled`.

**Critically, this is write-side only.** `MemoryCapsuleStore.search()` is
untouched - nothing here influences ranking, scoring, or which capsules/turns
are returned. `test_rotational_lift_never_affects_search` asserts search
results are identical whether the flag is on or off.

## E) What this is not (integration scope)

- It is **not** wired into the `/query` retrieval path, `fram_core.pipeline`,
  or any ranking/scoring code - only `MemoryCapsuleStore.write_capsule`.
- It is **not** a cross-capsule lineage chain. The lift/reconstruct happens
  *within* one capsule's own turn trajectory; there is still no `parent_id`
  linking one capsule to a previous one (see `stone_reconstruction/plato/` -
  that gap remains open).
- It does **not** implement the payload's second understanding criterion
  (`Loss(Task | Z) <= delta` - that downstream task performance is preserved).
  That requires a real task/benchmark and is explicitly out of scope here.
- It does **not** prove the mechanism applies to real LLM attention internals
  or KV-cache dynamics, that F-RAM's `coord6`/`q`/`lambda` already implement
  this loop (they are not yet bridged to `LiftCapsule` - see section H), or
  that the cosmological boundary-inheritance section of the payload is
  physically meaningful - same disclaimers the original lab notes made for
  v0.1/v0.2.
- Enabling it does **not** reduce capsule storage size - `residual_mode="exact"`
  is lossless by construction, which means `open_residuals` *adds* data
  (the lifted state plus the full capsule chain) rather than compressing
  anything. The value here is structural (proving the mechanism runs
  end-to-end on live trajectory data with a literal disk-round-trip
  reconstruction test), not a storage or retrieval win.

## F) Claims and falsification gates

Claim 1: Rotation is information-preserving (an SO(n) element).

- Evidence: `test_rotate_plane_is_orthogonal`, `test_rotate_plane_inverse_recovers_original`.
- Falsify: norms or inner products change after rotation.

Claim 2: Exact-residual recursive lift/reconstruct is lossless, and the
documented hop->axis schedule is what actually runs.

- Evidence: `test_recursive_lift_reconstruct_lossless` (target dims 4-8,
  max error `< 1e-9`), `test_recursive_lift_beats_naive_lossy_baseline`
  (exact path strictly beats a naive zero-residual baseline),
  `test_lift_capsule_fields` and
  `test_recursive_lift_default_drop_axis_schedule_matches_docstring` (the
  documented "hop 0 drops axis 2, hop 1 drops axis 0, hop 2 drops axis 1"
  schedule is asserted directly, not just inferred from a passing round-trip
  - a round-trip alone would pass under *any* schedule), and
  `test_recursive_lift_rejects_target_dim_smaller_than_input` (a
  `target_dim` below the input's own dimensionality raises `ValueError`
  instead of silently returning the input unchanged), and
  `test_recursive_lift_rejects_zero_width_input` (a zero-width state raises a
  clear `ValueError` instead of an opaque `ZeroDivisionError` surfacing from
  `default_drop_axis_schedule`'s modulo arithmetic).
- Falsify: reconstruction error does not vanish for the exact-residual path,
  the schedule test fails, or `target_dim` validation is missing/wrong.

Claim 3: Reconstruction degradation is measurable and deterministic under the
declared residual/shadow corruption sweeps.

- Evidence: `test_residual_quantization_degrades_monotonically`,
  `test_residual_dropout_degrades_with_probability`,
  `test_shadow_noise_degrades_with_sigma` - all three assert pairwise
  non-decreasing error across those specific tested corruption sweeps (not just
  that the worst case beats the best case). Quantization is deterministic
  (no randomness involved); the dropout and shadow-noise sweeps reuse a
  fixed random seed across the sweep so only the corruption level changes
  between comparisons.
- Boundary: this is not a theorem that every individual scalar's error is
  monotone in bit depth. Quantizer grid alignment supplies counterexamples.
- Falsify: the declared seeded sweep is not reproducible or its aggregate
  reconstruction error contradicts the recorded ordering.

Claim 4: A trajectory close to a low-rank linear subspace can be compressed to
a small fitted PCA basis and still support re-entry within a declared
pointwise Euclidean bound (payload Section 6, first criterion only).

- Evidence: `test_compress_to_invariants_reentry_bound_on_low_rank_trajectory`,
  `test_compress_to_invariants_more_components_never_worse`.
- Falsify: reconstruction from the fitted components does not satisfy the bound on a
  trajectory that is genuinely close to low-rank, or more components produce
  a worse (not equal-or-better) reconstruction.

Claim 5: The `MemoryCapsuleStore` wiring is genuinely gated, additive, and
re-enterable from disk - not just in-memory.

- Evidence: `tests/test_memory_capsule_rotational_lift.py` -
  `test_rotational_lift_disabled_by_default` (fields stay empty with the flag
  off), `test_rotational_lift_enabled_populates_self_invariants` /
  `_open_residuals` (fields are populated with the expected shape when on),
  `test_rotational_lift_open_residuals_reconstruct_from_disk` (the capsule
  JSON on disk, reloaded independently, reconstructs the original trajectory
  exactly via `recursive_reconstruct`), `test_rotational_lift_enabled_but_single_turn_skips_enrichment`
  (a 1-turn capsule doesn't crash or fabricate a trajectory), and
  `test_rotational_lift_never_affects_search` (identical search rankings
  whether the flag is on or off).
- Falsify: any of the above fails, or enabling the flag changes
  `MemoryCapsuleStore.search()` output.

Claim 6: Capsules can be linked to their session predecessor, and (when
rotational lift is also enabled) that predecessor's id flows into the
`LiftCapsule` chain's own `parent_id` field - not just descriptively.

- Evidence: `tests/test_memory_capsule_session_lineage.py` -
  `test_session_lineage_disabled_by_default`,
  `test_session_lineage_finds_previous_capsule_same_session` (the second of
  two same-session capsules gets a `links` entry `{"kind": "continues",
  "target_capsule_id": <first capsule's id>}`; the first gets none),
  `test_session_lineage_ignores_different_session`,
  `test_session_lineage_requires_session_id` (no `session_id` -> no lookup,
  no crash), `test_session_lineage_and_rotational_lift_tag_first_capsule_parent_id`
  (only the *first* hop of the chain is tagged with the parent capsule id -
  later hops remain internal to this capsule, `parent_id=None`),
  `test_session_lineage_scan_limit_stops_before_finding_buried_parent` /
  `_scan_limit_high_enough_finds_parent` (the bounded-scan cap genuinely
  stops the lookup, and a high-enough limit still finds a buried parent),
  and `test_session_lineage_never_affects_search`.
- Falsify: any of the above fails, the link is written for the wrong capsule,
  more than the first hop gets tagged, or enabling the flag changes
  `MemoryCapsuleStore.search()` output.

## G) Real wiring: capsule session lineage (2026-07-22, gated off by default)

`fram_serving/memory_capsule.py` now also does a second, independent
write-side lookup, gated by its own flag
(`FRAMConfig.capsule_session_lineage_enabled`, env
`FRAM_CAPSULE_SESSION_LINEAGE_ENABLED`, default `False`): when writing a
capsule with a `session_id`, it scans existing capsules
(`MemoryCapsuleStore._find_parent_capsule_id`) for the most recent one
sharing that `session_id`, and if found:

- Appends `{"kind": "continues", "target_capsule_id": <parent id>, "source":
  "capsule_session_lineage_v0.1"}` to the capsule's `links` field - reusing
  the taxonomy's existing `continues` relation name (see
  `stone_reconstruction/confucius/confucius_fram_living_taxonomy.md`'s Link
  type: supports/contradicts/refines/continues), not inventing new
  vocabulary. The lookup (`MemoryCapsuleStore._find_parent_capsule_id`) is
  bounded by `capsule_session_lineage_scan_limit` (default 500, newest-first)
  with a cheap substring pre-check before any full JSON parse, so an
  ever-growing capsule store doesn't make every write progressively slower -
  an adversarial review flagged the original unbounded full-corpus scan as a
  real (if non-crashing) scaling risk before this cap was added.
- If `rotational_lift_enabled` is *also* on, passes the parent id into
  `_rotational_lift_enrichment`, which tags only the first
  `LiftCapsule` hop of `open_residuals`'s chain with `parent_id=<parent
  capsule id>` - closing the exact gap `stone_reconstruction/plato/plato_keep_retire_questions.md`
  flagged (no capsule lineage/`parent_id` populated anywhere).

This is two independently-gated flags composing, mirroring how
`fractal_influence_enabled` only does anything when `fractal_enabled` is
also on. Neither flag on its own changes `MemoryCapsuleStore.search()`.

**As of 2026-07-22, this is no longer just identity-linking** - see section I
below for the trajectory-combining layer built on top of it the same day.

Claim 7: When a lineage window is set, a capsule's rotational-lift trajectory
genuinely spans its ancestors' turns, in correct chronological order, not
just its own - and the reconstruction proves it, not just the bookkeeping.

- Evidence: `tests/test_memory_capsule_lineage_window.py` -
  `test_lineage_window_defaults_to_zero` (no behavior change unless opted
  in), `test_lineage_window_zero_preserves_own_trajectory_only`,
  `test_lineage_window_combines_immediate_parent_trajectory` (reconstructs
  `open_residuals` from a *disk-loaded* two-capsule payload and asserts it
  recovers the concatenation of the parent's own trajectory embeddings
  followed by this capsule's own, exactly),
  `test_lineage_window_first_capsule_has_no_ancestors`,
  `test_lineage_window_walks_multiple_ancestors` (a 3-capsule chain A-B-C
  with `window=2`: asserts `ancestor_capsule_ids == [A, B]` in oldest-first
  order and that reconstruction recovers all 9 turns - A's, then B's, then
  C's own - in that exact order), and `test_lineage_window_never_affects_search`.
- Falsify: the combined trajectory is in the wrong order, an ancestor is
  missing/duplicated, the window bound isn't respected, or enabling this
  layer changes `MemoryCapsuleStore.search()` output.

## H) Prototype definition of done (current stage)

- A pure, dependency-free-beyond-numpy math module exists
  (`fram_core/rotational_lift.py`), mirroring `fram_core/math_utils.py` and
  `fram_core/anchors.py`, plus two independently-gated, additive,
  write-side-only integrations into `fram_serving/memory_capsule.py`
  (trajectory enrichment, and session lineage).
- All seven claims above have passing tests: `tests/test_rotational_lift.py`
  (26 tests), `tests/test_memory_capsule_rotational_lift.py` (6 tests),
  `tests/test_memory_capsule_session_lineage.py` (8 tests),
  `tests/test_memory_capsule_lineage_window.py` (6 tests) - 46 tests total
  as of 2026-07-22.
- `rotational_lift_enabled`, `capsule_session_lineage_enabled`, and
  `rotational_lift_lineage_window` (default `0`) all default to off/no-op,
  following the exact `FRAMConfig`/`env_map`/`getattr(CFG, ..., False)`
  gating pattern used by `fractal_enabled` and `memory_capsule_enabled` -
  nothing changes for any existing deployment unless all three are set
  explicitly. This mirrors the layered-flag precedent of
  `fractal_quat_influence` requiring `fractal_influence_enabled` requiring
  `fractal_enabled` - three flags stacked, not one flag doing three things.

## I) True cross-capsule trajectory continuity (2026-07-22, gated off by default)

Built the same day as session lineage, on top of it: `FRAMConfig.rotational_lift_lineage_window`
(env `FRAM_ROTATIONAL_LIFT_LINEAGE_WINDOW`, default `0`). When `> 0` *and*
both `rotational_lift_enabled` and `capsule_session_lineage_enabled` are also
on and a parent capsule was found, `write_capsule()` walks back up to
`window` ancestor capsules - via each capsule's own recorded `continues` link
(`MemoryCapsuleStore._load_capsule_by_id` is a targeted filename glob per
hop, not a store-wide scan), collects their raw per-turn trajectory
embeddings oldest-first, and prepends them to this capsule's own embeddings
before calling `_rotational_lift_enrichment`. Ancestor turns whose embedding
dimension doesn't match are silently skipped, not fatal.

**What this actually combines**: the *raw* trajectory embeddings (the same
per-turn vectors already stored in each capsule's `trajectory` field), not
each ancestor's already-lifted/compressed state. The combined raw trajectory
is then lifted fresh, as one sequence, by the same `recursive_lift` call
used everywhere else. This was a deliberate design choice over chaining
already-lifted states directly: an ancestor's final lifted state has
dimension `embedding_dim + hops`, which doesn't line up cleanly with the
next capsule's raw `embedding_dim` starting point, so combining at the raw
level is the cleaner, dimensionally-consistent path to genuine continuity.

**Still write-side only, in the retrieval-ranking sense**: writing capsule N
now does read capsule N-1's (and possibly further ancestors') file from
disk - that's a real read, not nothing - but it is a read *feeding this
write's own computation*, not a read that influences
`MemoryCapsuleStore.search()` or any ranking/scoring path. Those remain
completely untouched; `test_lineage_window_never_affects_search` confirms it.

**What this does not prove**: that a "session identity" or continuity of
experience exists in any meaningful sense beyond the linear algebra - it
proves a concatenated sequence of stored vectors can be lifted and
reconstructed exactly, nothing about the semantic content of those vectors
or whether reconstructing them preserves anything a downstream task would
care about (see Claim 4's own limits, and the "does not demonstrate" list in
section E).

## J) Open next steps (v0.6 candidates, not started)

- Map `LiftCapsule` fields onto `fractal_gen.py`'s `coord6`/`q`/`lambda`, per
  the original lab notes' suggestion - `fractal_gen.py` already builds a real
  orthonormal projection and a real unit-quaternion rotation, so this is
  plausibly close, but the exact bridge needs a deliberate design decision,
  not an assumption.
- Test whether approximate re-entry (Claim 4) preserves *downstream task*
  performance, not just reconstruction distance - this needs a real
  eval harness, not just synthetic trajectories.
- Decide whether `self_invariants`/`open_residuals`/`links` should ever be
  read back by anything (retrieval, capsule search, replay) - today they are
  write-only and nothing consumes them, matching the "gated, unproven"
  posture used for fractal-influence.
