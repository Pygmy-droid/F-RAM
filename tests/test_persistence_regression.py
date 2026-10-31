import numpy as np
import pytest

from fram_core.pipeline import QueryOrchestrator, _CorpusCache, PrototypeRecord, _default_calibration
from fram_index.sparse_keys import SparseKeyIndex
from fram_index.version_lattice import VersionLattice, VersionNode
from fram_serving.config import FRAMConfig
from fram_serving.memory import CognitiveMemoryStore


class FakeVectorizer:
    def __init__(self, dim: int = 4, fingerprint: str = "fake"):
        self.dim = dim
        self.fingerprint_ = fingerprint

    def transform(self, texts):
        return np.ones((len(texts), self.dim), dtype=float)


def _dummy_cache() -> _CorpusCache:
    vocab = {"q": 0}
    chunk_vecs = np.array([[1.0]], dtype=float)
    proto = PrototypeRecord(
        doc_id="docA",
        centroid=np.array([0.0]),
        basis=np.eye(1),
        timestamp=0.0,
        feature_medians={"score": 0.0},
        feature_mads={"score": 1.0},
    )
    return _CorpusCache(
        chunks=[{"file": "docA", "chunk_id": 1, "text": "chunk 1 q", "hierarchy": {"segment": "seg:1"}}],
        vocab=vocab,
        chunk_vecs=chunk_vecs,
        lattice=VersionLattice(),
        sparse_index=SparseKeyIndex(),
        prototypes=[proto],
        whiten_mean=np.zeros(1),
        whiten_matrix=np.eye(1),
        calibration=_default_calibration(FRAMConfig()),
        embedding_backend="vocab",
        embedder=None,
    )


def _make_orchestrator(tmp_path, enable_bridge: bool) -> QueryOrchestrator:
    cfg = FRAMConfig().model_copy(
        update={
            "STORAGE_ROOT": tmp_path,
            "enable_cognitive_ann_bridge": enable_bridge,
            "phase_d": FRAMConfig()
            .phase_d.model_copy(update={"enable_memory_bridge": enable_bridge, "debug_observability": True}),
        }
    )
    return QueryOrchestrator(config=cfg, persist_path=None, data_root=None)


def test_cognitive_ann_persists_across_restart(tmp_path):
    vectorizer = FakeVectorizer()
    cfg = FRAMConfig().model_copy(
        update={
            "STORAGE_ROOT": tmp_path,
            "enable_cognitive_ann_bridge": True,
        }
    )
    store = CognitiveMemoryStore(tmp_path / "memory", config=cfg)
    # Write belief with embedded vector
    store.append_belief(text="A", embedding=np.ones(vectorizer.dim), embedding_backend="hashing")

    # Simulate restart by reloading store and generating ANN candidates
    store_reloaded = CognitiveMemoryStore(tmp_path / "memory", config=cfg)
    ann_candidates, _ = store_reloaded.cognitive_ann_candidates(
        query="q",
        vectorizer=vectorizer,
        top_k=3,
        weight=1.0,
        floor_boost=0.0,
    )
    assert ann_candidates, "expected persisted cognitive ANN candidates"

    orchestrator = _make_orchestrator(tmp_path, enable_bridge=True)
    cache = _dummy_cache()
    result = orchestrator.run(
        "q",
        budget_reads=3,
        memory_chunks=ann_candidates,
        replay_last=False,
        cache_override=cache,
    )
    record = result.get("record", {}) or {}
    selection = record.get("trace", {}).get("selection", {}) if isinstance(record, dict) else {}
    pre = selection.get("cognitive_ann_premerge")
    merge = selection.get("cognitive_ann_merge")
    assert pre and pre["count"] >= 1
    assert merge and merge.get("enabled") is True
    assert merge.get("origins", {}).get("cognitive_memory") >= 1


def test_cognitive_ann_gate_off_excludes_merge(tmp_path):
    vectorizer = FakeVectorizer()
    cfg = FRAMConfig().model_copy(
        update={
            "STORAGE_ROOT": tmp_path,
            "enable_cognitive_ann_bridge": True,
        }
    )
    store = CognitiveMemoryStore(tmp_path / "memory", config=cfg)
    store.append_belief(text="A", embedding=np.ones(vectorizer.dim), embedding_backend="hashing")
    ann_candidates, _ = store.cognitive_ann_candidates(
        query="q",
        vectorizer=vectorizer,
        top_k=3,
        weight=1.0,
        floor_boost=0.0,
    )
    orchestrator = _make_orchestrator(tmp_path, enable_bridge=False)
    cache = _dummy_cache()
    result = orchestrator.run(
        "q",
        budget_reads=3,
        memory_chunks=ann_candidates,
        replay_last=False,
        cache_override=cache,
    )
    record = result.get("record", {}) or {}
    selection = record.get("trace", {}).get("selection", {}) if isinstance(record, dict) else {}
    assert "cognitive_ann_premerge" not in selection
    merge = selection.get("cognitive_ann_merge", {})
    assert merge.get("enabled") in (None, False)


def test_asof_filters_cognitive_candidates(tmp_path):
    vectorizer = FakeVectorizer()
    cfg = FRAMConfig().model_copy(
        update={
            "STORAGE_ROOT": tmp_path,
            "enable_cognitive_ann_bridge": True,
            "phase_d": FRAMConfig()
            .phase_d.model_copy(update={"enable_memory_bridge": True, "debug_observability": True}),
        }
    )
    store = CognitiveMemoryStore(tmp_path / "memory", config=cfg)
    store.append_belief(text="A", embedding=np.ones(vectorizer.dim), embedding_backend="hashing")
    ann_candidates, _ = store.cognitive_ann_candidates(
        query="q",
        vectorizer=vectorizer,
        top_k=3,
        weight=1.0,
        floor_boost=0.0,
    )
    # Tag versions
    old_vid = "v_old"
    new_vid = "v_new"
    for cand in ann_candidates:
        cand["version_id"] = new_vid
        cand["file"] = new_vid
    # Lattice: only old version active at as_of
    lattice = VersionLattice()
    from datetime import datetime, timezone

    lattice.add_node(VersionNode(node_id=old_vid, timestamp=datetime(2020, 1, 1, tzinfo=timezone.utc)))
    lattice.add_node(VersionNode(node_id=new_vid, timestamp=datetime(2030, 1, 1, tzinfo=timezone.utc)))
    cache = _dummy_cache()
    cache.lattice = lattice
    cache.chunks[0]["version_id"] = old_vid
    cache.chunks[0]["file"] = old_vid

    orchestrator = _make_orchestrator(tmp_path, enable_bridge=True)
    result = orchestrator.run(
        "q",
        budget_reads=3,
        memory_chunks=ann_candidates,
        replay_last=False,
        cache_override=cache,
        as_of=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    record = result.get("record", {}) or {}
    trace = record.get("trace", {}) if isinstance(record, dict) else {}
    selection = trace.get("selection", {}) if isinstance(trace, dict) else {}
    asof_block = trace.get("as_of_filter") or {}
    assert asof_block.get("dropped_candidates", 0) >= 1
    assert selection.get("cognitive_ann_premerge", {}).get("count", 0) == 0
