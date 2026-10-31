from __future__ import annotations

from pathlib import Path

from fram_serving.config import FRAMConfig
from fram_serving.apps import sdk_adapter
from fram_serving.memory import CognitiveMemoryStore


def test_ingest_app_event_writes_memory(tmp_path: Path):
    cfg = FRAMConfig().model_copy(update={"STORAGE_ROOT": tmp_path})
    result = sdk_adapter.ingest_app_event({"text": "app event text"}, config=cfg, root=tmp_path / "memory")
    assert result["status"] == "ok"
    store = CognitiveMemoryStore(tmp_path / "memory", config=cfg)
    episodes = list(store._iter_jsonl(store.FILE_EPISODES))
    assert episodes


def test_ingest_app_memory_guardrails_block(tmp_path: Path, monkeypatch):
    cfg = FRAMConfig().model_copy(update={"STORAGE_ROOT": tmp_path, "enable_guardrails": True})
    # Patch hook to block
    from fram_serving import guardrails
    monkeypatch.setattr(guardrails.hooks, "before_memory_write", lambda item: (False, "blocked"))
    res = sdk_adapter.ingest_app_memory("k", "v", config=cfg, root=tmp_path / "memory")
    assert res["status"] == "blocked"
