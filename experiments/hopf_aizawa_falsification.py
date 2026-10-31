"""Negative controls for proposed F-RAM/Hopf identifications.

This module deliberately lives under ``experiments``. It measures why three
existing constructions are not automatically Hopf structures:

* the Phase-D embedding projection is many-to-one;
* one recursive-lift Givens rotation is not the right ``S1`` action;
* base-space re-entry omits fiber phase even though ordinary Euclidean
  re-entry can detect an upstairs endpoint displacement.

The reports are deterministic and bounded. They are evidence about these
specific implementations, not claims about memory, identity, or Aizawa
trajectory recurrence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from fram_core.rotational_lift import (
    project_drop_axis,
    recursive_lift,
    recursive_reconstruct,
    reentry_distances,
    rotate_plane,
)
from fram_eval.aizawa_sphere import shell_field_report
from fram_eval.hopf_transport import (
    base_points,
    fiber_action,
    fiber_action_as_givens_pair,
    holonomy_report,
    latitude_loop,
    qnormalize,
    rotation_matrix,
)
from fram_serving.embedding.quaternion_adapter import (
    build_projection_matrix,
    hopf_map,
    to_quaternion,
)


@dataclass(frozen=True)
class Z2VersusS1Report:
    max_base_drift: float
    so3_spread_at_sign_flip: float
    max_so3_spread_along_fiber: float
    sampled_phases_matching_original_rotation: int
    fiber_arclength: float


def z2_versus_s1_report(
    *,
    q: np.ndarray | None = None,
    samples: int = 512,
    seed: int = 20260727,
) -> Z2VersusS1Report:
    """Separate the two-point SO(3) deck group from the circular Hopf fiber."""

    count = int(samples)
    if count < 4 or count % 2:
        raise ValueError("samples must be an even integer of at least 4")
    rng = np.random.default_rng(seed)
    value = qnormalize(rng.normal(size=4) if q is None else q)
    phases = np.linspace(0.0, 2.0 * np.pi, count, endpoint=False)
    fiber = fiber_action(value, phases)
    bases = base_points(fiber)
    base = hopf_map(value)
    rotations = np.stack([rotation_matrix(point) for point in fiber])
    original_rotation = rotation_matrix(value)
    spreads = np.linalg.norm(rotations - original_rotation, axis=(1, 2))
    closed = np.concatenate([fiber, fiber[:1]], axis=0)
    return Z2VersusS1Report(
        max_base_drift=float(np.linalg.norm(bases - base, axis=1).max()),
        so3_spread_at_sign_flip=float(np.linalg.norm(rotation_matrix(-value) - original_rotation)),
        max_so3_spread_along_fiber=float(spreads.max()),
        sampled_phases_matching_original_rotation=int(np.count_nonzero(spreads <= 1e-9)),
        fiber_arclength=float(np.linalg.norm(np.diff(closed, axis=0), axis=1).sum()),
    )


@dataclass(frozen=True)
class RotationalLiftFalsificationReport:
    paired_givens_max_error: float
    single_givens_mean_error: float
    max_shadow_drift_by_axis: dict[int, float]
    normalized_lift_base_error_mean: float
    normalized_lift_base_error_max: float
    exact_recursive_reentry_by_winding: dict[int, float]
    base_endpoint_distance: float
    lifted_endpoint_distance: float


def rotational_lift_falsification_report(
    *,
    samples: int = 128,
    phase_samples: int = 128,
    seed: int = 20260727,
) -> RotationalLiftFalsificationReport:
    """Measure the missing structure without claiming re-entry is intrinsically blind."""

    count = int(samples)
    phase_count = int(phase_samples)
    if count < 8 or phase_count < 16:
        raise ValueError("samples must be >= 8 and phase_samples must be >= 16")
    rng = np.random.default_rng(seed)
    quaternions = qnormalize(rng.normal(size=(count, 4)))
    angles = rng.uniform(-np.pi, np.pi, size=count)
    pair_error = 0.0
    single_errors: list[float] = []
    for quaternion, angle in zip(quaternions, angles):
        target = fiber_action(quaternion, angle)
        pair_error = max(
            pair_error,
            float(np.linalg.norm(fiber_action_as_givens_pair(quaternion, angle) - target)),
        )
        single_errors.append(
            float(np.linalg.norm(rotate_plane(quaternion, 0, 1, angle) - target))
        )

    phase_grid = np.linspace(0.0, 2.0 * np.pi, phase_count, endpoint=False)
    shadow_drift: dict[int, float] = {}
    for axis in range(4):
        maximum = 0.0
        for quaternion in quaternions[:32]:
            fiber = fiber_action(quaternion, phase_grid)
            moved_shadow, _ = project_drop_axis(fiber, axis)
            initial_shadow, _ = project_drop_axis(quaternion[None, :], axis)
            maximum = max(
                maximum,
                float(np.linalg.norm(moved_shadow - initial_shadow, axis=1).max()),
            )
        shadow_drift[axis] = maximum

    sphere_points = rng.normal(size=(count, 3))
    sphere_points /= np.linalg.norm(sphere_points, axis=1, keepdims=True)
    lifted, _ = recursive_lift(sphere_points, target_dim=4)
    remapped = base_points(qnormalize(lifted))
    geodesic = np.arccos(
        np.clip(np.einsum("ij,ij->i", remapped, sphere_points), -1.0, 1.0)
    )

    winding_errors: dict[int, float] = {}
    for winding in (1, 2, 4):
        curve = latitude_loop(1.0, 128, turns=winding)
        recursive, capsules = recursive_lift(curve, target_dim=6)
        reconstructed = recursive_reconstruct(recursive, capsules)
        winding_errors[winding] = float(reentry_distances(curve, reconstructed).max())

    transport = holonomy_report(1.1, steps=750)
    return RotationalLiftFalsificationReport(
        paired_givens_max_error=pair_error,
        single_givens_mean_error=float(np.mean(single_errors)),
        max_shadow_drift_by_axis=shadow_drift,
        normalized_lift_base_error_mean=float(geodesic.mean()),
        normalized_lift_base_error_max=float(geodesic.max()),
        exact_recursive_reentry_by_winding=winding_errors,
        base_endpoint_distance=transport.base_endpoint_distance,
        lifted_endpoint_distance=transport.lifted_endpoint_distance,
    )


@dataclass(frozen=True)
class AdapterPreimageReport:
    dimension: int
    rank: int
    kernel_dimension: int
    positive_scale_invariance_error: float
    hopf_sign_quotient_error: float
    kernel_invariance_error: float
    fiber_preimage_error: float
    generic_preimage_dimension: int
    max_relative_preimage_displacement: float


def adapter_preimage_report(
    dimension: int = 64,
    *,
    samples: int = 32,
    phase_samples: int = 24,
    seed: int = 17,
    rng_seed: int = 20260727,
) -> AdapterPreimageReport:
    """Construct generic high-dimensional preimages of the adapter/Hopf map.

    Equality of ``x`` and ``-x`` after the Hopf map is recorded as the expected
    sign quotient, not misreported as a failure of projective injectivity.
    Non-injectivity is established by the kernel and continuous fiber
    preimages.
    """

    width = int(dimension)
    count = int(samples)
    phase_count = int(phase_samples)
    if width < 4:
        raise ValueError("dimension must be at least 4")
    if count < 1 or phase_count < 4:
        raise ValueError("samples must be positive and phase_samples must be >= 4")
    projection = build_projection_matrix(width, seed=seed)
    rank = int(np.linalg.matrix_rank(projection))
    if rank != 4:
        raise ValueError("projection must have full row rank for this experiment")
    rng = np.random.default_rng(rng_seed)
    vectors = rng.normal(size=(count, width))
    _, _, right_vectors = np.linalg.svd(projection, full_matrices=True)
    kernel = right_vectors[rank:]
    pseudo_inverse = np.linalg.pinv(projection)
    phases = np.linspace(0.0, 2.0 * np.pi, phase_count, endpoint=False)

    scale_error = 0.0
    sign_error = 0.0
    kernel_error = 0.0
    fiber_error = 0.0
    max_displacement = 0.0
    for vector in vectors:
        quaternion = to_quaternion(vector, projection)
        base = hopf_map(quaternion)
        scale_error = max(
            scale_error,
            float(np.linalg.norm(quaternion - to_quaternion(3.7 * vector, projection))),
        )
        sign_error = max(
            sign_error,
            float(np.linalg.norm(base - hopf_map(to_quaternion(-vector, projection)))),
        )
        if kernel.size:
            moved = vector + kernel.T @ rng.normal(scale=10.0, size=kernel.shape[0])
            kernel_error = max(
                kernel_error,
                float(np.linalg.norm(base - hopf_map(to_quaternion(moved, projection)))),
            )
        magnitude = float(np.linalg.norm(projection @ vector))
        for target in fiber_action(quaternion, phases):
            preimage = pseudo_inverse @ (magnitude * target)
            fiber_error = max(
                fiber_error,
                float(np.linalg.norm(base - hopf_map(to_quaternion(preimage, projection)))),
            )
            max_displacement = max(
                max_displacement,
                float(np.linalg.norm(preimage - vector) / np.linalg.norm(vector)),
            )
    return AdapterPreimageReport(
        dimension=width,
        rank=rank,
        kernel_dimension=width - rank,
        positive_scale_invariance_error=scale_error,
        hopf_sign_quotient_error=sign_error,
        kernel_invariance_error=kernel_error,
        fiber_preimage_error=fiber_error,
        generic_preimage_dimension=width - 2,
        max_relative_preimage_displacement=max_displacement,
    )


def bounded_evidence_payload() -> dict[str, Any]:
    """Return reproducible in-memory evidence without writing runtime artifacts."""

    shell = shell_field_report(grid_points=2_000, trajectory_steps=None)
    return {
        "schema": "fram-hopf-aizawa-falsification-1",
        "z2_vs_s1": asdict(z2_versus_s1_report(samples=256)),
        "rotational_lift": asdict(
            rotational_lift_falsification_report(samples=64, phase_samples=64)
        ),
        "adapter": asdict(adapter_preimage_report(samples=16, phase_samples=12)),
        "aizawa_shell": asdict(shell),
        "claims": {
            "holonomy": "principal phase modulo 2pi; no Chern-number claim",
            "reentry": "base-only representation omits fiber phase; Euclidean upstairs distance detects displacement",
            "defects": "analytic shell-field poles with numerical corroboration; no attractor-recurrence claim",
        },
    }
