from __future__ import annotations

import numpy as np
import pytest

from fram_eval.aizawa_sphere import (
    AizawaParams,
    DEFAULT_AIZAWA,
    aizawa_velocity,
    analytic_shell_defects,
    integrate_aizawa_rk4,
    sphere_tangential_field,
)
from fram_eval.fractal_falsification import simulate_aizawa


def test_aizawa_origin_velocity_is_nonzero() -> None:
    np.testing.assert_allclose(
        aizawa_velocity([0.0, 0.0, 0.0]),
        [0.0, 0.0, DEFAULT_AIZAWA.c],
    )


def test_aizawa_velocity_accepts_single_and_batched_points() -> None:
    point = np.array([0.1, -0.2, 0.3])
    single = aizawa_velocity(point)
    batch = aizawa_velocity(np.stack([point, point]))
    assert single.shape == (3,)
    assert batch.shape == (2, 3)
    np.testing.assert_allclose(batch[0], single)


def test_legacy_euler_simulator_uses_the_shared_velocity_contract() -> None:
    state = np.array([0.1, -0.2, 0.3])
    dt = 0.01
    trajectory = simulate_aizawa(tuple(state), 1, dt=dt)
    expected = state + dt * aizawa_velocity(state)
    assert np.array_equal(trajectory[0], expected)


def test_shell_construction_is_tangent_and_discards_radial_dynamics() -> None:
    rng = np.random.default_rng(9)
    points = rng.normal(size=(500, 3))
    points /= np.linalg.norm(points, axis=1, keepdims=True)
    tangent = sphere_tangential_field(points)
    assert np.abs(np.einsum("ij,ij->i", tangent, points)).max() < 1e-12
    ambient = aizawa_velocity(points)
    assert np.linalg.norm(ambient - tangent, axis=1).mean() > 0.1


def test_analytic_default_shell_zero_set_is_exactly_two_poles() -> None:
    defects = analytic_shell_defects()
    assert {defect.point for defect in defects} == {
        (0.0, 0.0, -1.0),
        (0.0, 0.0, 1.0),
    }
    assert sum(defect.index for defect in defects) == 2
    assert all(defect.residual_norm == pytest.approx(0.0) for defect in defects)
    assert all(defect.evidence == "analytic_d_nonzero" for defect in defects)


def test_analytic_two_pole_proof_declares_d_nonzero_precondition() -> None:
    with pytest.raises(ValueError, match="d != 0"):
        analytic_shell_defects(AizawaParams(d=0.0))


def test_rk4_is_deterministic_and_includes_initial_point() -> None:
    first = integrate_aizawa_rk4(steps=50)
    second = integrate_aizawa_rk4(steps=50)
    assert np.array_equal(first, second)
    np.testing.assert_allclose(first[0], [0.1, 0.0, 0.0])
    assert first.shape == (51, 3)
    assert np.isfinite(first).all()


@pytest.mark.parametrize(
    "call",
    (
        lambda: sphere_tangential_field([1.0, 0.0, 0.0], radius=0.0),
        lambda: sphere_tangential_field([1.0, 0.0, 0.0], radius=-1.0),
        lambda: sphere_tangential_field([0.0, 0.0, 0.0]),
        lambda: integrate_aizawa_rk4(dt=0.0, steps=10),
        lambda: integrate_aizawa_rk4(dt=0.01, steps=0),
        lambda: integrate_aizawa_rk4(x0=(0.0, 0.0)),
    ),
)
def test_public_input_guards(call) -> None:
    with pytest.raises(ValueError):
        call()


def test_parameter_model_rejects_nonfinite_values() -> None:
    with pytest.raises(ValueError):
        AizawaParams(a=float("nan"))
