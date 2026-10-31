"""Declared exploratory coordinate ladder for the Chaos Playground.

The ladder is an evaluation/visualization contract.  Dimensions above the
source trajectory are deterministic auxiliary coordinates, not claims about a
physical state space.  ``-1D`` is a non-geometric UI sentinel; ordinary
Euclidean coordinates begin at ``R^0``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

import numpy as np

DIMENSIONAL_LADDER_V1 = "fram-chaos-dimensional-ladder/v1"
TurnSense = Literal["clockwise", "counterclockwise"]


@dataclass(frozen=True)
class DimensionStage:
    dimension: int
    key: str
    mathematical_status: str
    reconstruction: str
    visual_channel: str
    geometric: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


DIMENSION_STAGES = (
    DimensionStage(
        -1,
        "latent",
        "non-geometric sentinel; not an ordinary Euclidean vector space",
        "uninstantiated carrier before the origin is declared",
        "empty field",
        False,
    ),
    DimensionStage(
        0,
        "origin",
        "R^0 is the singleton origin",
        "still point with no extent",
        "origin glyph",
        True,
    ),
    DimensionStage(1, "line", "R^1", "signed scalar carrier", "x position", True),
    DimensionStage(2, "plane", "R^2", "first turn plane", "xy position", True),
    DimensionStage(3, "space", "R^3", "ambient trajectory", "xyz position", True),
    DimensionStage(
        4,
        "phase",
        "R^4 with one declared auxiliary coordinate",
        "centered trajectory phase",
        "cyclic hue",
        True,
    ),
    DimensionStage(
        5,
        "rhythm",
        "R^5 with two declared auxiliary coordinates",
        "local motion magnitude",
        "pulse and point radius",
        True,
    ),
    DimensionStage(
        6,
        "trace",
        "R^6 with three declared auxiliary coordinates",
        "smoothed motion trace",
        "trail memory",
        True,
    ),
    DimensionStage(
        7,
        "braid",
        "R^7 with four declared auxiliary coordinates",
        "signed turn-path witness",
        "clockwise/counterclockwise braid",
        True,
    ),
    DimensionStage(
        8,
        "atlas",
        "R^8 with five declared auxiliary coordinates",
        "local bending witness",
        "linked shadow projections",
        True,
    ),
)

_STAGES = {stage.dimension: stage for stage in DIMENSION_STAGES}


@dataclass(frozen=True)
class DimensionalProjection:
    """One prefix projection of the canonical exploratory eight-coordinate carrier."""

    stage: DimensionStage
    coordinates: np.ndarray
    carrier: np.ndarray
    schema_version: str = DIMENSIONAL_LADDER_V1


def dimension_stage(dimension: int) -> DimensionStage:
    """Return the declared stage or reject dimensions outside ``[-1, 8]``."""

    if not isinstance(dimension, (int, np.integer)) or isinstance(dimension, bool):
        raise ValueError("dimension must be an integer in [-1, 8]")
    try:
        return _STAGES[int(dimension)]
    except KeyError as exc:
        raise ValueError("dimension must be an integer in [-1, 8]") from exc


def _unit_interval(values: np.ndarray) -> np.ndarray:
    minimum = float(np.min(values))
    span = float(np.max(values) - minimum)
    if span <= np.finfo(float).eps:
        return np.zeros_like(values, dtype=float)
    return (values - minimum) / span


def exploratory_carrier(
    trajectory: np.ndarray,
    *,
    turn_sense: TurnSense = "counterclockwise",
) -> np.ndarray:
    """Build one deterministic 8-coordinate carrier from an input trajectory.

    The first three columns preserve the source coordinates (zero-padded when
    needed).  The five auxiliary columns are declared visualization witnesses:
    centered sample phase, local speed, an exponential speed trace, a signed
    half-turn path witness, and local bending magnitude.
    """

    values = np.asarray(trajectory, dtype=float)
    if values.ndim != 2 or values.shape[0] == 0 or values.shape[1] == 0:
        raise ValueError("trajectory must have shape [steps, dimensions] with no zero axis")
    if not np.isfinite(values).all():
        raise ValueError("trajectory must be finite")
    if turn_sense not in ("clockwise", "counterclockwise"):
        raise ValueError("turn_sense must be 'clockwise' or 'counterclockwise'")

    count = values.shape[0]
    spatial = np.zeros((count, 3), dtype=float)
    retained = min(3, values.shape[1])
    spatial[:, :retained] = values[:, :retained]

    phase = np.zeros(count, dtype=float)
    if count > 1:
        phase = np.linspace(-1.0, 1.0, count, dtype=float)

    delta = np.diff(spatial, axis=0, prepend=spatial[[0]])
    speed = _unit_interval(np.linalg.norm(delta, axis=1))

    trace = np.empty(count, dtype=float)
    trace[0] = speed[0]
    for index in range(1, count):
        trace[index] = 0.82 * trace[index - 1] + 0.18 * speed[index]
    trace = _unit_interval(trace)

    sense = -1.0 if turn_sense == "clockwise" else 1.0
    path_witness = sense * np.sin(np.pi * (phase + 1.0) / 2.0)

    bend = np.diff(delta, axis=0, prepend=delta[[0]])
    bending = _unit_interval(np.linalg.norm(bend, axis=1))

    return np.column_stack(
        (spatial, phase, speed, trace, path_witness, bending)
    )


def dimensional_projection(
    trajectory: np.ndarray,
    dimension: int,
    *,
    turn_sense: TurnSense = "counterclockwise",
) -> DimensionalProjection:
    """Project the same carrier onto a declared rung.

    ``-1D`` and ``0D`` both have zero coordinate columns, but their stage
    metadata distinguishes the non-geometric latent sentinel from ``R^0``.
    """

    stage = dimension_stage(dimension)
    carrier = exploratory_carrier(trajectory, turn_sense=turn_sense)
    width = max(0, stage.dimension)
    coordinates = np.array(carrier[:, :width], copy=True)
    return DimensionalProjection(
        stage=stage,
        coordinates=coordinates,
        carrier=carrier,
    )


__all__ = [
    "DIMENSIONAL_LADDER_V1",
    "DIMENSION_STAGES",
    "DimensionStage",
    "DimensionalProjection",
    "dimension_stage",
    "dimensional_projection",
    "exploratory_carrier",
]
