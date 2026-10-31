from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fram_serving.config import FRAMConfig  # noqa: E402
from fram_serving.memory import CognitiveMemoryStore  # noqa: E402


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fail if a session ends without logging the final turn or updating "
            "docs/CODEX_DIARY.md + docs/F-RAM-roadmap.md."
        )
    )
    parser.add_argument(
        "--session-id",
        help="Session id to check (defaults to $COGMEM_SESSION_ID or 'default').",
    )
    parser.add_argument(
        "--storage-root",
        help="Override FRAM storage root (defaults to FRAMConfig.STORAGE_ROOT).",
    )
    parser.add_argument(
        "--diary",
        type=Path,
        default=REPO_ROOT / "docs" / "CODEX_DIARY.md",
        help="Path to the diary markdown (default: docs/CODEX_DIARY.md).",
    )
    parser.add_argument(
        "--roadmap",
        type=Path,
        default=REPO_ROOT / "docs" / "F-RAM-roadmap.md",
        help="Path to the roadmap markdown (default: docs/F-RAM-roadmap.md).",
    )
    parser.add_argument(
        "--grace-sec",
        type=int,
        default=300,
        help="Grace window in seconds for diary/roadmap timestamps (default 300).",
    )
    parser.add_argument(
        "--allow-user-last",
        action="store_true",
        help="Allow the last logged turn to be a user entry (default: require assistant).",
    )
    return parser.parse_args(argv)


def _parse_iso(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        stamp = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp


def _doc_mtime(path: Path) -> Optional[datetime]:
    if not path.exists():
        return None
    stamp = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return stamp


def _iter_segments(store: CognitiveMemoryStore) -> Iterable[Path]:
    meta = store._belief_meta()  # intentional: guard needs segment ordering
    segments = meta.get("segments", [])
    if segments:
        for entry in reversed(list(segments)):
            name = entry.get("name")
            if not name:
                continue
            yield store._belief_segment_path(name)
        return
    legacy = store._path(store.FILE_BELIEFS)
    if legacy.exists():
        yield legacy


def _last_session_record(store: CognitiveMemoryStore, session_id: str) -> Optional[Dict[str, Any]]:
    for path in _iter_segments(store):
        if not path.exists():
            continue
        last: Optional[Dict[str, Any]] = None
        for payload in store._iter_jsonl_segment(path):
            if payload.get("session_id") != session_id:
                continue
            last = payload
        if last is not None:
            return last
    return None


def _load_store(storage_root: Optional[str]) -> CognitiveMemoryStore:
    cfg = FRAMConfig.from_env()
    if storage_root:
        override = Path(storage_root).expanduser().resolve()
        cfg = cfg.model_copy(update={"STORAGE_ROOT": override})
    root = cfg.STORAGE_ROOT / cfg.STORAGE_SUBFOLDERS.get("memory", "memory") / "cognitive"
    return CognitiveMemoryStore(root, config=cfg)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    session_id = args.session_id or os.getenv("COGMEM_SESSION_ID") or "default"
    store = _load_store(args.storage_root)
    record = _last_session_record(store, session_id)
    errors: list[str] = []
    if record is None:
        errors.append(f"No logged turns found for session '{session_id}'.")
    else:
        role = record.get("role") or record.get("metadata", {}).get("speaker")
        if not args.allow_user_last and str(role or "").lower() != "assistant":
            errors.append("Last logged turn is not an assistant entry.")
        record_time = _parse_iso(record.get("time"))
        if record_time is None:
            errors.append("Latest logged turn has no valid timestamp.")
        else:
            grace = timedelta(seconds=max(0, int(args.grace_sec)))
            diary_mtime = _doc_mtime(args.diary)
            roadmap_mtime = _doc_mtime(args.roadmap)
            if diary_mtime is None:
                errors.append(f"Diary file not found: {args.diary}")
            elif diary_mtime + grace < record_time:
                errors.append("Diary is older than the latest logged turn.")
            if roadmap_mtime is None:
                errors.append(f"Roadmap file not found: {args.roadmap}")
            elif roadmap_mtime + grace < record_time:
                errors.append("Roadmap is older than the latest logged turn.")

    if errors:
        for err in errors:
            print(f"[closeout] FAIL: {err}", file=sys.stderr)
        return 2

    record_time = record.get("time") if record else "unknown"
    print(f"[closeout] OK: session={session_id} last_turn={record_time}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
