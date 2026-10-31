from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="List docs/* files that changed recently so bootstrap reads stay current."
    )
    parser.add_argument(
        "--root",
        default="docs",
        help="Path to the docs directory (default: %(default)s).",
    )
    parser.add_argument(
        "--hours",
        type=float,
        default=24.0,
        help="Look back window in hours for recent edits (default: %(default)s).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Show all files sorted by modified time instead of filtering by --hours.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Maximum number of rows to display (default: %(default)s).",
    )
    parser.add_argument(
        "--reverse",
        action="store_true",
        help="Sort ascending (oldest first). Defaults to newest first.",
    )
    return parser.parse_args()


def _iter_doc_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_file():
            yield path


def _format_delta(delta: timedelta) -> str:
    # delta is non-negative (now - mtime)
    seconds = int(delta.total_seconds())
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes and not days:
        # only include minutes when within the same day to keep output concise
        parts.append(f"{minutes}m")
    if not parts:
        return "just now"
    return " ".join(parts) + " ago"


def main() -> int:
    args = _parse_args()
    doc_root = Path(args.root).resolve()
    if not doc_root.exists():
        print(f"[recent-docs] docs directory not found: {doc_root}")
        return 1

    now = datetime.now(timezone.utc)
    window = timedelta(hours=args.hours)
    rows: list[tuple[datetime, Path]] = []
    for file_path in _iter_doc_files(doc_root):
        try:
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)
        except OSError:
            continue
        rows.append((mtime, file_path))

    if not rows:
        print("[recent-docs] No files detected under", doc_root)
        return 0

    rows.sort(key=lambda item: item[0], reverse=not args.reverse)

    shown = 0
    for mtime, file_path in rows:
        if not args.all and now - mtime > window:
            continue
        rel_path = file_path.relative_to(Path.cwd())
        delta = now - mtime
        mtime_str = mtime.isoformat(timespec="seconds")
        print(f"{mtime_str} | {_format_delta(delta):>12} | {rel_path}")
        shown += 1
        if shown >= args.limit:
            break

    if shown == 0:
        print(
            f"[recent-docs] No files updated within the last {args.hours:g}h under {doc_root}. "
            "Use --all to list everything.",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
