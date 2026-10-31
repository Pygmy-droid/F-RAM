from __future__ import annotations

import json
from pathlib import Path

from fram_serving.config import FRAMConfig
from fram_serving.storage.compaction import compact_active_store
import fram_serving.app as app


def _write_jsonl(path: Path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def test_compaction_dry_run_identity(tmp_path: Path):
    active = tmp_path / "active" / "memory_active.jsonl"
    records = [{"id": "a", "score": 0.1}, {"id": "b", "score": 0.2}]
    _write_jsonl(active, records)
    cfg = FRAMConfig().model_copy(update={"enable_hard_forgetting": True, "active_store_min_items": 0, "STORAGE_ROOT": tmp_path})
    summary = compact_active_store(cfg, dry_run=True, active_path=active)
    assert summary["counts"]["kept"] == 2
    assert summary["replaced"] is False
    assert active.read_text(encoding="utf-8").strip().splitlines() == [
        json.dumps(r, ensure_ascii=False) for r in records
    ]


def test_compaction_respects_floor(tmp_path: Path):
    active = tmp_path / "active" / "memory_active.jsonl"
    records = [{"id": "a", "score": 0.01}, {"id": "b", "score": 0.02}]
    _write_jsonl(active, records)
    cfg = FRAMConfig().model_copy(
        update={
            "enable_hard_forgetting": True,
            "active_store_min_items": 5,
            "forgetting_threshold": 0.5,
            "STORAGE_ROOT": tmp_path,
        }
    )
    summary = compact_active_store(cfg, dry_run=True, active_path=active)
    assert summary["counts"]["kept"] == len(records)
    assert summary["counts"]["forgotten"] == 0


def test_compaction_forgetting_monotonic_threshold(tmp_path: Path):
    active = tmp_path / "active" / "memory_active.jsonl"
    records = [{"id": f"r{i}", "score": s} for i, s in enumerate([0.05, 0.1, 0.2, 0.6])]
    _write_jsonl(active, records)
    cfg_lo = FRAMConfig().model_copy(
        update={"enable_hard_forgetting": True, "active_store_min_items": 0, "forgetting_threshold": 0.05, "STORAGE_ROOT": tmp_path}
    )
    cfg_hi = cfg_lo.model_copy(update={"forgetting_threshold": 0.3})
    res_lo = compact_active_store(cfg_lo, dry_run=True, active_path=active)
    res_hi = compact_active_store(cfg_hi, dry_run=True, active_path=active)
    forgotten_lo = res_lo["counts"]["forgotten"]
    forgotten_hi = res_hi["counts"]["forgotten"]
    assert forgotten_hi >= forgotten_lo


def test_compaction_non_dry_run_rewrites_atomically(tmp_path: Path):
    active = tmp_path / "active" / "memory_active.jsonl"
    records = [
        {"id": "a", "score": 0.9},
        {"id": "a", "score": 0.1},  # duplicate id should be dropped
        {"id": "b", "score": 0.01},  # forgotten
    ]
    _write_jsonl(active, records)
    before_size = active.stat().st_size
    cfg = FRAMConfig().model_copy(
        update={
            "enable_hard_forgetting": True,
            "hard_forgetting_mode": "enforce",
            "active_store_min_items": 0,
            "forgetting_threshold": 0.05,
            "STORAGE_ROOT": tmp_path,
        }
    )
    summary = compact_active_store(cfg, dry_run=False, active_path=active)
    assert summary["replaced"] is True
    lines = active.read_text(encoding="utf-8").strip().splitlines()
    # Duplicate removed, forgotten removed, one record kept.
    assert len(lines) == 1
    kept = json.loads(lines[0])
    assert kept["id"] == "a"


def test_storage_summary_shape(tmp_path: Path, monkeypatch):
    active = tmp_path / "active" / "memory_active.jsonl"
    archive = tmp_path / "archive" / "memory_archive.jsonl"
    _write_jsonl(active, [{"id": "a", "score": 1.0}])
    _write_jsonl(archive, [{"id": "arch", "score": 0.1}])
    compaction_meta = tmp_path / "observability" / "compaction_latest.json"
    compaction_meta.parent.mkdir(parents=True, exist_ok=True)
    compaction_meta.write_text(json.dumps({"status": "ok"}), encoding="utf-8")
    cfg = FRAMConfig().model_copy(update={"STORAGE_ROOT": tmp_path, "phase_d": app.CFG.phase_d})
    monkeypatch.setattr(app, "CFG", cfg)
    summary = app._storage_summary()
    assert "active" in summary and "archive" in summary
    assert summary["active"]["count"] >= 1
    assert summary["archive"]["count"] >= 1
    assert summary.get("last_compaction", {}).get("status") == "ok"
