"""Versioned rotational encoding for scalar chaotic orbits.

This is an explicit reconstruction rule, not a claim that the missing
Chaos Playground formula has been recovered.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

import numpy as np

RadiusRule = Literal["absolute_state", "centered_state", "unit"]


@dataclass(frozen=True)
class RotationalPair:
    """Mirrored branches produced from one scalar orbit."""

    clockwise: np.ndarray
    counterclockwise: np.ndarray
    radius: np.ndarray
    height: np.ndarray
    phase: np.ndarray


@dataclass(frozen=True)
class RotationalEncodingV1:
    """The first declared reconstruction of the missing rotational rule.

    Looking from positive z toward the origin, positive mathematical phase is
    counter-clockwise (CCW).  CW uses its exact negative.  Phase accumulates
    ``angular_gain * orbit_value`` at every sample; both branches share the
    same radius and height.
    """

    angular_gain: float = 2.0 * np.pi
    radius_rule: RadiusRule = "absolute_state"
    pitch: float = 0.01

    def encode(self, orbit: Sequence[float] | np.ndarray) -> RotationalPair:
        return rotational_accumulation(
            orbit,
            angular_gain=self.angular_gain,
            radius_rule=self.radius_rule,
            pitch=self.pitch,
        )


def _radius_for(values: np.ndarray, rule: RadiusRule) -> np.ndarray:
    if rule == "absolute_state":
        return np.abs(values)
    if rule == "centered_state":
        if values.size == 0:
            return values.copy()
        return np.abs(values - np.mean(values))
    if rule == "unit":
        return np.ones_like(values)
    raise ValueError(
        "radius_rule must be 'absolute_state', 'centered_state', or 'unit'"
    )


def rotational_accumulation(
    orbit: Sequence[float] | np.ndarray,
    *,
    angular_gain: float,
    radius_rule: RadiusRule,
    pitch: float,
) -> RotationalPair:
    """Encode a scalar orbit as exactly mirrored CW and CCW curves."""

    values = np.asarray(orbit, dtype=np.float64)
    if values.ndim == 2 and values.shape[1] == 1:
        values = values[:, 0]
    if values.ndim != 1:
        raise ValueError("orbit must be one-dimensional")
    if not np.isfinite(values).all():
        raise ValueError("orbit must contain only finite values")
    gain = float(angular_gain)
    rise = float(pitch)
    if not np.isfinite((gain, rise)).all():
        raise ValueError("angular_gain and pitch must be finite")

    radius = _radius_for(values, radius_rule)
    height = rise * np.arange(values.size, dtype=np.float64)
    phase = gain * np.cumsum(values, dtype=np.float64)

    ccw = np.column_stack(
        (radius * np.cos(phase), radius * np.sin(phase), height)
    )
    cw = np.column_stack(
        (radius * np.cos(-phase), radius * np.sin(-phase), height)
    )
    return RotationalPair(
        clockwise=cw,
        counterclockwise=ccw,
        radius=radius,
        height=height,
        phase=phase,
    )


__all__ = [
    "RadiusRule",
    "RotationalEncodingV1",
    "RotationalPair",
    "rotational_accumulation",
]
