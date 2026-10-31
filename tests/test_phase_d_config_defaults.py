from __future__ import annotations

import math

from fram_serving.config import PhaseDConfig


def test_phase_d_config_defaults_are_safe():
    cfg = PhaseDConfig()
    numeric_fields = [
        "priority_clip_min",
        "priority_clip_max",
        "priority_graph_similarity_threshold",
        "priority_graph_cluster_boost_weight",
        "memory_bridge_priority_weight",
        "temporal_recency_weight",
        "temporal_decay_half_life",
        "temporal_min_floor",
        "hysteresis_weight",
    ]
    for field in numeric_fields:
        value = getattr(cfg, field)
        assert isinstance(value, (int, float))
        assert math.isfinite(float(value))
    # Bounds sanity
    assert cfg.priority_clip_min <= cfg.priority_clip_max
    assert 0.0 <= cfg.priority_graph_similarity_threshold <= 1.0
    assert 0.0 <= cfg.temporal_min_floor <= 1.0
