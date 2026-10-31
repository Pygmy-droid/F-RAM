from __future__ import annotations

import logging
from typing import Any, Iterable

import numpy as np

from fram_core.pipeline import _make_hashing_vectorizer

try:  # Optional dependency for semantic embeddings.
    from sentence_transformers import SentenceTransformer
except Exception:  # pragma: no cover - optional dependency
    SentenceTransformer = None  # type: ignore[assignment]


_LOG = logging.getLogger(__name__)
_SEMANTIC_MODELS: dict[str, Any] = {}


def normalize_cognitive_backend(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"semantic", "sbert", "sentence-transformers", "sentence_transformers"}:
        return "semantic"
    if raw == "":
        return "hashing"
    return raw


class _SemanticVectorizer:
    def __init__(self, model: Any) -> None:
        self._model = model

    def transform(self, texts: Iterable[str]) -> np.ndarray:
        batch = [str(text) for text in texts]
        embeddings = self._model.encode(batch, normalize_embeddings=True)
        return np.asarray(embeddings, dtype=float)


def _load_semantic_model(model_name: str) -> Any | None:
    if SentenceTransformer is None:
        return None
    cached = _SEMANTIC_MODELS.get(model_name)
    if cached is not None:
        return cached
    try:
        model = SentenceTransformer(model_name)
    except Exception as exc:
        _LOG.warning("Failed to load sentence-transformers model '%s': %s", model_name, exc)
        return None
    _SEMANTIC_MODELS[model_name] = model
    return model


def build_cognitive_vectorizer(config: Any) -> Any | None:
    backend = normalize_cognitive_backend(
        getattr(config, "cognitive_memory_embedding_backend", "hashing")
    )
    if backend == "hashing":
        return _make_hashing_vectorizer(config)
    if backend == "semantic":
        model_name = str(
            getattr(config, "cognitive_memory_semantic_model", "all-MiniLM-L6-v2")
        ).strip() or "all-MiniLM-L6-v2"
        model = _load_semantic_model(model_name)
        if model is None:
            _LOG.warning(
                "Semantic backend requested but sentence-transformers is unavailable; "
                "falling back to lexical search."
            )
            return None
        return _SemanticVectorizer(model)
    return None
