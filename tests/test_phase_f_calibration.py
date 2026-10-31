from __future__ import annotations

import json
from pathlib import Path

from fram_serving.config import FRAMConfig
from tools.phase_f_calibrate import calibration_grid
from tools.phase_f_replay import replay_lifecycle


def _phase_f_config(**overrides):
    base = FRAMConfig()
    return base.model_copy(update=overrides)


def test_calibration_gates_off_all_keep():
    cfg = _phase_f_config(enable_retention_curve=False, enable_decay=False, enable_hard_forgetting=False)
    result = calibration_grid(cfg, age_multipliers=[0, 1], base_scores=[0.2, 0.5])
    assert all(entry.decision_dry == "keep" for entry in result.grid)
    assert all(entry.decision_enforce == "keep" for entry in result.grid)


def test_forgetting_threshold_monotonic_non_decreasing_enforce():
    cfg_lo = _phase_f_config(
        enable_retention_curve=True,
        enable_decay=True,
        enable_hard_forgetting=True,
        retention_half_life_days=1.0,
        forgetting_half_life_days=1.0,
        forgetting_threshold=0.05,
        min_active_items=0,
    )
    cfg_hi = cfg_lo.model_copy(update={"forgetting_threshold": 0.5})
    base_scores = [0.1, 0.2, 0.3]
    ages = [0, 1, 2]
    res_lo = calibration_grid(cfg_lo, age_multipliers=ages, base_scores=base_scores)
    res_hi = calibration_grid(cfg_hi, age_multipliers=ages, base_scores=base_scores)
    forgotten_lo = res_lo.decision_counts["enforce"]["forget_enforce"]
    forgotten_hi = res_hi.decision_counts["enforce"]["forget_enforce"]
    # Higher threshold is stricter; forgotten count is non-decreasing.
    assert forgotten_hi >= forgotten_lo
    forgotten_dry_lo = res_lo.decision_counts["dry_run"]["forget_dry"]
    forgotten_dry_hi = res_hi.decision_counts["dry_run"]["forget_dry"]
    assert forgotten_dry_hi >= forgotten_dry_lo


def test_min_active_items_floor_reduces_forgetting():
    cfg_low_floor = _phase_f_config(
        enable_retention_curve=True,
        enable_decay=True,
        enable_hard_forgetting=True,
        retention_half_life_days=1.0,
        forgetting_half_life_days=1.0,
        forgetting_threshold=0.2,
        min_active_items=0,
    )
    cfg_high_floor = cfg_low_floor.model_copy(update={"min_active_items": 50})
    ages = [0, 1, 2, 5]
    base_scores = [0.1, 0.2]
    res_low = calibration_grid(cfg_low_floor, age_multipliers=ages, base_scores=base_scores)
    res_high = calibration_grid(cfg_high_floor, age_multipliers=ages, base_scores=base_scores)
    forgotten_low = res_low.decision_counts["enforce"]["forget_enforce"]
    forgotten_high = res_high.decision_counts["enforce"]["forget_enforce"]
    assert forgotten_high <= forgotten_low


def test_replay_respects_min_active_floor_and_keys(tmp_path: Path):
    cfg = _phase_f_config(
        enable_retention_curve=True,
        enable_decay=True,
        enable_hard_forgetting=True,
        retention_half_life_days=1.0,
        forgetting_half_life_days=1.0,
        forgetting_threshold=0.2,
        min_active_items=10,
    )
    entries = [
        {"id": "fresh", "score": 0.9, "age_seconds": 0},
        {"id": "old_low", "score": 0.1, "age_seconds": 100 * 86400},
        {"id": "mid", "score": 0.4, "age_seconds": 2 * 86400},
    ]
    summary = replay_lifecycle(entries, cfg)
    assert summary["counts"]["decisions"]["enforce"]["forget_enforce"] == 0  # floor keeps everything
    # Write and reload through JSON to exercise serialization shape.
    out = tmp_path / "replay.json"
    out.write_text(json.dumps(summary), encoding="utf-8")
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert "age_buckets" in loaded
    assert "decisions" in loaded["counts"]


def test_lifecycle_summary_observability(monkeypatch):
    # Build a fresh config with lifecycle gates on.
    import fram_serving.app as app

    phase_d_cfg = app.CFG.phase_d.model_copy(update={"enabled": True, "enable_memory_bridge": True})
    cfg = FRAMConfig().model_copy(
        update={
            "enable_retention_curve": True,
            "enable_decay": True,
            "enable_hard_forgetting": True,
            "retention_half_life_days": 1.0,
            "forgetting_half_life_days": 1.0,
            "forgetting_threshold": 0.05,
            "min_active_items": 0,
            "phase_d": phase_d_cfg,
        }
    )
    monkeypatch.setattr(app, "CFG", cfg)
    sample_events = [
        {
            "time": "2025-01-01T00:00:00Z",
            "query_id": "q1",
            "phase_d_memory": {
                "enabled": True,
                "bridge_enabled": True,
                "retention": [{"id": "a", "retention_score": 0.4, "age_seconds": 86400.0, "half_life_days": 1.0}],
                "decay": [{"id": "a", "decay_factor": 0.4, "age_seconds": 86400.0, "half_life_days": 1.0, "retention_score": 0.4}],
                "forgetting_snapshot": [
                    {
                        "id": "a",
                        "decision": "forget_enforce",
                        "forget_score": 0.04,
                        "retention_score": 0.4,
                        "decay_factor": 0.4,
                        "threshold": 0.05,
                        "mode": "enforce",
                        "active_count": 1,
                        "min_active_items": 0,
                    }
                ],
            },
        }
    ]
    monkeypatch.setattr(app.observability, "iter_jsonl", lambda path: list(sample_events))
    payload = app._phase_d_memory_events(limit=5)
    lifecycle = payload.get("lifecycle_summary")
    assert lifecycle is not None
    assert lifecycle.get("counts", {}).get("total_candidates") == 1
    buckets = lifecycle.get("age_buckets") or []
    assert any(b.get("forgotten_enforce") >= 1 for b in buckets)
