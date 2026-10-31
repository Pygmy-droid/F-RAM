from __future__ import annotations

import numpy as np
import pytest

from fram_serving.embedding.quaternion_adapter import hopf_map


def test_hopf_map_identity_has_expected_base_point() -> None:
    np.testing.assert_allclose(hopf_map([1.0, 0.0, 0.0, 0.0]), [1.0, 0.0, 0.0])


def test_hopf_map_is_invariant_under_quaternion_sign_and_scale() -> None:
    quaternion = np.array([0.3, -0.2, 0.7, 0.6])
    np.testing.assert_allclose(hopf_map(quaternion), hopf_map(-quaternion))
    np.testing.assert_allclose(hopf_map(quaternion), hopf_map(4.5 * quaternion))


def test_hopf_map_has_unit_sphere_output() -> None:
    mapped = hopf_map([0.2, 0.4, -0.1, 0.8])
    assert mapped.shape == (3,)
    assert np.linalg.norm(mapped) == pytest.approx(1.0)


def test_hopf_map_exposes_the_s1_fiber_over_the_identity_base_point() -> None:
    for phase in np.linspace(0.0, 2.0 * np.pi, 17):
        fiber_point = [np.cos(phase), np.sin(phase), 0.0, 0.0]
        np.testing.assert_allclose(hopf_map(fiber_point), [1.0, 0.0, 0.0], atol=1e-12)


def test_hopf_map_rotates_x_axis_by_declared_wxyz_convention() -> None:
    half_angle = np.pi / 4.0
    quarter_turn_about_z = [np.cos(half_angle), 0.0, 0.0, np.sin(half_angle)]
    np.testing.assert_allclose(hopf_map(quarter_turn_about_z), [0.0, 1.0, 0.0], atol=1e-12)


@pytest.mark.parametrize(
    "invalid",
    (
        [0.0, 0.0, 0.0, 0.0],
        [1.0, 2.0, 3.0],
        [1.0, 2.0, 3.0, np.nan],
    ),
)
def test_hopf_map_rejects_values_outside_its_domain(invalid: list[float]) -> None:
    with pytest.raises(ValueError):
        hopf_map(invalid)
