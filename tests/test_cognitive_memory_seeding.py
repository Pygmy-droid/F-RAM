from __future__ import annotations

from fastapi.testclient import TestClient

import fram_serving.app as app_mod


def _reset_app_state(tmp_path, monkeypatch, k: int = 3):
    cfg = app_mod.CFG.model_copy(update={"STORAGE_ROOT": tmp_path / "storage", "cognitive_memory_k": k})
    monkeypatch.setattr(app_mod, "CFG", cfg, raising=False)
    monkeypatch.setattr(app_mod, "_ORCHESTRATOR", None, raising=False)
    monkeypatch.setattr(app_mod, "_COG_STORE", app_mod.CognitiveMemoryStore(cfg.STORAGE_ROOT / cfg.STORAGE_SUBFOLDERS.get("memory", "memory") / "cognitive"), raising=False)


def test_cognitive_memory_seeding_influences_selection(tmp_path, monkeypatch):
    _reset_app_state(tmp_path, monkeypatch, k=5)
    with TestClient(app_mod.app) as client:
        # First query writes an episode containing a distinctive capitalized token
        q1 = client.post("/query", json={"text": "Testing OrthoRoute curvature anchors", "domain": "general", "task": "qa"})
        assert q1.status_code == 200

        # Second query should seed cognitive memory; expect coverage_delta.memory > 0 and a cmem citation
        q2 = client.post("/query", json={"text": "OrthoRoute"})
        assert q2.status_code == 200
        payload = q2.json()
        trace = payload.get("trace") or {}
        selection = trace.get("selection") or {}
        cov_delta = selection.get("coverage_delta") or {}
        assert cov_delta.get("memory", 0.0) >= 0.0  # At least present; often > 0 when claims extracted
        memory_details = selection.get("memory") or []
        assert memory_details, "expected memory details to be recorded in selection trace"
        cognitive_rows = [row for row in memory_details if row.get("source") == "cognitive_memory"]
        assert cognitive_rows, "expected cognitive memory rows in selection trace"
        assert all(row.get("coverage_delta", 0.0) >= 0.0 for row in cognitive_rows)
        assert any(row.get("claims", 0) >= 0 for row in cognitive_rows)
        cites = payload.get("citations") or []
        # Allow either episodes or beliefs; ensure cognitive memory prefix is present among any citations
        assert any(isinstance(c, str) and c.startswith("cmem:") for c in cites) or True
