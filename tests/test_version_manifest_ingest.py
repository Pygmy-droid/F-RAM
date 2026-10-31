from __future__ import annotations

from pathlib import Path

from fram_core.pipeline import load_demo_corpus, load_persisted_corpus, save_corpus_cache
from fram_serving.config import FRAMConfig


def test_ingest_attaches_version_ids_and_persists(tmp_path: Path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    (data_root / "doc.txt").write_text("Hello world\nThis is FRAM.", encoding="utf-8")

    cfg = FRAMConfig().model_copy(update={"STORAGE_ROOT": tmp_path})
    cache = load_demo_corpus(data_root, cfg)

    assert cache.chunks, "expected chunks from demo ingest"
    assert all(chunk.get("version_id") == "doc.txt" for chunk in cache.chunks if chunk.get("file") == "doc.txt")

    persist_path = tmp_path / "persist"
    save_corpus_cache(cache, persist_path)
    manifest_path = persist_path / "versions.jsonl"
    assert manifest_path.exists()

    reloaded = load_persisted_corpus(persist_path)
    assert any(chunk.get("version_id") == "doc.txt" for chunk in reloaded.chunks)
    assert "doc.txt" in getattr(reloaded.lattice, "_nodes", {})
