"""Validated Hopf transport primitives for proof-track experiments.

The conventions are deliberately explicit:

* quaternions use ``(w, x, y, z)`` order;
* ``h(q) = q i q^-1`` is imported from the canonical adapter;
* the principal ``S1`` action is right multiplication ``q -> q exp(i theta)``;
* the connection is the round-metric connection
  ``H_q = {v in T_q S3 : <v, q i> = 0}``.

This module defines geometry only. It does not identify an embedding
projection, a dropped Euclidean coordinate, or ``recursive_lift`` with a Hopf
lift.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np

from fram_core.rotational_lift import rotate_plane
from fram_serving.embedding.quaternion_adapter import hopf_map

UNIT_I = np.array([0.0, 1.0, 0.0, 0.0], dtype=float)
BASE_POLE = np.array([1.0, 0.0, 0.0], dtype=float)


def _finite_array(value: object, *, name: str) -> np.ndarray:
    array = np.asarray(value, dtype=float)
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain only finite values")
    return array


def qmul(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Hamilton product, broadcast over leading axes."""

    left = _finite_array(a, name="left quaternion")
    right = _finite_array(b, name="right quaternion")
    if left.shape[-1:] != (4,) or right.shape[-1:] != (4,):
        raise ValueError("quaternion operands must end in four components")
    a0, a1, a2, a3 = (left[..., index] for index in range(4))
    b0, b1, b2, b3 = (right[..., index] for index in range(4))
    return np.stack(
        [
            a0 * b0 - a1 * b1 - a2 * b2 - a3 * b3,
            a0 * b1 + a1 * b0 + a2 * b3 - a3 * b2,
            a0 * b2 - a1 * b3 + a2 * b0 + a3 * b1,
            a0 * b3 + a1 * b2 - a2 * b1 + a3 * b0,
        ],
        axis=-1,
    )


def qconj(q: np.ndarray) -> np.ndarray:
    """Quaternion conjugate."""

    value = _finite_array(q, name="quaternion")
    if value.shape[-1:] != (4,):
        raise ValueError("quaternion must end in four components")
    return np.concatenate([value[..., :1], -value[..., 1:]], axis=-1)


def qnormalize(q: np.ndarray) -> np.ndarray:
    """Normalize nonzero finite quaternion vectors along the last axis."""

    value = _finite_array(q, name="quaternion")
    if value.shape[-1:] != (4,):
        raise ValueError("quaternion must end in four components")
    norm = np.linalg.norm(value, axis=-1, keepdims=True)
    if np.any(norm == 0.0):
        raise ValueError("quaternion must be nonzero")
    return value / norm


def base_points(q: np.ndarray) -> np.ndarray:
    """Apply the canonical Hopf map to one quaternion or a batch."""

    value = qnormalize(q)
    if value.ndim == 1:
        return hopf_map(value)
    flat = value.reshape(-1, 4)
    mapped = np.stack([hopf_map(row) for row in flat], axis=0)
    return mapped.reshape(value.shape[:-1] + (3,))


def fiber_action(q: np.ndarray, theta: float | np.ndarray) -> np.ndarray:
    """Right ``S1`` action ``q -> q exp(i theta)``.

    A scalar quaternion with a scalar angle returns shape ``(4,)``. A scalar
    quaternion with an angle array returns ``theta.shape + (4,)``.
    """

    value = qnormalize(q)
    if value.ndim != 1:
        raise ValueError("fiber_action expects one quaternion")
    angle = _finite_array(theta, name="fiber angle")
    phase = np.zeros(angle.shape + (4,), dtype=float)
    phase[..., 0] = np.cos(angle)
    phase[..., 1] = np.sin(angle)
    return qmul(value, phase)


def rotation_matrix(q: np.ndarray) -> np.ndarray:
    """Return the SO(3) rotation represented by one unit quaternion."""

    value = qnormalize(q)
    if value.ndim != 1:
        raise ValueError("rotation_matrix expects one quaternion")
    w, x, y, z = value
    return np.array(
        [
            [w * w + x * x - y * y - z * z, 2 * (x * y - w * z), 2 * (x * z + w * y)],
            [2 * (x * y + w * z), w * w - x * x + y * y - z * z, 2 * (y * z - w * x)],
            [2 * (x * z - w * y), 2 * (y * z + w * x), w * w - x * x - y * y + z * z],
        ],
        dtype=float,
    )


def wrap_angle(theta: float | np.ndarray) -> float | np.ndarray:
    """Wrap angle(s) into ``(-pi, pi]``."""

    value = _finite_array(theta, name="angle")
    wrapped = (value + np.pi) % (2.0 * np.pi) - np.pi
    wrapped = np.where(
        np.isclose(wrapped, -np.pi, atol=1e-15, rtol=0.0),
        np.pi,
        wrapped,
    )
    if wrapped.ndim == 0:
        return float(wrapped)
    return wrapped


