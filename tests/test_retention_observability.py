from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

import fram_serving.app as app


def _write_cogmem_event(
    root: Path,
    include_retention: bool = True,
    include_decay: bool = False,
    include_forgetting: bool = False,
) -> None:
    root.mkdir(parents=True, exist_ok=True)
    path = root / "memory_cognitive.jsonl"
    event = {
        "time": datetime.now(timezone.utc).isoformat(),
        "query_id": "q1",
        "phase_d_memory": {
            "enabled": True,
            "debug": False,
            "scored": 1,
            "alpha_t": 0.6,
            "alpha_color": "bright",
            "retention": [
                {
                    "id": "cmem:ep:1",
                    "retention_score": 0.5,
                    "age_seconds": 86400.0,
                    "half_life_days": 1.0,
                }
            ] if include_retention else [],
            "retention_half_life_days": 1.0,
            "decay": [
                {
                    "id": "cmem:ep:1",
                    "decay_factor": 0.4,
                    "age_seconds": 86400.0,
                    "half_life_days": 0.5,
                    "retention_score": 0.5,
                }
            ] if include_decay else [],
            "forgetting_half_life_days": 0.5 if include_decay else None,
            "forgetting_snapshot": [
                {
                    "id": "cmem:ep:1",
                    "decision": "forget_dry",
                    "forget_score": 0.02,
                    "retention_score": 0.5,
                    "decay_factor": 0.4,
                    "threshold": 0.05,
                    "mode": "dry_run",
                    "active_count": 5,
                    "min_active_items": 2,
                }
            ] if include_forgetting else [],
        },
    }
    path.write_text(json.dumps(event) + "\n", encoding="utf-8")


def test_retention_snapshot_json(monkeypatch, tmp_path):
    root = tmp_path / "observability"
    _write_cogmem_event(root, include_retention=True)
    monkeypatch.setattr(app, "_observability_root", lambda: root)
    monkeypatch.setattr(app.CFG.phase_d, "enabled", True)
    monkeypatch.setattr(app.CFG.phase_d, "enable_memory_bridge", True)
    monkeypatch.setattr(app.CFG.phase_d, "enable_priority_inspector", True)
    monkeypatch.setattr(app.CFG, "enable_retention_curve", True)

    payload = app._phase_d_memory_events(limit=5)
    assert "retention_snapshot" in payload
    snapshot = payload["retention_snapshot"]
    assert snapshot
    assert snapshot[0]["retention_score"] == 0.5
    assert snapshot[0]["half_life_days"] == 1.0


def test_retention_snapshot_absent_when_disabled(monkeypatch, tmp_path):
    root = tmp_path / "observability"
    _write_cogmem_event(root, include_retention=True)
    monkeypatch.setattr(app, "_observability_root", lambda: root)
    monkeypatch.setattr(app.CFG.phase_d, "enabled", True)
    monkeypatch.setattr(app.CFG.phase_d, "enable_memory_bridge", True)
    monkeypatch.setattr(app.CFG, "enable_retention_curve", False)

    payload = app._phase_d_memory_events(limit=5)
    assert "retention_snapshot" not in payload


def test_retention_inspector_html(monkeypatch, tmp_path):
    root = tmp_path / "observability"
    _write_cogmem_event(root, include_retention=True)
    monkeypatch.setattr(app, "_observability_root", lambda: root)
    monkeypatch.setattr(app.CFG.phase_d, "enabled", True)
    monkeypatch.setattr(app.CFG.phase_d, "enable_memory_bridge", True)
    monkeypatch.setattr(app.CFG.phase_d, "enable_priority_inspector", True)
    monkeypatch.setattr(app.CFG, "enable_retention_curve", True)

    client = TestClient(app.app)
    resp = client.get("/observability/phase_d_memory?html=1")
    assert resp.status_code == 200
    body = resp.text
    assert "Retention Snapshot" in body
    assert "retention_score" in body


def test_decay_snapshot_json(monkeypatch, tmp_path):
    root = tmp_path / "observability"
    _write_cogmem_event(root, include_retention=True, include_decay=True)
    monkeypatch.setattr(app, "_observability_root", lambda: root)
    monkeypatch.setattr(app.CFG.phase_d, "enabled", True)
    monkeypatch.setattr(app.CFG.phase_d, "enable_memory_bridge", True)
    monkeypatch.setattr(app.CFG.phase_d, "enable_priority_inspector", True)
    monkeypatch.setattr(app.CFG, "enable_retention_curve", True)
    monkeypatch.setattr(app.CFG, "enable_decay", True)

    payload = app._phase_d_memory_events(limit=5)
    assert "decay_snapshot" in payload
    snapshot = payload["decay_snapshot"]
    assert snapshot
    assert snapshot[0]["decay_factor"] == 0.4
    assert snapshot[0]["half_life_days"] == 0.5


def test_decay_snapshot_absent_when_disabled(monkeypatch, tmp_path):
    root = tmp_path / "observability"
    _write_cogmem_event(root, include_retention=True, include_decay=True)
    monkeypatch.setattr(app, "_observability_root", lambda: root)
    monkeypatch.setattr(app.CFG.phase_d, "enabled", True)
    monkeypatch.setattr(app.CFG.phase_d, "enable_memory_bridge", True)
    monkeypatch.setattr(app.CFG, "enable_retention_curve", True)
    monkeypatch.setattr(app.CFG, "enable_decay", False)

    payload = app._phase_d_memory_events(limit=5)
    assert "decay_snapshot" not in payload


def test_decay_inspector_html(monkeypatch, tmp_path):
    root = tmp_path / "observability"
    _write_cogmem_event(root, include_retention=True, include_decay=True)
    monkeypatch.setattr(app, "_observability_root", lambda: root)
    monkeypatch.setattr(app.CFG.phase_d, "enabled", True)
    monkeypatch.setattr(app.CFG.phase_d, "enable_memory_bridge", True)
    monkeypatch.setattr(app.CFG.phase_d, "enable_priority_inspector", True)
    monkeypatch.setattr(app.CFG, "enable_retention_curve", True)
    monkeypatch.setattr(app.CFG, "enable_decay", True)

    client = TestClient(app.app)
    resp = client.get("/observability/phase_d_memory?html=1")
    assert resp.status_code == 200
    body = resp.text
    assert "Decay Snapshot" in body
    assert "decay_factor" in body


def test_forgetting_snapshot(monkeypatch, tmp_path):
    root = tmp_path / "observability"
    _write_cogmem_event(root, include_retention=True, include_decay=True, include_forgetting=True)
    monkeypatch.setattr(app, "_observability_root", lambda: root)
    monkeypatch.setattr(app.CFG.phase_d, "enabled", True)
    monkeypatch.setattr(app.CFG.phase_d, "enable_memory_bridge", True)
    monkeypatch.setattr(app.CFG.phase_d, "enable_priority_inspector", True)
    monkeypatch.setattr(app.CFG, "enable_retention_curve", True)
    monkeypatch.setattr(app.CFG, "enable_decay", True)
    monkeypatch.setattr(app.CFG, "enable_hard_forgetting", True)

    payload = app._phase_d_memory_events(limit=5)
    assert "forgetting_snapshot" in payload
    snap = payload["forgetting_snapshot"]
    assert snap
    assert snap[0]["decision"] == "forget_dry"
    assert snap[0]["threshold"] == 0.05

    client = TestClient(app.app)
    resp = client.get("/observability/phase_d_memory?html=1")
    assert resp.status_code == 200
    body = resp.text
    assert "Forgetting Snapshot" in body
    assert "decision" in body
