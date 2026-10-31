"""CLI for building the lossless FRAM visual evidence ledger."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from fram_core.visual_evidence import parse_extensions, scan_visual_evidence, write_visual_manifest


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Recursively hash and inventory every FRAM visual without modifying source files."
    )
    parser.add_argument("source_root", type=Path, help="Root of the visual evidence corpus.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("storage") / "visual_evidence",
        help="Ledger destination (default: storage/visual_evidence).",
    )
    parser.add_argument(
        "--extension",
        action="append",
        default=None,
        help="Optional extension(s), repeatable or comma-separated. Defaults to all supported visuals.",
    )
    parser.add_argument(
        "--allow-errors",
        action="store_true",
        help="Return success even when files or directories could not be read.",
    )
    parser.add_argument("--json", action="store_true", help="Print the summary as JSON.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    report = scan_visual_evidence(args.source_root, extensions=parse_extensions(args.extension))
    paths = write_visual_manifest(report, args.output_dir)
    summary = report.summary()
    summary["manifest"] = str(paths.manifest.resolve())
    summary["summary"] = str(paths.summary.resolve())
    summary["duplicates"] = str(paths.duplicates.resolve())
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(
            "Indexed "
            f"{summary['indexed_visuals']}/{summary['discovered_visuals']} visuals "
            f"({summary['unique_content']} unique; {summary['exact_duplicate_files']} exact duplicates)."
        )
        print(
            f"Actual visuals: {summary['actual_visuals']}; "
            f"Mac metadata sidecars: {summary['metadata_sidecars']}; "
            f"unverified: {summary['unverified_visuals']}"
        )
        print(f"Completeness: {summary['completeness_status']}")
        print(f"Manifest: {paths.manifest}")
    return 0 if report.complete or args.allow_errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
