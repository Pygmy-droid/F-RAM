from datetime import datetime, timedelta, timezone
import numpy as np
from fastapi.testclient import TestClient
from sklearn.feature_extraction.text import HashingVectorizer
import pytest
import fram_serving.app as app
from fram_index.version_lattice import VersionLattice, VersionNode
from fram_index.sparse_keys import SparseKeyIndex


def _make_cache_two_chunks(text1: str, text2: str):
    # Build a minimal cache with two chunks using app helpers
    t1_tokens = app._tokenize(text1)
    t2_tokens = app._tokenize(text2)
    now = datetime.now(timezone.utc)
    lattice = VersionLattice()
    sparse_index = SparseKeyIndex()
    chunk_specs = [
        ("fake1.txt", text1, t1_tokens, now),
        ("fake2.txt", text2, t2_tokens, now + timedelta(minutes=1)),
    ]
    chunks = []
    for fname, raw_text, tokens, ts in chunk_specs:
        lattice.add_node(VersionNode(node_id=fname, timestamp=ts))
        sparse_index.add(fname, raw_text)
        chunks.append(
            {
                "file": fname,
                "chunk_id": 0,
                "text": raw_text,
                "tokens": tokens,
                "timestamp": ts.isoformat(),
            }
        )
    vectorizer = HashingVectorizer(
        lowercase=True,
        token_pattern=r"\b\w+\b",
        n_features=app.CFG.embedding_dim,
        alternate_sign=False,
        norm=None,
    )
    vecs = vectorizer.transform([text1, text2]).toarray().astype(float, copy=False)
    vocab = app._build_vocab([t1_tokens, t2_tokens])
    return {
        "chunks": chunks,
        "vocab": vocab,
        "chunk_vecs": vecs,
        "lattice": lattice,
        "sparse_index": sparse_index,
    }


@pytest.mark.slow
def test_coverage_facts_added_positive_when_new_facts_in_second(monkeypatch):
    # Two chunks; ensure the second introduces at least one new fact
    text1 = "Alice visited the Clinic and used 3D imaging."
    text2 = "Bob uses OrthoRoute 2.0 and 30mm screws."

    cache = _make_cache_two_chunks(text1, text2)

    # Reset and monkeypatch the loader to use our cache
    monkeypatch.setattr(app, "_DOC_CACHE", None, raising=False)
    monkeypatch.setattr(app, "_ORCHESTRATOR", None, raising=False)
    monkeypatch.setattr(app, "_load_and_index_corpus", lambda: cache)

    with TestClient(app.app) as c:
        r = c.post("/query", json={"text": "coverage demo"})
        assert r.status_code == 200
        js = r.json()
        cov = js["trace"]["coverage"]
        assert isinstance(cov.get("facts_added"), int)
        # Because second chunk adds new facts, coverage gain beyond first should be > 0
        assert cov["facts_added"] > 0
