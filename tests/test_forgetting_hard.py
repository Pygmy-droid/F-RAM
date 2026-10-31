from __future__ import annotations

from fram_serving.config import FRAMConfig
from fram_serving.memory.forgetting import ForgetDecision, decide_forgetting


def test_forgetting_gate_off_keeps_all():
    cfg = FRAMConfig(enable_hard_forgetting=False)
    decision = decide_forgetting(
        {"id": "a"},
        {"forget_score": 0.0, "retention_score": 0.1, "decay_factor": 0.2},
        cfg,
        active_count=10,
    )
    assert decision == ForgetDecision.KEEP


def test_forgetting_dry_run_does_not_prune():
    cfg = FRAMConfig(
        enable_hard_forgetting=True,
        hard_forgetting_mode="dry_run",
        forgetting_threshold=0.2,
        min_active_items=0,
    )
    decision = decide_forgetting(
        {"id": "a"},
        {"forget_score": 0.1, "retention_score": 0.1, "decay_factor": 0.5},
        cfg,
        active_count=5,
    )
    assert decision == ForgetDecision.FORGET_DRY


def test_forgetting_enforce_prunes_when_above_floor():
    cfg = FRAMConfig(
        enable_hard_forgetting=True,
        hard_forgetting_mode="enforce",
        forgetting_threshold=0.2,
        min_active_items=2,
    )
    decision_low = decide_forgetting(
        {"id": "a"},
        {"forget_score": 0.1, "retention_score": 0.1, "decay_factor": 0.5},
        cfg,
        active_count=5,
    )
    decision_high = decide_forgetting(
        {"id": "b"},
        {"forget_score": 0.3, "retention_score": 0.3, "decay_factor": 0.5},
        cfg,
        active_count=5,
    )
    floor_protected = decide_forgetting(
        {"id": "c"},
        {"forget_score": 0.0, "retention_score": 0.0, "decay_factor": 0.1},
        cfg,
        active_count=2,
    )
    assert decision_low == ForgetDecision.FORGET_ENFORCE
    assert decision_high == ForgetDecision.KEEP
    assert floor_protected == ForgetDecision.KEEP
