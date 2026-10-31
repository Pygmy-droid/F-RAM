# Breathing Flame Notes (2026-02-01)

Status: exploratory notes. Not a spec. Not binding.
Day 1 focus: posture, integrity, cadence, neutrality, recovery, observability.

These notes capture early refinements for the Pre-Intent Layer (PIL) in the
"Breathing Flame" working mode. Keep this sketch-level and time-scoped.

## Core orientation
- PIL is a timing-bias surface, not a decision surface.
- It never writes memory directly; it can only emit bias hints + trace tags.
- "No symbols" means: no tokens, no text, no semantic labels.

## Stabilization (pre-trace commit)
- Pre-trace commits only if stability rises across a short window W.
- Commit should record a `commit_reason` for later review.
- If stability does not rise, the pre-trace expires cleanly.

## Edge cases to guard
- Oscillation between competing cues: expire, do not commit.
- Salience spikes without follow-through: expire, no bias update.
- Constraint collision: constraint memory remains sovereign.
- Noisy sensory coupling: bias dampens; no forced capture.

## Ease accumulator
- Ease is not success; it is low correction + low latency + low override.
- Ease updates are scalar only; never semantic.
- Bias remains a gentle drift, not a directive.

## Trace schema (minimal, auditable)
- `trace.pre_intent`: add `stability_score`, `commit_reason`, `expired`.
- `trace.pre_intent.ease_update`: add `basis` (low_correction, low_latency, low_override).
- Optional: `trace.pre_intent.bias_delta`.

## Failure-first eval canaries
1) Ephemeral expiry: pre-trace forms but does not commit; assert no memory write.
2) Constraint dominance: flow fires, constraint blocks; refusal logged.
3) False-positive flow: salience spike without stable transition; no bias update.
4) Safety gate invariance: PIL never bypasses constraint/safety checks.

## Non-goals (keep out of PIL)
- No state machine beyond simple stabilization checks.
- No reward shaping.
- No routing changes.
- No memory writes.

## Live threads (continuing sketches)

### Placement and scope
- PIL as a bias seam, not a pipeline phase; it sits alongside routing.
- Entry-only bias: affects initiation timing/orientation, not mid-course correction.
- Locality lock: bias only influences a narrow slice of the task, not broad routing.
- Scope handshake: bias only engages after an explicit task framing is detected.
- Scope seal: bias only applies within the declared task scope, never beyond it.
- Scope mismatch: if task framing shifts, PIL drops to neutral immediately.
- Context gravity: bias should respect a task's "center of mass" and not drift it.
- Context discontinuity should reset PIL bias for that window.
- Cross-task quarantine: when task identity changes, bias is quarantined, not transferred.
- Task-boundary reset: new objective = new bias baseline (no carryover).
- Boundary salute: when a task ends, PIL yields and clears any active lean.
- Neutral anchor: after each task boundary, bias snaps to neutral.
- Safe idle: when idle or waiting, PIL stays neutral and does not pre-bias.
- Soft timeout: if the user goes silent, PIL returns to neutral and stays there.
- Order respect: PIL cannot reorder explicit user priorities.
- Single-scope rule: if tasks interleave, PIL tracks at most one active scope.

