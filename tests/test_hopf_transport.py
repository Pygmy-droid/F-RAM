from __future__ import annotations

import numpy as np
import pytest

from fram_eval.hopf_transport import (
    BASE_POLE,
    UNIT_I,
    base_points,
    fiber_action,
    fiber_action_as_givens_pair,
    holonomy_angle,
    holonomy_report,
    horizontal_lift,
    latitude_loop,
    qconj,
    qmul,
    qnormalize,
    rotation_matrix,
    spherical_polygon_solid_angle,
    wrap_angle,
)
from fram_serving.embedding.quaternion_adapter import hopf_map


def _reference_hopf(q: np.ndarray) -> np.ndarray:
    value = qnormalize(q)
    return qmul(qmul(value, UNIT_I), qconj(value))[1:]


def test_canonical_hopf_matches_independent_quaternion_product() -> None:
    rng = np.random.default_rng(42)
    for quaternion in qnormalize(rng.normal(size=(500, 4))):
        np.testing.assert_allclose(hopf_map(quaternion), _reference_hopf(quaternion), atol=1e-13)


def test_hopf_map_is_first_rotation_matrix_column() -> None:
    quaternion = qnormalize(np.array([0.3, -0.2, 0.7, 0.6]))
    np.testing.assert_allclose(hopf_map(quaternion), rotation_matrix(quaternion)[:, 0])


def test_arbitrary_right_fiber_action_preserves_base_point() -> None:
    quaternion = qnormalize(np.array([0.3, -0.2, 0.7, 0.6]))
    phases = np.linspace(-np.pi, np.pi, 101)
    mapped = base_points(fiber_action(quaternion, phases))
    np.testing.assert_allclose(mapped, np.broadcast_to(hopf_map(quaternion), mapped.shape), atol=1e-13)


def test_minus_quaternion_is_phase_pi_within_the_full_fiber() -> None:
    quaternion = qnormalize(np.array([0.1, 0.4, -0.3, 0.8]))
    np.testing.assert_allclose(fiber_action(quaternion, np.pi), -quaternion, atol=1e-14)
    quarter = fiber_action(quaternion, np.pi / 2.0)
    assert np.linalg.norm(rotation_matrix(quarter) - rotation_matrix(quaternion)) > 1.0


def test_fiber_action_equals_opposite_sense_givens_pair() -> None:
    rng = np.random.default_rng(7)
    for _ in range(100):
        quaternion = qnormalize(rng.normal(size=4))
        angle = float(rng.uniform(-np.pi, np.pi))
        np.testing.assert_allclose(
            fiber_action_as_givens_pair(quaternion, angle),
            fiber_action(quaternion, angle),
            atol=1e-14,
        )


def test_horizontal_lift_stays_over_curve_and_is_horizontal() -> None:
    path = latitude_loop(1.1, 300)
    lift = horizontal_lift(path)
    np.testing.assert_allclose(base_points(lift), path, atol=1e-12)
    phase, off_fiber = holonomy_angle(lift[0], lift[-1])
    assert abs(phase) > 0.1
    assert off_fiber < 1e-12


def test_holonomy_matches_polygon_half_area_modulo_two_pi() -> None:
    report = holonomy_report(1.1, steps=500)
    assert report.error_vs_polygon < 1e-11
    assert report.error_vs_smooth < 1e-4
    assert report.max_base_error < 1e-11
    assert report.max_horizontality_residual < 1e-10


def test_polygon_area_rejects_open_path() -> None:
    path = latitude_loop(1.0, 20)[:-1]
    with pytest.raises(ValueError, match="closed"):
        spherical_polygon_solid_angle(path)


def test_horizontal_lift_rejects_antipodal_consecutive_points() -> None:
    with pytest.raises(ValueError, match="antipodal"):
        horizontal_lift(np.array([[1.0, 0.0, 0.0], [-1.0, 0.0, 0.0]]))


def test_horizontal_lift_rejects_wrong_initial_fiber() -> None:
    path = latitude_loop(1.0, 20)
    with pytest.raises(ValueError, match="first base point"):
        horizontal_lift(path, q0=np.array([1.0, 0.0, 0.0, 0.0]))


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        (np.pi, np.pi),
        (-np.pi, np.pi),
        (3.0 * np.pi, np.pi),
        (0.0, 0.0),
    ),
)
def test_wrap_angle_uses_open_left_closed_right_interval(value: float, expected: float) -> None:
    assert wrap_angle(value) == pytest.approx(expected)


@pytest.mark.parametrize(
    "call",
    (
        lambda: qnormalize(np.zeros(4)),
        lambda: fiber_action(np.ones(3), 0.2),
        lambda: latitude_loop(0.0, 20),
        lambda: latitude_loop(1.0, 2),
        lambda: latitude_loop(1.0, 20, turns=0),
    ),
)
def test_public_input_guards(call) -> None:
    with pytest.raises(ValueError):
        call()


def test_identity_base_pole_is_declared_consistently() -> None:
    np.testing.assert_allclose(hopf_map(np.array([1.0, 0.0, 0.0, 0.0])), BASE_POLE)
