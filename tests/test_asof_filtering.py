from __future__ import annotations

import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import json

from fram_core.pipeline import QueryOrchestrator, save_corpus_cache, load_demo_corpus, load_persisted_corpus
from fram_index.version_lattice import VersionNode
from fram_serving.config import FRAMConfig


def _touch_with_time(path: Path, text: str, ts: datetime) -> None:
    path.write_text(text, encoding="utf-8")
    epoch = ts.timestamp()
    os.utime(path, (epoch, epoch))


def _memory_chunk(version_id: str, idx: int, source: str = "session_memory") -> dict:
    return {
        "file": version_id,
        "chunk_id": idx,
        "text": f"memory {version_id}",
        "tokens": [version_id],
        "version_id": version_id,
        "claims": [],
        "source": source,
        "hierarchy": {"cluster": version_id, "segment": f"{version_id}:seg", "chunk": f"chunk:{idx}"},
    }


def test_asof_filters_future_versions(tmp_path: Path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    now = datetime.now(timezone.utc)
    t1 = now - timedelta(hours=3)
    t2 = now - timedelta(hours=1)
    _touch_with_time(data_root / "v1.txt", "alpha v1", t1)
    _touch_with_time(data_root / "v2.txt", "beta v2 newer", t2)

    storage_root = tmp_path / "storage"
    persist_path = storage_root / "index" / "demo_corpus"
    cfg = FRAMConfig().model_copy(update={"STORAGE_ROOT": storage_root})

    cache = load_demo_corpus(data_root, cfg)
    orch = QueryOrchestrator(config=cfg, tracer=None, data_root=data_root, persist_path=persist_path, include_legacy=False)
    as_of = t1 + timedelta(minutes=10)
    result = orch.run("beta", as_of, 3, "general", "qa", cache_override=cache)

    citations = result["citations"]
    assert citations, "expected at least one citation"
    assert all(cite.startswith("v1.txt") for cite in citations)
    trace = result["record"]["trace"]
    as_of_block = trace.get("as_of_filter") or {}
    assert as_of_block.get("as_of")
    assert "v1.txt" in as_of_block.get("active_nodes", [])
    assert as_of_block.get("dropped_candidates", 0) >= 1


def test_asof_delta_snippet_and_restart(tmp_path: Path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    now = datetime.now(timezone.utc)
    t1 = now - timedelta(hours=5)
    t2 = now - timedelta(hours=3)
    t3 = now - timedelta(hours=1)
    _touch_with_time(data_root / "v1.txt", "doc v1 base", t1)
    _touch_with_time(data_root / "v2.txt", "doc v2 updated", t2)
    _touch_with_time(data_root / "v3.txt", "doc v3 newest", t3)

    storage_root = tmp_path / "storage"
    persist_path = storage_root / "index" / "demo_corpus"
    cfg = FRAMConfig().model_copy(update={"STORAGE_ROOT": storage_root})

    orch = QueryOrchestrator(config=cfg, tracer=None, data_root=data_root, persist_path=persist_path, include_legacy=False)
    cache = load_demo_corpus(data_root, cfg)
    # Stamp parent/diff relationships for delta snippets.
    lattice = cache.lattice
    lattice._nodes["v2.txt"] = VersionNode(node_id="v2.txt", timestamp=t2, parents=("v1.txt",), diff={"delta": "v2"})
    lattice._nodes["v3.txt"] = VersionNode(node_id="v3.txt", timestamp=t3, parents=("v2.txt",), diff={"delta": "v3"})
    save_corpus_cache(cache, persist_path)
    manifest = persist_path / "versions.jsonl"
    assert manifest.exists()
    manifest_rows = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(row.get("version_id") == "v2.txt" and row.get("diff") for row in manifest_rows)
    lattice_rows = json.loads((persist_path / "lattice.json").read_text(encoding="utf-8"))
    assert any(row.get("node_id") == "v2.txt" and row.get("diff") for row in lattice_rows)

    orch2 = QueryOrchestrator(config=cfg, tracer=None, data_root=data_root, persist_path=persist_path, include_legacy=False)
    cache2 = load_persisted_corpus(persist_path)
    node2 = cache2.lattice._nodes.get("v2.txt")
    assert node2 is not None and node2.diff is not None
    as_of = t2 + timedelta(minutes=1)
    memory_chunks = [
        _memory_chunk("v2.txt", 0),  # allowed, carries diff
        _memory_chunk("v3.txt", 1),  # Should be dropped by as-of.
    ]
    result = orch2.run("updated", as_of, 1, "general", "qa", memory_chunks=memory_chunks, cache_override=cache2)

    citations = result["citations"]
    assert citations, "expected citations after restart"
    assert all("v3.txt" not in cite for cite in citations)
    trace = result["record"]["trace"]
    as_of_block = trace.get("as_of_filter") or {}
    assert "v2.txt" in as_of_block.get("active_nodes", [])
    assert "v3.txt" not in as_of_block.get("active_nodes", [])
    # Delta snippets should surface the v2->v1 delta when serving as_of before v3.
    delta_snips = result["record"].get("delta_snippets", [])
    assert delta_snips, "expected delta snippets for as-of response"
    assert any(sn.get("version_id") == "v2.txt" and sn.get("parent_id") == "v1.txt" for sn in delta_snips)
