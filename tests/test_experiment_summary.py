from __future__ import annotations

from pathlib import Path

from fram_serving.config import FRAMConfig
from fram_serving.memory import CognitiveMemoryStore
from tools.experiment_log import log_experiment
from tools.experiment_summary import collect_experiments, summarise


def test_experiment_summary_filters(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("COGMEM_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("COGMEM_SESSION_ID", "summary-test")
    monkeypatch.setenv("FRAM_COGNITIVE_MEMORY_EMBEDDING_BACKEND", "hashing")

    log_experiment(
        title="First",
        decision="Keep",
        tags="experiment,decision,alpha",
    )
    log_experiment(
        title="Second",
        tags="experiment,beta",
    )

    cfg = FRAMConfig.from_env()
    root = tmp_path / cfg.STORAGE_SUBFOLDERS.get("memory", "memory") / "cognitive"
    store = CognitiveMemoryStore(root, config=cfg)
    all_items = collect_experiments(store)
    assert len(all_items) == 2

    tagged = collect_experiments(store, tag="alpha")
    assert len(tagged) == 1
    summary = summarise(all_items)
    assert summary["total"] == 2
    assert summary["decisions"] == 1
