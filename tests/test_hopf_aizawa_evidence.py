from __future__ import annotations

import numpy as np
import pytest

from experiments.hopf_aizawa_falsification import rotational_lift_falsification_report
from fram_eval.aizawa_sphere import (
    integrate_aizawa_rk4,
    numerical_shell_zero_corroboration,
)
from fram_eval.hopf_transport import holonomy_report


pytestmark = pytest.mark.slow


def test_holonomy_smooth_loop_error_converges_second_order() -> None:
    errors = [holonomy_report(1.1, steps=count).error_vs_smooth for count in (250, 500, 1000)]
    for coarse, fine in zip(errors, errors[1:]):
        assert coarse / fine == pytest.approx(4.0, rel=0.08)


def test_rk4_short_horizon_dt_refinement_has_fourth_order_evidence() -> None:
    duration = 0.4

    def endpoint(dt: float) -> np.ndarray:
        steps = int(round(duration / dt))
        return integrate_aizawa_rk4(dt=dt, steps=steps)[-1]

    reference = endpoint(0.00125)
    errors = [
        float(np.linalg.norm(endpoint(dt) - reference))
        for dt in (0.02, 0.01, 0.005)
    ]
    assert errors[0] > 8.0 * errors[1]
    assert errors[1] > 8.0 * errors[2]


def test_numerical_shell_search_corroborates_analytic_poles_across_grids() -> None:
    rng = np.random.default_rng(77)
    rotation, _ = np.linalg.qr(rng.normal(size=(3, 3)))
    if np.linalg.det(rotation) < 0.0:
        rotation[:, 0] *= -1.0
    baseline = numerical_shell_zero_corroboration(grid_points=20_000)
    rotated = numerical_shell_zero_corroboration(
        grid_points=20_000,
        grid_rotation=rotation,
    )
    expected = np.array([[0.0, 0.0, -1.0], [0.0, 0.0, 1.0]])
    for found in (baseline, rotated):
        assert len(found) == 2
        points = np.array([defect.point for defect in found])
        distances = np.linalg.norm(expected[:, None, :] - points[None, :, :], axis=2)
        assert np.max(np.min(distances, axis=1)) < 1e-8
        assert all(defect.index == 1 for defect in found)
        assert all("not_completeness" in defect.evidence for defect in found)


def test_recursive_lift_remapped_base_is_empirically_near_independent_chance() -> None:
    report = rotational_lift_falsification_report(samples=512, phase_samples=64)
    chance_mean = np.pi / 2.0
    assert report.normalized_lift_base_error_mean == pytest.approx(chance_mean, abs=0.12)
