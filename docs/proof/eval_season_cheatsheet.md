# Eval Season Cheat Sheet (F-RAM)

This is a one-page, no-code summary you can present. It explains what we tested, how we scored it, and where the evidence lives.

## Master Memory Principle (conceptual spine)
Memory = the accumulated deformation of a constrained surface under flow.

Canonical form (structure only, not physics-specific):
Delta S ∝ ∫_surface T_mu_nu k^mu k^nu d lambda

Mapping to F-RAM:
- Constrained surface -> capsule / trace manifold / version lattice
- Flow -> turn-by-turn interaction updates
- T_mu_nu -> update energy or salience (novelty, contradiction, relevance, commit vs scratch)
- k_mu -> direction of cognitive motion (trace tangent / quaternion orientation)
- Projection T_mu_nu k^mu k^nu -> aligned influence (not raw input)
- d lambda -> step index / turn weight
- Integral -> memory is path-dependent accumulation, not a saved state

Why our evals exist (invariants implied by the equation):
- Recall tests -> does accumulated deformation retrieve?
- Trace identity -> does a memory self-match its own deformation?
- Capsule falsification -> does corruption reduce alignment in predictable ways?
- Shadow bounds -> does memory influence stay bounded and non-hijacking?

Implementation hint (optional, not required yet):
delta_m_t = proj(u_t, Delta_t) * Delta_lambda_t
m = sum_t delta_m_t

## What we tested (plain language)
- Memory recall across sessions (can we remember without context?).
- Low-lex paraphrase recall (same meaning, different wording).
- Capsule integrity (does the stored episode survive corruption tests?).
- Trace identity (does a memory best-match its own trace geometry?).
- Shadow impact (does memory retrieval change the query embedding in a sane way?).

## What the metrics mean (short)
- top1 / top5: how often the correct memory is ranked first or in the top 5.
- hit rate: whether a target memory appears anywhere in the pool.
- shadow avg_delta: how much the query embedding shifts after memory injection.
- falsification drop: corruption should reduce alignment scores.

## Our current position (honest and grounded)
- Functional continuity is achieved: transcripts + capsules + traces persist and can be rehydrated.
- Fractal influence is still gated (KEEP_OFF) until it shows stable lift in live probes.
- KV/attention access is a validation and granularity upgrade, not a replacement.

## Core evals we already run
1) Conversation memory eval
   - Compare semantic vs lexical vs fractal retrieval.
   - Includes live probes + low-lex paraphrases.

2) Memory shadow eval
   - Measures embedding shift after memory injection.
   - Ensures memory does not destabilize reasoning.

3) Capsule falsification
   - Corrupt capsules (shuffle, drop, noise).
   - Expected: alignment drops in predictable patterns.

4) Trace identity check
   - Each memory should self-match its stored trace.
   - Confirms geometry is meaningful, not random.

## Where the evidence lives
- Proof packets:
  - `docs/proof/memory_capsule_evidence_report.md`
  - `docs/proof/memory_capsule_replication_checklist.md`
  - `docs/proof/fractal_core_proof.md`
- Run outputs:
  - `artifacts/observability/` (reports and summaries)
  - `storage/observability/` (raw eval JSONs)

## How we re-run (copy/paste)
- Conversation memory eval:
  - `python scripts/conversation_memory_eval.py --live --dataset fram_eval/data/conversation_memory_live_probes.jsonl`
- Memory shadow eval:
  - `python scripts/memory_shadow_eval.py --live`
- Capsule falsification:
  - `python tools/falsify_capsule.py storage/memory/capsules/<capsule>.json --json`
- Trace identity:
  - `python scripts/fractal_trace_identity_check.py`

## 30-second story you can tell
We log every turn, store full capsules, and persist trace geometry. We test memory recall against paraphrase probes, confirm that corrupted capsules reduce alignment, and verify that memories self-match their own traces. This gives us functional continuity today. KV access is next for validation and finer granularity, but the core memory behavior already holds under falsification.
