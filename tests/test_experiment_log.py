from __future__ import annotations

from pathlib import Path

from fram_serving.config import FRAMConfig
from fram_serving.memory import CognitiveMemoryStore
from tools.experiment_log import log_experiment


def test_experiment_log_writes_belief(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("COGMEM_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("COGMEM_SESSION_ID", "exp-test")
    monkeypatch.setenv("FRAM_COGNITIVE_MEMORY_EMBEDDING_BACKEND", "hashing")

    record = log_experiment(
        title="Capsule cadence test",
        hypothesis="More snapshots improve recall",
        method="Log every turn",
        result="Recall improved",
        decision="Keep cadence=per-turn",
        tags="alpha,beta",
    )

    assert record["type"] == "belief"
    cfg = FRAMConfig.from_env()
    root = tmp_path / cfg.STORAGE_SUBFOLDERS.get("memory", "memory") / "cognitive"
    store = CognitiveMemoryStore(root, config=cfg)
    beliefs = list(store._iter_belief_records())
    assert beliefs
    last_meta = beliefs[-1].get("metadata") or {}
    assert last_meta.get("kind") == "experiment"
    assert "experiment" in last_meta.get("tags", [])


def test_experiment_log_writes_capsule(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("COGMEM_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("COGMEM_SESSION_ID", "exp-capsule")
    monkeypatch.setenv("FRAM_COGNITIVE_MEMORY_EMBEDDING_BACKEND", "hashing")

    log_experiment(
        title="Capsule snapshot",
        decision="Keep cadence",
        write_capsule=True,
        working_session_id="exp-capsule",
    )

    cfg = FRAMConfig.from_env()
    capsule_root = tmp_path / cfg.STORAGE_SUBFOLDERS.get("memory", "memory") / "capsules"
    capsules = list(capsule_root.glob("capsule_*.json"))
    assert capsules
