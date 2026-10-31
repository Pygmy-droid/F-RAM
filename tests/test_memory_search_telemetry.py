import numpy as np

from fram_core.pipeline import QueryOrchestrator, _CorpusCache, PrototypeRecord, _default_calibration
from fram_index.sparse_keys import SparseKeyIndex
from fram_index.version_lattice import VersionLattice
from fram_serving.config import FRAMConfig


def _dummy_orchestrator(tmp_path, debug: bool = True, bridge: bool = True):
    cfg = FRAMConfig().model_copy(
        update={
            "STORAGE_ROOT": tmp_path,
            "enable_cognitive_ann_bridge": bridge,
            "phase_d": FRAMConfig()
            .phase_d.model_copy(update={"enable_memory_bridge": bridge, "debug_observability": debug}),
        }
    )
    return QueryOrchestrator(config=cfg, persist_path=None, data_root=None)


def _dummy_cache():
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


def test_memory_search_telemetry_present_with_debug(tmp_path):
    orchestrator = _dummy_orchestrator(tmp_path, debug=True, bridge=True)
    cache = _dummy_cache()
    memory_chunks = [
        {
            "candidate_id": "cmem:ann:x1",
            "doc_id": "cmem:ann:x1",
            "version_id": "cmem:ann:x1",
            "file": "cmem:ann:x1",
            "origin": "cognitive_memory",
            "source": "cognitive_memory",
            "score": 0.9,
        }
    ]
    result = orchestrator.run("q", budget_reads=3, memory_chunks=memory_chunks, replay_last=False, cache_override=cache)
    record = result.get("record", {}) or {}
    selection = record.get("trace", {}).get("selection", {}) if isinstance(record, dict) else {}
    layers = selection.get("memory_layers")
    assert layers is not None
    assert layers.get("merge_enabled") is True
    assert layers.get("cognitive", {}).get("count") == 1
    assert selection.get("cognitive_ann_premerge", {}).get("count") == 1
    assert selection.get("cognitive_ann_merge", {}).get("enabled") is True


def test_memory_search_telemetry_absent_when_debug_off(tmp_path):
    orchestrator = _dummy_orchestrator(tmp_path, debug=False, bridge=True)
    cache = _dummy_cache()
    memory_chunks = [
        {
            "candidate_id": "cmem:ann:x1",
            "doc_id": "cmem:ann:x1",
            "version_id": "cmem:ann:x1",
            "file": "cmem:ann:x1",
            "origin": "cognitive_memory",
            "source": "cognitive_memory",
            "score": 0.9,
        }
    ]
    result = orchestrator.run("q", budget_reads=3, memory_chunks=memory_chunks, replay_last=False, cache_override=cache)
    record = result.get("record", {}) or {}
    selection = record.get("trace", {}).get("selection", {}) if isinstance(record, dict) else {}
    assert selection.get("cognitive_ann_premerge") is None
    layers = selection.get("memory_layers")
    assert isinstance(layers, dict)
    assert "merged" in layers