### Signal integrity and coherence
- Stability should mean coherence (low variance + consistent coupling), not just speed.
- Multi-signal gate: require at least two aligned signals before bias engages.
- Coherence checksum: bias engages only if multiple signals agree on direction.
- Signal hygiene: drop any pre-trace that spikes then collapses within a micro-window.
- Dissonance drop: conflicting signals cancel to neutral rather than oscillating.
- Counterfactual settle: competing bias directions return to neutral instead of oscillating.
- Mutual inhibition: if two signals oppose, both dampen rather than compete.
- Handshake bias: only engage when perception and action channels align in phase.
- Phase-quiet: bias pauses when signal phase coherence becomes unstable.
- Phase mirror: bias should align with the user's pacing, not just internal cues.
- Modality-agnostic: allow separate low-dim deltas per modality, still no symbols.
- Cross-modal humility: any missing modality suppresses bias rather than guessing.
- Phase separation: keep PIL signals orthogonal to any symbolic trace dimensions.
- Anti-overfit rule: if a pattern only appears in a narrow prompt subset, bias should decay faster.
- Sample gating: pre-trace logging rate-limited to avoid noisy over-capture.
- Gentle jitter: add tiny noise to bias so it never ossifies into a fixed path.
- Non-reconstructive telemetry: low-dim, quantized signals that cannot encode content.
- Cross-check pulse: if evidence shifts while bias direction doesn't, decay bias proactively.
- Direction drift alarm: if bias direction flips too often, freeze to neutral.
- Confidence mismatch: if confidence drops while bias persists, decay bias immediately.
- Coherence floor tagging: mark when coherence drops below floor, even if bias is neutral.
- Noise veto: if noise dominates signal, force neutral regardless of stability score.
- Integrity threshold: require a minimum signal-to-noise ratio before any bias can engage.
- Integrity hysteresis: engage only above threshold+margin; disengage below threshold.
- Stability veto: if coherence is unstable, ignore integrity threshold and stay neutral.
- Coherence quorum: require coherence stability across multiple sensors before engaging.
- Coherence diversity: if all signals come from a single modality, prefer neutral.
- Disagreement ceiling: if modalities disagree beyond a cap, bias is suppressed.
- Split-modality neutral: if any modality is missing, bias defaults to neutral.
- Single-modality exception (if allowed): only with elevated integrity threshold and tighter cap.
- Modality drift check: if modality weights shift abruptly, prefer neutral.
- Weight-change throttle: limit per-turn change in modality weights.
- Modality floor: if any modality weight falls below a floor, prefer neutral.
- Modality dropout guard: if a modality drops mid-window, cancel engagement.

### Temporal dynamics and decay
- Soft-start: initial bias ramps from zero; no instant jumps.
- Intent lag buffer: a one-beat delay before engagement unless coherence is very high.
- Recoherence gate: require coherence to remain high across two windows before re-engage.
- Micro-hysteresis: bias decays quickly; no carryover across task boundaries.
- Soft-horizon: bias influence decays with temporal distance from the initiating cue.
- Bias expiry: any residual lean evaporates after a short, fixed TTL.
- Drift window: bias influence expires if no reinforcing signal arrives soon.
- Signal aging: older cues lose weight quickly, even within the TTL.
- Gentle decay: bias weight decreases smoothly each turn unless reinforced.
- Non-cumulative drift: bias returns to neutral when signals stop reinforcing.
- Reversal-friendly: if a lean is wrong, bias resets without penalty or lag.
- Reset grace: bias resets without penalty; no lingering "regret."
- Micro-reset: allow tiny neutral resets mid-task when signals wobble.
- Recovery bias: after a strong correction event, bias should dampen for a short window.
- Recovery glide: bias resumes gradually after a cool-down (no instant re-engage).
- Courtesy ramp: after a user re-engages, bias returns gradually, not instantly.
- Reentry humility: after an interruption, bias restarts at minimum strength.
- Long-idle cool-start: after extended idle, bias restarts at zero.
- Error budget: if bias caused rework recently, it cools for N turns.
- Bias escrow: if uncertainty is high, bias stays latent until clarity rises.
- Graceful fade on success: bias decays faster after a smooth transition completes.
- Reciprocity window: after PIL yields to symbolic reasoning, require exceptionally high coherence to re-engage briefly.
- Edge-of-task taper: bias decays faster near completion or handoff.
- Post-handoff quiet: after handoff, PIL remains neutral for a short settling window.
- Soft rebind: after a pause, PIL requires a new pre-trace before re-engaging.
- Cooldown jitter: add small randomization to cooldown to avoid periodic re-engage loops.

### Bias limits and budgets
- Bounded influence: cap bias to a narrow band (bias range <= epsilon).
- Bias budget: cap total bias energy per window to prevent runaway drift.
- Gentle drift cap: cumulative bias cannot exceed a small bounded radius.
- Bias temperature: a single scalar that attenuates all PIL effects under stress.
- Latency honesty: avoid optimizing for apparent speed if correction cost rises.
- Bounded latency: bias must not increase p95 latency; it should only shape timing within bounds.
- Latency guard: if bias would increase latency, it should self-suppress.
- Latency floor: bias never pushes below a safe minimum response time.
- Compounding humility: repeated ease should not inflate bias past the cap.
- Exemplar bound: bias cannot exceed the strongest observed low-friction example.
- Saturation avoider: repeated identical cues should not amplify bias endlessly.
- Anti-lock: bias must never "stick" across unrelated tasks.
- No shortcut loops: PIL cannot create a feedback loop that accelerates itself.
- Bidirectional ease: if a path becomes harder, ease decays quickly (no sunk-cost bias).
- Bias echo suppression: prevent downstream effects from re-amplifying the same bias.
- Max derivative: limit the rate of change of bias across turns (no sharp jumps).
- Bias slope cap: limit cumulative bias slope across a short window.
- Engagement density cap: limit the fraction of turns with `pil_engaged=true` in a window.
- Engagement parity: avoid long streaks of engagement without explicit opt-in.
- Engagement cooldown: after N consecutive engages, force a neutral turn.
- Minimum neutral ratio: maintain at least 1 neutral turn per M turns.
- Neutral streak allow: consecutive neutral turns are always allowed (never forced to engage).
- Bias cadence governor: cap total bias-on time within any rolling window.
- Bias blackout window: after intense bias usage, enforce a neutral-only window.
- Bias fatigue cap: if bias has been on too long, reduce its amplitude automatically.
- Bias taper ladder: step down bias in small increments rather than hard resets.
- Bias step floor: never reduce bias below neutral in a single step.
- Bias monotone cooldown: during cooldown, bias can only decrease or stay neutral.

