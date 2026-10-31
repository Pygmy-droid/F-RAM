"""Opt-in recognition in each persisted trace's own recorded IFS frame.

This recovers a six-dimensional projected seed, not its full embedding or an
observed life history. The default production scorer is deliberately unchanged.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np

from .fractal_types import TRACE_VERSION, TraceLine
from .metrics import min_max_normalize


def source_frame_components(
    generator: Any, trace: TraceLine, query: np.ndarray
) -> dict:
    """Verify the recorded recurrence and compare query/source in its frame.

    Every generated A_t is a scaled orthogonal matrix. With matching affine
    maps, ||q_t-x_t||^2 = product(s_t^2) * ||q_0-x_0||^2. Dividing total replay
    error by the summed contraction energy removes arbitrary trajectory length.
    Only the first step is inverted, avoiding unstable late-time reconstruction.
    """
    provenance = trace.provenance
    if provenance.get("version") != TRACE_VERSION:
        raise ValueError("unknown_recipe")
    seeds = []
    for name in ("projection_seed", "ifs_seed", "order_seed"):
        value = provenance.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("missing_recipe_seed")
        seeds.append(value)
    if not 2 <= len(trace.nodes) <= 4096:
        raise ValueError("invalid_node_count")
    if [node.index for node in trace.nodes] != list(range(len(trace.nodes))):
        raise ValueError("noncontiguous_nodes")
    coords = np.asarray([node.coord6 for node in trace.nodes], dtype=np.float64)
    if coords.shape != (len(trace.nodes), 6) or not np.isfinite(coords).all():
        raise ValueError("invalid_coordinates")
    vector = np.asarray(query, dtype=np.float64)
    if vector.shape != (generator.embedding_dim,) or not np.isfinite(vector).all():
        raise ValueError("invalid_query")
    projection_seed, ifs_seed, order_seed = seeds
    query_parent = generator.project(vector, projection_seed=projection_seed)
    transforms, offsets = generator._ifs_params(generator._rng(ifs_seed))
    order = generator._ifs_order(generator._rng(order_seed), len(transforms))
    first = order[0]
    parent = np.linalg.solve(transforms[first], coords[0] - offsets[first])
    energy = float(query_parent @ query_parent + parent @ parent)
    norm_product = float(np.linalg.norm(query_parent) * np.linalg.norm(parent))
    if not np.isfinite(energy) or norm_product <= 1e-24:
        raise ValueError("zero_or_invalid_parent")

    source_state, query_state = parent.copy(), query_parent.copy()
    contraction, contraction_energy, squared_error, max_error = 1.0, 0.0, 0.0, 0.0
    for index, stored in enumerate(coords):
        chosen = order[index % len(order)]
        matrix, offset = transforms[chosen], offsets[chosen]
        source_state = matrix @ source_state + offset
        query_state = matrix @ query_state + offset
        max_error = max(max_error, float(np.max(np.abs(source_state - stored))))
        if not np.allclose(source_state, stored, rtol=1e-9, atol=1e-9):
            raise ValueError("recurrence_mismatch")
        residual = query_state - stored
        squared_error += float(residual @ residual)
        contraction *= float(np.sum(matrix * matrix) / 6.0)
        contraction_energy += contraction
    distance = squared_error / contraction_energy / energy
    cosine = float(np.clip(query_parent @ parent / norm_product, -1.0, 1.0))
    if not np.isfinite(distance) or distance < 0:
        raise ValueError("invalid_replay_distance")
    return {
        "cosine": cosine,
        "source_frame_distance": distance,
        "replay_similarity": 1.0 / (1.0 + distance),
        "recurrence_max_abs_error": max_error,
        "projection_seed": projection_seed,
        "nodes": len(trace.nodes),
    }


def score_source_frames(
    store: Any,
    query: np.ndarray,
    limit: int,
    *,
    alpha: float,
    bound_episode_ids: set[str] | None,
) -> list[dict]:
    """Score only supported, internally consistent traces; never repair in place."""
    if limit <= 0:
        return []
    if not np.isfinite(alpha) or not 0 <= alpha <= 1:
        raise ValueError("source-frame blend alpha must be in [0, 1]")
    rows, rejected = [], Counter()
    for trace, metadata in store.iter_traces():
        if bound_episode_ids is not None and trace.seed_id not in bound_episode_ids:
            rejected["unbound_episode"] += 1
            continue
        try:
            components = source_frame_components(store.generator, trace, query)
        except (ValueError, np.linalg.LinAlgError) as exc:
            rejected[str(exc)] += 1
            continue
        rows.append(
            {
                "episode_id": trace.seed_id,
                **components,
                "metadata": metadata,
                "scoring_mode": "source_frame",
                "distance_kind": "contraction_normalized_aligned_replay",
                "normalization": "min_max",
                "provenance": trace.provenance,
            }
        )
    if not rows:
        return []
    cosine = min_max_normalize(np.array([row["cosine"] for row in rows]))
    replay = min_max_normalize(np.array([row["replay_similarity"] for row in rows]))
    for row, cos_n, replay_n in zip(rows, cosine, replay):
        row.update(
            score=float(alpha * cos_n + (1.0 - alpha) * replay_n),
            score_raw=float(
                alpha * row["cosine"] + (1.0 - alpha) * row["replay_similarity"]
            ),
            score_components={
                "cosine_norm": float(cos_n),
                "replay_norm": float(replay_n),
                "alpha": alpha,
            },
            trace_coverage={"valid": len(rows), "rejected": dict(rejected)},
        )
    rows.sort(key=lambda row: row["score"], reverse=True)
    return rows[:limit]
