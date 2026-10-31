# Fractal Core Semantics (coord6, q, lambda)

This document defines the on-disk and runtime semantics of the fractal trace core
as implemented today. All definitions below reference existing code and tests.

## A) coord6

Definition
- `coord6` is the 6-D coordinate for each trace node in a persisted fractal trace.
- It is generated in `fram_serving/fractal_memory/fractal_gen.py:FractalGenerator.generate`
  by iteratively transforming a 6-D state vector using deterministic transforms.

Generation (code-backed)
- The seed embedding is projected into 6-D using a stable orthonormal projection
  seeded by `root_seed` (derived from `episode_id`, `timestamp_ms`, and embedding bytes).
- For each node index, the 6-D state is updated by applying a selected transform
  and offset (`_ifs_params` + `_ifs_order`), then stored as the node `coord6`.

Invariants (enforced by code/tests)
- Dimensionality: `coord6` is exactly 6 floats (created from a 6-D state).
- Determinism: for the same seed (`episode_id`, `timestamp_ms`, `embedding`) and
  generator parameters, the generated `coord6` sequence is deterministic.
  Live runs may differ unless `timestamp_ms` is fixed/pinned.
  Tests: `tests/test_fractal_memory.py:test_generation_determinism`.

What coord6 is not
- It is not a metaphor or semantic embedding; it is a deterministic 6-D trace state.
- It is not currently used to alter retrieval or answer selection. The current
  code uses `coord6` only for fractal trace scoring and persistence
  (`fram_serving/query_runner.py:_fractal_trace_scores`,
  `fram_serving/fractal_memory/fractal_trace_store.py:_persist`).

## B) q (unit quaternion)

Definition
- `q` is a unit quaternion that encodes the local motion direction between
  successive trace nodes, derived from `coord6`.

Derivation (code-backed)
- `coord6` is deterministically mapped to 3-D using a pairwise mean:
  `p3 = [(x0+x3)/2, (x1+x4)/2, (x2+x5)/2]`.
  (`fram_serving/fractal_memory/fractal_gen.py:_coord6_to_vec3`)
  This mapping is part of the v2 core contract; any change requires a
  `trace_version` bump.
- Direction `d` is computed from successive nodes:
  - For node i < last: `d = normalize(p3[i+1] - p3[i])`
  - For the last node: `d = normalize(p3[i] - p3[i-1])`
- Quaternion construction uses reference axis `a=(1,0,0)`:
  `v = cross(a, d)`, `w = 1 + dot(a, d)`, then normalize `(w, v)`.
  (`fram_serving/fractal_memory/fractal_gen.py:_quat_from_direction`)

Normalization guarantees
- The quaternion is explicitly normalized; if normalization is unstable, the
  default `(1, 0, 0, 0)` is used.
- Enforcement is covered by `tests/test_fractal_memory.py:test_quaternion_normalized`.

180-degree fallback behavior
- When `a` is approximately opposite to `d` (dot < -0.999999), a stable
  orthogonal axis is chosen for a 180-degree rotation:
  - Primary axis `(0,1,0)`, fallback `(0,0,1)` if needed.
  (`fram_serving/fractal_memory/fractal_gen.py:_quat_from_direction`)

Determinism guarantees
- `q` is fully determined by the `coord6` sequence, which is deterministic
  for a given seed and generator parameters.
- Test: `tests/test_fractal_memory.py:test_generation_determinism`.

## C) lambda (coherence-pressure scalar)

Definition and purpose
- `lambda` is a scalar in (0,1) computed per node using a logistic map.
- It is stored as a trace attribute for observability and downstream use,
  but it is not currently used to alter retrieval or answer selection.

Computation (code-backed, high level)
- `x0` is derived from `hash(seed_id + ":" + index)` mapped into (0,1).
  (`fram_serving/fractal_memory/fractal_gen.py:_logistic_seed`)
- One logistic-map iteration is applied: `x1 = r * x0 * (1 - x0)`, with `r=3.99`.
  (`fram_serving/fractal_memory/fractal_gen.py:_logistic_lambda`)
- Values are clamped to stay strictly within (0,1).

