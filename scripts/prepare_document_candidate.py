"""Import explicitly supplied documents into a new offline evaluation candidate."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", nargs="+", type=Path, required=True)
    parser.add_argument("--base-memory", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--imported-at", required=True)
    parser.add_argument("--chunk-bytes", type=int, default=4096)
    args = parser.parse_args()
    bootstrap = args.destination.resolve() / "bootstrap"
    os.environ.update(
        FRAM_STORAGE_ROOT=str(bootstrap),
        COGMEM_AUTOLOG="0",
        FRAM_DEV_PROFILE="0",
        FRAM_FRACTAL_INFLUENCE="0",
    )
    from fram_eval.document_candidate import prepare_candidate

    receipt = prepare_candidate(
        args.sources,
        base_memory=args.base_memory,
        destination=args.destination,
        imported_at=args.imported_at,
        chunk_bytes=args.chunk_bytes,
    )
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "sources": len(receipt["sources"]),
                "records_added": receipt["records_added"],
                "memory_root": receipt["memory_root"],
                "source_files_unchanged": receipt["source_files_unchanged"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
