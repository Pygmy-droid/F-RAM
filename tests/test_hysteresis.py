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


def test_hysteresis_boosts_previous_selection():
    cfg = FRAMConfig()
    cfg.phase_d = cfg.phase_d.model_copy(
        update={
            "enabled": True,
            "enable_memory_bridge": True,
            "enable_memory_weighting": True,
            "enable_memory_bridge_priority": True,
            "enable_hysteresis": True,
            "hysteresis_weight": 0.5,
        }
    )
    orchestrator = QueryOrchestrator(config=cfg)
    cache = _make_cache(2)

    prior = {
        "file": "cmem:prior",
        "chunk_id": 0,
        "text": "alpha recall note",
        "tokens": ["alpha"],
        "claims": [],
        "source": "cognitive_memory",
        "phase_d_score": 0.8,
        "phase_d_priority": 1.0,
        "graph_priority": 1.0,
        "previous_session_selected": True,
        "previous_priority": 1.2,
        "hierarchy": {"segment": "cmem:prior"},
    }
    fresh = {
        "file": "cmem:fresh",
        "chunk_id": 0,
        "text": "beta recall note",
        "tokens": ["beta"],
        "claims": [],
        "source": "cognitive_memory",
        "phase_d_score": 0.8,
        "phase_d_priority": 1.1,
        "graph_priority": 1.1,
        "previous_session_selected": False,
        "previous_priority": 0.0,
        "hierarchy": {"segment": "cmem:fresh"},
    }

    result = orchestrator.run(
        text="alpha update",
        budget_reads=2,
        cache_override=cache,
        memory_chunks=[fresh, prior],
        replay_last=False,
    )
    memory_rows = result["record"]["trace"]["selection"].get("memory") or []
    boosts = {row.get("doc"): row.get("hysteresis_boost", 0.0) for row in memory_rows}
    assert boosts["cmem:prior"] > 0.0
    assert boosts["cmem:fresh"] == 0.0


def test_hysteresis_gate_off_restores_normal_order():
    cfg = FRAMConfig()
    cfg.phase_d = cfg.phase_d.model_copy(
        update={
            "enabled": True,
            "enable_memory_bridge": True,
            "enable_memory_weighting": True,
            "enable_memory_bridge_priority": True,
            "enable_hysteresis": False,
            "hysteresis_weight": 0.5,
        }
    )
    orchestrator = QueryOrchestrator(config=cfg)
    cache = _make_cache(2)

    prior = {
        "file": "cmem:prior",
        "chunk_id": 0,
        "text": "alpha recall note",
        "tokens": ["alpha"],
        "claims": [],
        "source": "cognitive_memory",
        "phase_d_score": 0.8,
        "phase_d_priority": 1.0,
        "graph_priority": 1.0,
        "previous_session_selected": True,
        "previous_priority": 1.2,
        "hierarchy": {"segment": "cmem:prior"},
    }
    fresh = {
        "file": "cmem:fresh",
        "chunk_id": 0,
        "text": "beta recall note",
        "tokens": ["beta"],
        "claims": [],
        "source": "cognitive_memory",
        "phase_d_score": 0.8,
        "phase_d_priority": 1.1,
        "graph_priority": 1.1,
        "previous_session_selected": False,
        "previous_priority": 0.0,
        "hierarchy": {"segment": "cmem:fresh"},
    }

    result = orchestrator.run(
        text="alpha update",
        budget_reads=2,
        cache_override=cache,
        memory_chunks=[fresh, prior],
        replay_last=False,
    )
    memory_rows = result["record"]["trace"]["selection"].get("memory") or []
    boosts = {row.get("doc"): row.get("hysteresis_boost", 0.0) for row in memory_rows}
    assert boosts["cmem:prior"] == 0.0
    assert boosts["cmem:fresh"] == 0.0
