from __future__ import annotations

import json

import numpy as np
import pytest

from fram_eval.chaos.lift import trajectory_digest, windowed_lift_trajectory
from fram_eval.chaos.systems import simulate


def test_window_rule_changes_active_view_without_mutating_parent() -> None:
    trajectory = np.arange(15, dtype=float).reshape(5, 3)
    original = trajectory.copy()
    scores = np.array([0.9, 0.1, 0.3, 0.2, 0.8])

    bottom = windowed_lift_trajectory(
        trajectory,
        scores,
        window_rule="bottom",
        fraction=0.6,
        target_dim=5,
    )
    top = windowed_lift_trajectory(
        trajectory,
        scores,
        window_rule="top",
        fraction=0.6,
        target_dim=5,
    )

    assert bottom.report.active_indices == (1, 2, 3)
    assert top.report.active_indices == (0, 2, 4)
    assert bottom.report.source_sha256 == top.report.source_sha256
    assert bottom.report.source_sha256 == trajectory_digest(trajectory)
    assert not np.array_equal(bottom.lifted, top.lifted)
    np.testing.assert_array_equal(trajectory, original)
    assert bottom.report.passes_reentry
    assert top.report.passes_reentry


def test_invalid_window_fails_before_a_report_exists() -> None:
    with pytest.raises(ValueError, match="unknown window rule"):
        windowed_lift_trajectory(
            np.eye(3),
            np.arange(3.0),
            window_rule="invented",
            fraction=0.6,
            target_dim=5,
        )


@pytest.mark.parametrize(
    ("system", "initial"),
    [
        ("logistic", 0.2),
        ("henon", (0.1, 0.1)),
        ("lorenz", (0.1, 0.0, 0.0)),
        ("aizawa", (0.1, 0.0, 0.0)),
    ],
)
def test_exact_windowed_lift_reenters_all_chaos_systems(system, initial) -> None:
    trajectory = simulate(system, initial, 32)
    scores = np.linalg.norm(trajectory, axis=1)
    result = windowed_lift_trajectory(
        trajectory,
        scores,
        window_rule="high_magnitude",
        fraction=0.75,
        target_dim=trajectory.shape[1] + 2,
    )

    assert result.report.max_reentry <= 1e-12
    assert result.report.passes_reentry
    np.testing.assert_allclose(result.reconstructed, result.selected, atol=1e-12)
    assert json.loads(result.report.to_json())["schema_version"].endswith("/v1")


def test_quantized_report_is_deterministic_and_nonzero() -> None:
    trajectory = simulate("henon", (0.1, 0.1), 64)
    scores = trajectory[:, 0]
    kwargs = dict(
        window_rule="middle_abs",
        fraction=0.5,
        target_dim=4,
        epsilon=1e-12,
        residual_mode="quantized",
        quantize_bits=3,
    )
    first = windowed_lift_trajectory(trajectory, scores, **kwargs)
    second = windowed_lift_trajectory(trajectory, scores, **kwargs)

    assert first.report.to_json() == second.report.to_json()
    assert first.report.max_reentry > 0.0
    assert not first.report.passes_reentry
