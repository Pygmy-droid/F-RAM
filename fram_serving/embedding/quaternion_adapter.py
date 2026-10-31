"""Quaternion Adapter - Phase D scaffold.

Stage 1 now exposes deterministic projection helpers. The module is still inert
until the Phase D feature flags are enabled; no runtime code references these
functions yet outside controlled tests.
"""

from __future__ import annotations

from typing import Iterable

import numpy as np

DEFAULT_IDENTITY_QUATERNION = np.array([1.0, 0.0, 0.0, 0.0], dtype=float)


def build_projection_matrix(d: int, seed: int = 17) -> np.ndarray:
    """Return a deterministic 4-by-d projection matrix (no orthonormalization).

    Phase D requires reproducible projections, so a fixed RandomState ensures the
    same 4×d matrix for a given seed. The distribution is standard normal and we
    intentionally skip orthonormalization per the Phase D spec.
    """
    if d <= 0:
        raise ValueError("Projection dimension 'd' must be positive")
    rng = np.random.RandomState(seed)
    return rng.randn(4, d).astype(float, copy=False)


def to_quaternion(x: Iterable[float], projection: np.ndarray) -> np.ndarray:
    """Project vector `x` into quaternion space and normalize to unit length.

    Stage 1 only performs `projection @ x` followed by normalization. All other
    blending/similarity logic stays out of this module until later phases.
    """
    if projection is None:
        raise ValueError("Projection matrix is required for quaternion mapping")
    projection = np.asarray(projection, dtype=float)
    if projection.shape[0] != 4:
        raise ValueError("Projection matrix must be shaped (4, d)")
    vector = np.asarray(x, dtype=float).ravel()
    if vector.shape[0] != projection.shape[1]:
        raise ValueError(
            f"Vector dimension {vector.shape[0]} does not match projection width "
            f"{projection.shape[1]}"
        )
    quat = projection @ vector
    norm = np.linalg.norm(quat)
    if not np.isfinite(norm) or norm == 0.0:
        # Degenerate projection; return deterministic default quaternion.
        return DEFAULT_IDENTITY_QUATERNION.copy()
    return (quat / norm).astype(float, copy=False)


def hopf_map(q: Iterable[float]) -> np.ndarray:
    """Map a nonzero quaternion to the S² base of the Hopf fibration.

    Quaternions use ``(w, x, y, z)`` order.  The returned three-vector is the
    image of the x-axis under ``q * i * q^-1``.  Inputs are normalized, so the
    map is invariant under nonzero scalar magnitude and under the ``q``/``-q``
    representation ambiguity.

    This is only the canonical map ``S³ -> S²``.  It does not define a lift,
    connection, fiber phase, or an identification between rotational-lift
    residuals and the Hopf ``S¹`` fiber.
    """

    quat = np.asarray(q, dtype=float).ravel()
    if quat.shape != (4,):
        raise ValueError("Hopf map input must contain exactly four quaternion components")
    norm = float(np.linalg.norm(quat))
    if not np.isfinite(norm) or norm == 0.0:
        raise ValueError("Hopf map input must be finite and nonzero")
    w, x, y, z = quat / norm
    base = np.array(
        [
            w * w + x * x - y * y - z * z,
            2.0 * (x * y + w * z),
            2.0 * (x * z - w * y),
        ],
        dtype=float,
    )
    # The closed form is unit length analytically; normalize once more to keep
    # floating-point drift from leaking into downstream proof-track checks.
    return base / np.linalg.norm(base)


def quat_similarity(q1, q2):
    """Stage 1 minimal similarity using the quaternion dot product.

    Later stages may replace this with angular distance, but for now we simply
    compute the dot product of two unit quaternions and clamp the result into
    [-1, 1]. If inputs are malformed we fall back to the identity-dot-identity
    baseline (1.0).
    """
    try:
        q1_arr = np.asarray(q1, dtype=float).ravel()
        q2_arr = np.asarray(q2, dtype=float).ravel()
    except Exception:
        return float(DEFAULT_IDENTITY_QUATERNION @ DEFAULT_IDENTITY_QUATERNION)
    if q1_arr.shape != (4,) or q2_arr.shape != (4,):
        return float(DEFAULT_IDENTITY_QUATERNION @ DEFAULT_IDENTITY_QUATERNION)
    if not np.all(np.isfinite(q1_arr)) or not np.all(np.isfinite(q2_arr)):
        return float(DEFAULT_IDENTITY_QUATERNION @ DEFAULT_IDENTITY_QUATERNION)
    sim = float(np.dot(q1_arr, q2_arr))
    if sim > 1.0:
        return 1.0
    if sim < -1.0:
        return -1.0
    return sim
