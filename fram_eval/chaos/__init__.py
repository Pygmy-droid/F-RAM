"""Deterministic mathematical core for the recovered Chaos Playground."""

from fram_eval.chaos.complex import ComplexBounds, julia_escape, mandelbrot_escape
from fram_eval.chaos.diagnostics import (
    detect_orbit_period,
    feigenbaum_delta_estimates,
    logistic_lyapunov,
    logistic_superstable_parameters,
)
from fram_eval.chaos.geometry import (
    RadiusRule,
    RotationalEncodingV1,
    RotationalPair,
    rotational_accumulation,
)
from fram_eval.chaos.lift import (
    LIFT_REPORT_V1,
    TrajectoryLiftReport,
    WindowedLiftResult,
    trajectory_digest,
    windowed_lift_trajectory,
)
from fram_eval.chaos.scene import (
    CHAOS_MATH_V1,
    SCENE_SCHEMA_V1,
    SceneV1,
)
from fram_eval.chaos.systems import SYSTEMS, SystemKind, SystemSpec, get_system, simulate

__all__ = [
    "CHAOS_MATH_V1",
    "LIFT_REPORT_V1",
    "SCENE_SCHEMA_V1",
    "SYSTEMS",
    "ComplexBounds",
    "RadiusRule",
    "RotationalEncodingV1",
    "RotationalPair",
    "SceneV1",
    "SystemKind",
    "SystemSpec",
    "TrajectoryLiftReport",
    "WindowedLiftResult",
    "detect_orbit_period",
    "feigenbaum_delta_estimates",
    "get_system",
    "julia_escape",
    "logistic_lyapunov",
    "logistic_superstable_parameters",
    "mandelbrot_escape",
    "rotational_accumulation",
    "simulate",
    "trajectory_digest",
    "windowed_lift_trajectory",
]
