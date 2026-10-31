"""Deterministic escape-time kernels for quadratic complex dynamics."""

from __future__ import annotations

from typing import Sequence

import numpy as np

ComplexBounds = tuple[float, float, float, float]


def _grid(
    bounds: Sequence[float],
    width: int,
    height: int,
) -> np.ndarray:
    if len(bounds) != 4:
        raise ValueError("bounds must be (real_min, real_max, imag_min, imag_max)")
    real_min, real_max, imag_min, imag_max = (float(value) for value in bounds)
    if not np.isfinite((real_min, real_max, imag_min, imag_max)).all():
        raise ValueError("bounds must contain only finite values")
    if real_min >= real_max or imag_min >= imag_max:
        raise ValueError("bounds minima must be less than maxima")
    if isinstance(width, bool) or not isinstance(width, (int, np.integer)):
        raise TypeError("width must be an integer")
    if isinstance(height, bool) or not isinstance(height, (int, np.integer)):
        raise TypeError("height must be an integer")
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")
    real = np.linspace(real_min, real_max, int(width), dtype=np.float64)
    imag = np.linspace(imag_min, imag_max, int(height), dtype=np.float64)
    return real[np.newaxis, :] + 1j * imag[:, np.newaxis]


def _validate_max_iter(max_iter: int) -> int:
    if isinstance(max_iter, bool) or not isinstance(max_iter, (int, np.integer)):
        raise TypeError("max_iter must be an integer")
    if max_iter <= 0:
        raise ValueError("max_iter must be positive")
    if max_iter > np.iinfo(np.int32).max:
        raise ValueError("max_iter exceeds the int32 result range")
    return int(max_iter)


def _escape_time(
    z: np.ndarray,
    c: np.ndarray | complex,
    *,
    max_iter: int,
) -> np.ndarray:
    # Bounded points retain max_iter.  Escaping points receive the 1-based
    # iteration at which abs(z) first exceeds the radius-two escape bound.
    escape = np.full(z.shape, max_iter, dtype=np.int32)
    active = np.ones(z.shape, dtype=bool)
    for iteration in range(1, max_iter + 1):
        z[active] = z[active] * z[active] + (
            c[active] if isinstance(c, np.ndarray) else c
        )
        newly_escaped = active & (np.abs(z) > 2.0)
        escape[newly_escaped] = iteration
        active[newly_escaped] = False
        if not np.any(active):
            break
    return escape


def mandelbrot_escape(
    bounds: Sequence[float],
    width: int,
    height: int,
    max_iter: int,
) -> np.ndarray:
    """Return Mandelbrot escape iterations on an inclusive rectangular grid."""

    limit = _validate_max_iter(max_iter)
    c = _grid(bounds, width, height)
    z = np.zeros_like(c)
    return _escape_time(z, c, max_iter=limit)


def julia_escape(
    c: complex,
    bounds: Sequence[float],
    width: int,
    height: int,
    max_iter: int,
) -> np.ndarray:
    """Return Julia escape iterations for ``z -> z*z + c``."""

    limit = _validate_max_iter(max_iter)
    constant = complex(c)
    if not np.isfinite((constant.real, constant.imag)).all():
        raise ValueError("c must be finite")
    z = _grid(bounds, width, height)
    return _escape_time(z, constant, max_iter=limit)


__all__ = [
    "ComplexBounds",
    "julia_escape",
    "mandelbrot_escape",
]
