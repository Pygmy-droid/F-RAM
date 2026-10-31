from __future__ import annotations

from fastapi.testclient import TestClient

from fram_serving.app import app, _phase_d_memory_events, CFG


def test_priority_inspector_json_fields():
    # Inspector should reuse existing plumbing; ensure snapshot keys exist even when empty.
    payload = _phase_d_memory_events(limit=1)
    # When the bridge is disabled, snapshot may be empty but the key should exist.
    assert "priority_snapshot" in payload or payload.get("enabled") is False
    assert "events" in payload


def test_priority_inspector_html_contains_sections(monkeypatch):
    # Enable inspector for this call only
    monkeypatch.setattr(CFG.phase_d, "enable_priority_inspector", True)
    client = TestClient(app)
    resp = client.get("/observability/phase_d_memory?html=1")
    assert resp.status_code == 200
    body = resp.text
    assert "Phase D Priority Inspector" in body
    assert "Priority Snapshot" in body
    assert "Recent Events" in body
