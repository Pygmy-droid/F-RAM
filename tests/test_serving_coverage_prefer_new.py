from datetime import datetime, timedelta, timezone
import numpy as np
from fastapi.testclient import TestClient
from sklearn.feature_extraction.text import HashingVectorizer

import fram_core.confidence as conf
import fram_serving.app as app
from fram_serving.config import FRAMConfig
from fram_serving.memory import CognitiveMemoryStore, WorkingMemoryStore
from fram_index.sparse_keys import SparseKeyIndex
from fram_index.version_lattice import VersionLattice, VersionNode


def _make_cache_three_chunks(seed_text: str, dup_text: str, new_text: str):
    t_seed = app._tokenize(seed_text)
    t_dup = app._tokenize(dup_text)
    t_new = app._tokenize(new_text)
    now = datetime.now(timezone.utc)
    lattice = VersionLattice()
    sparse_index = SparseKeyIndex()
    chunk_specs = [
        ("fake1_seed.txt", seed_text, t_seed, now),
        ("fake2_dup.txt", dup_text, t_dup, now + timedelta(minutes=1)),
        ("fake3_new.txt", new_text, t_new, now + timedelta(minutes=2)),
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
    vecs = vectorizer.transform([seed_text, dup_text, new_text]).toarray().astype(float, copy=False)
    vocab = app._build_vocab([t_seed, t_dup, t_new])
    return {
        "chunks": chunks,
        "vocab": vocab,
        "chunk_vecs": vecs,
        "lattice": lattice,
        "sparse_index": sparse_index,
    }

def _reset_app_state(tmp_path, monkeypatch):
    cfg = app.CFG.model_copy(update={"STORAGE_ROOT": tmp_path / "storage"})
    monkeypatch.setattr(app, "CFG", cfg, raising=False)
    monkeypatch.setattr(app, "_ORCHESTRATOR", None, raising=False)
    monkeypatch.setattr(
        app,
        "_MEMORY_STORE",
        WorkingMemoryStore(cfg.STORAGE_ROOT / cfg.STORAGE_SUBFOLDERS.get("memory", "memory")),
        raising=False,
    )
    monkeypatch.setattr(
        app,
        "_COG_STORE",
        CognitiveMemoryStore(
            cfg.STORAGE_ROOT / cfg.STORAGE_SUBFOLDERS.get("memory", "memory") / "cognitive",
            config=cfg,
        ),
        raising=False,
    )
    return cfg

def test_selection_prefers_new_claim_over_duplicate(tmp_path, monkeypatch):
    # Seed has three claims; dup shares those claims; new adds different claims
    seed = "Alice visited the Clinic and used 3D imaging"
    dup = "Alice Clinic 3D"  # no new claims beyond seed
    new = "Bob uses OrthoRoute 2.0 and 30mm screws"  # new claims

    _reset_app_state(tmp_path, monkeypatch)
    cache = _make_cache_three_chunks(seed, dup, new)

    # Force confidence to 'local' to avoid anchor-only neighbor pool
    cfg = FRAMConfig()

    def fake_logit_conf(_features, coefs=None, temperature=1.0):
        return max(cfg.tau1 + 0.05, 0.95)

    monkeypatch.setattr(conf, "logistic_confidence", fake_logit_conf)

    monkeypatch.setattr(app, "_DOC_CACHE", None, raising=False)
    monkeypatch.setattr(app, "_ORCHESTRATOR", None, raising=False)
    monkeypatch.setattr(app, "_load_and_index_corpus", lambda: cache)

    with TestClient(app.app) as c:
        # Query matches seed better than dup/new
        r = c.post("/query", json={"text": "Alice visited Clinic 3D imaging"})
        assert r.status_code == 200
        js = r.json()
        citations = js["citations"]
        # Cognitive memory seeds may precede corpus citations; restrict the check to corpus hits.
        corpus_citations = [c for c in citations if not c.startswith("cmem:")]
        assert len(corpus_citations) >= 2
        # After the seed, the next pick should be the 'new' chunk by coverage
        assert corpus_citations[1].startswith("fake3_new.txt:chunk0")
