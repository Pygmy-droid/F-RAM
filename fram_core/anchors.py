from __future__ import annotations
"""
Anchors utilities (lite)

This module provides minimal helpers to support an "anchors" widening path.
It deliberately stays light: we expose a novelty-based greedy selector that
prefers candidates which add the most new facts, and a function to compute
basic residualized directions that can later be used for curvature-aware steps.

When you are ready to implement full CELF over I"/C, expand these utilities
to include marginal-gain caching and composite costs.
"""

from typing import Dict, Iterable, List, Sequence, Set, Tuple
import numpy as np


def residualize(x: np.ndarray, p_k: np.ndarray, U_k: np.ndarray) -> np.ndarray:
    """Project residual (I - U U^T)(x - p_k)."""
    delta = x - p_k
    return delta - U_k @ (U_k.T @ delta)


def principal_residual_directions(
    neighbors: np.ndarray, p_k: np.ndarray, U_k: np.ndarray, top_m: int
) -> Tuple[np.ndarray, np.ndarray]:
    """Compute up to top_m principal directions on residuals.

    Parameters
    ----------
    neighbors
        Array shaped [k0, d] of L2-normalised vectors in the same space as ``p_k``.
    p_k
        Cluster centroid.
    U_k
        Cluster basis (columns are orthonormal directions).
    top_m
        Maximum number of directions/eigenvalues to return.

    Returns
    -------
    directions, eigenvalues
        ``directions`` is shaped [d, m] with unit-norm columns. ``eigenvalues``
        is shaped [m] with the corresponding principal residual variances.
    """

    if neighbors.size == 0:
        return np.zeros((p_k.shape[0], 0), dtype=float), np.zeros((0,), dtype=float)

    R = np.stack([residualize(x, p_k, U_k) for x in neighbors], axis=0)
    C = R.T @ R  # Residual covariance (unscaled)

    w, V = np.linalg.eigh(C)
    order = np.argsort(w)[::-1]
    w = w[order]
    V = V[:, order]

    count = min(top_m, V.shape[1]) if top_m > 0 else 0
    V = V[:, :count]
    w = w[:count]

    for j in range(V.shape[1]):
        n = np.linalg.norm(V[:, j])
        if n > 0:
            V[:, j] /= n

    return V, w


def select_by_novelty(
    candidates: Sequence[int],
    facts_map: Dict[int, Set[str]],
    k: int,
    already_selected: Iterable[int] | None = None,
) -> List[int]:
    """Greedy novelty selection: maximize new facts at each step.

    - candidates: pool of candidate indices
    - facts_map: index -> set of facts
    - k: number to select
    - already_selected: indices to exclude and seed seen facts
    """
    selected: List[int] = []
    seen: Set[str] = set()
    seed_indices: Set[int] = set()
    if already_selected is not None:
        seed_indices = {int(i) for i in already_selected}
        for i in seed_indices:
            seen |= facts_map.get(int(i), set())

    pool = [int(i) for i in candidates if int(i) not in seed_indices]
    while len(selected) < k and pool:
        best_i = None
        best_gain = -1
        for i in pool:
            gain = len(facts_map.get(int(i), set()) - seen)
            if gain > best_gain:
                best_gain = gain
                best_i = int(i)
        if best_i is None:
            # No gain; pick the first remaining to make progress
            best_i = int(pool[0])
        selected.append(best_i)
        seen |= facts_map.get(best_i, set())
        pool = [i for i in pool if i != best_i]
    return selected