Bounds
- `lambda` is bounded by clamping in `_logistic_lambda` and enforced by
  `tests/test_fractal_memory.py:test_lambda_bounds`.

What lambda must never be used for directly
- It must not be used to accept/reject candidates or modify answers by default.
  The current code computes lambda-weighted quaternion alignment for
  observability, and only uses it to influence ranking when
  `FRAM_FRACTAL_QUAT_INFLUENCE=1` (default is off).

## D) Determinism and Bounds

Determinism inputs
- `episode_id`, `timestamp_ms`, and the seed `embedding` in `FractalSeed`.
- Generator parameters: `embedding_dim`, `n_nodes`, `meso_stride`, `macro_stride`.
- Logistic map seed uses `seed_id` and node index.

Guarantees enforced by code/tests
- Deterministic generation and provenance: `tests/test_fractal_memory.py:test_generation_determinism`.
- Quaternion normalization: `tests/test_fractal_memory.py:test_quaternion_normalized`.
- Lambda bounds: `tests/test_fractal_memory.py:test_lambda_bounds`.
- Persisted schema includes `coord6`, `q`, `lambda`:
  `tests/test_fractal_trace_smoke.py:test_fractal_trace_smoke`.

Explicit bounds
- `coord6`: list/tuple of 6 finite floats.
- `q`: unit quaternion; normalization tolerance is enforced by
  `tests/test_fractal_memory.py:test_quaternion_normalized`.
- `lambda`: bounded by clamping in `_logistic_lambda` and enforced by
  `tests/test_fractal_memory.py:test_lambda_bounds`.

## E) Role in the System

Contract statement
- This fractal trace core is the substrate for identity, continuity,
  re-entry, and narrative recursion; everything else is downstream.

Current implementation reality
- The core is persisted and exposed in trace/replay payloads; scoring uses
  coord6 (cosine + soft-DTW) and now reports quaternion/lambda alignment for
  evaluation. Optional ranking influence is gated by
  `FRAM_FRACTAL_QUAT_INFLUENCE` and remains disabled by default
  (`fram_serving/query_runner.py:_fractal_trace_scores`).

## F) Scope and Clarity (What It Is / Is Not)

What this prototype is
- A deterministic geometric trace derived from each episode embedding.
- A retrieval-time scoring signal that can re-rank memory candidates.
- A stable, repeatable "shape" per episode given the same seed inputs.

What this prototype is not
- It is not the model's internal attention tensors or KV cache.
- It does not prevent the model from recomputing attention at answer time.
- It is not guaranteed to preserve the live attention heatmap of a run.

## G) Claims and Falsification Gates

Claim 1: Proxy geometry improves low-lexical recall.
- Evidence: `scripts/conversation_memory_eval.py` and
  `scripts/memory_shadow_eval.py` runs show a lift on low-lex paraphrase probes
  versus lexical/semantic baselines.
- Falsify: no lift (or regressions) across new probe sets.
- Gate: keep auto-flip OFF unless the lift is consistent and stable.

Claim 2: Trace similarity is discriminative.
- Evidence: `scripts/fractal_trace_probe_eval.py` shows expected traces ranking
  above distractors in percentile diagnostics.
- Falsify: expected trace percentiles are consistently below top hits.

Claim 3: Quaternion influence helps (when enabled).
- Evidence: enabling `FRAM_FRACTAL_QUAT_INFLUENCE=1` shows measurable lift
  without latency regressions.
- Falsify: no lift or unstable swings; keep it OFF by default.

## H) Prototype Definition of Done (Current Stage)

- A single run can reproduce the latest eval artifacts and metrics.
- Claims and falsification gates are documented and used for decisions.
- Auto-flip remains OFF unless the evidence meets the gates above.
- Defaults and dials are documented in the cheatsheet and roadmap.

## I) Glossary (Short)

- Attention tensors: internal model arrays (layers x heads x tokens x tokens)
  produced during inference. Not captured here.
- KV cache: per-layer key/value tensors used to speed attention. Not captured
  here.
- Proxy geometry: the deterministic trace derived from episode embeddings.
- Trace: a sequence of nodes with `coord6`, `q`, and `lambda` values.
