from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import fram_serving.app as app_mod
from fram_serving.archive import (
    ArchiveWriter,
    compute_content_hash,
    iter_manifest,
    load_chunk,
    verify_chain,
)
from fram_serving.memory import CognitiveMemoryStore, WorkingMemoryStore


def _reset_app_state(tmp_path, monkeypatch):
    cfg = app_mod.CFG.model_copy(update={"STORAGE_ROOT": tmp_path / "storage"})
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
    return cfg


def test_archive_append_only_and_chain(tmp_path):
    root = tmp_path / "archive"
    writer = ArchiveWriter(root)
    writer.append_event(
        kind="query",
        request={"text": "hello"},
        response={"answer": "world"},
        trace_id="trace-1",
        meta={"query_id": "q1"},
    )
    manifest_path = root / "manifest.jsonl"
    first_lines = manifest_path.read_text(encoding="utf-8").splitlines()
    assert len(first_lines) == 1

    writer.append_event(
        kind="query",
        request={"text": "second"},
        response={"answer": "entry"},
        trace_id="trace-2",
        meta={"query_id": "q2"},
    )
    second_lines = manifest_path.read_text(encoding="utf-8").splitlines()
    assert len(second_lines) == 2
    assert second_lines[:1] == first_lines

    entries = list(iter_manifest(root))
    assert verify_chain(entries)


def test_archive_chunk_immutability_and_hash(tmp_path):
    root = tmp_path / "archive"
    writer = ArchiveWriter(root)
    entry = writer.append_event(
        kind="query",
        request={"text": "immutable"},
        response={"answer": "chunk"},
        trace_id="trace-imm",
        meta={"query_id": "qimm"},
        event_id="fixed-event",
    )
    chunk = load_chunk(root, "fixed-event")
    assert chunk is not None
    assert compute_content_hash(chunk) == entry.get("content_hash")

    with pytest.raises(FileExistsError):
        writer.append_event(
            kind="query",
            request={"text": "immutable"},
            response={"answer": "chunk"},
            trace_id="trace-imm",
            meta={"query_id": "qimm"},
            event_id="fixed-event",
        )


def test_archive_chain_tamper_detection(tmp_path):
    root = tmp_path / "archive"
    writer = ArchiveWriter(root)
    writer.append_event(
        kind="query",
        request={"text": "first"},
        response={"answer": "one"},
        trace_id="trace-1",
        meta={"query_id": "q1"},
    )
    writer.append_event(
        kind="query",
        request={"text": "second"},
        response={"answer": "two"},
        trace_id="trace-2",
        meta={"query_id": "q2"},
    )
    entries = list(iter_manifest(root))
    assert verify_chain(entries)

    manifest_path = root / "manifest.jsonl"
    lines = manifest_path.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(lines[0])
    tampered["content_hash"] = "0" * 64
    lines[0] = json.dumps(tampered, ensure_ascii=False)
    manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    tampered_entries = list(iter_manifest(root))
    assert not verify_chain(tampered_entries)


def test_query_writes_archive_event(tmp_path, monkeypatch):
    cfg = _reset_app_state(tmp_path, monkeypatch)
    with TestClient(app_mod.app) as client:
        resp = client.post("/query", json={"text": "Archive event smoke"})
        assert resp.status_code == 200

    archive_root = cfg.STORAGE_ROOT / "archive"
    entries = list(iter_manifest(archive_root))
    assert entries
    live_entries = [entry for entry in entries if entry.get("kind") != "rep_milestone"]
    assert live_entries
    last = live_entries[-1]
    assert last.get("trace_id")
    chunk = load_chunk(archive_root, last.get("event_id"))
    assert chunk is not None
    assert chunk.get("trace_id") == last.get("trace_id")
    assert compute_content_hash(chunk) == last.get("content_hash")
    assert verify_chain(entries)
