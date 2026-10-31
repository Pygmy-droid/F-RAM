from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

import numpy as np


@dataclass(slots=True)
class _StreamState:
    prev: np.ndarray | None = None
    prev_delta: np.ndarray | None = None
    steps: int = 0


def _normalized_entropy_from_abs(values: np.ndarray, *, eps: float) -> float:
    if values.size <= 1:
        return 0.0
    total = float(np.sum(values))
    if total <= eps:
        return 0.0
    p = values / total
    p = p[p > 0]
    if p.size == 0:
        return 0.0
    entropy = -float(np.sum(p * np.log(p)))
    denom = float(np.log(values.size))
    if denom <= eps:
        return 0.0
    return float(entropy / denom)


class TransitionalComplexityProbe:
    """Instrumentation-only probe for structured change over time.

    The probe maintains lightweight per-stream state. Call `update()` each time
    a stable internal vector is produced (e.g., query embeddings, routing scores)
    and log the returned scalar(s) for observability. No pipeline behavior should
    depend on these values.
    """

    def __init__(self, *, eps: float = 1e-12) -> None:
        self._eps = float(eps)
        self._streams: dict[str, _StreamState] = {}

    def reset(self, stream: str | None = None) -> None:
        if stream is None:
            self._streams.clear()
            return
        self._streams.pop(stream, None)

    def update(self, stream: str, vector: np.ndarray) -> Dict[str, Any]:
        vec = np.asarray(vector, dtype=float).reshape(-1)
        state = self._streams.get(stream)
        if state is None:
            state = _StreamState()
            self._streams[stream] = state

        dim = int(vec.size)
        if dim == 0:
            return {
                "stream": stream,
                "step": int(state.steps),
                "dim": 0,
                "delta_l2": 0.0,
                "delta_entropy": 0.0,
                "curvature_l2": 0.0,
                "tc": 0.0,
                "has_prev": False,
            }

        prev = state.prev
        prev_delta = state.prev_delta
        if prev is None or prev.shape != vec.shape:
            delta = np.zeros_like(vec)
            delta_l2 = 0.0
            curvature_l2 = 0.0
            delta_entropy = 0.0
            has_prev = False
        else:
            delta = vec - prev
            delta_l2 = float(np.linalg.norm(delta))
            if prev_delta is None or prev_delta.shape != delta.shape:
                curvature_l2 = 0.0
            else:
                curvature_l2 = float(np.linalg.norm(delta - prev_delta))
            delta_entropy = _normalized_entropy_from_abs(np.abs(delta), eps=self._eps)
            has_prev = True

        tc_total = float(delta_l2 * (1.0 + delta_entropy))

        state.prev = vec.copy()
        state.prev_delta = delta.copy()
        state.steps += 1

        return {
            "stream": stream,
            "step": int(state.steps),
            "dim": dim,
            "delta_l2": float(delta_l2),
            "delta_entropy": float(delta_entropy),
            "curvature_l2": float(curvature_l2),
            "tc": float(tc_total),
            "has_prev": bool(has_prev),
        }

