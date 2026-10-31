from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

from fram_serving.archive import load_chunk, tail_manifest
from fram_serving.config import FRAMConfig


def _resolve_archive_root(storage_root: Optional[str]) -> Path:
    if storage_root:
        base = Path(storage_root)
    else:
        base = Path(FRAMConfig.from_env().STORAGE_ROOT)
    return base / "archive"


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect archive manifest tail and chunks")
    parser.add_argument("--storage-root", dest="storage_root", default=None, help="Override storage root path")
    parser.add_argument("--tail", type=int, default=5, help="Number of manifest entries to show")
    parser.add_argument("--event-id", dest="event_id", default=None, help="Fetch a chunk by event_id")
    parser.add_argument("--json", action="store_true", help="Emit JSON payload")
    args = parser.parse_args(argv)

    archive_root = _resolve_archive_root(args.storage_root)
    try:
        root_resolved = str(archive_root.resolve())
    except Exception:
        root_resolved = str(archive_root)

    entries = tail_manifest(archive_root, limit=max(0, int(args.tail)))
    payload = {
        "archive_root": root_resolved,
        "manifest_path": str(archive_root / "manifest.jsonl"),
        "count": len(entries),
        "events": entries,
    }
    if args.event_id:
        payload["chunk"] = load_chunk(archive_root, args.event_id)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        ids = [entry.get("event_id") for entry in entries if isinstance(entry, dict)]
        print(f"archive_root={root_resolved} count={len(entries)} ids={ids}")
        if args.event_id:
            print(f"event_id={args.event_id} chunk_found={payload.get('chunk') is not None}")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
