from collections import OrderedDict

import pytest
from fastapi.testclient import TestClient

import fram_serving.app as app_mod
from fram_serving import observability
from fram_serving.config import FRAMConfig
from fram_core.pipeline import CalibrationPayload


def _reset_app_state(tmp_path, monkeypatch):
    cfg = FRAMConfig().model_copy(update={"STORAGE_ROOT": tmp_path})
    trace_dir = tmp_path / cfg.STORAGE_SUBFOLDERS.get("traces", "traces")
    monkeypatch.setattr(app_mod, "CFG", cfg, raising=False)
    monkeypatch.setattr(app_mod, "_TRACE_DIR", trace_dir, raising=False)
    monkeypatch.setattr(app_mod, "TRACE_LOGGER", observability.TraceLogWriter(trace_dir), raising=False)
    monkeypatch.setattr(app_mod, "_ORCHESTRATOR", None, raising=False)
    monkeypatch.setattr(app_mod, "_PROB_CACHE", OrderedDict(), raising=False)
    monkeypatch.setattr(app_mod, "REL", observability.LiveReliability(maxlen=max(1, int(cfg.metrics_window))), raising=False)
    monkeypatch.setattr(app_mod, "ALM", observability.AlarmBook(alpha1=cfg.alpha1, alpha2=cfg.alpha2), raising=False)
    memory_dir = cfg.STORAGE_ROOT / cfg.STORAGE_SUBFOLDERS.get("memory", "memory")
    monkeypatch.setattr(app_mod, "_MEMORY_STORE", app_mod.WorkingMemoryStore(memory_dir), raising=False)


def test_calibration_endpoint_lists_maps(tmp_path, monkeypatch):
    _reset_app_state(tmp_path, monkeypatch)
    client = TestClient(app_mod.app)

    response = client.get("/calibration")
    assert response.status_code == 200
    payload = response.json()

    assert payload["default_domain"] == app_mod.CFG.default_domain
    assert payload["default_task"] == app_mod.CFG.default_task
    assert payload["precedence"] == ["task", "domain", "global", "default"]

    global_payload = payload.get("global")
    assert global_payload is not None
    assert global_payload["tau1"] >= global_payload["tau2"]
    assert "logistic_coefs" in global_payload

    assert isinstance(payload.get("domains"), dict)
    assert isinstance(payload.get("tasks"), dict)


def test_calibration_endpoint_reflects_task_override(tmp_path, monkeypatch):
    _reset_app_state(tmp_path, monkeypatch)
    client = TestClient(app_mod.app)

    engine = app_mod._get_orchestrator()
    cache = engine.ensure_corpus()
    base = cache.calibration

    override = CalibrationPayload(
        logistic_coefs=dict(base.logistic_coefs),
        temperature=base.temperature,
        tau1=0.97,
        tau2=0.91,
    )
    cache.calibration_by_task["qa"] = override

    response = client.get("/calibration")
    assert response.status_code == 200
    payload = response.json()

    tasks = payload.get("tasks") or {}
    qa_entry = tasks.get("qa")
    assert qa_entry is not None
    assert qa_entry["tau1"] == pytest.approx(0.97)
    assert qa_entry["tau2"] == pytest.approx(0.91)
    assert qa_entry.get("temperature") == pytest.approx(float(base.temperature))
    assert set(qa_entry.get("logistic_coefs", {}).keys()) == set(base.logistic_coefs.keys())
