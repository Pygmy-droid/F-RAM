from __future__ import annotations

import hashlib
from typing import Optional, Sequence, Tuple

import numpy as np

from .fractal_types import DEFAULT_QUATERNION


def _hash_seed(vector: np.ndarray) -> int:
    data = np.asarray(vector, dtype=np.float32).tobytes()
    digest = hashlib.blake2s(data, digest_size=8).digest()
    return int.from_bytes(digest, "big") & 0x7FFFFFFF


def coord6_to_vec3(coord6: Sequence[float]) -> np.ndarray:
    vec = np.asarray(coord6, dtype=float).ravel()
    if vec.size != 6:
        raise ValueError("coord6 must have six elements")
    return np.array(
        [
            0.5 * (vec[0] + vec[3]),
            0.5 * (vec[1] + vec[4]),
            0.5 * (vec[2] + vec[5]),
        ],
        dtype=float,
    )


def _unit_vector(vec: np.ndarray, *, eps: float = 1e-12) -> np.ndarray | None:
    norm = float(np.linalg.norm(vec))
    if norm <= eps:
        return None
    return vec / norm


def _quat_from_direction(
    direction: np.ndarray | None,
) -> Tuple[float, float, float, float]:
    if direction is None:
        return DEFAULT_QUATERNION
    axis = np.array([1.0, 0.0, 0.0], dtype=float)
    d = np.asarray(direction, dtype=float)
    dot = float(np.clip(np.dot(axis, d), -1.0, 1.0))
    if dot < -0.999999:
        ortho = np.array([0.0, 1.0, 0.0], dtype=float)
        if abs(float(np.dot(ortho, d))) > 0.9:
            ortho = np.array([0.0, 0.0, 1.0], dtype=float)
        ortho = ortho / float(np.linalg.norm(ortho))
        return (0.0, float(ortho[0]), float(ortho[1]), float(ortho[2]))
    v = np.cross(axis, d)
    w = 1.0 + dot
    q_raw = np.array([w, v[0], v[1], v[2]], dtype=float)
    norm = float(np.linalg.norm(q_raw))
    if norm <= 1e-12:
        return DEFAULT_QUATERNION
    q = q_raw / norm
    return (float(q[0]), float(q[1]), float(q[2]), float(q[3]))


def path_quaternions(path6: np.ndarray) -> np.ndarray:
    coords = np.asarray(path6, dtype=np.float64)
    if coords.ndim != 2 or coords.shape[1] != 6:
        raise ValueError("path must be 2-D with 6 columns")
    if coords.shape[0] == 0:
        return np.zeros((0, 4), dtype=np.float64)
    p3 = np.column_stack(
        [
            0.5 * (coords[:, 0] + coords[:, 3]),
            0.5 * (coords[:, 1] + coords[:, 4]),
            0.5 * (coords[:, 2] + coords[:, 5]),
        ]
    )
    directions = np.zeros_like(p3)
    if p3.shape[0] == 1:
        directions[0] = 0.0
    else:
        directions[:-1] = p3[1:] - p3[:-1]
        directions[-1] = p3[-1] - p3[-2]
    quats = np.zeros((p3.shape[0], 4), dtype=np.float64)
    for idx, direction in enumerate(directions):
        unit = _unit_vector(direction)
        quats[idx] = np.array(_quat_from_direction(unit), dtype=np.float64)
    return quats


def quaternion_alignment(
    query_quats: np.ndarray,
    trace_quats: np.ndarray,
    *,
    absolute: bool = True,
) -> np.ndarray:
    q_a = np.asarray(query_quats, dtype=np.float64)
    q_b = np.asarray(trace_quats, dtype=np.float64)
    if q_a.ndim != 2 or q_b.ndim != 2 or q_a.shape[1] != 4 or q_b.shape[1] != 4:
        raise ValueError("quaternion arrays must be 2-D with 4 columns")
    length = min(q_a.shape[0], q_b.shape[0])
    if length == 0:
        return np.zeros((0,), dtype=np.float64)
    dots = np.einsum("ij,ij->i", q_a[:length], q_b[:length], optimize=True)
    if absolute:
        dots = np.abs(dots)
    return dots


def _logistic_seed(seed_id: str, index: int) -> float:
    key = f"{seed_id}:{index}"
    digest = hashlib.blake2s(key.encode("utf-8"), digest_size=8).digest()
    value = int.from_bytes(digest, "big")
    denom = float(2**64)
    return (value + 0.5) / denom


def logistic_lambda(seed_id: str, index: int) -> float:
    r = 3.99
    x = _logistic_seed(seed_id, index)
    x = r * x * (1.0 - x)
    if x <= 0.0:
        return 1e-12
    if x >= 1.0:
        return 1.0 - 1e-12
    return float(x)


