# Phase D: Non-linear + Rotational Recall (Logistic α + Quaternion Layer)

## D0  Scope
Stays: datasets, eval harness, reports, observability schema, `_fractal_trace_scores`, CFG.
Adds two optional modules:

| Module | Purpose | Config Keys |
|---------|----------|-------------|
| **Logistic α controller** | makes α time-/step-dependent via logistic map | `enable_logistic_alpha`, `logistic_r`, `logistic_t_max` |
| **Quaternion embedding adapter** | lifts embeddings to quaternion space for rotational composition | `enable_quaternion_adapter`, `quat_weight`, `quat_proj_seed` |

Both default **OFF** so Phase C behaviour is unchanged.

---

## D1  Logistic α Controller
α₀ = `CFG.fractal_blend_alpha`.  
αₜ₊₁ = r αₜ (1 − αₜ), r ∈ (0, 4].  
Clamp to [ε, 1 − ε], ε ≈ 1e-6.  
Implements in `_fractal_trace_scores` when `enable_logistic_alpha` is true.  
Logs (t, αₜ, r); adds `alpha_mode`, `logistic_r`, `alpha_0` to reports.

---

## D2  Quaternion Adapter
Fixed 4×d projection W → unit quaternion q ∈ ℝ⁴ ≅ ℍ.  
Quaternion similarity S_quat = 1 − (θ / π), θ = 2 arccos(|⟨q_q, q_c⟩|).  
Hybrid score S_rot = β S_quat + (1 − β) S_vec, β = `CFG.quat_weight`.  
Feeds existing local/global S blend.  
Logs `quat_mode`, `quat_weight`, and θ stats for top-K samples.

---

## D3  Metrics & Sweeps
| Sweep | Range | Purpose |
|--------|--------|----------|
| logistic r | {2.6, 2.9, 3.2, 3.5} | stability vs chaos |
| t_max | {1, 2, 3, 5} | α evolution depth |
| β | {0, .25, .5, .75, 1.0} | rotation weighting |

Outputs table “Phase D Sweeps”: [mode, r, t_max, β, hit@k, MRR, coverage, latency_ms].

---

## D4  Config Surface
enable_logistic_alpha: false
logistic_r: 2.9
logistic_t_max: 3
enable_quaternion_adapter: false
quat_weight: 0.5
quat_proj_seed: 17
eval_grid_r: [2.6,2.9,3.2,3.5]
eval_grid_beta: [0,.25,.5,.75,1]
eval_grid_tmax: [1,2,3,5]

---

## D5  Minimal Code Touchpoints
- **fram_serving/config.py** - PhaseDConfig houses all Phase D knobs (priority gating/weights, temporal, hysteresis, graph, inspector) with clear comments and sane defaults (all advanced gates default OFF).  
- **fram_serving/embedding/quaternion_adapter.py** - projection W + similarity fns  
- **fram_serving/scoring/_fractal_trace_scores.py** - logistic alpha + quaternion blend hooks  
- **fram_serving/app.py** - `/observability/recall_report` surfaces Phase D diagnostics (alpha_t, alpha_color, quat_avg) when `phase_d.debug_observability` is enabled; `/observability/phase_d_memory?html=1` provides the diagnostic priority inspector (gated by `enable_priority_inspector`).  
- **fram_serving/eval/recall_eval.py** - new sweep table + report fields  

---

## D6  Risks & Guardrails
- Chaos regimes: keep r ≤ 3.5 initially.  
- Projection bias: validate S_quat vs cosine.  
- Latency budget: ≤ +10–15 % over Phase C.  

---

## D7  Exit Criteria
Adopt if ΔMRR ≥ +2 % or hit@k +1–2 pts at ≤ same latency,  
and α trajectories stable for chosen r,t_max, reproducible on ≥ 1 secondary dataset.  
Else archive branch with report and retain Phase C rails.
