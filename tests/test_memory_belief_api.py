from __future__ import annotations

from fastapi.testclient import TestClient

import fram_serving.app as app_mod


def _reset_app_state(tmp_path, monkeypatch):
    monkeypatch.setattr(app_mod, "CFG", app_mod.CFG.model_copy(update={"STORAGE_ROOT": tmp_path / "storage"}), raising=False)
    monkeypatch.setattr(app_mod, "_ORCHESTRATOR", None, raising=False)
    monkeypatch.setattr(app_mod, "_COG_STORE", app_mod.CognitiveMemoryStore(tmp_path / "storage" / "memory" / "cognitive"), raising=False)


def test_post_memory_belief_and_summary(tmp_path, monkeypatch):
    _reset_app_state(tmp_path, monkeypatch)
    with TestClient(app_mod.app) as client:
        # Append a belief
        r = client.post("/memory/belief", json={"text": "FRAM uses calibrated thresholds tau1/tau2"})
        assert r.status_code == 200
        belief_id = r.json().get("id")
        assert belief_id

        # Endpoint reachable for summary (no strict count assertion here)
        s = client.get("/observability/memory/summary", params={"window": 5})
        assert s.status_code == 200
