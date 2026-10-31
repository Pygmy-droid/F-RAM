# Phase D Implementation Roadmap
(High-level, staged plan - no logic)

## Purpose
Define the recommended sequence for implementing Phase D, ensuring:
- stability,
- reproducibility,
- zero impact on Phase C,
- and clear incremental milestones.

The roadmap converts concept -> structure -> safe implementation phases.

---

# Stage 0 - Completed Scaffold (Current)
These items are already implemented:
- Placeholders:
  - `quaternion_adapter.py`
  - `_fractal_trace_scores_phase_d.py`
- Config model:
  - `enable_quaternions`
  - `enable_logistic_alpha`
  - `quat_proj_seed`
  - `logistic_r`
  - `logistic_t_max`
  - `logistic_state_reporting`
- Observability placeholders:
  - `logistic_state_color`
  - `logistic_alpha_preview`
  - `quaternion_similarity_avg`
- Documentation:
  - `logistic_alpha_spec.md`
  - `quaternion_adapter_spec.md`
  - `behavioral_rfc.md`
  - `phase_d_plan.md`
  - `dev_journal.md`
  - system diagram

Phase D is fully scaffolded and inert.

---

# Stage 1 - Low-Risk Logic Foundations
Implement the following components, strictly behind feature flags:

### 1. Quaternion Projection
- Generate deterministic 4xd matrix via seed.
- No orthonormalization in Phase D.
- Implement `to_quaternion(x)`: normalize projected vector.

### 2. Basic Quaternion Similarity
- Use dot-product or unit quaternion angle.
- Add placeholder test: "similar orientation increases score."

### 3. Logistic Alpha Trajectory
- Implement alpha_{t+1} = r * alpha_t * (1 - alpha_t).
- Enforce `t_max` cap.
- Determine conceptual color zone.

All behavior must remain dormant unless flags are enabled.

---

# Stage 2 - Blending Layer
Integrate Phase D signals into recall scoring:

- Define `combine_quaternion_similarity(vec_sim, quat_sim, beta)` in stub.
- Define logistic-weighted blending:
  - `blended = alpha_t * quat_sim + (1 - alpha_t) * vec_sim`
- Keep blending gated by config flags.

Add observability reporting:
- `logistic_state_color`
- `logistic_alpha_preview`
- `quaternion_similarity_avg`

---

# Stage 3 - Trace-Aware Enhancements (Optional)
Introduce enhancements such as:

- quaternion-based trace continuity scoring,
- orientation-aware step-to-step transitions,
- alpha-driven path exploration (yellow/red zones).

This stage is optional until Phase C stability is reconfirmed.

---

# Stage 4 - Evaluation + Stability Pass
After implementation completes:

1. Validate determinism (seed, projection, alpha-sequence).
2. Benchmark performance impact.
3. Verify Phase C metrics remain unchanged when Phase D disabled.
4. Test Phase D across:
   - blue zone (stability)
  - green zone (cycles)
  - yellow zone (bifurcation)
  - red zone (chaos with `t_max` cap)

Add regression tests.

---

# Stage 5 - Merge Path
When Phase D passes evaluation:

- Prepare integration PR.
- Merge `phase-d-dev` back into `main`.
- Tag release (e.g., `v22.1-PhaseD-alpha`).

Until then:
- `main` remains stable.
- `phase-d-dev` remains isolated.

---

## Summary
This roadmap defines the safe, ordered sequence for implementing runtime logic in Phase D. All work remains behind feature flags and must preserve Phase C behavior until explicit activation.

End of roadmap.
