from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

import fram_serving.app as app_mod


def _reset_app_state(tmp_path, monkeypatch):
    monkeypatch.setattr(app_mod, "CFG", app_mod.CFG.model_copy(update={"STORAGE_ROOT": tmp_path / "storage"}), raising=False)
    monkeypatch.setattr(app_mod, "_ORCHESTRATOR", None, raising=False)


def test_observability_ui_renders(tmp_path, monkeypatch):
    _reset_app_state(tmp_path, monkeypatch)
    with TestClient(app_mod.app) as client:
        resp = client.get("/ui/observability")
        assert resp.status_code == 200
        assert "FRAM Observability" in resp.text


def test_experiments_ui_renders(tmp_path, monkeypatch):
    _reset_app_state(tmp_path, monkeypatch)
    with TestClient(app_mod.app) as client:
        resp = client.get("/ui/experiments")
        assert resp.status_code == 200
        assert "Experiment Review" in resp.text


@pytest.mark.slow
def test_observability_traces_and_trace_by_id(tmp_path, monkeypatch):
    _reset_app_state(tmp_path, monkeypatch)
    with TestClient(app_mod.app) as client:
        # Trigger a query to generate at least one trace
        q = client.post("/query", json={"text": "trace check"})
        assert q.status_code == 200
        trace_id = q.json().get("id")

        r = client.get("/observability/traces", params={"limit": 5})
        assert r.status_code == 200
        traces = r.json().get("traces") or []
        assert isinstance(traces, list) and traces
        ids = {str(item.get("id")) for item in traces}
        assert trace_id in ids

        r2 = client.get(f"/observability/trace/{trace_id}")
        assert r2.status_code == 200
        body2 = r2.json()
        assert body2.get("id") == trace_id
