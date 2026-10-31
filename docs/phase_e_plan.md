# Phase E - Retention Curve & Forgetting (Draft)

This is the scaffolding plan for Phase E. Behaviour remains unchanged until the gates flip on.

## Goals (foundation only)
- Introduce config knobs for retention/decay while keeping current outputs identical by default.
- Add stub helpers for retention curves and forgetting so downstream callers can wire them in safely later.
- Land initial tests that document the placeholders (xfail for future behaviour) and prove gating defaults to no-op.

## Config (FRAMConfig)
- `enable_retention_curve` (bool, default `False`)
- `enable_decay` (bool, default `False`)
- `retention_half_life_days` (float, default `30.0`)
- `forgetting_half_life_days` (float, default `30.0`)
- `enable_hard_forgetting` (bool, default `False`)
- `hard_forgetting_mode` (str, `"dry_run"` or `"enforce"`, default `"dry_run"`)
- `forgetting_threshold` (float, default `0.05`)
- `min_active_items` (int, floor on active memory entries, default `100`)

All gates default to OFF; half-life values are placeholders to shape upcoming decay curves.

## Stubs (now wired as no-op by default)
- `fram_serving.memory.retention_curve.compute_retention_score(age_seconds, config)`  
  - Exponential decay keyed to `retention_half_life_days`; returns `1.0` when the gate is off or age is unknown.
- `fram_serving.memory.retention_curve.apply_retention_curve(scores, timestamps, config)`  
  - Applies `compute_retention_score` element-wise; returns the input unchanged when `enable_retention_curve` is `False` (current default).
- `fram_serving.memory.forgetting.apply_forgetting(candidates, config)`  
  - Returns candidates unchanged when `enable_decay` is `False` (current default).
- `fram_serving.memory.forgetting.compute_decay_factor(age_seconds, config)`  
  - Exponential decay keyed to `forgetting_half_life_days`; returns `1.0` when the gate is off or age is unknown; clamped to `[0.1, 1]`.
- `fram_serving.memory.forgetting.decide_forgetting(...)`  
  - Computes hard-forgetting decisions (KEEP/DRY-RUN/ENFORCE) using retention/decay scores, thresholds, mode, and minimum-active guardrails. Defaults to KEEP unless the hard-forgetting gate and thresholds permit pruning.

## Tests (placeholders)
- `tests/test_phase_e_placeholders.py`:
  - xfail smoke for retention/forgetting effects (documents the future contract).
  - Passing meta-test asserting defaults stay disabled and stubs are identity when gates are off.

## Next steps (future sessions)
- Shape the retention curve (exponential decay keyed to half-life) against cognitive timestamps.
- Wire forgetting into cognitive memory ranking and traces.
- Add observability for retention/decay weights and calibration hooks.
