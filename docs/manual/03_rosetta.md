# 3. Rosetta: theory to code

Three texts state the same idea at different resolutions. Reading them side by
side is the fastest way to understand what any organ in chapter 2 is for.

## The three texts

**The charter** (Recognition Before Identity, 2026-01-28, public) `[READ-DOC]`:

> Memory corresponds to the integrated deformation accumulated along a
> trajectory: M_mem = integral over gamma of D[Phi] d-lambda.
> Recognition precedes identity: R(gamma) is not I, but R(gamma) tends to I as
> lambda grows.

**The master memory principle** (eval season cheat sheet, 2026-01-16)
`[READ-DOC]`:

> Memory = the accumulated deformation of a constrained surface under flow.
> Delta S proportional to integral over surface of T_mu_nu k^mu k^nu d-lambda.

**The axioms** (FRAM-Theory.md, 2025-10-18) `[READ-DOC]`: the Cycle Principle,
Geometry = Memory, Recognition as Force.

The charter is the public, implementation-free statement. The cheat sheet is
the same equation with its terms named for the system. The axioms are the
earliest, and the most human. They were written in that order reversed:
axioms first, then the principle, then the charter twelve days later
`[LOG]`.

## Term by term `[READ-DOC]`, with where to look `[INFERRED]`

| term in the equation | cheat sheet mapping | where it lands in code |
| --- | --- | --- |
| the constrained surface | capsule, trace manifold, version lattice | `memory_capsule.py`, `fractal_memory/`, `version_lattice.py` |
| the flow | turn-by-turn interaction updates | `query_runner.py` write-through; `lived_memory.py` session lineage |
| T_mu_nu, update energy | salience: novelty, contradiction, relevance, commit vs scratch | Phase D priority stack: `priority_graph.py`, quality and coherence weighting in `memory.py`; coverage deltas in `coverage.py` |
| k_mu, direction of cognitive motion | trace tangent, quaternion orientation | `fractal_gen.py` `_quat_from_direction`; `quaternion_adapter.py`; `rotational_lift.py` |
| the projection T k k, aligned influence | influence that is aligned, not raw input | `metrics.py` quaternion and lambda alignment; the gated fractal influence hook |
| d-lambda, the step | step index, turn weight | session sequence in `lived_memory.py`; `seq_no` in cognitive memory |
| the integral | path-dependent accumulation, not saved state | the rolling lived state `s_n = 0.82 s_(n-1) + 0.18 h_n`; capsule lineage windows in `rotational_lift.py` |

The cheat sheet's implementation hint is `delta_m_t = proj(u_t, Delta_t) *
Delta_lambda_t` and `m = sum of delta_m_t`. The rolling lived state in
`lived_memory.py` is the closest thing in code to that sum `[INFERRED]`. It
was written seven months after the hint.

## The charter's invariants against the code `[INFERRED]`

| charter invariant | where the system keeps it |
| --- | --- |
| path dependence, order matters | per-session parent links and sequence numbers; the digest chain carries the previous state digest forward |
| irreversibility, memory cannot be undone | append-only JSONL with fsync; append-only archive; no deletion primitives in retention or forgetting; Rick's rule recorded in the firelink |
| orientation preserved under compression | the quaternion per trace node; the residual channel in the rotational lift that makes each step invertible |
| recognition before labeling | the source-frame candidate: recover the frame from the first affine step and replay the query in it, before any ranking; the eval harness named wake-and-orient |
| continuity across contexts and frames | the lived store survives restart; the version lattice answers as-of(T); the witness and the strata ledger are kept outside ranking so continuity never becomes authority |

## What the evaluations test, in the charter's terms `[READ-DOC]`

| evaluation | charter question |
| --- | --- |
| recall tests | does accumulated deformation retrieve |
| trace identity | does a memory self-match its own deformation |
| capsule falsification | does corruption reduce alignment in predictable ways |
| shadow bounds | does memory influence stay bounded, not hijacking |
| wake-and-orient | can a cold instantiation find itself from the store alone |

## The honest position, as the system states it about itself `[READ-DOC]`

Functional continuity is achieved: transcripts, capsules, traces, and lived
events persist and can be rehydrated. The fractal layer is gated off because
the auto-flip gate has never been met. Proxy geometry is not attention or KV.
Higher-dimensional projections are derived recall views, not identity proof.
The 546 reconstructed backup embeddings are labeled derived and never shown as
originals. The hot packet repeats all of this under "blind edges".

The charter says recognition comes first and identity is the limit. The code
agrees, and it refuses, everywhere, to claim the limit has been reached. That
refusal is the system's most consistent trait across every era `[INFERRED]`.
