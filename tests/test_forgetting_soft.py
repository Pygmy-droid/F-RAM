from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from fram_serving.config import FRAMConfig
from fram_serving.memory.forgetting import compute_decay_factor


def test_decay_gate_off_is_identity():
    cfg = FRAMConfig(enable_decay=False)
    assert compute_decay_factor(age_seconds=10 * 86400.0, config=cfg) == pytest.approx(1.0)
    assert compute_decay_factor(age_seconds=None, config=cfg) == pytest.approx(1.0)


def test_decay_half_life_shape():
    cfg = FRAMConfig(enable_decay=True, forgetting_half_life_days=1.0)
    now = datetime.now(timezone.utc)
    fresh = compute_decay_factor(age_seconds=0.0, config=cfg)
    half = compute_decay_factor(age_seconds=86400.0, config=cfg)
    double = compute_decay_factor(age_seconds=2 * 86400.0, config=cfg)
    assert fresh == pytest.approx(1.0, rel=1e-6)
    assert half == pytest.approx(0.5, rel=1e-3)
    assert double == pytest.approx(0.25, rel=1e-3)
    assert 0.1 <= double <= half <= fresh <= 1.0


def test_decay_monotonic_and_clamped():
    cfg = FRAMConfig(enable_decay=True, forgetting_half_life_days=0.5)
    ages = [0.0, 3600.0, 86400.0, 5 * 86400.0]
    factors = [compute_decay_factor(a, cfg) for a in ages]
    assert all(0.1 <= f <= 1.0 for f in factors)
    assert factors == sorted(factors, reverse=True)
    assert factors[-1] >= 0.1  # clamped floor
