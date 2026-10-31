"""Bounded numerical diagnostics for the temporal logistic map."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np


def logistic_lyapunov(
    x0: float,
    r: float,
    steps: int,
    *,
    burn_in: int = 1000,
) -> float:
    """Estimate the orbit-averaged Lyapunov exponent.

    The result is a finite-sample estimate of
    ``mean(log(abs(r * (1 - 2*x)))))``.  A visit to the critical point has a
    zero derivative and returns ``-inf`` rather than hiding that singularity.
    """

    x = float(x0)
    rate = float(r)
    if not np.isfinite((x, rate)).all():
        raise ValueError("x0 and r must be finite")
    if isinstance(steps, bool) or not isinstance(steps, (int, np.integer)):
        raise TypeError("steps must be an integer")
    if isinstance(burn_in, bool) or not isinstance(burn_in, (int, np.integer)):
        raise TypeError("burn_in must be an integer")
    if steps <= 0:
        raise ValueError("steps must be positive")
    if burn_in < 0:
        raise ValueError("burn_in must be non-negative")

    for _ in range(int(burn_in)):
        x = rate * x * (1.0 - x)

    total = 0.0
    for _ in range(int(steps)):
        derivative = abs(rate * (1.0 - 2.0 * x))
        if derivative == 0.0:
            return float("-inf")
        total += float(np.log(derivative))
        x = rate * x * (1.0 - x)
    return total / float(steps)


def detect_orbit_period(
    samples: Sequence[float] | np.ndarray,
    *,
    max_period: int = 1024,
    atol: float = 1e-8,
    repeats: int = 4,
) -> int | None:
    """Return the smallest period supported by the trailing samples.

    A candidate period must repeat for ``repeats`` consecutive comparisons.
    This is a finite-tolerance detector, not a proof that an exact orbit is
    periodic.
    """

    values = np.asarray(samples, dtype=np.float64)
    if values.ndim == 0:
        raise ValueError("samples must have a time axis")
    if values.shape[0] == 0:
        return None
    if not np.isfinite(values).all():
        raise ValueError("samples must contain only finite values")
    if isinstance(max_period, bool) or not isinstance(max_period, (int, np.integer)):
        raise TypeError("max_period must be an integer")
    if isinstance(repeats, bool) or not isinstance(repeats, (int, np.integer)):
        raise TypeError("repeats must be an integer")
    if max_period <= 0:
        raise ValueError("max_period must be positive")
    if repeats <= 0:
        raise ValueError("repeats must be positive")
    if not np.isfinite(atol) or atol < 0.0:
        raise ValueError("atol must be a finite non-negative number")

    available = values.shape[0] // (repeats + 1)
    for period in range(1, min(int(max_period), available) + 1):
        window = (repeats + 1) * period
        tail = values[-window:]
        reference = tail[-period:]
        if all(
            np.allclose(
                tail[-(repeat + 1) * period : -repeat * period],
                reference,
                rtol=0.0,
                atol=atol,
            )
            for repeat in range(1, repeats + 1)
        ):
            return period
    return None


def _critical_return(rate: float, power: int) -> float:
    x = 0.5
    for _ in range(1 << power):
        x = rate * x * (1.0 - x)
    return x - 0.5


def _bisect_root(
    function: Callable[[float], float],
    left: float,
    right: float,
    *,
    tolerance: float,
    max_iterations: int = 200,
) -> float:
    f_left = float(function(left))
    f_right = float(function(right))
    if f_left == 0.0:
        return left
    if f_right == 0.0:
        return right
    if np.signbit(f_left) == np.signbit(f_right):
        raise RuntimeError("root bracket does not change sign")
    for _ in range(max_iterations):
        midpoint = 0.5 * (left + right)
        f_mid = float(function(midpoint))
        if f_mid == 0.0 or right - left <= tolerance:
            return midpoint
        if np.signbit(f_mid) == np.signbit(f_left):
            left, f_left = midpoint, f_mid
        else:
            right, f_right = midpoint, f_mid
    raise RuntimeError("bisection did not converge within max_iterations")


def _next_superstable_root(
    power: int,
    previous: float,
    *,
    tolerance: float,
) -> float:
    # The primary period-doubling cascade lies below 3.6.  A dense deterministic
    # scan is used only to establish a sign-changing bracket; bisection then
    # supplies the requested tolerance.  Starting above the previous root
    # avoids rediscovering the lower-period solution shared by every iterate.
    start = previous + max(32.0 * tolerance, 1e-11)
    stop = 3.6
    scan_count = 20_001
    left = start
    f_left = _critical_return(left, power)
    for right in np.linspace(start, stop, scan_count, dtype=np.float64)[1:]:
        f_right = _critical_return(float(right), power)
        if f_right == 0.0:
            return float(right)
        if np.signbit(f_left) != np.signbit(f_right):
            return _bisect_root(
                lambda rate: _critical_return(rate, power),
                float(left),
                float(right),
                tolerance=tolerance,
            )
        left, f_left = float(right), f_right
    raise RuntimeError(f"could not bracket the period-{1 << power} superstable root")


def logistic_superstable_parameters(
    max_power: int,
    *,
    tolerance: float = 1e-12,
) -> list[float]:
    """Return primary-cascade superstable parameters through ``2**max_power``.

    Entry ``n`` solves ``f_r**(2**n)(0.5) - 0.5 = 0`` on the primary
    period-doubling branch.  The first entry is the period-one value ``r=2``.
    The routine is intentionally bounded to powers 0 through 10: beyond that,
    float64 root spacing makes stronger convergence claims inappropriate.
    """

    if isinstance(max_power, bool) or not isinstance(max_power, (int, np.integer)):
        raise TypeError("max_power must be an integer")
    if not 0 <= max_power <= 10:
        raise ValueError("max_power must be between 0 and 10")
    if not np.isfinite(tolerance) or not 0.0 < tolerance < 1e-4:
        raise ValueError("tolerance must be finite and between 0 and 1e-4")

    roots = [2.0]
    for power in range(1, int(max_power) + 1):
        roots.append(
            _next_superstable_root(
                power,
                roots[-1],
                tolerance=float(tolerance),
            )
        )
    return roots


def feigenbaum_delta_estimates(parameters: Sequence[float]) -> list[float]:
    """Return finite spacing ratios from successive superstable parameters."""

    values = np.asarray(parameters, dtype=np.float64)
    if values.ndim != 1:
        raise ValueError("parameters must be one-dimensional")
    if not np.isfinite(values).all():
        raise ValueError("parameters must contain only finite values")
    if values.size < 3:
        return []
    spacings = np.diff(values)
    if np.any(spacings <= 0.0):
        raise ValueError("parameters must be strictly increasing")
    return [
        float(spacings[index - 1] / spacings[index])
        for index in range(1, spacings.size)
    ]


__all__ = [
    "detect_orbit_period",
    "feigenbaum_delta_estimates",
    "logistic_lyapunov",
    "logistic_superstable_parameters",
]
