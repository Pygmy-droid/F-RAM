from __future__ import annotations
"""
Recursive Rotational Lift - prototype math primitives.

Formalizes and generalizes (to N dimensions, vectorized over batches of
states) the toy simulation in
``2026_07_01/Integrated Diary and Workflow Hub/hearthforge/experiments/recursive_rotational_lift/``
(v0.1 + v0.2, Rick Berghahn + Vesper (5.5-Extra High), 2026-07-01) and the
accompanying formal sketch ``2026-07-01_recursive_rotational_lift_payload.md``
("a formal sketch, not a completed proof and not a settled physics claim").

Status: as of 2026-07-21, ``fram_serving.memory_capsule`` imports this module
to populate two previously-always-empty capsule fields (``self_invariants``,
``open_residuals``), gated off by default behind
``FRAMConfig.rotational_lift_enabled`` / ``FRAM_ROTATIONAL_LIFT_ENABLED``.
That wiring is write-side only: it never touches ``/query``, retrieval
ranking, or ``MemoryCapsuleStore.search()``. No claim is made that this
improves retrieval, that F-RAM already implements this loop end-to-end, or
that it models real LLM attention/KV-cache dynamics. See
``docs/rotational_lift.md`` for the full scope statement (mirrors the
"what this is / is not" discipline used in ``docs/fractal_core.md``).

Core claim being formalized: parent/transform/residual bookkeeping is one
sufficient construction for exact reconstruction of the implemented
coordinate projection. It is not a universal necessity theorem: a projection
may already be injective on a restricted state set, and other encodings or
side-channels can preserve the omitted information. Reconstruction here
reverses each recorded hop in turn.
"""

from dataclasses import dataclass
from typing import Callable, Sequence

import numpy as np

DEFAULT_ROTATION_SCHEDULE: tuple[float, ...] = (np.pi, np.pi / 2.0, 3.0 * np.pi / 4.0)


@dataclass(frozen=True)
class LiftCapsule:
    """Parent-frame metadata for one recursive-lift hop.

    Mirrors the toy simulation's ``HopCapsule`` (generalized: adds an
    optional ``parent_id`` so a chain of capsules could later be linked via
    a parent-lineage field added to ``fram_serving.memory_capsule``, if one
    is ever added - no such field exists there today, and this module does
    not do that wiring itself).
    """

    previous_dim: int
    drop_axis: int
    rotation_plane: tuple[int, int]
    rotation_theta: float
    window_rule: str
    residual_mode: str
    parent_id: str | None = None
    rotations: tuple[tuple[tuple[int, int], float], ...] | None = None
    """Optional full rotation as a product of Givens rotations, applied in order.

    The formal sketch (``2026-07-01_recursive_rotational_lift_payload.md`` S4)
    specifies the capsule as ``C_k = (P_k, W_k, L_k, Q_{k+1}, r_k, parent_id)``
    with ``Q_{n+1} in SO(n+1)`` - a *full* rotation. ``rotation_plane`` plus
    ``rotation_theta`` can only encode a single Givens rotation, which is a
    strict subgroup of SO(n+1); it cannot represent a rotation acting in two
    planes at once. In four dimensions, the declared Hopf-fiber convention is
    represented by a paired opposite-sense Givens product.

    When ``None`` the capsule behaves exactly as before - one plane, one angle.
    When set, this sequence is the source of truth and ``rotation_plane`` /
    ``rotation_theta`` mirror its first element for backward compatibility.
    """

    @property
    def rotation_sequence(self) -> tuple[tuple[tuple[int, int], float], ...]:
        """The effective rotation, always as an ordered Givens product."""

        if self.rotations is not None:
            return self.rotations
        return ((self.rotation_plane, self.rotation_theta),)


def isoclinic_partner_plane(plane: tuple[int, int], dim: int) -> tuple[int, int] | None:
    """Return a deterministic plane disjoint from ``plane``.

    Returns the two lowest axis indices not already in ``plane``, or ``None``
    when ``dim`` is too small for a disjoint second plane to exist. The choice
    is deterministic so capsules stay reproducible. In dimension four, equal
    and opposite angles in the two complementary planes give the exact paired
    action used by the declared Hopf convention. In higher dimensions the
    remaining axes are fixed, so the product is not globally isoclinic despite
    the retained public mode name.
    """

    i, j = plane
    if i == j:
        raise ValueError("rotation plane axes must be distinct")
    if not 0 <= i < dim or not 0 <= j < dim:
        raise ValueError("rotation plane axis is outside the declared dimension")
    remaining = [ax for ax in range(dim) if ax not in (i, j)]
    if len(remaining) < 2:
        return None
    return (remaining[0], remaining[1])


