from __future__ import annotations

import numpy as np
import pytest

from fram_core.claims import Claim, ClaimType
from fram_core.pipeline import (
    QueryOrchestrator,
    _CorpusCache,
    _default_calibration,
    _origin_counts,
)
from fram_index.sparse_keys import SparseKeyIndex
from fram_index.version_lattice import VersionLattice
from fram_serving.config import FRAMConfig


def test_origin_counts_are_json_safe_when_provenance_is_missing() -> None:
    counts = _origin_counts(
        [
            {"origin": None},
            {"origin": "ann"},
            {"source": "cognitive_memory"},
            {"origin": 7},
        ],
        fallback="unknown",
    )

    assert counts == {
        "unknown": 1,
        "ann": 1,
        "cognitive_memory": 1,
        "7": 1,
    }
    assert all(isinstance(key, str) for key in counts)


def test_cognitive_memory_reserves_read_budget() -> None:
    """Memory seeds should consume read slots and stay in the final citations."""
    cfg = FRAMConfig()
    orchestrator = QueryOrchestrator(config=cfg)
    dim = 2
    chunks = [
        {"file": "doc1", "chunk_id": 0, "text": "alpha beta", "tokens": ["alpha", "beta"], "hierarchy": {"segment": "section:1"}},
        {"file": "doc2", "chunk_id": 0, "text": "beta only", "tokens": ["beta"], "hierarchy": {"segment": "section:2"}},
    ]
    chunk_vecs = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=float)
    cache = _CorpusCache(
        chunks=chunks,
        vocab={"alpha": 0, "beta": 1},
        chunk_vecs=chunk_vecs,
        lattice=VersionLattice(),
        sparse_index=SparseKeyIndex(),
        prototypes=[],
        whiten_mean=np.zeros(dim),
        whiten_matrix=np.eye(dim),
        calibration=_default_calibration(cfg),
        embedding_backend="vocab",
        embedder=None,
    )
    memory_claim = Claim(key="alpha", type=ClaimType.Entity, buckets=("doc:cmem",))
    memory_chunk = {
        "file": "cmem:ep:1",
        "chunk_id": 0,
        "text": "alpha recall note",
        "tokens": ["alpha"],
        "claims": [memory_claim],
        "source": "cognitive_memory",
        "phase_d_score": 0.9,
        "hierarchy": {"segment": "cmem:ep:1"},
    }

    result = orchestrator.run(
        text="alpha update",
        budget_reads=2,
        cache_override=cache,
        memory_chunks=[memory_chunk],
        replay_last=False,
    )

    record = result["record"]
    selection = record["trace"]["selection"]
    citations = record["citations"]

    assert any(str(cite).startswith("cmem:ep:1") for cite in citations), "cognitive memory seed should be cited"
    assert selection["budgets"]["reads_used"] >= 2.0
    memory_rows = selection.get("memory") or []
    assert any(row.get("source") == "cognitive_memory" for row in memory_rows)
    assert any(row.get("phase_d_score") == pytest.approx(0.9) for row in memory_rows)


def test_priority_graph_applied_to_cognitive_memory() -> None:
    """Graph priority should be attached when the config enables it."""
    cfg = FRAMConfig()
    cfg.phase_d.enable_priority_graph = True
    cfg.phase_d.priority_graph_cluster_boost_weight = 0.5
    orchestrator = QueryOrchestrator(config=cfg)
    dim = 2
    chunks = [
        {"file": "doc1", "chunk_id": 0, "text": "alpha beta", "tokens": ["alpha", "beta"], "hierarchy": {"segment": "section:1"}},
        {"file": "doc2", "chunk_id": 0, "text": "beta only", "tokens": ["beta"], "hierarchy": {"segment": "section:2"}},
    ]
    chunk_vecs = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=float)
    cache = _CorpusCache(
        chunks=chunks,
        vocab={"alpha": 0, "beta": 1},
        chunk_vecs=chunk_vecs,
        lattice=VersionLattice(),
        sparse_index=SparseKeyIndex(),
        prototypes=[],
        whiten_mean=np.zeros(dim),
        whiten_matrix=np.eye(dim),
        calibration=_default_calibration(cfg),
        embedding_backend="vocab",
        embedder=None,
    )
    memory_chunks = [
        {
            "file": "cmem:ep:1",
            "chunk_id": 0,
            "text": "alpha beta gamma",
            "tokens": ["alpha", "beta", "gamma"],
            "claims": [],
            "source": "cognitive_memory",
            "phase_d_priority": 1.0,
            "hierarchy": {"segment": "cmem:ep:1"},
        },
        {
            "file": "cmem:ep:2",
            "chunk_id": 0,
            "text": "alpha beta delta",
            "tokens": ["alpha", "beta", "delta"],
            "claims": [],
            "source": "cognitive_memory",
            "phase_d_priority": 0.9,
            "hierarchy": {"segment": "cmem:ep:2"},
        },
    ]
    result = orchestrator.run(
        text="alpha beta",
        budget_reads=2,
        cache_override=cache,
        memory_chunks=memory_chunks,
        replay_last=False,
    )
    memory_rows = result["record"]["trace"]["selection"].get("memory") or []
    assert memory_rows, "memory rows should be present"
    assert any("graph_priority" in row for row in memory_rows)


def test_ann_bridge_runs_without_phase_d_gate() -> None:
    """Cognitive ANN merge should run when enabled even if Phase D bridge is off."""
    cfg = FRAMConfig().model_copy(update={"enable_cognitive_ann_bridge": True})
    cfg.phase_d.debug_observability = True
    cfg.phase_d.enable_memory_bridge = False
    dim = 2
    chunks = [
        {"file": "doc1", "chunk_id": 0, "text": "alpha beta", "tokens": ["alpha", "beta"], "hierarchy": {"segment": "section:1"}},
        {"file": "doc2", "chunk_id": 0, "text": "beta only", "tokens": ["beta"], "hierarchy": {"segment": "section:2"}},
    ]
    chunk_vecs = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=float)
    cache = _CorpusCache(
        chunks=chunks,
        vocab={"alpha": 0, "beta": 1},
        chunk_vecs=chunk_vecs,
        lattice=VersionLattice(),
        sparse_index=SparseKeyIndex(),
        prototypes=[],
        whiten_mean=np.zeros(dim),
        whiten_matrix=np.eye(dim),
        calibration=_default_calibration(cfg),
        embedding_backend="vocab",
        embedder=None,
    )
    memory_chunk = {
        "file": "cmem:ep:1",
        "chunk_id": 0,
        "text": "alpha recall note",
        "tokens": ["alpha"],
        "claims": [],
        "source": "cognitive_memory",
        "hierarchy": {"segment": "cmem:ep:1"},
    }
    orchestrator = QueryOrchestrator(config=cfg)
    result = orchestrator.run(
        text="alpha beta",
        budget_reads=2,
        cache_override=cache,
        memory_chunks=[memory_chunk],
        replay_last=False,
    )
    selection = result["record"]["trace"]["selection"]
    layers = selection.get("memory_layers") or {}
    assert layers.get("merge_enabled") is True
    # Ensure merged origins include the cognitive candidate.
    merged = layers.get("merged", {})
    assert merged.get("count", 0) >= 1
