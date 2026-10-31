from __future__ import annotations

from pathlib import Path

from fram_serving.config import FRAMConfig
from fram_serving.memory import CognitiveMemoryStore
from tools.experiment_export import export_markdown


def test_experiment_export_writes_markdown(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("COGMEM_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("COGMEM_SESSION_ID", "export-test")

    cfg = FRAMConfig.from_env()
    cog_root = tmp_path / cfg.STORAGE_SUBFOLDERS.get("memory", "memory") / "cognitive"
    store = CognitiveMemoryStore(cog_root, config=cfg)
    store.append_belief(
        text="Experiment: Export\nDecision: Keep",
        session_id="export-test",
        role="assistant",
        metadata={"kind": "experiment", "title": "Export", "tags": ["experiment", "decision"]},
    )

    out_path = tmp_path / "digest.md"
    export_markdown(limit=5, session_id="export-test", tag=None, out_path=out_path)
    content = out_path.read_text(encoding="utf-8")
    assert "Experiment Digest" in content
    assert "Export" in content
