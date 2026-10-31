from __future__ import annotations

import argparse
import json
from typing import Sequence

from fram_serving.config import FRAMConfig
from fram_serving.storage.snapshot import create_snapshot


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase G snapshot (read-only).")
    parser.add_argument("--label", type=str, help="Optional label to append to the snapshot filename.")
    args = parser.parse_args(argv)

    cfg = FRAMConfig.from_env()
    summary = create_snapshot(cfg, label=args.label)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
