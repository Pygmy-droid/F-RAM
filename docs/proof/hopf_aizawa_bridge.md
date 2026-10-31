# Hopf/Aizawa bridge: proof-track boundary

Date: 2026-07-27  
Status: validated Hopf transport and fixed-shell Aizawa construction
implemented; runtime correspondence remains unestablished.

## What is now concrete

`fram_serving.embedding.quaternion_adapter.hopf_map` implements the canonical
Hopf projection

```text
h(q) = q i q^-1 : S3 -> S2
```

using `(w, x, y, z)` quaternion order. The function accepts any finite nonzero
four-vector, normalizes it onto S3, and returns the corresponding unit
three-vector on S2.

`tests/test_hopf_bridge.py` pins the properties needed before using the map as a
reasoning primitive:

- the declared identity base point;
- unit-S2 output;
- invariance under nonzero scale and the `q`/`-q` representation ambiguity;
- an explicit S1 fiber over the identity base point;
- a known quarter-turn under the declared quaternion convention; and
- rejection of zero, non-finite, and wrong-dimensional inputs.

The function is proof-track only. It is not called by ranking, memory search,
capsule persistence, or serving defaults.

`fram_eval.hopf_transport` now adds the declared right-S1 fiber action,
validated horizontal transport, principal holonomy modulo `2π`, spherical
polygon area, and the exact paired opposite-sense Givens representation of
fiber phase. It rejects antipodal consecutive base segments rather than
silently choosing a non-unique transport axis.

`fram_eval.aizawa_sphere` shares the canonical Aizawa velocity primitive with
the legacy Euler simulator. It keeps the ambient R3 flow separate from the new
fixed-shell field `V_R(n)=(I-nn^T)F(Rn)`. For positive radius and `d != 0`, the
two z-pole zeros are established analytically; numerical root finding is only
corroboration and makes no completeness claim.

`experiments/hopf_aizawa_falsification.py` contains bounded negative controls
for the adapter, recursive lift, dropped-coordinate shadow, and base-only
re-entry. None of these proof surfaces has a runtime caller.

## The distinctions that remain binding

1. The Aizawa attractor is ordinarily a flow in R3. It is not, without an
   additional construction, a tangent vector field on S2. Radial normalization
   or tangent projection changes its dynamics and must define behavior near the
   origin.
2. A deterministic projection from an embedding into four coordinates,
   followed by normalization, is not automatically a global coordinate chart
   for the original embedding space.
3. The `q`/`-q` ambiguity is the Z2 ambiguity of the SU(2) to SO(3) double
   cover. It must not be identified with the continuous S1 fiber of the Hopf
   fibration.
4. A coordinate dropped by `project_drop_axis` is a Euclidean residual. It does
   not become a Hopf fiber phase until a connection and lift law make that
   interpretation precise.
5. The Hairy Ball Theorem constrains continuous tangent vector fields on
   even-dimensional spheres. It cannot be invoked for the Aizawa system until
   an S2 tangent field has actually been constructed.

## Falsification status and next experiment

The first three construction stages now have executable proof primitives:

1. Generate a deterministic Aizawa trajectory in R3.
2. Declare and test a projection that produces an S2 base curve and an S2
   tangent field, recording singular/undefined cases instead of hiding them.
3. Declare a connection, lift a closed S2 loop into S3, and measure its S1
   holonomy.
4. Compare holonomy and rotational-lift representations against a runtime path
   that is explicitly intended to live on S3. Defect-location perturbation is
   a separate empirical experiment, not "attractor recurrence."

The current evidence establishes the geometry and several negative controls.
It does not establish that any F-RAM runtime representation belongs on S3, or
that topology governs memory or identity.

## Independent seam results

The 2026-07-27 read-only falsification pass established:

- `fram_serving.fractal_memory.metrics._quat_from_direction(d)` is already a
  local Hopf section. Across 1,000 random unit directions,
  `hopf_map(_quat_from_direction(d))` returned `d` with maximum error
  `7.75e-15`.
- That section has a gauge seam at the antipodal direction `(-1, 0, 0)`;
  approaching along different meridians yields different quaternion limits.
- Phase D's signed `quat_similarity(q, -q)` is `-1` while their Hopf images are
  identical. Signed projected-embedding similarity may be intentional, but it
  must not be described as quotient rotation identity.
- Exact recursive-lift reconstruction remained within `2.22e-16` for closed
  curves with one, two, and four windings. Current re-entry error is therefore
  holonomy-independent by construction and is the required negative control.

The declared Hopf fiber action for experiments is `q -> q exp(i phi)`, with
metric connection `A_q(v) = <v, q i>`. Synthetic loops precede Aizawa:

- base reconstruction error below `1e-10`;
- horizontality residual below `1e-8`;
- holonomy error below `1e-4`;
- loop reversal negates phase; and
- refinement reduces discretization error.

Keep the normalized Aizawa path
`u(t) = x(t) / ||x(t)||` separate from the autonomous fixed-shell tangent field
`V_R(u) = (I - u u^T) F(Ru)`. Hairy Ball applies to the latter. Inputs with
`||x|| < epsilon` are reported as undefined rather than silently normalized.

For defect evidence, the default two-pole result is analytic. Mesh refinement,
local indices, and Poincare-Hopf sum `2` corroborate it but do not prove a
generic numerical search complete. Rediscovering the same zeros of an
autonomous shell field measures solver stability, not recurrence in an Aizawa
trajectory, memory, or lived experience.
