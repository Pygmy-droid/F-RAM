from fastapi.testclient import TestClient
import pytest

import fram_serving.app as app_mod
from fram_serving.config import FRAMConfig
from fram_serving.memory import CognitiveMemoryStore, WorkingMemoryStore


def _reset_app_state(tmp_path, monkeypatch, cfg=None):
    base_cfg = cfg or app_mod.CFG
    cfg = base_cfg.model_copy(update={"STORAGE_ROOT": tmp_path / "storage"})
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


def test_query_endpoint_minimal_flow(tmp_path, monkeypatch):
    _reset_app_state(tmp_path, monkeypatch)
    cfg = FRAMConfig()
    with TestClient(app_mod.app) as c:
        r = c.post("/query", json={"text": "What does OrthoRoute+ use?"})
        assert r.status_code == 200
        js = r.json()
        assert isinstance(js.get("citations"), list)
        # Expect 1-N citations depending on corpus size and match
        assert 1 <= len(js["citations"]) <= cfg.default_query_reads
        assert "trace" in js and isinstance(js["trace"].get("scores"), list)
        assert isinstance(js["trace"].get("transitional_complexity"), dict)
        assert isinstance(js["trace"]["transitional_complexity"].get("tc"), (int, float))
        assert isinstance(js["trace"].get("tc_routing"), dict)
        assert isinstance(js["trace"]["tc_routing"].get("tc"), (int, float))
        budgets = js["trace"]["selection"]["budgets"]
        assert budgets["reads_limit"] == pytest.approx(float(cfg.default_query_reads))


def test_query_unlimited_cognitive_token_budget(tmp_path, monkeypatch):
    cfg = app_mod.CFG.model_copy(
        update={
            "cognitive_memory_token_budget": 0,
            "default_query_reads": 6,
            "cognitive_memory_k": 5,
        }
    )
    _reset_app_state(tmp_path, monkeypatch, cfg)
    store = app_mod._COG_STORE
    for idx in range(5):
        store.append_episode(
            query=f"Breathing cue {idx}",
            domain="general",
            task="qa",
            answer="Memory chunk for breathing mode.",
        )
    with TestClient(app_mod.app) as c:
        r = c.post("/query", json={"text": "Breathing cue"})
        assert r.status_code == 200
        js = r.json()
        cog = js["trace"].get("cognitive_memory", {})
        assert cog.get("token_budget") is None
        assert cog.get("token_budget_unlimited") is True
        assert cog.get("total_selected") == 5


def test_query_unlimited_cognitive_slot_budget(tmp_path, monkeypatch):
    cfg = app_mod.CFG.model_copy(
        update={
            "cognitive_memory_token_budget": 0,
            "cognitive_memory_slot_budget": 0,
            "default_query_reads": 3,
            "cognitive_memory_k": 8,
        }
    )
    _reset_app_state(tmp_path, monkeypatch, cfg)
    store = app_mod._COG_STORE
    for idx in range(8):
        store.append_episode(
            query=f"Breathing slot cue {idx}",
            domain="general",
            task="qa",
            answer="Memory chunk for slot breathing.",
        )
    with TestClient(app_mod.app) as c:
        r = c.post("/query", json={"text": "Breathing slot cue"})
        assert r.status_code == 200
        js = r.json()
        cog = js["trace"].get("cognitive_memory", {})
        assert cog.get("slot_budget") is None
        assert cog.get("slot_budget_unlimited") is True
        assert cog.get("total_selected") == 8
        budgets = js["trace"]["selection"]["budgets"]
        assert budgets["reads_limit"] == pytest.approx(float(cfg.default_query_reads))
