# Logistic alpha Controller - Phase D Specification

## Purpose
- Provide a dynamic scalar alpha_t that controls blending between local and global recall paths.
- Let alpha_t evolve over time via logistic map dynamics so recall can switch between stable and exploratory regimes.
- Categorize behavior into conceptual "color states" so operators can reason about expected trajectories without inspecting raw numbers.

This document is informational only. No code or runtime logic should be derived directly from it until Phase D implementation is approved.

## Equation (informational only)
alpha_{t+1} = r * alpha_t * (1 - alpha_t)

- This is the classic logistic map.  
- Future code must treat it as a spec reference only; do **not** implement the recurrence until Phase D is active.

## Parameter Definitions
- `r`: Controls the logistic-map regime, which maps directly to the color zones below. Higher values push toward chaotic behavior.
- `alpha_0`: Initial value. Phase D will later decide whether to use a fixed default or a seeded draw.
- `t_max`: Maximum number of steps to generate. Conceptual ranges come from the color table and keep trajectories bounded.

## Conceptual Color Zones

| Color | r Range | t_max Range | Description |
|-------|---------|-------------|-------------|
| Blue | 2.4 <= r < 2.8 | 10-20 | Stable regime that quickly converges to a fixed point; suitable for conservative recall. |
| Green | 2.8 <= r < 3.2 | 15-30 | Oscillatory regime with shallow cycles; good for periodic revisits. |
| Yellow | 3.2 <= r < 3.57 | 25-50 | Bifurcation region with branching trajectories; enables divergent recall while remaining structured. |
| Red | r >= 3.57 | 30-80 | Chaotic regime. Exploration-heavy and requires capped depths to avoid runaway behavior. |

These bands are conceptual scaffolding for tests and defaults; they are not enforced until Phase D behavior ships.

## Observability Fields
- `logistic_state_color` (`str`): Reports the active color zone (`"blue"`, `"green"`, `"yellow"`, `"red"`). Defaults to `None` until Phase D logic populates it.
- `logistic_alpha_preview` (`list[float]`): Optional truncated preview of alpha_t values to help operators inspect trajectories.

## Integration Points
- `scoring/_fractal_trace_scores_phase_d.py` (placeholder module where the controller will live).
- `config.phase_d.logistic_r`
- `config.phase_d.logistic_t_max`

This spec must stay synchronized across branches; treat it as the canonical reference for all logistic-alpha controller work in Phase D.
