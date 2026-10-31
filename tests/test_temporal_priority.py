from __future__ import annotations

from fram_core.pipeline import temporal_recency_score
from fram_serving.config import PhaseDConfig


def test_temporal_half_life_behavior():
    cfg = PhaseDConfig(
        enable_temporal_priority=True,
        temporal_recency_weight=1.0,
        temporal_decay_half_life=2.0,
        temporal_min_floor=0.1,
    )
    half_life = cfg.temporal_decay_half_life
    score_half = temporal_recency_score(age_seconds=half_life, half_life=half_life, min_floor=cfg.temporal_min_floor)
    score_double = temporal_recency_score(age_seconds=half_life * 2, half_life=half_life, min_floor=cfg.temporal_min_floor)
    assert score_half == 0.5  # half-life halves the score
    assert score_double == 0.25  # doubling age halves again


def test_temporal_min_floor_and_zero_weight():
    cfg = PhaseDConfig(
        enable_temporal_priority=True,
        temporal_recency_weight=0.0,  # no effect
        temporal_decay_half_life=1.0,
        temporal_min_floor=0.5,
    )
    # recency score respects floor
    low = temporal_recency_score(age_seconds=10.0, half_life=cfg.temporal_decay_half_life, min_floor=cfg.temporal_min_floor)
    assert low == cfg.temporal_min_floor

    # weight 0 should imply a neutral factor when applied (handled by caller)
    assert temporal_recency_score(age_seconds=None, half_life=1.0, min_floor=0.2) == 1.0
