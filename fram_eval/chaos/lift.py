"""Evidence adapter connecting trajectory windows to the rotational lift."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from fram_core.rotational_lift import (
    LiftCapsule,
    recursive_lift,
    recursive_reconstruct,
    reentry_distances,
    select_window,
    summarize_errors,
)

LIFT_REPORT_V1 = "fram-chaos-trajectory-lift/v1"


def trajectory_digest(trajectory: np.ndarray) -> str:
    """Hash a trajectory's declared float64 shape and values."""

    values = np.ascontiguousarray(np.asarray(trajectory, dtype="<f8"))
    header = json.dumps(
        {"dtype": "<f8", "shape": list(values.shape)},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    return hashlib.sha256(header + b"\0" + values.tobytes()).hexdigest()


@dataclass(frozen=True)
class TrajectoryLiftReport:
    """Versioned evidence for one declared row-window/lift/re-entry run."""

    source_sha256: str
    source_shape: tuple[int, int]
    active_indices: tuple[int, ...]
    window_rule: str
    window_fraction: float
    target_dim: int
    residual_mode: str
    rotation_mode: str
    epsilon: float
    max_reentry: float
    mean_reentry: float
    rms_reentry: float
    passes_reentry: bool
    schema_version: str = LIFT_REPORT_V1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )


@dataclass(frozen=True)
class WindowedLiftResult:
    """Arrays, capsules, and report produced by a windowed lift."""

    selected: np.ndarray
    lifted: np.ndarray
    reconstructed: np.ndarray
    capsules: tuple[LiftCapsule, ...]
    report: TrajectoryLiftReport


def windowed_lift_trajectory(
    trajectory: np.ndarray,
    scores: np.ndarray,
    *,
    window_rule: str,
    fraction: float,
    target_dim: int,
    epsilon: float = 1e-12,
    residual_mode: str = "exact",
    rotation_mode: str = "single",
    quantize_bits: int | None = None,
    rng: np.random.Generator | None = None,
) -> WindowedLiftResult:
    """Select a declared row window, lift it, and score exact-scope re-entry.

    ``select_window`` chooses trajectory rows. The coordinate projection inside
    ``recursive_lift`` is pointwise, so applying the fixed row indices before
    that projection is equivalent to applying them immediately after it.
    Scores are not recomputed from the projected state.

    This adapter reports reconstruction only against the selected parent scope.
    The source digest preserves lineage to the full parent trajectory without
    claiming that a digest alone can reconstruct it.
    """

    values = np.asarray(trajectory, dtype=float)
    if values.ndim != 2 or values.shape[0] == 0 or values.shape[1] == 0:
        raise ValueError("trajectory must have shape [steps, dimensions] with no zero axis")
    score_values = np.asarray(scores, dtype=float)
    if score_values.ndim != 1 or score_values.shape[0] != values.shape[0]:
        raise ValueError("scores must be one-dimensional and match trajectory steps")
    if not np.isfinite(values).all() or not np.isfinite(score_values).all():
        raise ValueError("trajectory and scores must be finite")
    if not np.isfinite(fraction) or not 0.0 < fraction <= 1.0:
        raise ValueError("fraction must be finite and in (0, 1]")
    if not np.isfinite(epsilon) or epsilon <= 0.0:
        raise ValueError("epsilon must be finite and positive")

    source_sha256 = trajectory_digest(values)
    active = select_window(score_values, window_rule, fraction)
    selected = np.array(values[active], copy=True)
    lifted, capsules = recursive_lift(
        selected,
        target_dim=target_dim,
        window_rule=window_rule,
        residual_mode=residual_mode,
        rotation_mode=rotation_mode,
        quantize_bits=quantize_bits,
        rng=rng,
    )
    reconstructed = recursive_reconstruct(lifted, capsules)
    errors = reentry_distances(selected, reconstructed)
    summary = summarize_errors(errors)
    report = TrajectoryLiftReport(
        source_sha256=source_sha256,
        source_shape=(int(values.shape[0]), int(values.shape[1])),
        active_indices=tuple(int(index) for index in active),
        window_rule=window_rule,
        window_fraction=float(fraction),
        target_dim=int(target_dim),
        residual_mode=residual_mode,
        rotation_mode=rotation_mode,
        epsilon=float(epsilon),
        max_reentry=summary["max"],
        mean_reentry=summary["mean"],
        rms_reentry=summary["rms"],
        passes_reentry=bool(summary["max"] < epsilon),
    )
    return WindowedLiftResult(
        selected=selected,
        lifted=lifted,
        reconstructed=reconstructed,
        capsules=tuple(capsules),
        report=report,
    )


__all__ = [
    "LIFT_REPORT_V1",
    "TrajectoryLiftReport",
    "WindowedLiftResult",
    "trajectory_digest",
    "windowed_lift_trajectory",
]
