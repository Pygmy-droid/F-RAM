from __future__ import annotations

import numpy as np

from fram_eval.chaos.complex import julia_escape, mandelbrot_escape


def test_mandelbrot_known_bounded_and_exterior_points() -> None:
    max_iter = 64
    origin = mandelbrot_escape((-0.1, 0.1, -0.1, 0.1), 3, 3, max_iter)
    assert origin[1, 1] == max_iter

    exterior = mandelbrot_escape((2.0, 3.0, 0.0, 1.0), 1, 1, max_iter)
    assert exterior[0, 0] == 2


def test_julia_known_points_and_parameter_coupling_are_deterministic() -> None:
    bounds = (-1.5, 1.5, -1.5, 1.5)
    first = julia_escape(0.0j, bounds, 31, 31, 80)
    repeated = julia_escape(0.0j, bounds, 31, 31, 80)
    changed = julia_escape(-0.8 + 0.156j, bounds, 31, 31, 80)

    assert np.array_equal(first, repeated)
    assert first[15, 15] == 80
    assert not np.array_equal(first, changed)
