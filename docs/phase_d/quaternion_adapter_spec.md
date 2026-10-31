# Quaternion Adapter - Phase D Specification

## Purpose
Provide an orientation-aware representation of embedding vectors by projecting them into a 4-dimensional quaternion space and computing quaternion-based similarity. This enables F-RAM to reason about "rotation" or "orientation continuity" between traces.

This document is informational only. It captures design intent for Phase D; no runtime behavior should be derived directly from it until the feature is implemented.

## Projection
- Use a fixed random 4xd projection matrix seeded by `config.phase_d.quat_proj_seed`.
- Deterministic behavior: the same seed yields the same projection across runs and machines.
- No orthonormalization in Phase D. Later phases may explore QR-based orthonormalization or multi-seed projection families.
- Shape:
  - Input: embedding vector in R^d.
  - Output: 4-element real vector to be normalized as a unit quaternion.

## Mapping to Quaternion
The adapter will later expose helper functions (names subject to change) such as:

- `to_quaternion(x)`
  - Maps the projected 4-vector to a normalized quaternion `q`.
  - `q` must satisfy ||q|| = 1 after normalization.

No math or implementation is included here; treat this as a placeholder description.

## Similarity
Conceptual quaternion similarity (implementation TBD):
- `sim_quat(q1, q2)` measures angular distance or orientation alignment between two quaternions.
- The final formula may use dot products, angles, or distances on the unit 3-sphere.
- Serves as an orientation-aware signal that complements standard vector similarity.

## Integration Points
- `fram_serving/embedding/quaternion_adapter.py` (stubbed adapter module).
- `scoring/_fractal_trace_scores_phase_d.py` (planned blending strategies for Phase D).
- `config.phase_d.quat_proj_seed` (controls projection determinism).
- Observability: `quaternion_similarity_avg` (placeholder field surfaced in recall summaries).

## Constraints
- Optional feature: only active when `config.phase_d.enable_quaternions` is `True`.
- When disabled, the adapter must not affect existing vector-based relevance scores.
- Deterministic seeding is required for reproducibility in tests and multi-host deployments.

## Relation to Logistic alpha Controller
- Quaternion similarity captures orientation continuity between traces.
- Logistic alpha controls dynamic blending between orientation-aware and vector-based signals.
- Together, they provide rotational memory plus time-evolving weighting, but this spec does not define the blending logic.

Use this document as the canonical guide for Phase D quaternion adapter work until the implementation is approved.
