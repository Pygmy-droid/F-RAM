from __future__ import annotations

from fastapi.testclient import TestClient

import fram_serving.app as app_mod


def _reset_app_state(tmp_path, monkeypatch):
    monkeypatch.setattr(app_mod, "CFG", app_mod.CFG.model_copy(update={"STORAGE_ROOT": tmp_path / "storage"}), raising=False)
    monkeypatch.setattr(app_mod, "_ORCHESTRATOR", None, raising=False)
    monkeypatch.setattr(app_mod, "_COG_STORE", app_mod.CognitiveMemoryStore(tmp_path / "storage" / "memory" / "cognitive"), raising=False)


def test_memory_summary_counts_and_recent(tmp_path, monkeypatch):
    _reset_app_state(tmp_path, monkeypatch)
    with TestClient(app_mod.app) as client:
        # Write a couple of episodes via query
        client.post("/query", json={"text": "What is FRAM?"})
        client.post("/query", json={"text": "Explain OrthoRoute anchors"})
        # Add a belief directly to store
        app_mod._COG_STORE.append_belief(text="FRAM uses conformal thresholds tau1/tau2")

        r = client.get("/observability/memory/summary", params={"window": 2})
        assert r.status_code == 200
        payload = r.json()
        counts = payload.get("counts", {})
        assert counts.get("episodes", 0) >= 2
        assert counts.get("beliefs", 0) >= 1
        recent = payload.get("recent", {})
        assert isinstance(recent.get("episodes", []), list)
        assert len(recent.get("episodes", [])) <= 2
        assert isinstance(recent.get("beliefs", []), list)
        assert len(recent.get("beliefs", [])) <= 2