def latitude_loop(alpha: float, steps: int, *, turns: int = 1) -> np.ndarray:
    """Closed latitude loop about ``BASE_POLE``.

    ``alpha`` must lie strictly between the poles; degenerate pole loops do not
    provide a holonomy experiment.
    """

    angle = float(alpha)
    count = int(steps)
    repetitions = int(turns)
    if not np.isfinite(angle) or not 0.0 < angle < np.pi:
        raise ValueError("alpha must satisfy 0 < alpha < pi")
    if count < 3:
        raise ValueError("steps must be at least 3")
    if repetitions < 1:
        raise ValueError("turns must be positive")
    phi = np.linspace(0.0, 2.0 * np.pi * repetitions, count * repetitions + 1)
    return np.stack(
        [
            np.full_like(phi, np.cos(angle)),
            np.sin(angle) * np.cos(phi),
            np.sin(angle) * np.sin(phi),
        ],
        axis=-1,
    )


def solid_angle_of_cap(alpha: float) -> float:
    """Smooth spherical-cap area for ``0 < alpha < pi``."""

    angle = float(alpha)
    if not np.isfinite(angle) or not 0.0 < angle < np.pi:
        raise ValueError("alpha must satisfy 0 < alpha < pi")
    return float(2.0 * np.pi * (1.0 - np.cos(angle)))


def spherical_polygon_solid_angle(
    vertices: np.ndarray,
    pole: np.ndarray = BASE_POLE,
) -> float:
    """Signed area of a closed spherical polygon fan-triangulated from ``pole``.

    This implementation is intended for the simple latitude polygons generated
    by :func:`latitude_loop`, not arbitrary self-intersecting curves.
    """

    path = _finite_array(vertices, name="vertices")
    if path.ndim != 2 or path.shape[1] != 3 or path.shape[0] < 4:
        raise ValueError("vertices must be shaped (n, 3) with n >= 4")
    norms = np.linalg.norm(path, axis=1, keepdims=True)
    if np.any(norms == 0.0):
        raise ValueError("vertices must be nonzero")
    path = path / norms
    if np.linalg.norm(path[0] - path[-1]) > 1e-10:
        raise ValueError("spherical polygon must be closed")
    origin = _finite_array(pole, name="pole").ravel()
    if origin.shape != (3,) or np.linalg.norm(origin) == 0.0:
        raise ValueError("pole must be a nonzero three-vector")
    origin = origin / np.linalg.norm(origin)
    total = 0.0
    for first, second in zip(path[:-1], path[1:]):
        numerator = float(np.dot(origin, np.cross(first, second)))
        denominator = (
            1.0
            + float(np.dot(origin, first))
            + float(np.dot(first, second))
            + float(np.dot(second, origin))
        )
        total += 2.0 * float(np.arctan2(numerator, denominator))
    return total


def _section_lift(n: np.ndarray) -> np.ndarray:
    """One local-section representative over a base point."""

    point = _finite_array(n, name="base point").ravel()
    if point.shape != (3,) or np.linalg.norm(point) == 0.0:
        raise ValueError("base point must be a nonzero three-vector")
    point = point / np.linalg.norm(point)
    dot = float(np.clip(np.dot(BASE_POLE, point), -1.0, 1.0))
    if dot > 1.0 - 1e-15:
        return np.array([1.0, 0.0, 0.0, 0.0])
    if dot < -1.0 + 1e-15:
        return np.array([0.0, 0.0, 0.0, 1.0])
    axis = np.cross(BASE_POLE, point)
    axis /= np.linalg.norm(axis)
    half = 0.5 * np.arccos(dot)
    return np.array([np.cos(half), *(np.sin(half) * axis)])


def _unit_base_curve(curve: np.ndarray) -> np.ndarray:
    path = _finite_array(curve, name="base curve")
    if path.ndim != 2 or path.shape[1] != 3 or path.shape[0] < 2:
        raise ValueError("base curve must be shaped (n, 3) with n >= 2")
    norms = np.linalg.norm(path, axis=1, keepdims=True)
    if np.any(norms == 0.0):
        raise ValueError("base curve points must be nonzero")
    return path / norms


def horizontal_lift(curve: np.ndarray, q0: np.ndarray | None = None) -> np.ndarray:
    """Parallel-transport a piecewise-geodesic base curve.

    Consecutive antipodal points are rejected because their shortest geodesic
    and rotation axis are non-unique. Silently copying the prior lift would
    leave the requested base curve.
    """

    path = _unit_base_curve(curve)
    q = _section_lift(path[0]) if q0 is None else qnormalize(q0)
    if q.ndim != 1:
        raise ValueError("q0 must be one quaternion")
    if np.linalg.norm(hopf_map(q) - path[0]) > 1e-10:
        raise ValueError("q0 must lie over the first base point")
    lifted = np.empty((path.shape[0], 4), dtype=float)
    lifted[0] = q
    for index, (first, second) in enumerate(zip(path[:-1], path[1:])):
        cross = np.cross(first, second)
        cross_norm = float(np.linalg.norm(cross))
        dot = float(np.clip(np.dot(first, second), -1.0, 1.0))
        if cross_norm < 1e-14:
            if dot < 0.0:
                raise ValueError("consecutive antipodal base points are not uniquely transportable")
            lifted[index + 1] = lifted[index]
            continue
        axis = cross / cross_norm
        delta = float(np.arctan2(cross_norm, dot))
        rotation = np.array([np.cos(delta / 2.0), *(np.sin(delta / 2.0) * axis)])
        lifted[index + 1] = qnormalize(qmul(rotation, lifted[index]))
    return lifted


