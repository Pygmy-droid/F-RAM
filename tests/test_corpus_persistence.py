import json
from pathlib import Path

import numpy as np

from fram_core.pipeline import (
    QueryOrchestrator,
    corpus_cache_to_dict,
    export_claim_log,
    load_demo_corpus,
    load_persisted_corpus,
    save_corpus_cache,
)
from fram_serving.config import FRAMConfig


def test_corpus_persistence_roundtrip(tmp_path):
    data_root = Path(__file__).resolve().parents[1] / "examples" / "data"
    cfg = FRAMConfig()
    cache = load_demo_corpus(data_root, cfg)
    dest = tmp_path / "persist"

    save_corpus_cache(cache, dest)
    restored = load_persisted_corpus(dest)

    assert len(restored.chunks) == len(cache.chunks)
    assert restored.chunk_vecs.shape == cache.chunk_vecs.shape
    assert restored.vocab == cache.vocab
    assert cache.prototypes
    assert len(restored.prototypes) == len(cache.prototypes)
    assert np.allclose(restored.prototypes[0].centroid, cache.prototypes[0].centroid)
    assert restored.prototypes[0].basis.shape[0] == cache.chunk_vecs.shape[1]
    assert restored.whiten_mean.shape[0] == len(cache.vocab)
    assert restored.whiten_matrix.shape[0] == restored.whiten_matrix.shape[1] == len(cache.vocab)
    assert restored.prototypes[0].feature_medians
    assert restored.calibration.logistic_coefs
    assert "a" in restored.calibration.logistic_coefs
    assert restored.calibration.temperature > 0.0
    assert restored.calibration.tau1 > restored.calibration.tau2
    assert restored.embedding_backend == cache.embedding_backend


def test_tfidf_embedding_persistence(tmp_path):
    data_root = Path(__file__).resolve().parents[1] / "examples" / "data"
    cfg = FRAMConfig().model_copy(update={"embedding_backend": "tfidf"})
    cache = load_demo_corpus(data_root, cfg)
    dest = tmp_path / "persist_tfidf"

    save_corpus_cache(cache, dest)
    restored = load_persisted_corpus(dest)

    assert restored.embedding_backend == "tfidf"
    assert restored.embedder is not None


def test_demo_corpus_skips_legacy_docs_by_default():
    data_root = Path(__file__).resolve().parents[1] / "examples" / "data"
    cfg = FRAMConfig()
    cache = load_demo_corpus(data_root, cfg)

    files = {str(chunk.get("file")) for chunk in cache.chunks}
    assert "doc1.txt" not in files
    assert "doc2.txt" not in files


def test_demo_corpus_includes_legacy_when_requested():
    data_root = Path(__file__).resolve().parents[1] / "examples" / "data"
    cfg = FRAMConfig()
    cache = load_demo_corpus(data_root, cfg, include_legacy=True)

    files = {str(chunk.get("file")) for chunk in cache.chunks}
    assert "doc1.txt" in files
    assert "doc2.txt" in files


def test_orchestrator_uses_persisted_cache(tmp_path):
    data_root = Path(__file__).resolve().parents[1] / "examples" / "data"
    cfg = FRAMConfig()
    cache = load_demo_corpus(data_root, cfg)
    persist_path = tmp_path / "demo"
    save_corpus_cache(cache, persist_path)

    orchestrator = QueryOrchestrator(
        config=cfg,
        tracer=None,
        data_root=data_root,
        persist_path=persist_path,
    )

    # First run should pick up persisted cache without raising
    result = orchestrator.run("memory", None)
    assert result["citations"]

    # cache_override should accept dict form as before
    orchestrator.run("memory", None, cache_override=corpus_cache_to_dict(cache))


def test_export_claim_log_writes_jsonl(tmp_path):
    data_root = Path(__file__).resolve().parents[1] / "examples" / "data"
    cfg = FRAMConfig()
    cache = load_demo_corpus(data_root, cfg)
    out_dir = tmp_path / "claims"
    path = export_claim_log(cache, out_dir, dataset_name="demo_corpus")

    assert path.exists()
    content = path.read_text(encoding="utf-8").strip()
    assert content
    entry = json.loads(content.splitlines()[0])
    assert "claim" in entry
    assert entry["claim"]["key"]
    assert entry["claim"]["type"]
