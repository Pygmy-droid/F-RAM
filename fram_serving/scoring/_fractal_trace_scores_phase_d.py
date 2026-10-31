"""Fractal Trace Scores (Phase D extensions).

Stage 1 introduced logistic-alpha utilities; Stage 2 adds observability helpers.
This module now also exposes a standalone Phase D scorer that remains opt-in.
"""

from __future__ import annotations

import math
from typing import Iterable, List, Sequence

import numpy as np

from fram_serving.embedding.quaternion_adapter import (
    build_projection_matrix,
    quat_similarity,
    to_quaternion,
)


def compute_logistic_alpha(alpha0: float, r: float, t_max: int) -> List[float]:
    """Stage 1: generate a logistic alpha trajectory (clamped, no wiring yet)."""
    try:
        alpha = float(alpha0)
        rate = float(r)
        steps = int(t_max)
    except (TypeError, ValueError):
        return [float(alpha0)]
    if not np.isfinite(alpha) or not np.isfinite(rate) or steps < 0:
        return [float(alpha0)]
    alpha = float(np.clip(alpha, 0.0, 1.0))
    trajectory = [alpha]
    for _ in range(steps):
        next_alpha = rate * alpha * (1.0 - alpha)
        if not np.isfinite(next_alpha):
            trajectory.append(alpha)
            break
        alpha = float(np.clip(next_alpha, 0.0, 1.0))
        trajectory.append(alpha)
    desired_length = steps + 1
    if len(trajectory) > desired_length:
        trajectory = trajectory[:desired_length]
    elif len(trajectory) < desired_length:
        trajectory.extend([trajectory[-1]] * (desired_length - len(trajectory)))
    return trajectory


def classify_logistic_zone(r: float) -> str:
    """Stage 1 conceptual color zones for logistic-map regimes."""
    try:
        rate = float(r)
    except (TypeError, ValueError):
        return "blue"
    if rate < 2.8:
        return "blue"
    if rate < 3.5:
        return "green"
    if rate < 3.9:
        return "yellow"
    return "red"


def blend_scores_dynamic(local_score, global_score, alpha_t):
    """Stub: blend local/local scores using current alpha_t."""
    pass


def _safe_float(value):
    """Coerce to float where possible, returning None when conversion fails."""
    try:
        return float(value)
    except Exception:
        return None


def combine_quaternion_similarity(
    quat_sim,
    vec_sim,
    alpha_t,
    phase_d_enabled: bool,
) -> float:
    """Stage 2A: blend quaternion + vector similarity with safe fallbacks."""
    if not phase_d_enabled:
        return _safe_float(vec_sim) or 0.0

    q = _safe_float(quat_sim)
    v = _safe_float(vec_sim)
    a = _safe_float(alpha_t)

    if a is None or not np.isfinite(a):
        a = 0.0
    a = float(np.clip(a, 0.0, 1.0))

    q_valid = q is not None and np.isfinite(q)
    v_valid = v is not None and np.isfinite(v)

    if not v_valid and q_valid:
        return q
    if not v_valid and not q_valid:
        return 1.0
    if v_valid and not q_valid:
        return v
    return (a * q) + ((1.0 - a) * v)


def logistic_alpha_preview(alpha_t) -> float:
    """Stage 2B helper: expose the clamped logistic-alpha value."""
    a = _safe_float(alpha_t)
    if a is None or not np.isfinite(a):
        return 0.0
    return float(np.clip(a, 0.0, 1.0))


def quaternion_similarity_avg(sim_values) -> float:
    """Stage 2B helper: compute avg quaternion similarity ignoring invalids."""
    cleaned = []
    for value in sim_values or []:
        score = _safe_float(value)
        if score is not None and np.isfinite(score):
            cleaned.append(score)
    if not cleaned:
        return 0.0
    return float(sum(cleaned) / len(cleaned))


def logistic_state_color(alpha_t) -> str:
    """Stage 2B helper: qualitative labels for clamped alpha values."""
    a = logistic_alpha_preview(alpha_t)
    if a < 0.2:
        return "base"
    if a < 0.4:
        return "rising"
    if a < 0.6:
        return "transition"
    if a < 0.8:
        return "strong"
    return "saturated"