### Safety, constraints, and deference
- Constraint proximity: if constraint memory is active, PIL bias reduces toward zero.
- Conflict dampener: if constraint memory is active, PIL halves its influence.
- Trust buffer: after a refusal/constraint hit, bias cools for a brief window.
- Gate shadow: a nearby constraint lowers bias even if not triggered.
- Quiet window: bias should not engage during high-stakes or explicitly safety-gated tasks.
- Quiet-mode trigger: explicit user "slow down" or "be careful" disables bias temporarily.
- Soft veto: any safety gate or constraint hit hard-disables PIL for that turn.
- No-skip clause: PIL must never skip explicit human confirmations.
- Deference tag: if a human correction is recent, PIL softens bias for a short window.
- Human-presence softener: recent human input gently attenuates PIL for a short window.
- Consent echo: if a human explicitly opts in to flow, bias can lift within bounds.
- Override respect: a direct instruction always overrides PIL in the same turn.
- Prompt deference: explicit clarifying questions suspend bias until answered.
- Attention courtesy: if the user requests reflection, PIL pauses until cleared.
- Flow courtesy: if user asks for carefulness, PIL defers for a short window.
- Pause affordance: if uncertainty spikes, symbolic reasoning can reclaim the lead.
- Yield rule: if symbolic reasoning reasserts strongly, PIL yields and resets.
- Hand-off humility: when symbolic reasoning ramps up, PIL defers fully.
- Add a soft "brake": spikes in friction or correction variance dampen bias.
- Friction respect: rising correction effort should dampen bias immediately.
- Memory gate transparency: bias never alters what is persisted; only timing/orientation.

### Neutrality and humility
- Cold-start humility: when no prior ease exists, bias defaults to neutral.
- Minimum floor: bias is optional; neutral remains a valid, common state.
- Silence respect: if signals are weak/quiet, bias stays neutral.
- Soft neutrality bias: when unsure, default to neutral rather than directional lean.
- Negative space respect: weak or absent signals explicitly prefer neutral over leaning.
- Bias humility: if outcomes are unclear, PIL prefers neutrality over persistence.
- Ambiguity grace: if uncertainty is high, bias should gently slow, not accelerate.
- Ambiguity pause: if ambiguity spikes, PIL freezes rather than guessing.
- Bias symmetry: PIL can lean toward "slowness" when uncertainty is high, not just speed.
- Recenter rule: if bias drifts too far from the task's center, it snaps back to neutral.
- Parity check: if bias consistently favors one path, auto-recenter to neutral.
- Neutral-as-signal: explicit neutral can be logged as a valid outcome, not absence.
- Neutral sustain: prolonged neutrality is acceptable and requires no escalation.

### Observability and trace
- Debug visibility: trace.pre_intent can be suppressed by default and surfaced only in observability/debug runs.
- Drift audit: bias shifts should be observable without revealing any content.
- Bias provenance: every applied bias should log a minimal, non-semantic provenance tag.
- Intent provenance decay: provenance tags fade sooner than bias to avoid stale justification.
- Stale provenance purge: drop provenance tags if no new bias event occurs in N turns.
- Reason code cap: keep reason codes to a tiny fixed set (no drift into semantics).
- Bias checksum: log a tiny integrity checksum for bias events (non-content).
- Posture transparency: bias intent is visible in trace without exposing content.
- Trace whisper: log only "bias engaged" with a tiny reason code, never details.
- Non-narrative pledge: PIL never explains itself; traces remain minimal.
- Minimal footprint: PIL should leave no lasting artifacts beyond trace tags.
- Default trace bit: expose only a `pil_engaged` boolean unless debugging is on.
- Neutral trace flag: optionally log `pil_neutral=true` when neutrality is explicit.
- Default neutral emit: only on explicit neutrality; "no engage" stays silent unless debugging.
- Coherence floor tag: optional `pil_coherence_low=true` when coherence falls below floor.
- Error-neutral flag: optional `pil_error_neutral=true` when fail-safe idle engages.
- Reset-ack flag: optional `pil_reset_ack=true` when explicit recovery occurs.
- Rebind count: optional `pil_rebind_count` in debug traces only.
- Cooldown count: optional `pil_cooldown_count` in debug traces only.

