from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from fram_serving.config import FRAMConfig
from fram_serving.memory.retention_curve import compute_retention_score


def test_retention_half_life_shape():
    cfg = FRAMConfig(enable_retention_curve=True, retention_half_life_days=1.0)
    score_now = compute_retention_score(age_seconds=0.0, config=cfg)
    score_half = compute_retention_score(age_seconds=86400.0, config=cfg)
    score_double = compute_retention_score(age_seconds=2 * 86400.0, config=cfg)
    assert score_now == pytest.approx(1.0, rel=1e-6)
    assert score_half == pytest.approx(0.5, rel=1e-3)
    assert score_double == pytest.approx(0.25, rel=1e-3)
    assert 0.0 <= score_double <= score_half <= score_now <= 1.0


def test_retention_monotonic_and_clamped():
    cfg = FRAMConfig(enable_retention_curve=True, retention_half_life_days=2.0)
    ages = [0.0, 3600.0, 86400.0, 3 * 86400.0, 30 * 86400.0]
    scores = [compute_retention_score(age, cfg) for age in ages]
    assert all(0.0 <= s <= 1.0 for s in scores)
    assert scores == sorted(scores, reverse=True)
    # Very old entries approach but do not hit zero.
    assert scores[-1] > 0.0


def test_retention_gate_off_returns_one():
    cfg = FRAMConfig(enable_retention_curve=False)
    assert compute_retention_score(age_seconds=10 * 86400.0, config=cfg) == pytest.approx(1.0)
    assert compute_retention_score(age_seconds=None, config=cfg) == pytest.approx(1.0)


def test_retention_prefers_fresh_when_enabled():
    cfg = FRAMConfig(enable_retention_curve=True, retention_half_life_days=0.25)
    fresh = compute_retention_score(age_seconds=0.0, config=cfg)
    old = compute_retention_score(age_seconds=86400.0, config=cfg)
    assert fresh > old
