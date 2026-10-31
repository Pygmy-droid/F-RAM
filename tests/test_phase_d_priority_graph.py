from __future__ import annotations

from fram_core.priority_graph import apply_priority_graph
from fram_serving.config import PhaseDConfig


def _by_id(candidates):
    return {c["doc_id"]: c for c in candidates}


def test_cluster_boosts_linked_nodes():
    cfg = PhaseDConfig(
        enable_priority_graph=True,
        priority_graph_similarity_threshold=0.4,
        priority_graph_cluster_boost_weight=0.5,
        priority_graph_aggregation_mode="mean",
    )
    candidates = [
        {"doc_id": "a1", "text": "alpha beta", "phase_d_priority": 1.0, "group": "g1"},
        {"doc_id": "a2", "text": "alpha gamma", "phase_d_priority": 1.1, "group": "g1"},
        {"doc_id": "b1", "text": "delta", "phase_d_priority": 1.0, "group": "g2"},
    ]
    updated = apply_priority_graph(candidates, cfg)
    m = _by_id(updated)
    assert m["a1"]["graph_priority"] > m["b1"]["graph_priority"]
    assert m["a2"]["graph_priority"] > m["b1"]["graph_priority"]


def test_no_edges_returns_base_priority():
    cfg = PhaseDConfig(
        enable_priority_graph=True,
        priority_graph_similarity_threshold=1.0,  # effectively disables edges
        priority_graph_cluster_boost_weight=0.5,
    )
    candidates = [
        {"doc_id": "solo", "text": "alpha", "phase_d_priority": 1.2},
        {"doc_id": "solo2", "text": "beta", "phase_d_priority": 0.8},
    ]
    updated = apply_priority_graph(candidates, cfg)
    for original, scored in zip(candidates, updated):
        assert scored["graph_priority"] == original["phase_d_priority"]


def test_gating_disables_graph_influence():
    cfg = PhaseDConfig(enable_priority_graph=False, priority_graph_cluster_boost_weight=0.5)
    candidates = [
        {"doc_id": "a1", "text": "alpha beta", "phase_d_priority": 1.0, "group": "g1"},
        {"doc_id": "a2", "text": "alpha gamma", "phase_d_priority": 1.1, "group": "g1"},
    ]
    updated = apply_priority_graph(candidates, cfg)
    for original, scored in zip(candidates, updated):
        assert scored["graph_priority"] == original["phase_d_priority"]


def test_max_aggregation_boosts_with_strong_node():
    cfg = PhaseDConfig(
        enable_priority_graph=True,
        priority_graph_similarity_threshold=0.4,
        priority_graph_cluster_boost_weight=0.5,
        priority_graph_aggregation_mode="max",
    )
    candidates = [
        {"doc_id": "weak", "text": "alpha beta", "phase_d_priority": 0.8, "group": "g1"},
        {"doc_id": "strong", "text": "alpha gamma", "phase_d_priority": 1.4, "group": "g1"},
        {"doc_id": "solo", "text": "delta", "phase_d_priority": 1.0, "group": "g2"},
    ]
    updated = apply_priority_graph(candidates, cfg)
    m = _by_id(updated)
    # Cluster boost should raise the weak node above the isolated solo.
    assert m["weak"]["graph_priority"] > m["solo"]["graph_priority"]
    # Strong node should remain the highest within its cluster.
    assert m["strong"]["graph_priority"] > m["weak"]["graph_priority"]
