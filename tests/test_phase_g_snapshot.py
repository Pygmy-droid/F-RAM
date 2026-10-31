from __future__ import annotations

import json
from pathlib import Path

from fram_serving.config import FRAMConfig
from fram_serving.storage.snapshot import create_snapshot


def _write_jsonl(path: Path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def test_snapshot_no_active_archive(tmp_path: Path):
    cfg = FRAMConfig().model_copy(update={"STORAGE_ROOT": tmp_path})
    meta = create_snapshot(cfg, label="empty")
    snapshots_dir = tmp_path / "snapshots"
    assert snapshots_dir.exists()
    latest = json.loads((snapshots_dir / "snapshot_latest.json").read_text(encoding="utf-8"))
    assert latest["counts"]["total"] == 0
    snapshot_path = Path(meta["path"])
    assert snapshot_path.exists()
    assert snapshot_path.read_text(encoding="utf-8") == ""


def test_snapshot_with_data(tmp_path: Path):
    active = tmp_path / "active" / "memory_active.jsonl"
    archive = tmp_path / "archive" / "memory_archive.jsonl"
    _write_jsonl(active, [{"id": "a", "score": 1.0}])
    _write_jsonl(archive, [{"id": "z", "score": 0.5}])
    cfg = FRAMConfig().model_copy(update={"STORAGE_ROOT": tmp_path})
    meta = create_snapshot(cfg, label="test")
    snap_path = Path(meta["path"])
    lines = snap_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    sources = [json.loads(line)["source"] for line in lines]
    assert "active" in sources
    assert "archive" in sources
    latest = json.loads((tmp_path / "snapshots" / "snapshot_latest.json").read_text(encoding="utf-8"))
    assert latest["counts"]["active"] == 1
    assert latest["counts"]["archive"] == 1


def test_snapshot_latest_shape(tmp_path: Path):
    cfg = FRAMConfig().model_copy(update={"STORAGE_ROOT": tmp_path})
    create_snapshot(cfg, label=None)
    latest = json.loads((tmp_path / "snapshots" / "snapshot_latest.json").read_text(encoding="utf-8"))
    assert "path" in latest and "counts" in latest and "created_at" in latest
