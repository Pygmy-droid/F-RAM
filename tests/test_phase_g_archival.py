from __future__ import annotations

import json
from pathlib import Path

from fram_serving.config import FRAMConfig
from fram_serving.storage.archival import archive_from_active_store


def _write_jsonl(path: Path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def test_archival_dry_run_identity(tmp_path: Path):
    active = tmp_path / "active" / "memory_active.jsonl"
    _write_jsonl(active, [{"id": "a", "score": 0.1}])
    cfg = FRAMConfig().model_copy(
        update={"enable_hard_forgetting": True, "enable_archival": True, "active_store_min_items": 0, "STORAGE_ROOT": tmp_path}
    )
    summary = archive_from_active_store(cfg, dry_run=True, active_path=active)
    assert summary["counts"]["archived"] == 0
    assert active.read_text(encoding="utf-8").strip() != ""


def test_archival_respects_floor(tmp_path: Path):
    active = tmp_path / "active" / "memory_active.jsonl"
    _write_jsonl(active, [{"id": "a", "score": 0.01}, {"id": "b", "score": 0.02}])
    cfg = FRAMConfig().model_copy(
        update={
            "enable_hard_forgetting": True,
            "enable_archival": True,
            "active_store_min_items": 10,
            "forgetting_threshold": 0.5,
            "STORAGE_ROOT": tmp_path,
        }
    )
    summary = archive_from_active_store(cfg, dry_run=True, active_path=active)
    assert summary["counts"]["archived"] == 0
    assert summary["counts"]["kept"] == 2


def test_archival_cap_hit(tmp_path: Path):
    active = tmp_path / "active" / "memory_active.jsonl"
    _write_jsonl(active, [{"id": "a", "score": 0.0}, {"id": "b", "score": 0.0}])
    cfg = FRAMConfig().model_copy(
        update={
            "enable_hard_forgetting": True,
            "enable_archival": True,
            "active_store_min_items": 0,
            "forgetting_threshold": 0.5,
            "max_archive_size_mb": 0.0,
            "STORAGE_ROOT": tmp_path,
        }
    )
    summary = archive_from_active_store(cfg, dry_run=False, active_path=active, archive_path=tmp_path / "archive" / "memory_archive.jsonl")
    assert summary["cap_hit"] is True
    assert summary["counts"]["archived"] == 0


def test_archival_non_dry_run_moves_items_with_dedupe(tmp_path: Path):
    active = tmp_path / "active" / "memory_active.jsonl"
    archive = tmp_path / "archive" / "memory_archive.jsonl"
    _write_jsonl(active, [{"id": "x", "score": 0.01}, {"id": "x", "score": 0.9}, {"id": "y", "score": 0.9}])
    _write_jsonl(archive, [{"id": "z", "score": 0.5}])
    cfg = FRAMConfig().model_copy(
        update={
            "enable_hard_forgetting": True,
            "enable_archival": True,
            "hard_forgetting_mode": "enforce",
            "active_store_min_items": 0,
            "forgetting_threshold": 0.05,
            "STORAGE_ROOT": tmp_path,
        }
    )
    summary = archive_from_active_store(cfg, dry_run=False, active_path=active, archive_path=archive)
    assert summary["replaced"]["active"] is True
    assert summary["replaced"]["archive"] is True
    active_lines = active.read_text(encoding="utf-8").strip().splitlines()
    archive_lines = archive.read_text(encoding="utf-8").strip().splitlines()
    # At least one item archived, active shrinks.
    assert len(archive_lines) >= 2
    assert len(active_lines) < 3
    # Dedupe preserved newest/highest for id x.
    ids_in_archive = [json.loads(line)["id"] for line in archive_lines]
    assert ids_in_archive.count("x") == 1


def test_archival_determinism(tmp_path: Path):
    active = tmp_path / "active" / "memory_active.jsonl"
    _write_jsonl(active, [{"id": f"a{i}", "score": 0.01 * i} for i in range(5)])
    cfg = FRAMConfig().model_copy(
        update={
            "enable_hard_forgetting": True,
            "enable_archival": True,
            "hard_forgetting_mode": "enforce",
            "active_store_min_items": 0,
            "forgetting_threshold": 0.05,
            "STORAGE_ROOT": tmp_path,
        }
    )
    res1 = archive_from_active_store(cfg, dry_run=True, active_path=active)
    res2 = archive_from_active_store(cfg, dry_run=True, active_path=active)
    assert res1["counts"] == res2["counts"]
