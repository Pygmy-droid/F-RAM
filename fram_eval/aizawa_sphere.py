"""Aizawa flow and an explicitly constructed tangent field on ``S2``.

The ambient Aizawa system and the fixed-shell tangent construction are kept
separate:

``F(x)``
    The autonomous Aizawa vector field on ``R3``.

``V_R(n) = (I - n n^T) F(R n)``
    A new autonomous tangent field on the sphere of declared radius ``R``.
    Its integral curves are not radial projections of Aizawa trajectories.

For the default model with ``d != 0``, the shell field has exactly two zeros,
the north and south z-poles. That result is analytic. Numerical search is
provided only as corroboration, never as a completeness proof.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from fram_eval.fractal_falsification import (
    aizawa_velocity as _canonical_aizawa_velocity,
)


@dataclass(frozen=True)
class AizawaParams:
    a: float = 0.95
    b: float = 0.7
    c: float = 0.6
    d: float = 3.5
    e: float = 0.25
    f: float = 0.1

    def __post_init__(self) -> None:
        values = (self.a, self.b, self.c, self.d, self.e, self.f)
        if not all(np.isfinite(value) for value in values):
            raise ValueError("Aizawa parameters must be finite")


DEFAULT_AIZAWA = AizawaParams()


def _points3(points: np.ndarray | Sequence[float], *, name: str) -> tuple[np.ndarray, bool]:
    value = np.asarray(points, dtype=float)
    scalar = value.ndim == 1
    if scalar:
        value = value[None, :]
    if value.ndim != 2 or value.shape[1] != 3:
        raise ValueError(f"{name} must be shaped (3,) or (n, 3)")
    if not np.all(np.isfinite(value)):
        raise ValueError(f"{name} must contain only finite values")
    return value, scalar


def aizawa_velocity(
    points: np.ndarray | Sequence[float],
    params: AizawaParams = DEFAULT_AIZAWA,
) -> np.ndarray:
    """Evaluate the standard Aizawa vector field on ``R3``."""

    value, scalar = _points3(points, name="points")
    velocity = np.stack(
        _canonical_aizawa_velocity(
            (value[:, 0], value[:, 1], value[:, 2]),
            a=params.a,
            b=params.b,
            c=params.c,
            d=params.d,
            e=params.e,
            f=params.f,
        ),
        axis=-1,
    )
    return velocity[0] if scalar else velocity


def integrate_aizawa_rk4(
    x0: Sequence[float] = (0.1, 0.0, 0.0),
    *,
    dt: float = 0.002,
    steps: int = 10_000,
    params: AizawaParams = DEFAULT_AIZAWA,
) -> np.ndarray:
    """RK4 reference trajectory, returning the initial point plus every step."""

    step_size = float(dt)
    count = int(steps)
    if not np.isfinite(step_size) or step_size <= 0.0:
        raise ValueError("dt must be finite and positive")
    if count < 1:
        raise ValueError("steps must be positive")
    point, _ = _points3(x0, name="x0")
    current = point[0]
    trajectory = np.empty((count + 1, 3), dtype=float)
    trajectory[0] = current
    for index in range(count):
        k1 = aizawa_velocity(current, params)
        k2 = aizawa_velocity(current + 0.5 * step_size * k1, params)
        k3 = aizawa_velocity(current + 0.5 * step_size * k2, params)
        k4 = aizawa_velocity(current + step_size * k3, params)
        current = current + (step_size / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
        if not np.all(np.isfinite(current)):
            raise FloatingPointError(f"Aizawa integration became non-finite at step {index + 1}")
        trajectory[index + 1] = current
    return trajectory


def sphere_tangential_field(
    points: np.ndarray | Sequence[float],
    params: AizawaParams = DEFAULT_AIZAWA,
    *,
    radius: float = 1.0,
) -> np.ndarray:
    """Evaluate ``V_R(n)=(I-nn^T)F(Rn)`` on unit-normalized inputs."""

    shell_radius = float(radius)
    if not np.isfinite(shell_radius) or shell_radius <= 0.0:
        raise ValueError("radius must be finite and positive")
    value, scalar = _points3(points, name="sphere points")
    norms = np.linalg.norm(value, axis=1, keepdims=True)
    if np.any(norms == 0.0):
        raise ValueError("sphere points must be nonzero")
    unit = value / norms
    ambient = aizawa_velocity(shell_radius * unit, params)
    radial = np.einsum("ij,ij->i", ambient, unit)
    tangent = ambient - radial[:, None] * unit
    return tangent[0] if scalar else tangent


def _tangent_frame(point: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    seed = np.array([1.0, 0.0, 0.0]) if abs(point[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    first = seed - np.dot(seed, point) * point
    first /= np.linalg.norm(first)
    return first, np.cross(point, first)


@dataclass(frozen=True)
class FieldDefect:
    point: tuple[float, float, float]
    residual_norm: float
    index: int
    evidence: str


def analytic_shell_defects(
    params: AizawaParams = DEFAULT_AIZAWA,
    *,
    radius: float = 1.0,
) -> tuple[FieldDefect, FieldDefect]:
    """Return the analytically complete shell-zero set when ``d != 0``.

    If ``V_R(n)=0``, then ``F(Rn)=lambda n``. For ``(x,y) != (0,0)``, the
    first two components would require a real eigenvector of

    ``R * ((R z - b) I + d J)``, where ``J`` is a quarter-turn.

    Its eigenvalues have nonzero imaginary part whenever ``R>0`` and ``d!=0``.
    Therefore ``x=y=0``, leaving exactly the two z-poles. The local tangent
    Jacobian at either pole has determinant ``s^2 + (R d)^2 > 0``, so each
    isolated zero has index ``+1``.
    """

    shell_radius = float(radius)
    if not np.isfinite(shell_radius) or shell_radius <= 0.0:
        raise ValueError("radius must be finite and positive")
    if params.d == 0.0:
        raise ValueError("the analytic two-pole result requires d != 0")
    defects: list[FieldDefect] = []
    for z_value in (-1.0, 1.0):
        point = np.array([0.0, 0.0, z_value])
        residual = float(np.linalg.norm(sphere_tangential_field(point, params, radius=shell_radius)))
        defects.append(
            FieldDefect(
                point=(0.0, 0.0, z_value),
                residual_norm=residual,
                index=1,
                evidence="analytic_d_nonzero",
            )
        )
    return defects[0], defects[1]


def _fibonacci_sphere(count: int, rotation: np.ndarray | None = None) -> np.ndarray:
    if int(count) < 32:
        raise ValueError("grid_points must be at least 32")
    index = np.arange(int(count), dtype=float) + 0.5
    z_value = 1.0 - 2.0 * index / count
    radius = np.sqrt(np.clip(1.0 - z_value * z_value, 0.0, None))
    phase = np.pi * (1.0 + np.sqrt(5.0)) * index
    points = np.stack([radius * np.cos(phase), radius * np.sin(phase), z_value], axis=1)
    if rotation is not None:
        matrix = np.asarray(rotation, dtype=float)
        if matrix.shape != (3, 3) or not np.all(np.isfinite(matrix)):
            raise ValueError("grid rotation must be a finite 3-by-3 matrix")
        points = points @ matrix.T
    return points / np.linalg.norm(points, axis=1, keepdims=True)


def _refine_zero(
    seed: np.ndarray,
    params: AizawaParams,
    radius: float,
    *,
    iterations: int = 80,
) -> tuple[np.ndarray, float]:
    point = np.asarray(seed, dtype=float)
    point /= np.linalg.norm(point)
    finite_step = 1e-6
    for _ in range(iterations):
        first, second = _tangent_frame(point)
        velocity = sphere_tangential_field(point, params, radius=radius)
        coordinates = np.array([np.dot(velocity, first), np.dot(velocity, second)])
        if np.linalg.norm(coordinates) < 1e-14:
            break
        jacobian = np.empty((2, 2), dtype=float)
        for column, direction in enumerate((first, second)):
            displaced = point + finite_step * direction
            displaced /= np.linalg.norm(displaced)
            moved = sphere_tangential_field(displaced, params, radius=radius)
            jacobian[:, column] = (
                np.array([np.dot(moved, first), np.dot(moved, second)]) - coordinates
            ) / finite_step
        delta = np.linalg.lstsq(jacobian, -coordinates, rcond=None)[0]
        delta_norm = float(np.linalg.norm(delta))
        if delta_norm > 0.25:
            delta *= 0.25 / delta_norm
        point = point + delta[0] * first + delta[1] * second
        point /= np.linalg.norm(point)
    residual = float(np.linalg.norm(sphere_tangential_field(point, params, radius=radius)))
    return point, residual


def poincare_index(
    point: Sequence[float],
    params: AizawaParams = DEFAULT_AIZAWA,
    *,
    radius: float = 1.0,
    loop_radius: float = 1e-3,
    samples: int = 720,
) -> int:
    """Numerically corroborate the local winding index around one zero."""

    center, _ = _points3(point, name="defect point")
    center = center[0]
    center /= np.linalg.norm(center)
    first, second = _tangent_frame(center)
    phase = np.linspace(0.0, 2.0 * np.pi, int(samples), endpoint=False)
    ring = center + loop_radius * (
        np.cos(phase)[:, None] * first + np.sin(phase)[:, None] * second
    )
    ring /= np.linalg.norm(ring, axis=1, keepdims=True)
    velocity = sphere_tangential_field(ring, params, radius=radius)
    angles = np.arctan2(velocity @ second, velocity @ first)
    increments = (np.diff(np.concatenate([angles, angles[:1]])) + np.pi) % (2.0 * np.pi) - np.pi
    return int(np.round(increments.sum() / (2.0 * np.pi)))


def numerical_shell_zero_corroboration(
    params: AizawaParams = DEFAULT_AIZAWA,
    *,
    radius: float = 1.0,
    grid_points: int = 20_000,
    candidates: int = 128,
    grid_rotation: np.ndarray | None = None,
) -> tuple[FieldDefect, ...]:
    """Numerically search for shell zeros.

    The returned set is corroborative and may be incomplete. Completeness for
    the default ``d != 0`` model comes from :func:`analytic_shell_defects`.
    """

    grid = _fibonacci_sphere(grid_points, grid_rotation)
    magnitude = np.linalg.norm(sphere_tangential_field(grid, params, radius=radius), axis=1)
    order = np.argsort(magnitude)[: max(1, int(candidates))]
    found: list[FieldDefect] = []
    for seed in grid[order]:
        point, residual = _refine_zero(seed, params, radius)
        if residual > 1e-10:
            continue
        if any(np.linalg.norm(point - np.asarray(existing.point)) < 1e-5 for existing in found):
            continue
        found.append(
            FieldDefect(
                point=tuple(float(value) for value in point),
                residual_norm=residual,
                index=poincare_index(point, params, radius=radius),
                evidence="numerical_corroboration_not_completeness",
            )
        )
    found.sort(key=lambda defect: defect.point)
    return tuple(found)


@dataclass(frozen=True)
class ShellFieldReport:
    mean_abs_ambient_radial_component: float
    max_tangency_residual: float
    analytic_defects: tuple[FieldDefect, ...]
    numerical_defects: tuple[FieldDefect, ...]
    numerical_matches_analytic: bool
    sampled_trajectory_min_radius: float | None


def shell_field_report(
    params: AizawaParams = DEFAULT_AIZAWA,
    *,
    radius: float = 1.0,
    grid_points: int = 10_000,
    trajectory_steps: int | None = None,
) -> ShellFieldReport:
    """Build a bounded report with explicitly graded analytic/numerical evidence."""

    grid = _fibonacci_sphere(grid_points)
    ambient = aizawa_velocity(radius * grid, params)
    radial = np.einsum("ij,ij->i", ambient, grid)
    tangent = sphere_tangential_field(grid, params, radius=radius)
    analytic = analytic_shell_defects(params, radius=radius)
    numerical = numerical_shell_zero_corroboration(
        params,
        radius=radius,
        grid_points=grid_points,
    )
    analytic_points = np.array([defect.point for defect in analytic])
    numerical_points = np.array([defect.point for defect in numerical])
    matches = numerical_points.shape == analytic_points.shape
    if matches:
        distances = np.linalg.norm(
            analytic_points[:, None, :] - numerical_points[None, :, :],
            axis=2,
        )
        matches = bool(np.all(np.min(distances, axis=1) < 1e-6))
    min_radius = None
    if trajectory_steps is not None:
        if int(trajectory_steps) < 1:
            raise ValueError("trajectory_steps must be positive when provided")
        trajectory = integrate_aizawa_rk4(steps=int(trajectory_steps), params=params)
        min_radius = float(np.linalg.norm(trajectory, axis=1).min())
    return ShellFieldReport(
        mean_abs_ambient_radial_component=float(np.abs(radial).mean()),
        max_tangency_residual=float(np.abs(np.einsum("ij,ij->i", tangent, grid)).max()),
        analytic_defects=analytic,
        numerical_defects=numerical,
        numerical_matches_analytic=matches,
        sampled_trajectory_min_radius=min_radius,
    )
