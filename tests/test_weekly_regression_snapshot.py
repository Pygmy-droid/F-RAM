from __future__ import annotations

import json
from pathlib import Path

from fram_serving.config import FRAMConfig
from fram_serving.memory import CognitiveMemoryStore
from tools.weekly_regression_snapshot import build_snapshot


def test_weekly_snapshot_payload(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("COGMEM_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("COGMEM_SESSION_ID", "weekly-test")

    cfg = FRAMConfig.from_env()
    cog_root = tmp_path / cfg.STORAGE_SUBFOLDERS.get("memory", "memory") / "cognitive"
    store = CognitiveMemoryStore(cog_root, config=cfg)
    store.append_belief(
        text="Experiment: Weekly\nDecision: Keep",
        session_id="weekly-test",
        role="assistant",
        metadata={"kind": "experiment", "title": "Weekly", "tags": ["experiment", "decision"]},
    )

    obs_dir = tmp_path / cfg.STORAGE_SUBFOLDERS.get("observability", "observability")
    obs_dir.mkdir(parents=True, exist_ok=True)
    memory_path = obs_dir / "memory_cognitive.jsonl"
    memory_path.write_text(
        json.dumps({"backend": "hashing", "selected_count": 1, "token_budget": 0}) + "\n",
        encoding="utf-8",
    )

    snapshot = build_snapshot(limit=5, session_id="weekly-test", memory_path=memory_path)
    assert snapshot["experiments"]["total"] == 1
    assert snapshot["cognitive_memory"]["total_events"] == 1
