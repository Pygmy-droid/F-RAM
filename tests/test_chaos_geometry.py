from __future__ import annotations

import numpy as np

from fram_eval.chaos.geometry import (
    RotationalEncodingV1,
    rotational_accumulation,
)


def test_cw_and_ccw_are_exact_mirrors_with_shared_radius_and_height() -> None:
    orbit = np.array([0.2, 0.4, 0.8, 0.6, 0.3], dtype=np.float64)
    pair = rotational_accumulation(
        orbit,
        angular_gain=0.4,
        radius_rule="absolute_state",
        pitch=0.125,
    )

    np.testing.assert_array_equal(pair.clockwise[:, 0], pair.counterclockwise[:, 0])
    np.testing.assert_array_equal(pair.clockwise[:, 1], -pair.counterclockwise[:, 1])
    np.testing.assert_array_equal(pair.clockwise[:, 2], pair.counterclockwise[:, 2])
    np.testing.assert_allclose(
        np.linalg.norm(pair.clockwise[:, :2], axis=1),
        pair.radius,
        rtol=0.0,
        atol=1e-15,
    )
    np.testing.assert_array_equal(pair.clockwise[:, 2], pair.height)

    ccw_phase = np.unwrap(np.arctan2(pair.counterclockwise[:, 1], pair.counterclockwise[:, 0]))
    cw_phase = np.unwrap(np.arctan2(pair.clockwise[:, 1], pair.clockwise[:, 0]))
    assert ccw_phase[-1] - ccw_phase[0] > 0.0
    assert cw_phase[-1] - cw_phase[0] == -(ccw_phase[-1] - ccw_phase[0])


def test_rotational_encoding_v1_declares_and_reuses_its_rule() -> None:
    encoding = RotationalEncodingV1(
        angular_gain=0.25,
        radius_rule="centered_state",
        pitch=-0.5,
    )
    orbit = [0.1, 0.2, 0.4]
    encoded = encoding.encode(orbit)
    direct = rotational_accumulation(
        orbit,
        angular_gain=0.25,
        radius_rule="centered_state",
        pitch=-0.5,
    )
    np.testing.assert_array_equal(encoded.clockwise, direct.clockwise)
    np.testing.assert_array_equal(encoded.counterclockwise, direct.counterclockwise)
    np.testing.assert_array_equal(encoded.radius, direct.radius)
    np.testing.assert_array_equal(encoded.height, direct.height)
    np.testing.assert_array_equal(encoded.phase, direct.phase)
