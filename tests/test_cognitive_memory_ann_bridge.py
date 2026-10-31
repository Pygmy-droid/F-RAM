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


def test_cognitive_ann_candidates_returns_top_hit(tmp_path):
    cfg = FRAMConfig().model_copy(update={"STORAGE_ROOT": tmp_path / "storage"})
    store = CognitiveMemoryStore(tmp_path / "storage" / "memory" / "cognitive", config=cfg)
    vectorizer = build_cognitive_vectorizer(cfg)
    assert vectorizer is not None

    first = store.append_episode(
        query="alpha",
        answer="alpha response",
        embedding=_embed(vectorizer, "alpha response"),
    )
    store.append_episode(
        query="beta",
        answer="beta response",
        embedding=_embed(vectorizer, "beta response"),
    )

    candidates, obs = store.cognitive_ann_candidates(
        "alpha response",
        vectorizer=vectorizer,
        top_k=2,
    )

    assert obs["enabled"] is True
    assert obs["returned"] >= 1
    assert candidates[0]["doc_id"] == f"cmem:ep:{first['id']}"
    assert "ann_used" in obs
    if obs["ann_used"]:
        assert obs["index_backend"] in {"sklearn", "faiss"}
