from __future__ import annotations

import math
import re
from collections import Counter
from typing import List, Tuple

_TOKEN_RE = re.compile(r"\b\w+\b")


class Reranker:
    """Abstract interface for scoring query-document pairs."""

    def score(self, pairs: List[Tuple[str, str]]) -> List[float]:
        raise NotImplementedError


class SimpleCosineReranker(Reranker):
    """Bag-of-words cosine similarity reranker."""

    def score(self, pairs: List[Tuple[str, str]]) -> List[float]:
        scores: List[float] = []
        for query, document in pairs:
            q_counts = self._bow(query)
            d_counts = self._bow(document)
            scores.append(self._cosine(q_counts, d_counts))
        return scores

    @staticmethod
    def _bow(text: str) -> Counter[str]:
        tokens = _TOKEN_RE.findall(text.lower())
        return Counter(tokens)

    @staticmethod
    def _cosine(vec1: Counter[str], vec2: Counter[str]) -> float:
        if not vec1 or not vec2:
            return 0.0
        dot = 0.0
        for term, weight in vec1.items():
            dot += weight * vec2.get(term, 0)
        if dot == 0.0:
            return 0.0
        norm1 = math.sqrt(sum(v * v for v in vec1.values()))
        norm2 = math.sqrt(sum(v * v for v in vec2.values()))
        if norm1 == 0.0 or norm2 == 0.0:
            return 0.0
        return dot / (norm1 * norm2)
