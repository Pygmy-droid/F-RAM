from __future__ import annotations
"""
Prototype bank (lite)

Stores a set of centroids p_k and subspace bases U_k, and supports a simple
cosine-based shortlist over p_k. This is a lightweight placeholder for an ANN
index; replace with FAISS/HNSW or vendor-specific indices when needed.
"""

from dataclasses import dataclass
from typing import List, Sequence, Tuple
import numpy as np


@dataclass
class Prototype:
    p_k: np.ndarray  # centroid [d]
    U_k: np.ndarray  # basis [d, r]


class PrototypeBank:
    def __init__(self, prototypes: Sequence[Prototype]):
        self._P = prototypes
        if len(self._P) == 0:
            self._d = 0
        else:
            self._d = int(self._P[0].p_k.shape[0])

    @property
    def dim(self) -> int:
        return self._d

    def __len__(self) -> int:
        return len(self._P)

    def shortlist(self, e: np.ndarray, k0: int) -> List[int]:
        """Return indices of top-k0 prototypes by cosine similarity on p_k.

        Assumes p_k are L2-normalized or that cosine ~ inner product is acceptable.
        """
        if len(self._P) == 0:
            return []
        d = e.shape[0]
        scores = np.array([float(np.dot(e, p.p_k)) for p in self._P], dtype=float)
        order = np.argsort(scores)[::-1]
        k = min(int(k0), len(order))
        return [int(i) for i in order[:k]]
