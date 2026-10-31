from __future__ import annotations

import json

from fastapi.testclient import TestClient

import fram_serving.app as app_mod
from fram_serving.memory import CognitiveMemoryStore, WorkingMemoryStore


def _reset_app_state(tmp_path, monkeypatch, *, cognitive_k: int = 2) -> None:
    cfg = app_mod.CFG.model_copy(update={"STORAGE_ROOT": tmp_path / "storage", "cognitive_memory_k": cognitive_k})
    monkeypatch.setattr(app_mod, "CFG", cfg, raising=False)
    monkeypatch.setattr(app_mod, "_ORCHESTRATOR", None, raising=False)
    monkeypatch.setattr(app_mod, "_NEGATIVE_COOLDOWNS", {}, raising=False)
    monkeypatch.setattr(app_mod, "_COOLDOWNS_LOADED", False, raising=False)
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


def test_dismiss_accepts_citation_and_skips_cognitive_seed(tmp_path, monkeypatch) -> None:
    _reset_app_state(tmp_path, monkeypatch, cognitive_k=2)
    with TestClient(app_mod.app) as client:
        # First call creates an episode but cannot seed (empty store at start).
        first = client.post("/query", json={"text": "Alpha memory item"})
        assert first.status_code == 200

        second = client.post("/query", json={"text": "Alpha memory item"})
        assert second.status_code == 200
        payload2 = second.json()
        cmem2 = (payload2.get("trace") or {}).get("cognitive_memory") or {}
        selected2 = cmem2.get("selected") or []
        assert selected2, "expected cognitive memory selections on second query"
        dismissed_id = str(selected2[0]["id"])
        citations2 = payload2.get("citations") or []
        citation = next(
            c
            for c in citations2
            if isinstance(c, str) and c.startswith(f"{dismissed_id}:chunk")
        )

        dismiss = client.post("/memory/dismiss", json={"doc_id": citation, "reason": "test"})
        assert dismiss.status_code == 200
        dismiss_payload = dismiss.json()
        assert dismiss_payload.get("doc_id") == dismissed_id
        assert dismiss_payload.get("requested") == citation

        third = client.post("/query", json={"text": "Alpha memory item"})
        assert third.status_code == 200
        obs_dir = app_mod.CFG.STORAGE_ROOT / app_mod.CFG.STORAGE_SUBFOLDERS.get("observability", "observability")
        log_path = obs_dir / "memory_cognitive.jsonl"
        assert log_path.exists()
        events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert events, "expected cognitive memory events to be logged"
        last = events[-1]
        skipped = last.get("cooldowns_skipped") or []
        assert dismissed_id in skipped


def test_dismiss_rehydrates_across_restart(tmp_path, monkeypatch) -> None:
    _reset_app_state(tmp_path, monkeypatch, cognitive_k=2)

    dismissed_id = None
    citation = None
    with TestClient(app_mod.app) as client:
        client.post("/query", json={"text": "Alpha memory item"})
        second = client.post("/query", json={"text": "Alpha memory item"})
        payload2 = second.json()
        cmem2 = (payload2.get("trace") or {}).get("cognitive_memory") or {}
        selected2 = cmem2.get("selected") or []
        assert selected2
        dismissed_id = str(selected2[0]["id"])
        citations2 = payload2.get("citations") or []
        citation = next(
            c
            for c in citations2
            if isinstance(c, str) and c.startswith(f"{dismissed_id}:chunk")
        )
        dismiss = client.post("/memory/dismiss", json={"doc_id": citation, "reason": "restart-test"})
        assert dismiss.status_code == 200

    # Simulate a restart: clear in-memory cooldown state but keep persisted observability logs.
    monkeypatch.setattr(app_mod, "_NEGATIVE_COOLDOWNS", {}, raising=False)
    monkeypatch.setattr(app_mod, "_COOLDOWNS_LOADED", False, raising=False)

    with TestClient(app_mod.app) as client:
        resp = client.post("/query", json={"text": "Alpha memory item"})
        assert resp.status_code == 200

    obs_dir = app_mod.CFG.STORAGE_ROOT / app_mod.CFG.STORAGE_SUBFOLDERS.get("observability", "observability")
    log_path = obs_dir / "memory_cognitive.jsonl"
    assert log_path.exists()
    events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert events
    last = events[-1]
    skipped = last.get("cooldowns_skipped") or []
    assert dismissed_id in skipped
    selected = last.get("selected") or []
    assert all(item.get("id") != dismissed_id for item in selected)
