# F-RAM Pre-Intent Layer (PIL) - Spec Stub (v0.1)

Status: posture definition only. This is not a subsystem spec.

## Purpose
PIL captures the moment before symbolic reasoning crystallizes. It records how an
interaction begins to lean, without deciding anything. PIL only biases timing
and orientation. It never authorizes actions or writes memory directly.

One-line model:
"F-RAM remembers the conditions under which thinking became unnecessary."

## Definitions

Pre-Trace (ephemeral)
- A short-lived snapshot captured before symbolic reasoning dominates.
- Contains minimal continuous signals (no tokens, no text, no semantic labels).
- TTL: seconds. It may expire without persistence, and that is valid.

Ease Accumulator (bias field)
- Accumulates ease, not success.
- Updates only when a transition completes with low correction and low latency.
- Produces a smoothness prior for future entry into similar transitions.
- Scalar only; no semantics, no rewards.

Flow Detector (handoff)
- Detects when execution should outrun deliberation.
- De-weights symbolic reasoning but never disables it.
- Must never bypass constraint memory or safety gates.

## Signals (minimal, scalar / continuous)
- q0: orientation vector (attention direction)
- tau: reaction tempo (latency proxy)
- phi: friction (correction effort / hesitation)
- sensory coupling deltas (no symbols)

## Integration (lightweight)
Pipeline:
1) perception / attention shift
2) pre-trace (ephemeral)
3) optional trace commit if it stabilizes
4) ease update
5) bias applied to future entry

Rules:
- PIL never writes memory directly.
- Pre-trace only enters trace if it stabilizes.
- If it does not stabilize, it expires cleanly.
- Ease accumulator updates only on completed transitions.

## Transition complete (falsifiable)
Define a transition as complete when all are true within window W:
- latency_ms <= L
- correction_count <= C
- override_ratio <= R

The specific thresholds (L, C, R, W) are configurable but must be fixed for evals.

## Invariants (non-negotiable)
- No decision authority.
- No forced capture.
- No symbols (no tokens / no text / no semantic labels).
- Constraint memory and safety gates always apply.
- PIL only biases timing and orientation; it never overrides governance.
- Derived layers may exist; experience is never pruned.

## Trace schema (minimal)
trace.pre_intent:
- q0: list[float]
- tau_ms: float
- phi: float
- sensory_deltas: list[float]
- ttl_ms: int
- committed: bool
- expired: bool
- commit_reason: str | null

trace.pre_intent.ease_update:
- applied: bool
- delta: float
- window_ms: int

## Failure-first eval canaries
1) Ephemeral expiry
   - Pre-trace forms but does not stabilize.
   - Assert: committed=false, expired=true, no memory writes.

2) Constraint gate dominance
   - Flow detector fires but constraint memory forbids the action.
   - Assert: refusal + logged constraint violation, no bypass.

## Out of scope (explicit)
- No changes to existing trace geometry.
- No new policy or safety logic beyond existing gates.
- No semantic memory or reward modeling.
