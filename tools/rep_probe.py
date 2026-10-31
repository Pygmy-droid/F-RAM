from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

from fram_serving.rep import load_rep, update_rep
from fram_serving.config import FRAMConfig


def _resolve_storage_root(storage_root: Optional[str]) -> Path:
    if storage_root:
        return Path(storage_root)
    return Path(FRAMConfig.from_env().STORAGE_ROOT)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect the REP (re-entry packet)")
    parser.add_argument("--storage-root", dest="storage_root", default=None, help="Override storage root path")
    parser.add_argument("--update", action="store_true", help="Rebuild REP before reading")
    parser.add_argument("--json", action="store_true", help="Emit full JSON payload")
    args = parser.parse_args(argv)

    storage_root = _resolve_storage_root(args.storage_root)
    if args.update:
        update_rep(storage_root=storage_root)
    rep = load_rep(storage_root)
    if rep is None:
        print("REP not found")
        return 2
    if args.json:
        print(json.dumps(rep, ensure_ascii=False))
        return 0
    print(f"rep_version={rep.get('version')} trace_id={rep.get('trace_link', {}).get('trace_id')}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
