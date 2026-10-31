from __future__ import annotations

import json

from fastapi.testclient import TestClient

import fram_serving.app as app_mod
from fram_serving.memory import CognitiveMemoryStore, WorkingMemoryStore


def _reset_app_state(tmp_path, monkeypatch, *, metrics_window: int = 3):
    cfg = app_mod.CFG.model_copy(update={"STORAGE_ROOT": tmp_path / "storage", "metrics_window": metrics_window})
    monkeypatch.setattr(app_mod, "CFG", cfg, raising=False)
    monkeypatch.setattr(app_mod, "_ORCHESTRATOR", None, raising=False)
    monkeypatch.setattr(
        app_mod,
        "_MEMORY_STORE",
        WorkingMemoryStore(cfg.STORAGE_ROOT / cfg.STORAGE_SUBFOLDERS.get("memory", "memory")),
        raising=False,
    )
    monkeypatch.setattr(
        app_mod,
        "_COG_STORE",
        CognitiveMemoryStore(
            cfg.STORAGE_ROOT / cfg.STORAGE_SUBFOLDERS.get("memory", "memory") / "cognitive",
            config=cfg,
        ),
        raising=False,
    )


def test_tc_timeseries_persisted_and_bounded(tmp_path, monkeypatch):
    _reset_app_state(tmp_path, monkeypatch, metrics_window=3)

    with TestClient(app_mod.app) as client:
        for idx in range(5):
            resp = client.post("/query", json={"text": f"tc series probe {idx}"})
            assert resp.status_code == 200

    obs_root = app_mod.CFG.STORAGE_ROOT / app_mod.CFG.STORAGE_SUBFOLDERS.get("observability", "observability")
    for filename, expected_name in (
        ("transitional_complexity_window.json", "transitional_complexity"),
        ("tc_routing_window.json", "tc_routing"),
    ):
        path = obs_root / filename
        assert path.exists()

        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload.get("schema_version") == "tc-window-1"
        assert payload.get("name") == expected_name
        assert payload.get("window_max") == 3
        assert payload.get("window_size") == 3
        series = payload.get("series") or []
        assert isinstance(series, list)
        assert len(series) == 3

        stats = payload.get("stats") or {}
        assert isinstance(stats, dict)
        for key in ("count", "min", "max", "mean", "std", "p50", "p95"):
            assert key in stats

        for entry in series:
            assert isinstance(entry, dict)
            assert isinstance(entry.get("time"), str) and entry.get("time")
            assert isinstance(entry.get("tc"), (int, float))
