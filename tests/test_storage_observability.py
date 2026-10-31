from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import fram_serving.app as app
from fram_serving.config import FRAMConfig


def _write_jsonl(path: Path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def test_storage_observability_json(tmp_path: Path, monkeypatch):
    active = tmp_path / "active" / "memory_active.jsonl"
    archive = tmp_path / "archive" / "memory_archive.jsonl"
    _write_jsonl(active, [{"id": "a"}])
    _write_jsonl(archive, [{"id": "b"}])
    cfg = FRAMConfig().model_copy(update={"STORAGE_ROOT": tmp_path, "phase_d": app.CFG.phase_d})
    monkeypatch.setattr(app, "CFG", cfg)
    client = TestClient(app.app)
    resp = client.get("/observability/storage")
    assert resp.status_code == 200
    payload = resp.json()
    assert "active" in payload and "archive" in payload and "snapshots" in payload
    assert payload["active"]["count"] >= 1


def test_storage_observability_html(tmp_path: Path, monkeypatch):
    cfg = FRAMConfig().model_copy(update={"STORAGE_ROOT": tmp_path, "phase_d": app.CFG.phase_d})
    monkeypatch.setattr(app, "CFG", cfg)
    client = TestClient(app.app)
    resp = client.get("/observability/storage?html=1")
    assert resp.status_code == 200
    assert "Storage Summary" in resp.text