def attach_phase_d_observability(alpha_t, quat_similarity_values, phase_d_enabled: bool):
    """Stage 2C: build an observability block for Phase D diagnostics."""
    if not phase_d_enabled:
        return None
    return {
        "alpha_t": logistic_alpha_preview(alpha_t),
        "alpha_color": logistic_state_color(alpha_t),
        "quat_avg": quaternion_similarity_avg(quat_similarity_values),
    }


def compute_logistic_alpha_from_delta(vec_sim, quat_sim, k: float = 2.5, bias: float = 0.0) -> float:
    """Stage 4A helper: logistic response based on similarity delta.

    Tuned gain (k=2.5) emphasizes clear quaternion > vector regimes without
    saturating extremes (Phase D 4B/4C).
    """
    v = _safe_float(vec_sim)
    q = _safe_float(quat_sim)
    if v is None or not np.isfinite(v):
        v = 0.0
    if q is None or not np.isfinite(q):
        q = 0.0
    raw = (k * (q - v)) + bias
    try:
        a = 1.0 / (1.0 + math.exp(-raw))
    except OverflowError:
        a = 1.0 if raw > 0 else 0.0
    return float(np.clip(a, 0.0, 1.0))


def _cosine_similarity(a: Iterable[float], b: Iterable[float]) -> float:
    """Return cosine similarity with safe fallbacks."""
    try:
        vec_a = np.asarray(list(a), dtype=float).ravel()
        vec_b = np.asarray(list(b), dtype=float).ravel()
    except Exception:
        return 0.0
    if vec_a.size == 0 or vec_b.size == 0:
        return 0.0
    denom = np.linalg.norm(vec_a) * np.linalg.norm(vec_b)
    if denom == 0.0 or not np.isfinite(denom):
        return 0.0
    return float(np.dot(vec_a, vec_b) / denom)


def _to_quaternion(vec: Sequence[float], projection: np.ndarray) -> np.ndarray:
    """Helper to map a vector into quaternion space."""
    return to_quaternion(vec, projection)


def phase_d_score_batch(
    query_embedding: Sequence[float],
    episode_embeddings: Sequence[Sequence[float]],
    *,
    phase_d_enabled: bool = False,
    phase_d_debug: bool = False,
) -> dict[str, object]:
    """Standalone Phase D scorer for smoke tests and future integration."""
    query_vec = np.asarray(list(query_embedding), dtype=float).ravel()
    dim = query_vec.size
    projection = None
    if dim > 0:
        try:
            projection = build_projection_matrix(dim, seed=17)
        except ValueError:
            projection = None
    query_quat = _to_quaternion(query_vec, projection) if projection is not None else None

    scores: List[float] = []
    quat_values: List[float] = []
    alpha_values: List[float] = []

    for ep in episode_embeddings:
        ep_vec = np.asarray(list(ep), dtype=float).ravel()
        v = _cosine_similarity(query_vec, ep_vec)

        if projection is not None and query_quat is not None:
            ep_quat = _to_quaternion(ep_vec, projection)
            q = quat_similarity(query_quat, ep_quat)
        else:
            q = v

        alpha_t = compute_logistic_alpha_from_delta(v, q)
        quat_values.append(q)
        alpha_values.append(alpha_t)

        if phase_d_enabled:
            blended = combine_quaternion_similarity(
                quat_sim=q,
                vec_sim=v,
                alpha_t=alpha_t,
                phase_d_enabled=True,
            )
            scores.append(blended)
        else:
            scores.append(v)

    phase_d_obs = attach_phase_d_observability(
        alpha_t=alpha_values[-1] if alpha_values else 0.0,
        quat_similarity_values=quat_values,
        phase_d_enabled=phase_d_enabled,
    )

    diagnostics = {
        "phase_d": phase_d_obs if phase_d_debug else None,
    }
    return {
        "scores": scores,
        "diagnostics": diagnostics,
    }