def default_drop_axis_schedule(hop: int, dim: int) -> int:
    """Which coordinate becomes hidden (residual) at a given hop.

    The first three hops deliberately touch different axes (index 2, then 0,
    then 1) so a recursive stress test touches every original source axis
    early, matching the v0.2 toy harness's schedule.
    """

    preferred = (2, 0, 1)
    if hop < len(preferred) and preferred[hop] < dim:
        return preferred[hop]
    return (hop * 2 + 1) % dim


def project_drop_axis(state: np.ndarray, axis: int) -> tuple[np.ndarray, np.ndarray]:
    """Projection P: split state (..., d) into shadow (..., d-1) + residual (...,).

    ``shadow`` is the readable view; ``residual`` is exactly what the
    projection drops. Keeping both (vs. discarding the residual) is the
    difference between a lossy projection and a lift.
    """

    residual = np.array(state[..., axis], copy=True)
    shadow = np.delete(state, axis, axis=-1)
    return shadow, residual


def lift_insert_axis(shadow: np.ndarray, axis: int, residual: np.ndarray) -> np.ndarray:
    """Lift L: reinsert a residual at ``axis``, undoing project_drop_axis exactly
    when ``residual`` has not been degraded."""

    return np.insert(shadow, axis, residual, axis=-1)


def derived_coordinate(state: np.ndarray, hop: int) -> np.ndarray:
    """Deterministic bounded extra coordinate appended at each lift hop.

    Supplies the new axis a lift hop needs to grow dimensionality by one
    (state shape (..., d) -> returns shape (...,); bounded in [-0.43, 0.43]).
    Its specific value is arbitrary for correctness: ``recursive_reconstruct``
    truncates this coordinate away rather than reading it back, so losslessness
    does not depend on this formula - only on ``rotate_plane`` being invertible,
    which holds for any value here. Keeping it deterministic (vs. e.g. zero)
    is a stylistic choice inherited from the toy simulation, not a requirement.
    """

    idx = np.arange(1, state.shape[-1] + 1, dtype=float)
    weighted = (state * idx).sum(axis=-1)
    norm2 = (state * state).sum(axis=-1)
    return 0.35 * np.sin(weighted + hop * 0.7) + 0.08 * np.cos(norm2 + hop)


def rotate_plane(state: np.ndarray, i: int, j: int, theta: float) -> np.ndarray:
    """Rotation Q: a Givens rotation of ``state`` (..., d) in the (i, j) plane.

    This is an element of SO(d) for any theta: it preserves the L2 norm and
    all inner products exactly (Q^T Q = I). Rotating never destroys
    information by itself - it only changes which face is visible.
    """

    values = np.asarray(state)
    if values.ndim == 0:
        raise ValueError("state must have at least one coordinate axis")
    if i == j:
        raise ValueError("rotation plane axes must be distinct")
    dim = values.shape[-1]
    if not 0 <= i < dim or not 0 <= j < dim:
        raise ValueError("rotation plane axis is outside the state dimension")
    if not np.isfinite(theta):
        raise ValueError("rotation angle must be finite")

    out = np.array(values, copy=True, dtype=float)
    c = np.cos(theta)
    s = np.sin(theta)
    vi = np.array(values[..., i], copy=True)
    vj = np.array(values[..., j], copy=True)
    out[..., i] = c * vi - s * vj
    out[..., j] = s * vi + c * vj
    return out


def quantize(values: np.ndarray, bits: int, lo: float = -1.5, hi: float = 1.5) -> np.ndarray:
    """Uniform scalar quantization over a fixed range, vectorized."""

    levels = (1 << bits) - 1
    if levels <= 0:
        return np.zeros_like(values, dtype=float)
    clamped = np.clip(values, lo, hi)
    normalized = (clamped - lo) / (hi - lo)
    bucket = np.round(normalized * levels)
    return lo + (bucket / levels) * (hi - lo)


def apply_dropout(values: np.ndarray, p: float, rng: np.random.Generator) -> np.ndarray:
    """Zero out each element independently with probability ``p``."""

    if p <= 0.0:
        return values
    if p >= 1.0:
        return np.zeros_like(values, dtype=float)
    mask = rng.random(np.shape(values)) < p
    out = np.array(values, copy=True, dtype=float)
    out[mask] = 0.0
    return out


