from __future__ import annotations

import numpy as np
import pytest

# Recovered unreviewed from firelink/sol-inflight (52621cb) on 2026-10-28. It
# needs origin_completion_lift, which exists only in that branch's lift.py.
# Skipped until that seam is reviewed, so canonical stays green.
pytest.importorskip("fram_eval.chaos.lift")
if not hasattr(__import__("fram_eval.chaos.lift", fromlist=["x"]), "origin_completion_lift"):
    pytest.skip("origin_completion_lift not in canonical lift.py", allow_module_level=True)

from fram_eval.chaos.dimensions import (
    DIMENSIONAL_LADDER_V1,
    DIMENSION_STAGES,
    dimension_stage,
    dimensional_projection,
    exploratory_carrier,
)
from fram_eval.chaos.lift import origin_completion_lift
from fram_eval.chaos.systems import simulate


def test_ladder_declares_every_rung_from_negative_one_through_eight() -> None:
    assert [stage.dimension for stage in DIMENSION_STAGES] == list(range(-1, 9))
    assert dimension_stage(-1).geometric is False
    assert dimension_stage(0).mathematical_status.startswith("R^0")
    assert dimension_stage(8).visual_channel == "linked shadow projections"


def test_one_carrier_supplies_prefix_stable_rungs() -> None:
    trajectory = simulate("aizawa", (0.1, 0.0, 0.0), 48)
    carrier = exploratory_carrier(trajectory)

    assert carrier.shape == (48, 8)
    np.testing.assert_array_equal(carrier[:, :3], trajectory)
    for dimension in range(0, 9):
        projection = dimensional_projection(trajectory, dimension)
        assert projection.schema_version == DIMENSIONAL_LADDER_V1
        assert projection.coordinates.shape == (48, dimension)
        np.testing.assert_array_equal(
            projection.coordinates,
            carrier[:, :dimension],
        )


def test_every_declared_auxiliary_coordinate_is_live() -> None:
    trajectory = simulate("aizawa", (0.1, 0.0, 0.0), 96)
    carrier = exploratory_carrier(trajectory)

    for coordinate in range(3, 8):
        assert np.ptp(carrier[:, coordinate]) > 1e-8


def test_negative_one_and_zero_are_distinct_zero_coordinate_states() -> None:
    trajectory = np.ones((4, 1))
    latent = dimensional_projection(trajectory, -1)
    origin = dimensional_projection(trajectory, 0)

    assert latent.coordinates.shape == origin.coordinates.shape == (4, 0)
    assert latent.stage.key == "latent"
    assert latent.stage.geometric is False
    assert origin.stage.key == "origin"
    assert origin.stage.geometric is True


def test_turn_sense_changes_only_the_declared_path_witness() -> None:
    trajectory = simulate("aizawa", (0.1, 0.0, 0.0), 32)
    clockwise = exploratory_carrier(trajectory, turn_sense="clockwise")
    counterclockwise = exploratory_carrier(
        trajectory,
        turn_sense="counterclockwise",
    )

    np.testing.assert_allclose(clockwise[:, :6], counterclockwise[:, :6])
    np.testing.assert_allclose(clockwise[:, 6], -counterclockwise[:, 6])
    np.testing.assert_allclose(clockwise[:, 7], counterclockwise[:, 7])


def test_eight_coordinate_carrier_obeys_whole_shape_origin_completion() -> None:
    trajectory = simulate("aizawa", (0.1, 0.0, 0.0), 40)
    carrier = exploratory_carrier(trajectory)
    result = origin_completion_lift(
        carrier[:, :7],
        lift_coordinate=carrier[:, 7],
        zoom_fraction=0.6,
        rotation_plane=(0, 7),
        turn_sense="counterclockwise",
    )

    assert result.rotated_full.shape == (40, 8)
    np.testing.assert_allclose(
        result.zoomed_projection + result.origin_completion,
        result.rotated_full,
        atol=1e-12,
    )
    np.testing.assert_allclose(
        result.reconstructed_parent,
        carrier[:, :7],
        atol=1e-12,
    )


@pytest.mark.parametrize("dimension", [-2, 9, 1.5, "four"])
def test_invalid_rungs_are_rejected(dimension: object) -> None:
    with pytest.raises(ValueError, match=r"\[-1, 8\]"):
        dimension_stage(dimension)  # type: ignore[arg-type]
