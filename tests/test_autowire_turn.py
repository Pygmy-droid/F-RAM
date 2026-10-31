from __future__ import annotations

import os
from pathlib import Path

from fram_serving.config import FRAMConfig
from fram_serving.memory import CognitiveMemoryStore
from tools.autowire_turn import main as autowire_main


def _capsule_count(root: Path) -> int:
    return len(list((root / "capsules").glob("capsule_*.json")))


def test_autowire_capsule_cadence(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("COGMEM_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("COGMEM_SESSION_ID", "auto-cadence")
    monkeypatch.setenv("COGMEM_WORKING_SESSION_ID", "auto-cadence")
    monkeypatch.setenv("FRAM_MEMORY_CAPSULE_ENABLED", "1")
    monkeypatch.setenv("FRAM_COGNITIVE_MEMORY_EMBEDDING_BACKEND", "hashing")
    monkeypatch.setenv("COGMEM_CAPSULE_EVERY_N", "2")

    monkeypatch.setenv("COGMEM_USER_TMP", "u1")
    monkeypatch.setenv("COGMEM_ASSISTANT_TMP", "a1")
    autowire_main()
    cfg = FRAMConfig.from_env()
    root = tmp_path / cfg.STORAGE_SUBFOLDERS.get("memory", "memory")
    assert _capsule_count(root) == 0

    monkeypatch.setenv("COGMEM_USER_TMP", "u2")
    monkeypatch.setenv("COGMEM_ASSISTANT_TMP", "a2")
    autowire_main()
    assert _capsule_count(root) == 1


def test_autowire_tags_trigger_and_experiment(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("COGMEM_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("COGMEM_SESSION_ID", "auto-tags")
    monkeypatch.setenv("COGMEM_WORKING_SESSION_ID", "auto-tags")
    monkeypatch.setenv("FRAM_MEMORY_CAPSULE_ENABLED", "1")
    monkeypatch.setenv("FRAM_COGNITIVE_MEMORY_EMBEDDING_BACKEND", "hashing")
    monkeypatch.setenv("COGMEM_CAPSULE_EVERY_N", "10")
    monkeypatch.setenv("COGMEM_CAPSULE_TAGS", "decision")
    monkeypatch.setenv("COGMEM_EXPERIMENT_AUTO", "1")

    monkeypatch.setenv(
        "COGMEM_USER_TMP",
        "@decision\nExperiment: Auto tag\nDecision: Keep it\n",
    )
    monkeypatch.setenv("COGMEM_ASSISTANT_TMP", "ack")
    autowire_main()

    cfg = FRAMConfig.from_env()
    memory_root = tmp_path / cfg.STORAGE_SUBFOLDERS.get("memory", "memory")
    assert _capsule_count(memory_root) == 1

    cog_root = memory_root / "cognitive"
    store = CognitiveMemoryStore(cog_root, config=cfg)
    beliefs = list(store._iter_belief_records())
    assert any(
        (entry.get("metadata") or {}).get("kind") == "experiment" for entry in beliefs
    )


def test_autowire_cadence_warning(tmp_path: Path, monkeypatch) -> None:
    warn_path = tmp_path / "warnings.jsonl"
    monkeypatch.setenv("COGMEM_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("COGMEM_SESSION_ID", "auto-warn")
    monkeypatch.setenv("COGMEM_WORKING_SESSION_ID", "auto-warn")
    monkeypatch.setenv("FRAM_MEMORY_CAPSULE_ENABLED", "1")
    monkeypatch.setenv("FRAM_COGNITIVE_MEMORY_EMBEDDING_BACKEND", "hashing")
    monkeypatch.setenv("COGMEM_CAPSULE_EVERY_N", "30")
    monkeypatch.setenv("COGMEM_WARN_LOG", str(warn_path))
    monkeypatch.setenv("COGMEM_USER_TMP", "u1")
    monkeypatch.setenv("COGMEM_ASSISTANT_TMP", "a1")

    autowire_main()

    assert warn_path.exists()
    content = warn_path.read_text(encoding="utf-8")
    assert "capsule_cadence_sparse" in content


def test_autowire_ack_log(tmp_path: Path, monkeypatch) -> None:
    ack_path = tmp_path / "ack.jsonl"
    monkeypatch.setenv("COGMEM_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("COGMEM_SESSION_ID", "auto-ack")
    monkeypatch.setenv("COGMEM_WORKING_SESSION_ID", "auto-ack")
    monkeypatch.setenv("FRAM_MEMORY_CAPSULE_ENABLED", "1")
    monkeypatch.setenv("FRAM_COGNITIVE_MEMORY_EMBEDDING_BACKEND", "hashing")
    monkeypatch.setenv("COGMEM_CAPSULE_EVERY_N", "1")
    monkeypatch.setenv("COGMEM_ACK_LOG", str(ack_path))
    monkeypatch.setenv("COGMEM_USER_TMP", "u1")
    monkeypatch.setenv("COGMEM_ASSISTANT_TMP", "a1")

    autowire_main()

    assert ack_path.exists()
    payload = ack_path.read_text(encoding="utf-8")
    assert "fram_write" in payload
    assert "\"capsule_written\": true" in payload
