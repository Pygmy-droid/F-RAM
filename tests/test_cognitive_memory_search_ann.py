from __future__ import annotations

import numpy as np

from fram_serving.config import FRAMConfig
from fram_serving.cognitive_embeddings import build_cognitive_vectorizer
from fram_serving.memory import CognitiveMemoryStore


def _embed(vectorizer, text: str) -> list[float]:
    matrix = vectorizer.transform([text])
    if hasattr(matrix, "toarray"):
        arr = matrix.toarray()[0]
    else:
        arr = np.asarray(matrix, dtype=float).ravel()
    arr = np.asarray(arr, dtype=float).ravel()
    return arr.tolist()


def test_cognitive_search_ann_diagnostics(tmp_path):
    cfg = FRAMConfig().model_copy(update={"STORAGE_ROOT": tmp_path / "storage"})
    store = CognitiveMemoryStore(tmp_path / "storage" / "memory" / "cognitive", config=cfg)
    vectorizer = build_cognitive_vectorizer(cfg)
    assert vectorizer is not None

    store.append_episode(
        query="alpha",
        answer="alpha response",
        embedding=_embed(vectorizer, "alpha response"),
    )

    diag: dict[str, object] = {}
    results = store.search("alpha response", k=1, vectorizer=vectorizer, diagnostics=diag)

    assert results
    assert "ann_enabled" in diag
    if diag.get("ann_enabled"):
        assert diag.get("ann_backend") in {"sklearn", "faiss"}
