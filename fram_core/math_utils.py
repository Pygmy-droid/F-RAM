from __future__ import annotations
import numpy as np

def whiten_embeddings(X: np.ndarray, mean: np.ndarray, W: np.ndarray) -> np.ndarray:
    """Whiten embeddings: (X - mean) @ W

    Shapes:
      X: [n, d] or [d]
      mean: [d]
      W: [d, d] (can be reduced if pre-truncated)
    """
    X2 = np.atleast_2d(X)
    Y = (X2 - mean) @ W
    return Y if X.ndim > 1 else Y[0]  # keep original shape


def robust_z(x: np.ndarray | float, median: float, mad: float, eps: float = 1e-9) -> np.ndarray | float:
    """Median/MAD z-score. Uses 1.4826 scaling to make MAD ~= std for Gaussians.

    rZ = (x - median) / (1.4826 * MAD + eps)
    """
    return (x - median) / (1.4826 * mad + eps)


def subspace_projection(e: np.ndarray, p_k: np.ndarray, U_k: np.ndarray) -> np.ndarray:
    """μ_k = p_k + U_k U_k^T (e - p_k)"""
    delta = e - p_k
    return p_k + U_k @ (U_k.T @ delta)


def mhd(e: np.ndarray, p_k: np.ndarray, U_k: np.ndarray, eps: float = 1e-9) -> float:
    """Subspace match in [0,1]: ||U_k^T (e - p_k)||^2 / (||e - p_k||^2 + eps).

    Spec mapping (docs/FRAMv2.2-SPEC.md Section 5.1): Ensure the ratio stays inside [0,1]
    even when numerical noise or imperfect orthonormal bases push the raw
    computation slightly outside the interval.
    """
    delta = e - p_k
    proj = U_k.T @ delta
    num = float(np.dot(proj, proj))
    den = float(np.dot(delta, delta))
    if den <= eps:
        return 0.0
    ratio = num / (den + eps)
    return float(np.clip(ratio, 0.0, 1.0))


def pairwise_mean_knn_dist(mu_k: np.ndarray, neighbors: np.ndarray) -> float:
    """Mean distance from μ_k to its k0 neighbors (neighbors shape [k0, d])."""

    if neighbors.size == 0:
        return 0.0
    diffs = neighbors - mu_k[None, :]
    if diffs.size == 0:
        return 0.0
    dists = np.sqrt((diffs * diffs).sum(axis=1))
    if not np.isfinite(dists).all():
        dists = dists[np.isfinite(dists)]
        if dists.size == 0:
            return 0.0
    return float(dists.mean())


def projection_help_delta(e: np.ndarray, p_k: np.ndarray, U_k: np.ndarray) -> float:
    """Projection help Δd = ||e - p_k||^2 - ||I*_k - p_k||^2.

    Positive values indicate the subspace projection reduces distance to the centroid
    (i.e., helps). Higher is better per spec.

    Spec mapping:
      - FRAM v2.2 Spec, Section 5.1: Projection help Δd; use rZ_k(Δd)
      - Cheatsheet: "Δd = ||e - p_k||^2 - ||I*_k - p_k||^2 ; z-score via median/MAD"
    """
    delta = e - p_k
    mu_k = subspace_projection(e, p_k, U_k)
    d_full = float(np.dot(delta, delta))
    d_proj = float(np.dot(mu_k - p_k, mu_k - p_k))
    return d_full - d_proj


def centroid_distance(e: np.ndarray, p_k: np.ndarray) -> float:
    """Euclidean distance ||e - p_k|| used for d_c before robust z-normalization.

    Spec mapping:
      - FRAM v2.2 Spec, Section 5.1: d_c,norm = rZ_k(||e - p_k||)
      - Cheatsheet: "d_c = z(||e - p_k||)"
    """
    delta = e - p_k
    return float(np.sqrt(float(np.dot(delta, delta))))
