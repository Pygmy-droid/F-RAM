from __future__ import annotations

import numpy as np

from fram_core.pipeline import QueryOrchestrator, _CorpusCache, _default_calibration
from fram_index.sparse_keys import SparseKeyIndex
from fram_index.version_lattice import VersionLattice
from fram_serving.config import FRAMConfig


def _make_cache(dim: int) -> _CorpusCache:
    chunks = [
        {"file": "doc1", "chunk_id": 0, "text": "alpha beta", "tokens": ["alpha", "beta"], "hierarchy": {"segment": "section:1"}},
        {"file": "doc2", "chunk_id": 0, "text": "beta only", "tokens": ["beta"], "hierarchy": {"segment": "section:2"}},
    ]
    chunk_vecs = np.array([[1.0] + [0.0] * (dim - 1), [0.0] * (dim - 1) + [1.0]], dtype=float)
    return _CorpusCache(
        chunks=chunks,
        vocab={"alpha": 0, "beta": 1},
        chunk_vecs=chunk_vecs,
        lattice=VersionLattice(),
        sparse_index=SparseKeyIndex(),
        prototypes=[],
        whiten_mean=np.zeros(dim),
        whiten_matrix=np.eye(dim),
        calibration=_default_calibration(FRAMConfig()),
        embedding_backend="vocab",
        embedder=None,
    )


def test_memory_bridge_priority_influences_selection():
    cfg = FRAMConfig()
    cfg.phase_d.enabled = True
    cfg.phase_d.enable_memory_bridge = True
    cfg.phase_d.enable_memory_weighting = True
    cfg.phase_d.enable_memory_bridge_priority = True
    cfg.phase_d.memory_bridge_priority_weight = 1.0
    orchestrator = QueryOrchestrator(config=cfg)
    cache = _make_cache(2)

    high_priority = {
        "file": "cmem:high",
        "chunk_id": 0,
        "text": "alpha recall note",
        "tokens": ["alpha"],
        "claims": [],
        "source": "cognitive_memory",
        "phase_d_score": 0.8,
        "phase_d_priority": 1.5,
        "graph_priority": 1.4,
        "final_priority_for_bridge": 1.45,
        "hierarchy": {"segment": "cmem:high"},
    }
    low_priority = {
        "file": "cmem:low",
        "chunk_id": 0,
        "text": "beta recall note",
        "tokens": ["beta"],
        "claims": [],
        "source": "cognitive_memory",
        "phase_d_score": 0.8,
        "phase_d_priority": 0.8,
        "graph_priority": 0.8,
        "final_priority_for_bridge": 0.8,
        "hierarchy": {"segment": "cmem:low"},
    }

    result = orchestrator.run(
        text="alpha update",
        budget_reads=2,
        cache_override=cache,
        memory_chunks=[high_priority, low_priority],
        replay_last=False,
    )

    selection = result["record"]["trace"]["selection"]
    memory_rows = selection.get("memory") or []
    assert any(row.get("source") == "cognitive_memory" for row in memory_rows)
    scores = {row.get("doc"): row.get("phase_d_score") for row in memory_rows}
    assert "cmem:high" in scores and "cmem:low" in scores
    # Higher priority should appear first in memory rows.
    assert memory_rows[0].get("doc") == "cmem:high"


def test_memory_bridge_priority_gating_disables_effect():
    cfg = FRAMConfig()
    cfg.phase_d.enabled = True
    cfg.phase_d.enable_memory_bridge = True
    cfg.phase_d.enable_memory_weighting = True
    cfg.phase_d.enable_memory_bridge_priority = False
    cfg.phase_d.memory_bridge_priority_weight = 1.0
    orchestrator = QueryOrchestrator(config=cfg)
    cache = _make_cache(2)

    high_priority = {
        "file": "cmem:high",
        "chunk_id": 0,
        "text": "alpha recall note",
        "tokens": ["alpha"],
        "claims": [],
        "source": "cognitive_memory",
        "phase_d_score": 0.8,
        "phase_d_priority": 1.5,
        "graph_priority": 1.4,
        "final_priority_for_bridge": 1.45,
        "hierarchy": {"segment": "cmem:high"},
    }
    low_priority = {
        "file": "cmem:low",
        "chunk_id": 0,
        "text": "beta recall note",
        "tokens": ["beta"],
        "claims": [],
        "source": "cognitive_memory",
        "phase_d_score": 0.8,
        "phase_d_priority": 0.8,
        "graph_priority": 0.8,
        "final_priority_for_bridge": 0.8,
        "hierarchy": {"segment": "cmem:low"},
    }

    result = orchestrator.run(
        text="alpha update",
        budget_reads=2,
        cache_override=cache,
        memory_chunks=[high_priority, low_priority],
        replay_last=False,
    )

    memory_rows = result["record"]["trace"]["selection"].get("memory") or []
    # With gating off, ranking should fall back to original order (as provided).
    assert memory_rows[0].get("doc") == "cmem:high"


def test_memory_bridge_priority_weight_blend():
    cfg = FRAMConfig()
    cfg.phase_d.enabled = True
    cfg.phase_d.enable_memory_bridge = True
    cfg.phase_d.enable_memory_weighting = True
    cfg.phase_d.enable_memory_bridge_priority = True
    cfg.phase_d.memory_bridge_priority_weight = 0.0
    orchestrator = QueryOrchestrator(config=cfg)
    cache = _make_cache(2)

    high_priority = {
        "file": "cmem:high",
        "chunk_id": 0,
        "text": "alpha recall note",
        "tokens": ["alpha"],
        "claims": [],
        "source": "cognitive_memory",
        "phase_d_score": 0.9,
        "phase_d_priority": 1.5,
        "graph_priority": 1.4,
        "final_priority_for_bridge": 1.45,
        "hierarchy": {"segment": "cmem:high"},
    }
    low_priority = {
        "file": "cmem:low",
        "chunk_id": 0,
        "text": "beta recall note",
        "tokens": ["beta"],
        "claims": [],
        "source": "cognitive_memory",
        "phase_d_score": 0.9,
        "phase_d_priority": 0.8,
        "graph_priority": 0.8,
        "final_priority_for_bridge": 0.8,
        "hierarchy": {"segment": "cmem:low"},
    }

    result = orchestrator.run(
        text="alpha update",
        budget_reads=2,
        cache_override=cache,
        memory_chunks=[high_priority, low_priority],
        replay_last=False,
    )
    memory_rows = result["record"]["trace"]["selection"].get("memory") or []
    # With weight 0, priorities should not affect ordering; both have same phase_d_score
    # so ordering should remain input order.
    assert memory_rows[0].get("doc") == "cmem:high"