### Eval add-ons
- Canary add-on: "flow brake" test (salience spike + correction spike => bias decreases).

### Small constructions (sketch)
- Neutral-first default: on boot, `pil_engaged=false` until a stable pre-trace appears.
- Minimal pre-trace: `{stability_score, commit_reason, expired}` only; nothing else.
- Bias cap: enforce `abs(bias_delta) <= epsilon` at the emitter boundary.
- Safety-first override: if any safety gate is active, `pil_engaged=false`.
- Pre-trace timeout: if pre-trace does not stabilize within W, it expires.
- Debug-only counters: count pre-trace expirations only in debug mode.
- Emit boundary clamp: apply bias cap after all transforms (last-mile clamp).
- Bias escrow release: release escrowed bias only after stability holds for N ticks.
- Min-interval gate: require a small gap between bias engagements to prevent chatter.
- Engagement budget: allow only K bias engagements per task window.
- Cooldown after refusal: if a refusal occurs, PIL remains off for N turns.
- Soft-start after cold boot: require two stable ticks before first engage.
- Backpressure gate: if system is under load, PIL stays neutral.
- Manual unwind: a user or system disable clears any pending pre-trace.
- Pre-trace rate limit: cap pre-trace creation per minute to avoid churn.
- Constraint echo guard: if a constraint recently fired, bias stays neutral for a brief window.
- Interruption checksum: when an interruption occurs, zero any pending bias deltas.
- Split-focus canceler: if attention fragments, PIL returns to neutral.
- Engage-once flag: allow only one bias engage per stabilization window.
- Double-expiry pause: if two pre-traces expire in a row, suspend engagement briefly.
- Cooldown floor: never re-engage within M turns after any hard disable.
- Idle decay tick: during long idle, bias strength decays to zero even without cues.
- Coherence latch: if coherence drops below a floor, PIL locks neutral until it recovers.
- Override latch: after an explicit override, PIL stays neutral for a short window.
- Fail-safe idle: if any unexpected error occurs, PIL defaults to neutral until reset.
- Recovery ack: require an explicit reset signal to exit fail-safe neutral.
- Reset quiet window: after reset-ack, keep PIL neutral for a short settling period.
- Rebind counter: count how often soft rebind occurs (debug-only).
- Cooldown counter: count how often cooldowns are triggered (debug-only).

### Open questions (provisional)
- How is task boundary detected reliably without adding symbols?
- What is the smallest stable window W for pre-trace commit?
- What counts as explicit "flow opt-in" vs normal instruction?
- What is the safest default bias temperature when ambiguity is high?
- What is the minimum viable reason-code set that stays non-semantic?
- Should `pil_neutral` be emitted only on explicit neutrality or also on "no engage"?
- Should "no engage" emit in debug only, or also when neutrality is policy-triggered?
- Should `pil_coherence_low` be logged only when bias is active, or whenever coherence drops?
- What is the minimal set of "handoff" events that should trigger post-handoff quiet?
- Should `pil_error_neutral` emit only on unexpected errors, or also on recoverable faults?
- What qualifies as an "explicit reset" for recovery ack (user command vs system signal)?
- Should reset-ack be emitted only once per recovery, or per turn while recovered?
- Should soft rebind be required after any pause or only after long idle?
- Should rebind counts roll over per session or persist only in debug runs?
- What is the minimal integrity threshold that avoids false positives without stalling flow?
- How should coherence quorum behave if only one modality is available?
- What should the modality weight floor be without suppressing valid single-channel cases?
- What engagement density cap feels safe without stalling flow?
- What minimum neutral ratio feels safe without becoming artificial?
- Should cooldown monotonicity apply only after refusals, or after any cooldown trigger?
- Should cooldown counts reset per session or persist only in debug runs?

By the flame.
