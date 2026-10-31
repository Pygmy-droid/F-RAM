from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path
from typing import Dict

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fram_serving.config import FRAMConfig
from fram_serving.memory import CognitiveMemoryStore


def _parse_metadata(items: list[str] | None) -> Dict[str, str]:
    metadata: Dict[str, str] = {}
    if not items:
        return metadata
    for item in items:
        if "=" not in item:
            metadata[item] = ""
            continue
        key, value = item.split("=", 1)
        metadata[key.strip()] = value.strip()
    return metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Append a belief entry to the cognitive memory store. "
            "Intended for logging chat turns or high-level summaries."
        )
    )
    parser.add_argument(
        "--text",
        help="Belief text. When omitted, reads from stdin.",
    )
    parser.add_argument(
        "--speaker",
        help="Optional speaker tag (e.g., user, assistant). Stored in metadata and raised to the role field.",
    )
    parser.add_argument(
        "--session-id",
        help="Optional session identifier stored alongside the belief.",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        help="Optional confidence score (0-1) to store with the belief.",
    )
    parser.add_argument(
        "--metadata",
        metavar="KEY=VALUE",
        nargs="*",
        help="Additional metadata entries to attach (space separated KEY=VALUE pairs).",
    )
    parser.add_argument(
        "--pair-id",
        help="Optional pair identifier; defaults to a UUID when omitted.",
    )
    parser.add_argument(
        "--seq-no",
        type=int,
        help="Optional explicit sequence number (monotonic per session).",
    )
    parser.add_argument(
        "--created-at",
        help="Optional creation timestamp (ISO-8601). Defaults to now.",
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
        "--storage-root",
        help="Override storage root (defaults to FRAMConfig.STORAGE_ROOT).",
    )
    return parser.parse_args()


def load_text(arg_text: str | None) -> str:
    if arg_text is not None:
        return arg_text
    buffer = sys.stdin.read()
    text = buffer.strip()
    if not text:
        raise SystemExit("No text provided (pass --text or pipe input).")
    return text


def build_store(storage_root_override: str | None) -> CognitiveMemoryStore:
    cfg = FRAMConfig.from_env()
    if storage_root_override:
        root_override = Path(storage_root_override).expanduser().resolve()
        cfg = cfg.model_copy(update={"STORAGE_ROOT": root_override})
    root = cfg.STORAGE_ROOT / cfg.STORAGE_SUBFOLDERS.get("memory", "memory") / "cognitive"
    return CognitiveMemoryStore(root, config=cfg)


def main() -> int:
    args = parse_args()
    text = load_text(args.text)
    metadata = _parse_metadata(args.metadata)
    pair_id = args.pair_id or uuid.uuid4().hex
    if args.speaker:
        metadata.setdefault("speaker", args.speaker)
    if args.session_id:
        metadata.setdefault("session_id", args.session_id)
    metadata.setdefault("pair_id", pair_id)
    if args.seq_no is not None:
        metadata.setdefault("seq_no", str(args.seq_no))
    source = {"kind": args.source_kind}
    if args.trace_id:
        source["trace_id"] = args.trace_id
    store = build_store(args.storage_root)
    entry = store.append_belief(
        text=text,
        confidence=args.confidence,
        metadata=metadata or None,
        role=args.speaker,
        session_id=args.session_id,
        pair_id=pair_id,
        seq_no=args.seq_no,
        created_at=args.created_at,
        source=source,
    )
    speaker = args.speaker or metadata.get("speaker")
    speaker_prefix = f"[{speaker}] " if speaker else ""
    if entry.get("skipped"):
        hash_value = entry.get("hash")
        if hash_value:
            print(f"{speaker_prefix}belief skipped (duplicate hash {hash_value})")
        else:
            print(f"{speaker_prefix}belief skipped (duplicate/replay)")
    else:
        print(f"{speaker_prefix}belief stored: {entry['id']} ({entry['time']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