def build_query_path(
    query_point: np.ndarray,
    *,
    steps: int = 64,
    spread: float = 0.05,
) -> np.ndarray:
    """Construct a deterministic synthetic trajectory for the query embedding."""
    base = np.asarray(query_point, dtype=np.float64).ravel()
    if base.size != 6:
        raise ValueError(f"query point must be 6-D (received {base.size})")
    norm = float(np.linalg.norm(base))
    direction = (
        base / (norm + 1e-9) if norm > 0 else np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    )
    t = np.linspace(-1.0, 1.0, steps, dtype=np.float64)
    seed = _hash_seed(base)
    rng = np.random.RandomState(seed)
    jitter = rng.normal(scale=spread * 0.25, size=(steps, 6))
    arc = (t[:, None] * direction[None, :] * spread) + jitter
    path = base[None, :] + np.cumsum(arc, axis=0)
    return path.astype(np.float64, copy=False)


def downsample_path(path: np.ndarray, *, target: int = 128) -> tuple[np.ndarray, int]:
    """Downsample a path to a fixed number of steps using a deterministic stride."""
    array = np.asarray(path, dtype=np.float64)
    if array.ndim != 2:
        raise ValueError("path must be a 2-D array (steps x dims)")
    steps = array.shape[0]
    if steps <= target:
        return array, 1
    stride = max(1, steps // target)
    sampled = array[::stride]
    if sampled.shape[0] > target:
        sampled = sampled[:target]
    return sampled, stride


def soft_dtw_distance(
    path_a: np.ndarray,
    path_b: np.ndarray,
    *,
    gamma: float = 0.1,
    band: Optional[float] = 0.15,
) -> float:
    """Compute the soft-DTW distance between two sequences."""
    seq_a = np.asarray(path_a, dtype=np.float64)
    seq_b = np.asarray(path_b, dtype=np.float64)
    if seq_a.ndim != 2 or seq_b.ndim != 2:
        raise ValueError("paths must be 2-D arrays (steps x dims)")
    if seq_a.shape[0] == 0 or seq_b.shape[0] == 0:
        return float("inf")
    if seq_a.shape[1] != seq_b.shape[1]:
        raise ValueError("paths must share dimensionality")
    n, m = seq_a.shape[0], seq_b.shape[0]
    diff = seq_a[:, None, :] - seq_b[None, :, :]
    cost = np.einsum("ijk,ijk->ij", diff, diff, optimize=True)
    r = np.full((n + 1, m + 1), np.inf, dtype=np.float64)
    r[0, 0] = 0.0
    band_width = None
    if band is not None:
        band_width = max(1, int(band * max(n, m)))
    rows = np.arange(1, n + 1)
    if band_width is not None:
        # Keep the original row-dependent, asymmetric band and integer rounding.
        centers = np.fromiter(
            (int((i - 1) * (m / max(n, 1))) for i in range(1, n + 1)),
            dtype=np.intp,
            count=n,
        )
        starts = np.maximum(1, centers - band_width)
        stops = np.minimum(m + 1, centers + band_width + 1)
    # Cells with the same i+j depend only on earlier anti-diagonals. Evaluate
    # them together without changing the recurrence or reducing the path/band.
    for diagonal in range(2, n + m + 1):
        i = rows[max(1, diagonal - m) - 1 : min(n, diagonal - 1)]
        j = diagonal - i
        if band_width is not None:
            inside = (j >= starts[i - 1]) & (j < stops[i - 1])
            i, j = i[inside], j[inside]
        if i.size == 0:
            continue
        prev = np.stack((r[i - 1, j], r[i, j - 1], r[i - 1, j - 1]))
        v = -prev / gamma
        vmax = np.max(v, axis=0)
        softmin = -gamma * (vmax + np.log(np.exp(v - vmax).sum(axis=0)))
        r[i, j] = cost[i - 1, j - 1] + softmin
    return float(r[n, m])


def soft_dtw_similarity(distance: float | np.ndarray) -> float | np.ndarray:
    """Monotone reciprocal similarity over the full soft-DTW value range.

    Soft-DTW may be negative even for identical paths. Keep 1/(1+d) exactly
    for d >= 0; its continuous decreasing extension for d < 0 is
    2 - 1/(1-d). Finite scores lie in (0, 2), with no pole at d=-1.
    Non-finite distances retain the scorer's no-evidence value of zero.
    This is a score transform, not a nonnegative divergence or probability.
    """
    values = np.asarray(distance, dtype=np.float64)
    scores = np.zeros_like(values)
    finite = np.isfinite(values)
    positive = finite & (values >= 0)
    negative = finite & (values < 0)
    scores[positive] = 1.0 / (1.0 + values[positive])
    scores[negative] = 2.0 - 1.0 / (1.0 - values[negative])
    return float(scores) if scores.ndim == 0 else scores


def min_max_normalize(values: np.ndarray) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    if array.size == 0:
        return array
    v_min = float(np.min(array))
    v_max = float(np.max(array))
    if not np.isfinite(v_min) or not np.isfinite(v_max):
        return array
    if np.isclose(v_min, v_max):
        return np.zeros_like(array)
    norm = (array - v_min) / (v_max - v_min)
    return np.clip(norm * 2.0 - 1.0, -1.0, 1.0)
