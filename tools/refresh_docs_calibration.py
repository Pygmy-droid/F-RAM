from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Refresh docs ingestion and calibration payloads in one pass: "
            "list recent docs, rebuild docs ingest files, rebuild demo corpus, "
            "and lint/report calibration payloads."
        )
    )
    parser.add_argument(
        "--docs-root",
        default="docs",
        help="Docs directory to scan and ingest (default: %(default)s).",
    )
    parser.add_argument(
        "--hours",
        type=float,
        default=48.0,
        help="Look-back window for recent docs listing (default: %(default)s).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Maximum number of recent docs to list (default: %(default)s).",
    )
    parser.add_argument(
        "--skip-calibration",
        action="store_true",
        help="Skip calibration refresh during demo ingest (lint/status still run).",
    )
    parser.add_argument(
        "--lint-strict",
        action="store_true",
        help="Run calibration lint in strict mode.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the commands without executing them.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def _run_step(cmd: list[str], *, dry_run: bool) -> None:
    display = " ".join(cmd)
    print(f"[refresh] {display}")
    if dry_run:
        return
    subprocess.run(cmd, cwd=REPO_ROOT, check=True)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    python = sys.executable
    docs_root = str(Path(args.docs_root))

    steps = [
        [
            python,
            str(REPO_ROOT / "tools" / "list_recent_docs.py"),
            "--root",
            docs_root,
            "--hours",
            f"{args.hours:g}",
            "--limit",
            str(args.limit),
        ],
        [
            python,
            str(REPO_ROOT / "scripts" / "ingest_project_docs.py"),
            "--docs",
            docs_root,
        ],
        [python, str(REPO_ROOT / "scripts" / "ingest_demo.py")],
    ]
    if args.skip_calibration:
        steps[-1].append("--skip-calibration")

    lint_cmd = [python, str(REPO_ROOT / "tools" / "calibration_lint.py")]
    if args.lint_strict:
        lint_cmd.append("--strict")
    steps.append(lint_cmd)

    steps.append([python, str(REPO_ROOT / "tools" / "calibration_status.py")])

    for cmd in steps:
        _run_step(cmd, dry_run=args.dry_run)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
