from __future__ import annotations

import math

import numpy as np
import pytest

from fram_eval.chaos.diagnostics import (
    detect_orbit_period,
    feigenbaum_delta_estimates,
    logistic_lyapunov,
    logistic_superstable_parameters,
)
from fram_eval.chaos.systems import simulate


def _logistic_samples(rate: float) -> np.ndarray:
    return simulate(
        "logistic",
        0.2,
        1024,
        params={"r": rate},
        burn_in=2048,
    )[:, 0]


def test_logistic_lyapunov_stable_and_fully_chaotic_regimes() -> None:
    assert logistic_lyapunov(0.2, 3.2, 10_000) < 0.0
    exponent = logistic_lyapunov(0.123456789, 4.0, 20_000)
    assert exponent == pytest.approx(math.log(2.0), abs=2e-3)


@pytest.mark.parametrize(
    ("rate", "expected"),
    [(3.2, 2), (3.5, 4), (3.9, None)],
)
def test_period_detection_gate(rate: float, expected: int | None) -> None:
    assert (
        detect_orbit_period(
            _logistic_samples(rate),
            max_period=32,
            atol=1e-10,
            repeats=6,
        )
        == expected
    )


def test_period_detector_reports_smallest_supported_period() -> None:
    samples = np.tile(np.array([1.0, -1.0]), 10)
    assert detect_orbit_period(samples, max_period=8, repeats=4) == 2


def test_superstable_parameters_and_finite_feigenbaum_ratios() -> None:
    parameters = logistic_superstable_parameters(6)
    expected = [
        2.0,
        3.23606797749979,
        3.498561699327702,
        3.554640862768825,
        3.566667379856269,
        3.569243531637111,
        3.569795293749946,
    ]
    np.testing.assert_allclose(parameters, expected, rtol=0.0, atol=8e-12)

    estimates = feigenbaum_delta_estimates(parameters)
    assert estimates[2] == pytest.approx(4.662960, abs=2e-5)
    assert abs(estimates[-1] - 4.669201609) < abs(estimates[0] - 4.669201609)


def test_superstable_contract_is_explicitly_bounded() -> None:
    with pytest.raises(ValueError, match="between 0 and 10"):
        logistic_superstable_parameters(11)
    with pytest.raises(ValueError, match="strictly increasing"):
        feigenbaum_delta_estimates([2.0, 3.2, 3.1])
