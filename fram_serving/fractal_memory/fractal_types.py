from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Tuple

import numpy as np

ScaleLabel = Literal["macro", "meso", "micro"]


@dataclass(frozen=True)
class FractalSeed:
    """Seed parameters used to generate a deterministic fractal trace."""

    episode_id: str
    timestamp_ms: int
    embedding: np.ndarray
    metadata: Dict[str, Any] = field(default_factory=dict)

    def vector(self) -> np.ndarray:
        """Return the embedding as a 1-D float vector."""
        array = np.asarray(self.embedding, dtype=float).ravel()
        if array.ndim != 1:
            raise ValueError("fractal seed embeddings must be 1-D")
        return array


@dataclass(frozen=True)
class TraceNode:
    """Single point along a generated fractal trace line."""

    scale: ScaleLabel
    coord6: Tuple[float, float, float, float, float, float]
    s_arc: float
    index: int
    q: Tuple[float, float, float, float] | None = None
    lambda_value: float | None = None


@dataclass
class TraceLine:
    """Ordered list of sampled nodes representing a trace path."""

    seed_id: str
    nodes: List[TraceNode] = field(default_factory=list)
    provenance: Dict[str, Any] = field(default_factory=dict)


TRACE_VERSION = "fractal-trace-v0"
TRACE_SCHEMA_VERSION = 2
DEFAULT_QUATERNION = (1.0, 0.0, 0.0, 0.0)
DEFAULT_LAMBDA = 0.5
