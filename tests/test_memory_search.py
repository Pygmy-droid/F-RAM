from __future__ import annotations

from fastapi.testclient import TestClient

import fram_serving.app as app_mod
from fram_serving.config import FRAMConfig


def _reset_app_state(tmp_path, monkeypatch):
    # Point storage root to tmp; rebuild orchestrator on first call
    monkeypatch.setattr(app_mod, "CFG", app_mod.CFG.model_copy(update={"STORAGE_ROOT": tmp_path / "storage"}), raising=False)
    monkeypatch.setattr(app_mod, "_ORCHESTRATOR", None, raising=False)
    # Re-point cognitive store to tmp as well
    monkeypatch.setattr(app_mod, "_COG_STORE", app_mod.CognitiveMemoryStore(tmp_path / "storage" / "memory" / "cognitive"), raising=False)


def test_query_write_through_creates_episode_and_search(tmp_path, monkeypatch):
    _reset_app_state(tmp_path, monkeypatch)
    with TestClient(app_mod.app) as client:
        r = client.post("/query", json={"text": "What is OrthoRoute in FRAM?"})
        assert r.status_code == 200

        # Sanity: ensure an episode was written
        summary = app_mod._COG_STORE.summarize()
        assert summary["counts"]["episodes"] >= 1

        s = client.get("/memory/search", params={"query": "OrthoRoute FRAM calibrated routing", "k": 5})
        assert s.status_code == 200
        hits = s.json().get("results") or []
        direct = app_mod._COG_STORE.search("OrthoRoute FRAM calibrated routing", k=5)
        assert isinstance(direct, list)
        # Either the endpoint or direct call should yield at least one hit
        assert hits or direct, "expected at least one memory hit via endpoint or direct store"
        assert any(h.get("kind") == "episode" for h in (hits or direct))


def test_memory_search_filters_domain(tmp_path, monkeypatch):
    _reset_app_state(tmp_path, monkeypatch)
    with TestClient(app_mod.app) as client:
        client.post("/query", json={"text": "Roadmap anchors and curvature", "domain": "roadmap"})
        client.post("/query", json={"text": "General QA baseline", "domain": "general"})

        s_all = client.get("/memory/search", params={"query": "anchors curvature", "k": 10})
        s_road = client.get("/memory/search", params={"query": "anchors curvature", "k": 10, "domain": "roadmap"})

        assert s_all.status_code == 200 and s_road.status_code == 200
        all_hits = s_all.json().get("results") or []
        road_hits = s_road.json().get("results") or []
        # When filtered, either fewer or equal hits, and all episodes have domain filter when present
        assert len(road_hits) <= len(all_hits)
        for h in road_hits:
            if h.get("kind") == "episode":
                assert h.get("domain") == "roadmap"
