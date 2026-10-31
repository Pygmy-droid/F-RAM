from __future__ import annotations

from fastapi.testclient import TestClient

import fram_serving.app as app_mod
from fram_core.pipeline import _make_hashing_vectorizer as _pipeline_make_hashing_vectorizer
from fram_serving.config import FRAMConfig
from fram_serving.memory import CognitiveMemoryStore, WorkingMemoryStore
from fram_serving.memory_capsule import MemoryCapsuleStore


def _reset_app_state(tmp_path, monkeypatch, cfg: FRAMConfig) -> None:
    cfg = cfg.model_copy(update={"STORAGE_ROOT": tmp_path / "storage"})
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
    capsule_root = cfg.STORAGE_ROOT / cfg.STORAGE_SUBFOLDERS.get("memory", "memory") / "capsules"
    monkeypatch.setattr(
        app_mod,
        "_CAPSULE_STORE",
        MemoryCapsuleStore(capsule_root, config=cfg),
        raising=False,
    )
    monkeypatch.setattr(app_mod, "_MEMORY_VECTORIZER", None, raising=False)
    monkeypatch.setattr(app_mod, "_MEMORY_BACKEND", None, raising=False)


def test_query_reads_from_memory_capsule(tmp_path, monkeypatch) -> None:
    cfg = app_mod.CFG.model_copy(
        update={
            "embedding_dim": 64,
            "memory_capsule_retrieval_enabled": True,
            "memory_capsule_retrieval_k": 2,
            "memory_capsule_retrieval_turns_per_capsule": 1,
            "cognitive_memory_k": 0,
        }
    )
    _reset_app_state(tmp_path, monkeypatch, cfg)

    vectorizer = _pipeline_make_hashing_vectorizer(cfg)
    app_mod._CAPSULE_STORE.write_capsule(
        turns=[
            {"role": "user", "text": "nebula anchor note", "time": "2025-12-31T00:00:00+00:00"},
            {"role": "assistant", "text": "nebula anchor confirmed", "time": "2025-12-31T00:00:01+00:00"},
        ],
        session_id="capsule-session",
        source={"kind": "test", "tool": "pytest", "version": "v0"},
        vectorizer=vectorizer,
        vectorizer_backend="hashing",
        created_at="2025-12-31T00:00:02+00:00",
    )

    with TestClient(app_mod.app) as client:
        resp = client.post("/query", json={"text": "nebula anchor"})
        assert resp.status_code == 200
        payload = resp.json()
        capsule_trace = (payload.get("trace") or {}).get("memory_capsule") or {}
        assert capsule_trace.get("selected"), "expected memory capsule selections"
        selection = (payload.get("trace") or {}).get("selection") or {}
        memory_rows = selection.get("memory") or []
        assert any(row.get("source") == "memory_capsule" for row in memory_rows)


def test_query_skips_memory_capsule_when_gate_off(tmp_path, monkeypatch) -> None:
    cfg = app_mod.CFG.model_copy(
        update={
            "embedding_dim": 64,
            "memory_capsule_retrieval_enabled": False,
            "memory_capsule_enabled": False,
            "memory_capsule_retrieval_k": 2,
            "memory_capsule_retrieval_turns_per_capsule": 1,
            "cognitive_memory_k": 0,
        }
    )
    _reset_app_state(tmp_path, monkeypatch, cfg)

    vectorizer = _pipeline_make_hashing_vectorizer(cfg)
    app_mod._CAPSULE_STORE.write_capsule(
        turns=[
            {"role": "user", "text": "nebula anchor note", "time": "2025-12-31T00:00:00+00:00"},
            {"role": "assistant", "text": "nebula anchor confirmed", "time": "2025-12-31T00:00:01+00:00"},
        ],
        session_id="capsule-session",
        source={"kind": "test", "tool": "pytest", "version": "v0"},
        vectorizer=vectorizer,
        vectorizer_backend="hashing",
        created_at="2025-12-31T00:00:02+00:00",
    )

    with TestClient(app_mod.app) as client:
        resp = client.post("/query", json={"text": "nebula anchor"})
        assert resp.status_code == 200
        payload = resp.json()
        capsule_trace = (payload.get("trace") or {}).get("memory_capsule")
        assert not capsule_trace or not capsule_trace.get("selected")
        selection = (payload.get("trace") or {}).get("selection") or {}
        memory_rows = selection.get("memory") or []
        assert all(row.get("source") != "memory_capsule" for row in memory_rows)
