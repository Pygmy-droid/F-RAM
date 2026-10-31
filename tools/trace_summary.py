"""Summarize persisted FRAM trace logs for quick diagnostics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, List, Mapping, Sequence

import sys


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fram_serving.config import FRAMConfig
from fram_serving import observability


def _iter_traces_from_dir(traces_dir: Path, limit: int) -> List[dict]:
    files = sorted(traces_dir.glob("*.jsonl"), reverse=True)
    traces: List[dict] = []
    for file in files:
        for record in reversed(list(observability.iter_jsonl(file))):
            traces.append(record)
            if len(traces) >= limit:
                return traces
    return traces


def _collect_traces(
    storage_root: Path,
    *,
    limit: int,
    traces_dir: Path | None = None,
) -> List[dict]:
    if traces_dir is not None:
        return _iter_traces_from_dir(traces_dir, limit)
    return observability.load_recent_traces(storage_root, limit=limit)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize FRAM trace logs")
    parser.add_argument(
        "--storage-root",
        type=Path,
        default=None,
        help="Override FRAM storage root (defaults to FRAMConfig.STORAGE_ROOT)",
    )
    parser.add_argument(
        "--traces-dir",
        type=Path,
        default=None,
        help="Optional explicit traces directory (skips storage root layout)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of trace records to include in the summary",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Path to write the summary JSON (stdout by default)",
    )
    parser.add_argument(
        "--include-records",
        action="store_true",
        help="Include the raw trace records alongside the summary",
    )
    return parser.parse_args(argv)


def summarize_traces(
    traces: Iterable[Mapping[str, object]],
    *,
    include_records: bool = False,
) -> dict:
    traces_list = list(traces)
    summary = observability.summarize_traces(traces_list)
    payload = {"summary": summary}
    if include_records:
        payload["records"] = traces_list
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    cfg = FRAMConfig.from_env()
    storage_root = Path(args.storage_root) if args.storage_root is not None else Path(cfg.STORAGE_ROOT)

    traces = _collect_traces(storage_root, limit=max(1, args.limit), traces_dir=args.traces_dir)
    payload = summarize_traces(traces, include_records=args.include_records)

    data = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(data, encoding="utf-8")
    else:
        print(data)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
