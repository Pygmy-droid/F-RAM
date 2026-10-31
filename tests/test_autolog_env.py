from __future__ import annotations

import os
from pathlib import Path

from fram_serving.config import FRAMConfig
from fram_serving.memory import CognitiveMemoryStore
from tools.autolog_env import autolog_turn


def test_env_autolog_writes_timestamp(tmp_path: Path) -> None:
    # Arrange: point storage to tmp and enable autolog
    os.environ["COGMEM_AUTOLOG"] = "1"
    os.environ["COGMEM_STORAGE_ROOT"] = str(tmp_path)
    os.environ["COGMEM_SESSION_ID"] = "chat-test"
    os.environ["COGMEM_TAGS"] = "decision, action"

    # Act: write a user+assistant turn
    autolog_turn("hi", "hello", topic="unit-test")

    # Assert: records exist with ISO timestamps
    cfg = FRAMConfig.from_env()
    root = Path(os.environ["COGMEM_STORAGE_ROOT"]) / cfg.STORAGE_SUBFOLDERS.get("memory", "memory") / "cognitive"
    store = CognitiveMemoryStore(root, config=cfg)
    beliefs = list(store._iter_belief_records())
    assert len(beliefs) >= 2
    # last two entries should have time fields
    assert beliefs[-1].get("time")
    assert beliefs[-2].get("time")
    last_meta = beliefs[-1].get("metadata") or {}
    assert "decision" in last_meta.get("tags", [])
    os.environ.pop("COGMEM_TAGS", None)
