from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from fram_serving.config import FRAMConfig
from fram_serving.storage.archival import archive_from_active_store


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase G archival (maintenance).")
    parser.add_argument("--dry-run", action="store_true", help="Simulate archival without writing files (default).")
    parser.add_argument("--force", action="store_true", help="Allow file mutation (non-dry-run).")
    parser.add_argument("--active-path", type=Path, default=None, help="Override active store path.")
    parser.add_argument("--archive-path", type=Path, default=None, help="Override archive store path.")
    parser.add_argument("--max-archive-size-mb", type=float, help="Override max_archive_size_mb.")
    parser.add_argument("--active-store-min-items", type=int, help="Override active_store_min_items.")
    args = parser.parse_args(argv)

    cfg_updates = {}
    if args.max_archive_size_mb is not None:
        cfg_updates["max_archive_size_mb"] = float(args.max_archive_size_mb)
    if args.active_store_min_items is not None:
        cfg_updates["active_store_min_items"] = int(args.active_store_min_items)
    cfg = FRAMConfig.from_env().model_copy(update=cfg_updates)

    dry_run = not args.force or args.dry_run
    summary = archive_from_active_store(cfg, dry_run=dry_run, active_path=args.active_path, archive_path=args.archive_path)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
