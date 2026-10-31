from __future__ import annotations

from fastapi.testclient import TestClient

from fram_serving import app as app_mod


def _rank_payload():
    return {
        "query": "phase d relevance check",
        "candidates": [
            {"id": "a", "text": "alpha candidate text"},
            {"id": "b", "text": "beta candidate text"},
        ],
    }


def test_rank_relevance_phase_d_disabled():
    client = TestClient(app_mod.app)
    original = app_mod.CFG.phase_d.model_copy()
    try:
        app_mod.CFG.phase_d.enabled = False
        app_mod.CFG.phase_d.debug_observability = False

        resp = client.post("/rank/relevance", json=_rank_payload())
        assert resp.status_code == 200
        data = resp.json()
        assert data["phase_d_scores"] is None
        assert data["phase_d_diagnostics"] is None
    finally:
        app_mod.CFG.phase_d.enabled = original.enabled
        app_mod.CFG.phase_d.debug_observability = original.debug_observability


def test_rank_relevance_phase_d_enabled_no_debug():
    client = TestClient(app_mod.app)
    original = app_mod.CFG.phase_d.model_copy()
    try:
        app_mod.CFG.phase_d.enabled = True
        app_mod.CFG.phase_d.debug_observability = False

        resp = client.post("/rank/relevance", json=_rank_payload())
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data.get("phase_d_scores"), list)
        assert len(data["phase_d_scores"]) == len(_rank_payload()["candidates"])
        assert data.get("phase_d_diagnostics") is None
    finally:
        app_mod.CFG.phase_d.enabled = original.enabled
        app_mod.CFG.phase_d.debug_observability = original.debug_observability


def test_rank_relevance_phase_d_enabled_debug():
    client = TestClient(app_mod.app)
    original = app_mod.CFG.phase_d.model_copy()
    try:
        app_mod.CFG.phase_d.enabled = True
        app_mod.CFG.phase_d.debug_observability = True

        resp = client.post("/rank/relevance", json=_rank_payload())
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data.get("phase_d_scores"), list)
        assert len(data["phase_d_scores"]) == len(_rank_payload()["candidates"])
        diagnostics = data.get("phase_d_diagnostics")
        assert diagnostics is not None
        assert diagnostics.get("phase_d") is not None
    finally:
        app_mod.CFG.phase_d.enabled = original.enabled
        app_mod.CFG.phase_d.debug_observability = original.debug_observability
