from fastapi.testclient import TestClient

import fram_serving.app as app_mod
from fram_serving.memory import CognitiveMemoryStore, WorkingMemoryStore


def _reset_app_state(tmp_path, monkeypatch):
    cfg = app_mod.CFG.model_copy(update={"STORAGE_ROOT": tmp_path / "storage"})
    monkeypatch.setattr(app_mod, "CFG", cfg, raising=False)
    monkeypatch.setattr(app_mod, "_ORCHESTRATOR", None, raising=False)
    monkeypatch.setattr(
        app_mod,
        "_MEMORY_STORE",
        WorkingMemoryStore(
            cfg.STORAGE_ROOT / cfg.STORAGE_SUBFOLDERS.get("memory", "memory")
        ),
        raising=False,
    )
    monkeypatch.setattr(
        app_mod,
        "_COG_STORE",
        CognitiveMemoryStore(
            cfg.STORAGE_ROOT
            / cfg.STORAGE_SUBFOLDERS.get("memory", "memory")
            / "cognitive",
            config=cfg,
        ),
        raising=False,
    )
    return cfg


def test_config_includes_coverage_params(tmp_path, monkeypatch):
    cfg = _reset_app_state(tmp_path, monkeypatch)
    with TestClient(app_mod.app) as c:
        r = c.get("/config")
        assert r.status_code == 200
        js = r.json()
        assert "coverage_gamma" in js and "coverage_u_max" in js
        assert js["coverage_gamma"] == cfg.coverage_gamma
        assert js["coverage_u_max"] == cfg.coverage_u_max
        assert js["default_query_reads"] == cfg.default_query_reads


def test_config_omits_secret_bearing_fields(tmp_path, monkeypatch):
    cfg = _reset_app_state(tmp_path, monkeypatch).model_copy(
        update={"api_key": "unit-test-private-value"}
    )
    monkeypatch.setattr(app_mod, "CFG", cfg, raising=False)

    with TestClient(app_mod.app) as c:
        r = c.get("/config")
        assert r.status_code == 200
        assert "api_key" not in r.json()


def test_query_trace_includes_coverage_params(tmp_path, monkeypatch):
    cfg = _reset_app_state(tmp_path, monkeypatch)
    with TestClient(app_mod.app) as c:
        r = c.post("/query", json={"text": "quick check for coverage params"})
        assert r.status_code == 200
        js = r.json()
        cov = js["trace"]["coverage"]
        assert cov["gamma"] == cfg.coverage_gamma
        assert cov["u_max"] == cfg.coverage_u_max
