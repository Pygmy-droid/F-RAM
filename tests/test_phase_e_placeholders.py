from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest

from fram_serving.config import FRAMConfig
from fram_serving.memory.forgetting import apply_forgetting
from fram_serving.memory.retention_curve import apply_retention_curve, compute_retention_score


def test_retention_curve_decays_scores():
    config = FRAMConfig(enable_retention_curve=True, retention_half_life_days=1.0)
    now = datetime.now(timezone.utc)
    scores = [1.0, 0.5]
    timestamps = [now - timedelta(days=2), now]
    decayed = apply_retention_curve(scores, timestamps, config, now=now)
    assert decayed[0] < scores[0]
    assert decayed[1] == scores[1]


def test_phase_e_gates_default_to_noop():
    config = FRAMConfig()
    scores = [1.0, 0.5]
    timestamps = [datetime.now(timezone.utc)] * len(scores)
    candidates = [{"id": 1}, {"id": 2}]

    assert config.enable_retention_curve is False
    assert config.enable_decay is False
    assert apply_retention_curve(scores, timestamps, config) == scores
    assert apply_forgetting(candidates, config) == candidates


def test_retention_ordering_respects_gates():
    now = datetime.now(timezone.utc)
    fresh = now
    old = now - timedelta(days=10)

    base_scores = [1.0, 1.0]

    cfg_off = FRAMConfig(enable_retention_curve=False)
    off_scores = apply_retention_curve(base_scores, [old, fresh], cfg_off, now=now)
    assert off_scores == base_scores

    cfg_on = FRAMConfig(enable_retention_curve=True, retention_half_life_days=0.5)
    on_scores = apply_retention_curve(base_scores, [old, fresh], cfg_on, now=now)
    assert on_scores[0] < on_scores[1]
    assert on_scores[1] <= 1.0


def test_compute_retention_score_bounds_and_monotonicity():
    cfg = FRAMConfig(enable_retention_curve=True, retention_half_life_days=1.0)
    now = datetime.now(timezone.utc)
    age_zero = 0.0
    age_half = 86400.0
    age_double = 2 * 86400.0
    score_zero = compute_retention_score(age_zero, cfg)
    score_half = compute_retention_score(age_half, cfg)
    score_double = compute_retention_score(age_double, cfg)

    assert 0.0 <= score_double <= score_half <= score_zero <= 1.0
    assert score_half == pytest.approx(0.5, rel=1e-3)
