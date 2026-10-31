from __future__ import annotations

import numpy as np
import pytest

from fram_eval.chaos.systems import SYSTEMS, get_system, simulate
from fram_eval.fractal_falsification import (
    simulate_aizawa,
    simulate_henon,
    simulate_logistic_map,
    simulate_lorenz,
)


@pytest.mark.parametrize(
    ("system", "initial_state", "expected"),
    [
        (
            "logistic",
            0.2,
            np.array(
                [[0.624], [0.9150336], [0.303213732397056]],
                dtype=np.float64,
            ),
        ),
        (
            "henon",
            (0.1, 0.3),
            np.array(
                [
                    [1.286, 0.03],
                    [-1.2853144, 0.3858],
                    [-0.9270463495863044, -0.38559432],
                ],
                dtype=np.float64,
            ),
        ),
        (
            "lorenz",
            (1.0, 1.0, 1.0),
            np.array(
                [
                    [1.0, 1.26, 0.9833333333333333],
                    [1.026, 1.5175666666666667, 0.9697111111111111],
                    [1.0751566666666668, 1.779721764, 0.9594223821481481],
                ],
                dtype=np.float64,
            ),
        ),
        (
            "aizawa",
            (0.1, 0.0, 0.0),
            np.array(
                [
                    [0.0993, 0.0035, 0.0059],
                    [0.0984882587, 0.0069512065, 0.01185718206945361],
                    [
                        0.0975672265937511,
                        0.01035046132621073,
                        0.0178720595389917,
                    ],
                ],
                dtype=np.float64,
            ),
        ),
    ],
)
def test_golden_initial_steps(
    system: str,
    initial_state: float | tuple[float, ...],
    expected: np.ndarray,
) -> None:
    actual = simulate(system, initial_state, 3)
    np.testing.assert_allclose(actual, expected, rtol=0.0, atol=2e-15)


@pytest.mark.parametrize(
    ("system", "initial_state", "legacy"),
    [
        ("logistic", 0.314159, simulate_logistic_map),
        ("henon", (0.123, -0.456), simulate_henon),
        ("lorenz", (1.25, -2.5, 17.0), simulate_lorenz),
        ("aizawa", (0.1, 0.0, 0.0), simulate_aizawa),
    ],
)
def test_registry_preserves_legacy_output_bit_for_bit(
    system: str,
    initial_state: float | tuple[float, ...],
    legacy: object,
) -> None:
    expected = legacy(initial_state, 128)
    actual = simulate(system, initial_state, 128)
    assert np.array_equal(actual, expected)


def test_burn_in_slices_the_same_canonical_trajectory() -> None:
    full = simulate("logistic", 0.2, 12, params={"r": 3.7})
    retained = simulate("logistic", 0.2, 7, params={"r": 3.7}, burn_in=5)
    assert np.array_equal(retained, full[5:])


def test_registry_metadata_and_lookup_are_bounded() -> None:
    assert tuple(SYSTEMS) == ("logistic", "henon", "lorenz", "aizawa")
    assert get_system(" AIZAWA ") is SYSTEMS["aizawa"]
    assert SYSTEMS["aizawa"].simulate is simulate_aizawa
    with pytest.raises(ValueError, match="unknown system"):
        get_system("per-node-lambda")
    with pytest.raises(ValueError, match="unknown parameters"):
        simulate("logistic", 0.2, 4, params={"lambda": 0.5})
