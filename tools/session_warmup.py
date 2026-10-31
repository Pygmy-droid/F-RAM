from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.bootstrap_memory import format_text, load_payload  # noqa: E402
from fram_serving.config import FRAMConfig  # noqa: E402
from fram_serving.memory import CognitiveMemoryStore  # noqa: E402


def _docs_directory() -> Path:
    return REPO_ROOT / "docs"


def _collect_docs(root: Path, hours: float, limit: int) -> List[Dict[str, Any]]:
    if not root.exists():
        return []
    rows: List[tuple[datetime, Path]] = []
    now = datetime.now(timezone.utc)
    window = timedelta(hours=hours) if hours > 0 else None
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        except OSError:
            continue
        if window is not None and (now - mtime) > window:
            continue
        rows.append((mtime, path))
    rows.sort(key=lambda item: item[0], reverse=True)
    if limit > 0:
        rows = rows[:limit]
    docs: List[Dict[str, Any]] = []
    for mtime, path in rows:
        docs.append(
            {
                "path": str(path.relative_to(REPO_ROOT)),
                "mtime": mtime.isoformat(timespec="seconds"),
                "age": _format_age(now - mtime),
            }
        )
    return docs


def _format_age(delta: timedelta) -> str:
    seconds = int(delta.total_seconds())
    if seconds <= 0:
        return "just now"
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    parts: List[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes and not days:
        parts.append(f"{minutes}m")
    return " ".join(parts) + " ago" if parts else "just now"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the standard FRAM warm-up ritual (recent docs + cognitive memory snapshot)."
    )
    parser.add_argument("--docs-hours", type=float, default=48.0, help="Lookback window for docs.")
    parser.add_argument("--docs-limit", type=int, default=10, help="Maximum doc rows (0 = all).")
    parser.add_argument("--docs-root", type=Path, default=_docs_directory(), help="Docs directory.")
    parser.add_argument("--no-docs", action="store_true", help="Skip docs listing.")

    parser.add_argument("--memory-query", help="Optional search query for cognitive memory.")
    parser.add_argument("--memory-limit", type=int, default=5, help="Search results to return.")
    parser.add_argument("--memory-window", type=int, default=20, help="Recent summary window when no query.")
    parser.add_argument(
        "--memory-source",
        choices=["auto", "server", "files"],
        default="auto",
        help="Preferred data source (default: auto).",
    )
    parser.add_argument("--memory-domain", help="Domain filter for cognitive search.")
    parser.add_argument("--memory-task", help="Task filter for cognitive search.")
    parser.add_argument(
        "--storage-root",
        help="Override STORAGE_ROOT when reading files (mirrors tools/bootstrap_memory.py).",
    )
    parser.add_argument(
        "--identity-name",
        help="Preferred agent name to persist in cognitive memory (appends a belief when missing).",
    )
    parser.add_argument(
        "--identity-note",
        help="Additional note to store alongside the identity belief.",
    )
    parser.add_argument("--memory-timeout", type=float, default=3.0, help="Server timeout in seconds.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="FRAM server base URL.")
    parser.add_argument("--no-memory", action="store_true", help="Skip cognitive memory step.")

    parser.add_argument("--json", action="store_true", help="Emit JSON for automation.")
    parser.add_argument("--quiet", action="store_true", help="Suppress textual output (still exits 0/1).")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    cfg = FRAMConfig.from_env()
    storage_override: Optional[Path] = None
    if args.storage_root:
        storage_override = Path(args.storage_root).expanduser().resolve()
        cfg = cfg.model_copy(update={"STORAGE_ROOT": storage_override})

    docs_payload: Optional[List[Dict[str, Any]]] = None
    if not args.no_docs:
        docs_payload = _collect_docs(Path(args.docs_root), hours=args.docs_hours, limit=args.docs_limit)

    memory_payload: Optional[Dict[str, Any]] = None
    memory_mode: Optional[str] = None
    if not args.no_memory:
        storage_override_str = str(storage_override) if storage_override is not None else None
        try:
            memory_payload, memory_mode = load_payload(
                query=args.memory_query,
                limit=args.memory_limit,
                window=args.memory_window,
                domain=args.memory_domain,
                task=args.memory_task,
                base_url=args.base_url,
                storage_root=storage_override_str,
                source=args.memory_source,
                timeout=args.memory_timeout,
            )
        except RuntimeError as exc:
            if args.json:
                print(json.dumps({"error": str(exc)}))
            elif not args.quiet:
                print(f"[warmup] {exc}", file=sys.stderr)
            return 1

    if args.identity_name:
        _ensure_identity_belief(
            cfg,
            name=args.identity_name.strip(),
            note=args.identity_note.strip() if args.identity_note else None,
        )

    if args.json:
        payload: Dict[str, Any] = {"docs": docs_payload, "memory": memory_payload, "memory_mode": memory_mode}
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    if not args.quiet:
        if docs_payload is not None:
            if docs_payload:
                print("Recent docs:")
                for row in docs_payload:
                    print(f"  {row['path']}  ({row['age']})")
            else:
                print("Recent docs: <none within window>")
            print()
        if memory_payload is not None:
            print("Cognitive memory:")
            text = format_text(memory_payload, args.memory_query)
            print(text)
    return 0


def _ensure_identity_belief(cfg: FRAMConfig, *, name: str, note: Optional[str]) -> None:
    if not name:
        return
    store_root = cfg.STORAGE_ROOT / cfg.STORAGE_SUBFOLDERS.get("memory", "memory") / "cognitive"
    store = CognitiveMemoryStore(store_root, config=cfg)
    meta = store._belief_meta()
    exists = False
    for segment in meta.get("segments", []):
        seg_path = store._belief_segment_path(segment["name"])
        if not seg_path.exists():
            continue
        with seg_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                text = str(data.get("text") or "")
                if name.lower() in text.lower():
                    exists = True
                    break
        if exists:
            break
    if exists:
        return
    belief_text = f"The coding agent prefers to be called {name}."
    metadata: Dict[str, Any] = {"kind": "identity", "source": "session_warmup"}
    if note:
        metadata["note"] = note
    store.append_belief(
        text=belief_text,
        metadata=metadata,
        role="assistant",
        session_id="identity",
        pair_id="identity",
        source={"kind": "live", "tag": "identity"},
    )


if __name__ == "__main__":
    raise SystemExit(main())

