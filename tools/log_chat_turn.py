from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fram_serving.config import FRAMConfig  # noqa: E402
from fram_serving.memory import CognitiveMemoryStore  # noqa: E402


def _parse_kv(items: Optional[list[str]]) -> Dict[str, str]:
    metadata: Dict[str, str] = {}
    if not items:
        return metadata
    for raw in items:
        if "=" not in raw:
            metadata[raw.strip()] = ""
            continue
        key, value = raw.split("=", 1)
        metadata[key.strip()] = value.strip()
    return metadata


def _load_store(storage_root: Optional[str]) -> CognitiveMemoryStore:
    cfg = FRAMConfig.from_env()
    if storage_root:
        override = Path(storage_root).expanduser().resolve()
        cfg = cfg.model_copy(update={"STORAGE_ROOT": override})
    root = cfg.STORAGE_ROOT / cfg.STORAGE_SUBFOLDERS.get("memory", "memory") / "cognitive"
    return CognitiveMemoryStore(root, config=cfg)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Append a conversational turn (user/assistant text) to the cognitive memory store. "
            "Accepts user/assistant text simultaneously so a single call can log both sides of the exchange."
        )
    )
    parser.add_argument(
        "--user",
        help="User text for this turn (omit when only logging the assistant response).",
    )
    parser.add_argument(
        "--assistant",
        help="Assistant text for this turn (omit when only logging the user input).",
    )
    parser.add_argument(
        "--session-id",
        help="Optional session identifier to store alongside the belief entries.",
    )
    parser.add_argument(
        "--topic",
        help="Optional topic label stored in metadata.",
    )
    parser.add_argument(
        "--metadata",
        metavar="KEY=VALUE",
        nargs="*",
        help="Extra metadata to attach (space separated KEY=VALUE pairs).",
    )
    parser.add_argument(
        "--seq-no",
        type=int,
        help="Optional explicit sequence number for the user turn (assistant defaults to seq_no+1).",
    )
    parser.add_argument(
        "--created-at",
        help="Optional ISO timestamp applied to both turns (defaults to now).",
    )
    parser.add_argument(
        "--source-kind",
        default="live",
        help="Source kind metadata (default: live).",
    )
    parser.add_argument(
        "--trace-id",
        help="Optional trace identifier stored inside the source metadata.",
    )
    parser.add_argument(
        "--warn-log",
        help="Optional JSONL file where failures are recorded before exiting (script fails open).",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        help="Optional confidence for assistant text; applied only to the assistant entry when provided.",
    )
    parser.add_argument(
        "--storage-root",
        help="Override the FRAM storage root (defaults to FRAMConfig.STORAGE_ROOT).",
    )
    return parser.parse_args()


def _append_text(
    store: CognitiveMemoryStore,
    text: str,
    speaker: str,
    pair_id: str,
    session_id: Optional[str],
    topic: Optional[str],
    base_metadata: Dict[str, str],
    confidence: Optional[float] = None,
    seq_no: Optional[int] = None,
    created_at: Optional[str] = None,
    source_kind: str = "live",
    trace_id: Optional[str] = None,
) -> Dict[str, str]:
    if not text:
        raise ValueError("Empty text payload cannot be logged.")
    metadata = dict(base_metadata)
    metadata["speaker"] = speaker
    metadata["pair_id"] = pair_id
    if session_id:
        metadata["session_id"] = session_id
    if topic:
        metadata.setdefault("topic", topic)
    if seq_no is not None:
        metadata.setdefault("seq_no", str(seq_no))
    source = {"kind": source_kind}
    if trace_id:
        source["trace_id"] = trace_id
    entry = store.append_belief(
        text=text,
        confidence=confidence if speaker == "assistant" else None,
        metadata=metadata or None,
        role=speaker,
        session_id=session_id,
        pair_id=pair_id,
        seq_no=seq_no,
        created_at=created_at,
        source=source,
    )
    return entry


def _write_warning(path: str, *, session_id: Optional[str], message: str) -> None:
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "level": "WARN",
        "message": message,
    }
    warn_path = Path(path)
    warn_path.parent.mkdir(parents=True, exist_ok=True)
    with warn_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> int:
    args = parse_args()
    if not args.user and not args.assistant:
        print("Nothing to log: supply --user and/or --assistant.", file=sys.stderr)
        return 1

    try:
        store = _load_store(args.storage_root)
        base_metadata = _parse_kv(args.metadata)
        pair_id = uuid.uuid4().hex
        source_kind = args.source_kind
        trace_id = args.trace_id
        created_at = args.created_at
        user_seq = args.seq_no
        assistant_seq = None
        if args.assistant and args.user and args.seq_no is not None:
            assistant_seq = args.seq_no + 1
        elif args.assistant:
            assistant_seq = args.seq_no

        def _announce(label: str, entry: Dict[str, str]) -> None:
            if entry.get("skipped"):
                hash_value = entry.get("hash")
                if hash_value:
                    print(f"[{label}] belief skipped (duplicate hash {hash_value})")
                else:
                    print(f"[{label}] belief skipped (duplicate/replay)")
            else:
                print(f"[{label}] belief stored: {entry['id']} ({entry['time']})")

        if args.user:
            user_entry = _append_text(
                store,
                text=args.user,
                speaker="user",
                pair_id=pair_id,
                session_id=args.session_id,
                topic=args.topic,
                base_metadata=base_metadata,
                seq_no=user_seq,
                created_at=created_at,
                source_kind=source_kind,
                trace_id=trace_id,
            )
            _announce("user", user_entry)

        if args.assistant:
            assistant_entry = _append_text(
                store,
                text=args.assistant,
                speaker="assistant",
                pair_id=pair_id,
                session_id=args.session_id,
                topic=args.topic,
                base_metadata=base_metadata,
                confidence=args.confidence,
                seq_no=assistant_seq,
                created_at=created_at,
                source_kind=source_kind,
                trace_id=trace_id,
            )
            _announce("assistant", assistant_entry)

        return 0
    except Exception as exc:  # pragma: no cover - fail-open path
        if args.warn_log:
            _write_warning(args.warn_log, session_id=args.session_id, message=str(exc))
            return 0
        raise


if __name__ == "__main__":
    raise SystemExit(main())
