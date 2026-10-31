from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from fram_serving.config import FRAMConfig
from fram_serving.storage.compaction import _iter_jsonl, _write_atomic


def _default_paths(config: FRAMConfig) -> tuple[Path, Path, Path]:
    root = getattr(config, "STORAGE_ROOT", Path("./storage"))
    active = Path(root) / "active" / "memory_active.jsonl"
    archive = Path(root) / "archive" / "memory_archive.jsonl"
    snapshots_dir = Path(root) / "snapshots"
    return active, archive, snapshots_dir


def _timestamped_name(label: str | None) -> str:
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%d_%H%M%S")
    if label:
        return f"snapshot_{ts}_{label}.jsonl"
    return f"snapshot_{ts}.jsonl"


def create_snapshot(
    config: FRAMConfig,
    label: str | None = None,
) -> Dict[str, Any]:
    """
    Create a read-only snapshot of active + archive stores.

    Writes to storage/snapshots/snapshot_<ts>[_label].jsonl and updates
    snapshot_latest.json.
    """
    active_path, archive_path, snapshots_dir = _default_paths(config)
    snapshots_dir.mkdir(parents=True, exist_ok=True)

    snapshot_name = _timestamped_name(label)
    snapshot_path = snapshots_dir / snapshot_name

    entries: List[str] = []
    active_count = 0
    archive_count = 0

    for rec in _iter_jsonl(active_path):
        active_count += 1
        payload = dict(rec)
        payload["source"] = "active"
        entries.append(json.dumps(payload, ensure_ascii=False))
    for rec in _iter_jsonl(archive_path):
        archive_count += 1
        payload = dict(rec)
        payload["source"] = "archive"
        entries.append(json.dumps(payload, ensure_ascii=False))

    _write_atomic(snapshot_path, entries)
    meta = {
        "path": str(snapshot_path),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "label": label,
        "counts": {
            "active": active_count,
            "archive": archive_count,
            "total": active_count + archive_count,
        },
    }
    latest_meta_path = snapshots_dir / "snapshot_latest.json"
    latest_meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return meta
