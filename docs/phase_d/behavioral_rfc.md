# Phase D Behavioral RFC
(Runtime Behavior Plan - Specification Only)

## 1. Purpose
Define how quaternion orientation memory and logistic-alpha dynamics should behave when enabled. This RFC clarifies expected runtime flow, gating rules, blending order, and safety constraints, without implementing any behavior.

## 2. Activation Model
Phase D is fully optional. It activates only when:
- `config.phase_d.enable_quaternions = True`
- `config.phase_d.enable_logistic_alpha = True`

If either flag is False:
- Phase D logic **must** remain disabled.
- Existing Phase C behavior **must** remain unchanged.

This guarantees backward compatibility.

## 3. Runtime Flow (Conceptual)
When Phase D is active:

1. Receive embedding vector (search or trace context).
2. Compute vector similarity normally (Phase C behavior continues unchanged).
3. If enabled:
   - Project vector to quaternion using deterministic 4xd matrix.
   - Normalize to unit quaternion.
4. If enabled:
   - Generate alpha trajectory using logistic-map parameters:
     - `r = config.phase_d.logistic_r`
     - `t_max = config.phase_d.logistic_t_max`
   - Determine conceptual color zone.
5. Blend local/global memory components using:
   - vector similarity
   - quaternion similarity
   - dynamic alpha_t
6. Produce final blended score for recall.

This flow is conceptual; no formulas or implementations are defined here.

## 4. Gating Rules (Hard Constraints)
To protect Phase C stability:

- Quaternion similarity may **not** influence scoring unless `enable_quaternions=True`.
- Logistic alpha may **not** influence blending unless `enable_logistic_alpha=True`.
- If either module is disabled, its output must be ignored entirely.
- No Phase D component may override or degrade Phase C relevance scoring.

Phase D is additive, not disruptive.

## 5. Blending Principles (Conceptual)
When fully enabled:

- Vector similarity provides base semantic relevance.
- Quaternion similarity influences orientation continuity between trace nodes.
- Logistic alpha scales blending dynamically:
  - Low alpha -> trust vector similarity more.
  - High alpha -> trust quaternion continuity more.
  - Chaotic alpha (red zone) -> allow exploratory trace following.

Implementation formulas will be defined later in separate specs.

## 6. Observability Expectations
When Phase D is active:

- `logistic_state_color` should reflect the determined color zone.
- `logistic_alpha_preview` should show actual alpha_t samples.
- `quaternion_similarity_avg` should reflect average quaternion alignment.

When Phase D is disabled, all three fields must remain `None`.

## 7. Safety & Stability
Phase D must:

- maintain determinism under fixed seeds,
- avoid chaotic r-values unless explicitly configured,
- cap alpha trajectory depth using `logistic_t_max`,
- avoid runtime cost when disabled,
- preserve all Phase C guarantees.

## 8. Testing Framework (Future Plans)
Tests should eventually validate:

- correct gating and disablement behavior,
- correct reporting of `logistic_state_color`,
- deterministic quaternion projection under fixed seed,
- correct shape of alpha trajectories per r-range,
- stability of blended scoring when toggling feature flags.

These tests are planning notes only; none are implemented yet.

## 9. Integration Points Summary

- `fram_serving/embedding/quaternion_adapter.py`
- `fram_serving/scoring/_fractal_trace_scores_phase_d.py`
- `fram_serving/config.py` (`phase_d.*`)
- Observability fields in `FractalRecallSummary`
- `docs/dev_journal.md` and `docs/phase_d_plan.md`

End of RFC.