def apply_gaussian_noise(values: np.ndarray, sigma: float, rng: np.random.Generator) -> np.ndarray:
    """Add zero-mean Gaussian noise with standard deviation ``sigma``."""

    if sigma <= 0.0:
        return values
    return values + rng.normal(0.0, sigma, size=np.shape(values))


def select_window(scores: np.ndarray, rule: str, fraction: float = 0.6) -> np.ndarray:
    """Window W: select the active retrieval window's indices from per-item scores.

    Generalizes the toy harness's five window rules (which were hardcoded to
    a z-coordinate / deformation-energy score) to any scalar score array.
    Returns sorted integer indices into ``scores`` (a subset, not a copy of
    the data) - the full population is never deleted, only the active face
    is chosen.
    """

    n = int(np.shape(scores)[0])
    count = max(1, min(n, int(round(n * fraction))))
    if rule == "bottom":
        order = np.argsort(scores)
    elif rule == "top":
        order = np.argsort(-np.asarray(scores))
    elif rule == "middle_abs":
        order = np.argsort(np.abs(scores))
    elif rule == "random":
        rng = np.random.default_rng(20260701)
        order = rng.permutation(n)
    elif rule == "high_magnitude":
        order = np.argsort(-np.abs(scores))
    else:
        raise ValueError(f"unknown window rule: {rule}")
    return np.sort(order[:count])


def recursive_lift(
    state: np.ndarray,
    *,
    target_dim: int,
    window_rule: str = "unspecified",
    residual_mode: str = "exact",
    quantize_bits: int | None = None,
    dropout_p: float = 0.0,
    shadow_noise_sigma: float = 0.0,
    rotation_schedule: Sequence[float] = DEFAULT_ROTATION_SCHEDULE,
    drop_axis_fn: Callable[[int, int], int] = default_drop_axis_schedule,
    rng: np.random.Generator | None = None,
    rotation_mode: str = "single",
) -> tuple[np.ndarray, list[LiftCapsule]]:
    """Recursively lift a batch of states to ``target_dim`` via project/window/lift/rotate hops.

    Parameters
    ----------
    state
        Array shaped [N, d0] (or [d0], treated as a single point).
    target_dim
        Final dimensionality after repeated one-axis-at-a-time lifts.
    residual_mode
        "exact" (lossless), "quantized" (requires ``quantize_bits``), or
        "dropout" (zeroes residuals with probability ``dropout_p``).
    shadow_noise_sigma
        Optional Gaussian noise added to the projected shadow before lifting.

    Returns
    -------
    final_state, capsules
        ``final_state`` shaped [N, target_dim]; ``capsules`` is one
        :class:`LiftCapsule` per hop (shared across the whole batch, since
        every point in a batch follows the same window/hop schedule).
    """

    if residual_mode not in ("exact", "quantized", "dropout"):
        raise ValueError(f"unknown residual_mode: {residual_mode}")
    if rotation_mode not in ("single", "isoclinic"):
        raise ValueError(f"unknown rotation_mode: {rotation_mode}")
    if residual_mode == "quantized" and quantize_bits is None:
        raise ValueError("quantized residual_mode requires quantize_bits")
    if rng is None and (dropout_p > 0.0 or shadow_noise_sigma > 0.0):
        rng = np.random.default_rng(20260701)

    working = np.atleast_2d(np.asarray(state, dtype=float))
    if working.shape[1] == 0:
        raise ValueError("state must have at least one dimension; got a zero-width input")
    if target_dim < working.shape[1]:
        raise ValueError(
            f"target_dim ({target_dim}) must be >= the input dimensionality "
            f"({working.shape[1]}); recursive_lift only grows dimensionality, "
            "it does not project down."
        )
    capsules: list[LiftCapsule] = []
    hop = 0
    while working.shape[1] < target_dim:
        previous_dim = working.shape[1]
        drop_axis = drop_axis_fn(hop, previous_dim)
        shadow, residual = project_drop_axis(working, drop_axis)
        if shadow_noise_sigma > 0.0:
            shadow = apply_gaussian_noise(shadow, shadow_noise_sigma, rng)
        if residual_mode == "quantized":
            residual = quantize(residual, quantize_bits)
        elif residual_mode == "dropout":
            residual = apply_dropout(residual, dropout_p, rng)
        reconstructed = lift_insert_axis(shadow, drop_axis, residual)
        derived = derived_coordinate(reconstructed, hop)
        lifted = np.concatenate([reconstructed, derived[:, None]], axis=1)
        rotation_axis_new = lifted.shape[1] - 1
        theta = float(rotation_schedule[hop % len(rotation_schedule)])
        primary = (drop_axis, rotation_axis_new)

        sequence: list[tuple[tuple[int, int], float]] = [(primary, theta)]
        if rotation_mode == "isoclinic":
            partner = isoclinic_partner_plane(primary, lifted.shape[1])
            if partner is not None:
                # Equal and opposite angles on a disjoint plane. This is the
                # exact declared Hopf-fiber action only in the four-dimensional
                # coordinate convention tested by fram_eval.hopf_transport.
                sequence.append((partner, -theta))

        working = lifted
        for plane, angle in sequence:
            working = rotate_plane(working, plane[0], plane[1], angle)

        capsules.append(
            LiftCapsule(
                previous_dim=previous_dim,
                drop_axis=drop_axis,
                rotation_plane=primary,
                rotation_theta=theta,
                window_rule=window_rule,
                residual_mode=residual_mode,
                rotations=tuple(sequence) if len(sequence) > 1 else None,
            )
        )
        hop += 1
    return working, capsules


