from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from fram_serving.archive import ArchiveWriter, iter_manifest

REP_VERSION = "rep-1"
REP_FILENAME = "rep.json"
REP_MAX_ANCHORS = 7
REP_MAX_RECENT_EVENTS = 5
REP_MAX_BYTES = 8192


DEFAULT_IDENTITY = {
    "who": "FRAM re-entry packet for this repo",
    "stance": "small, pointer-only identity capsule",
    "not": "not a transcript; not a retrieval policy",
}

DEFAULT_DO_NOT_TOUCH = [
    "fractal_core_semantics_v2",
    "archive_append_only_hash_chain",
]

MILESTONE_DEFS = [
    {
        "name": "core_proof_packet",
        "label": "Core proof packet",
        "doc_path": "docs/proof/fractal_core_proof.md",
    },
    {
        "name": "core_semantics",
        "label": "Core semantics contract",
        "doc_path": "docs/fractal_core.md",
    },
    {
        "name": "archive_layer",
        "label": "Archive layer done",
        "doc_path": "docs/done_step_3_archive_layer.md",
    },
]


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _milestone_event_id(name: str, doc_path: str) -> str:
    raw = f"rep-milestone:{name}:{doc_path}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _rep_root(storage_root: Path) -> Path:
    return Path(storage_root) / "rep"


def _rep_path(storage_root: Path) -> Path:
    return _rep_root(storage_root) / REP_FILENAME


def _filter_live_entries(entries: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [entry for entry in entries if str(entry.get("kind")) != "rep_milestone"]


@dataclass(slots=True)
class RepBuildResult:
    payload: Dict[str, Any]
    path: Path


def load_rep(storage_root: Path) -> Dict[str, Any] | None:
    path = _rep_path(storage_root)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def update_rep(
    *,
    storage_root: Path,
    identity: Optional[Dict[str, Any]] = None,
    do_not_touch: Optional[List[str]] = None,
    recent_limit: int = REP_MAX_RECENT_EVENTS,
) -> RepBuildResult:
    storage_root = Path(storage_root)
    archive_root = storage_root / "archive"
    rep_root = _rep_root(storage_root)
    rep_root.mkdir(parents=True, exist_ok=True)

    entries = list(iter_manifest(archive_root))
    writer = ArchiveWriter(archive_root)

    milestone_event_ids: Dict[str, str] = {}
    for milestone in MILESTONE_DEFS:
        event_id = _milestone_event_id(milestone["name"], milestone["doc_path"])
        writer.ensure_event(
            kind="rep_milestone",
            request={"milestone": milestone["name"], "doc_path": milestone["doc_path"]},
            response={"label": milestone["label"]},
            trace_id=None,
            meta={"milestone": milestone["name"], "doc_path": milestone["doc_path"]},
            event_id=event_id,
            ts_ms=0,
        )
        milestone_event_ids[milestone["name"]] = event_id

    entries = list(iter_manifest(archive_root))
    live_entries = _filter_live_entries(entries)
    recent_limit = max(0, int(recent_limit))
    if recent_limit <= 0:
        recent_event_ids: List[str] = []
    else:
        recent_event_ids = [str(entry.get("event_id")) for entry in live_entries[-recent_limit:] if entry.get("event_id")]

    latest_event = live_entries[-1] if live_entries else None
    latest_trace_id = latest_event.get("trace_id") if latest_event else None
    latest_event_id = latest_event.get("event_id") if latest_event else None
    ts_ms = latest_event.get("ts_ms") if latest_event else _now_ms()

    anchors: List[Dict[str, Any]] = []
    for milestone in MILESTONE_DEFS:
        anchors.append(
            {
                "id": milestone["name"],
                "label": milestone["label"],
                "event_id": milestone_event_ids[milestone["name"]],
            }
        )
    anchors = anchors[:REP_MAX_ANCHORS]

    payload: Dict[str, Any] = {
        "version": REP_VERSION,
        "timestamp_ms": int(ts_ms),
        "identity": dict(identity or DEFAULT_IDENTITY),
        "do_not_touch": list(do_not_touch or DEFAULT_DO_NOT_TOUCH),
        "anchors": anchors,
        "archive_pointers": {
            "recent_event_ids": recent_event_ids,
            "milestones": dict(milestone_event_ids),
        },
        "trace_link": {
            "trace_id": latest_trace_id,
            "event_id": latest_event_id,
            "rule": "latest_non_milestone_event",
        },
    }

    payload_text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    while len(payload_text.encode("utf-8")) > REP_MAX_BYTES and recent_event_ids:
        recent_event_ids = recent_event_ids[1:]
        payload["archive_pointers"]["recent_event_ids"] = recent_event_ids
        payload_text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    if len(payload_text.encode("utf-8")) > REP_MAX_BYTES:
        raise ValueError("REP payload exceeds size limit")

    rep_path = _rep_path(storage_root)
    rep_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return RepBuildResult(payload=payload, path=rep_path)