def horizontality_residuals(lift: np.ndarray) -> np.ndarray:
    """Normalized finite-step vertical residuals ``|<dq, q i>| / |dq|``."""

    values = _finite_array(lift, name="lift")
    if values.ndim != 2 or values.shape[1] != 4 or values.shape[0] < 2:
        raise ValueError("lift must be shaped (n, 4) with n >= 2")
    values = qnormalize(values)
    difference = np.diff(values, axis=0)
    vertical = qmul(values[:-1], UNIT_I)
    numerator = np.abs(np.einsum("ij,ij->i", difference, vertical))
    denominator = np.linalg.norm(difference, axis=1)
    return np.divide(
        numerator,
        denominator,
        out=np.zeros_like(numerator),
        where=denominator > 0.0,
    )


def holonomy_angle(q_start: np.ndarray, q_end: np.ndarray) -> tuple[float, float]:
    """Return principal fiber phase and the endpoint's off-fiber residual.

    The phase lies in ``(-pi, pi]``. It cannot by itself distinguish phases
    differing by full turns; Chern-number measurement requires an unwrapped
    family or curvature integral and is outside this function's contract.
    """

    start = qnormalize(q_start)
    end = qnormalize(q_end)
    if start.ndim != 1 or end.ndim != 1:
        raise ValueError("holonomy endpoints must each be one quaternion")
    relative = qmul(qconj(start), end)
    phase = wrap_angle(float(np.arctan2(relative[1], relative[0])))
    return float(phase), float(np.hypot(relative[2], relative[3]))


@dataclass(frozen=True)
class HolonomyReport:
    alpha: float
    steps: int
    turns: int
    measured_phase_mod_2pi: float
    expected_phase_mod_2pi: float
    polygon_phase_mod_2pi: float
    error_vs_smooth: float
    error_vs_polygon: float
    smooth_solid_angle: float
    polygon_solid_angle: float
    max_base_error: float
    max_horizontality_residual: float
    off_fiber_residual: float
    lifted_endpoint_distance: float
    base_endpoint_distance: float


def holonomy_report(alpha: float = 1.1, *, steps: int = 1000, turns: int = 1) -> HolonomyReport:
    """Measure principal holonomy for a latitude loop.

    This tests the chosen connection's half-solid-angle law modulo ``2pi``. It
    makes no signed Chern-number claim.
    """

    path = latitude_loop(alpha, steps, turns=turns)
    lift = horizontal_lift(path)
    phase, off_fiber = holonomy_angle(lift[0], lift[-1])
    smooth_area = turns * solid_angle_of_cap(alpha)
    single_polygon = latitude_loop(alpha, steps)
    polygon_area = turns * spherical_polygon_solid_angle(single_polygon)
    smooth_phase = float(wrap_angle(smooth_area / 2.0))
    polygon_phase = float(wrap_angle(polygon_area / 2.0))
    mapped = base_points(lift)
    return HolonomyReport(
        alpha=float(alpha),
        steps=int(steps),
        turns=int(turns),
        measured_phase_mod_2pi=phase,
        expected_phase_mod_2pi=smooth_phase,
        polygon_phase_mod_2pi=polygon_phase,
        error_vs_smooth=float(abs(wrap_angle(phase - smooth_phase))),
        error_vs_polygon=float(abs(wrap_angle(phase - polygon_phase))),
        smooth_solid_angle=float(smooth_area),
        polygon_solid_angle=float(polygon_area),
        max_base_error=float(np.linalg.norm(mapped - path, axis=1).max()),
        max_horizontality_residual=float(horizontality_residuals(lift).max()),
        off_fiber_residual=off_fiber,
        lifted_endpoint_distance=float(np.linalg.norm(lift[-1] - lift[0])),
        base_endpoint_distance=float(np.linalg.norm(mapped[-1] - mapped[0])),
    )


def fiber_action_as_givens_pair(q: Iterable[float], theta: float) -> np.ndarray:
    """Represent right fiber action using two opposite-sense Givens rotations."""

    value = qnormalize(np.asarray(q, dtype=float))
    if value.ndim != 1:
        raise ValueError("fiber_action_as_givens_pair expects one quaternion")
    angle = float(theta)
    if not np.isfinite(angle):
        raise ValueError("theta must be finite")
    return rotate_plane(rotate_plane(value, 0, 1, angle), 2, 3, -angle)