def recursive_reconstruct(final_state: np.ndarray, capsules: Sequence[LiftCapsule]) -> np.ndarray:
    """Invert :func:`recursive_lift` given the capsule chain it produced.

    Reconstruction is exact when ``residual_mode="exact"`` throughout, and
    degrades gracefully (measurably, not catastrophically) as residuals or
    shadows are quantized, dropped, or noised - see
    ``tests/test_rotational_lift.py`` for the measured degradation curves.
    """

    working = np.atleast_2d(np.asarray(final_state, dtype=float))
    for capsule in reversed(capsules):
        # Rotations compose in order, so the inverse applies them in reverse
        # with negated angles. For a single-plane capsule this is exactly the
        # previous behaviour.
        for plane, angle in reversed(capsule.rotation_sequence):
            working = rotate_plane(working, plane[0], plane[1], -angle)
        working = working[:, : capsule.previous_dim]
    return working


def compress_to_invariants(
    trajectory: np.ndarray, n_components: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """"Understanding" as compression (payload section 6): PCA via SVD.

    Extracts the top ``n_components`` principal-component directions of a
    trajectory gamma (shape [T, d]). The historical function name is retained
    for compatibility; fitted PCA directions are sample-density- and
    coordinate-dependent and are not generally dynamical invariants.

    Returns
    -------
    Z, basis, mean
        ``Z`` shape [T, n_components] - each state's coordinates in the
        fitted basis. ``basis`` shape [d, n_components] - orthonormal
        directions. ``mean`` shape [d] - the trajectory mean removed before
        projection. Reconstruct with :func:`reconstruct_from_invariants`.
    """

    trajectory = np.atleast_2d(np.asarray(trajectory, dtype=float))
    mean = trajectory.mean(axis=0)
    centered = trajectory - mean
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    n_components = max(0, min(n_components, vt.shape[0]))
    basis = vt[:n_components].T
    z = centered @ basis
    return z, basis, mean


def reconstruct_from_invariants(z: np.ndarray, basis: np.ndarray, mean: np.ndarray) -> np.ndarray:
    """Reconstruct trajectory points from compressed invariants Z."""

    return z @ basis.T + mean


def reentry_distances(trajectory: np.ndarray, reconstructed: np.ndarray) -> np.ndarray:
    """Per-step Euclidean distance between a trajectory and its reconstruction."""

    diff = np.asarray(trajectory, dtype=float) - np.asarray(reconstructed, dtype=float)
    return np.sqrt((diff * diff).sum(axis=-1))


def summarize_errors(errors: np.ndarray) -> dict[str, float]:
    """max/mean/rms summary of an error array (empty-safe)."""

    errors = np.asarray(errors, dtype=float)
    if errors.size == 0:
        return {"max": 0.0, "mean": 0.0, "rms": 0.0}
    return {
        "max": float(errors.max()),
        "mean": float(errors.mean()),
        "rms": float(np.sqrt((errors * errors).mean())),
    }


def passes_reentry_bound(trajectory: np.ndarray, reconstructed: np.ndarray, epsilon: float) -> bool:
    """"Understanding" re-entry criterion (payload section 6):
    d(gamma, Reconstruct(Z)) < epsilon for every step of the trajectory.

    This checks re-entry fidelity only. It does NOT check the payload's
    second understanding criterion (Loss(Task | Z) <= delta) - that requires
    a real downstream task and is explicitly out of scope for this module
    (see docs/rotational_lift.md, "What this does not demonstrate").
    """

    distances = reentry_distances(trajectory, reconstructed)
    if distances.size == 0:
        return True
    return bool(distances.max() < epsilon)
