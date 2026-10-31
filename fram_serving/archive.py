from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

MANIFEST_FILENAME = "manifest.jsonl"
CHUNKS_DIRNAME = "chunks"


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def serialize_payload(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def compute_content_hash(payload: Dict[str, Any]) -> str:
    return _hash_text(serialize_payload(payload))


def compute_chain_hash(prev_chain_hash: Optional[str], content_hash: str) -> str:
    return _hash_text(f"{prev_chain_hash or ''}{content_hash}")


def iter_manifest(root: Path) -> Iterable[Dict[str, Any]]:
    path = Path(root) / MANIFEST_FILENAME
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def tail_manifest(root: Path, limit: int = 10) -> list[Dict[str, Any]]:
    entries = list(iter_manifest(root))
    if limit <= 0:
        return []
    if len(entries) > limit:
        return entries[-limit:]
    return entries


def load_chunk(root: Path, event_id: str) -> Dict[str, Any] | None:
    path = Path(root) / CHUNKS_DIRNAME / f"{event_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def find_manifest_entry(root: Path, event_id: str) -> Optional[Dict[str, Any]]:
    for entry in iter_manifest(root):
        if str(entry.get("event_id")) == str(event_id):
            return entry
    return None


def verify_chain(entries: Iterable[Dict[str, Any]]) -> bool:
    prev_chain: Optional[str] = None
    for entry in entries:
        content_hash = entry.get("content_hash")
        chain_hash = entry.get("chain_hash")
        prev_hash = entry.get("prev_chain_hash")
        if prev_hash != prev_chain:
            return False
        if not content_hash or not chain_hash:
            return False
        expected = compute_chain_hash(prev_chain, str(content_hash))
        if expected != chain_hash:
            return False
        prev_chain = chain_hash
    return True


@dataclass(slots=True)
class ArchiveWriter:
    root: Path
    chunks_dir: Path = field(init=False)
    manifest_path: Path = field(init=False)

    def __post_init__(self) -> None:
        root = Path(self.root)
        root.mkdir(parents=True, exist_ok=True)
        self.root = root
        self.chunks_dir = root / CHUNKS_DIRNAME
        self.manifest_path = root / MANIFEST_FILENAME
        self.chunks_dir.mkdir(parents=True, exist_ok=True)

    def _read_last_entry(self) -> Optional[Dict[str, Any]]:
        last: Optional[Dict[str, Any]] = None
        for entry in iter_manifest(self.root):
            last = entry
        return last

    def find_manifest_entry(self, event_id: str) -> Optional[Dict[str, Any]]:
        return find_manifest_entry(self.root, event_id)

    def _append_manifest(self, entry: Dict[str, Any]) -> None:
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with self.manifest_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")

    def append_event(
        self,
        *,
        kind: str,
        request: Dict[str, Any],
        response: Dict[str, Any],
        trace_id: Optional[str],
        meta: Optional[Dict[str, Any]] = None,
        event_id: Optional[str] = None,
        ts_ms: Optional[int] = None,
    ) -> Dict[str, Any]:
        event_id = event_id or uuid.uuid4().hex
        ts_value = int(ts_ms) if ts_ms is not None else _now_ms()
        payload = {
            "event_id": event_id,
            "ts_ms": ts_value,
            "kind": str(kind),
            "trace_id": trace_id,
            "request": dict(request),
            "response": dict(response),
            "meta": dict(meta or {}),
        }
        payload_text = serialize_payload(payload)
        content_hash = _hash_text(payload_text)
        last_entry = self._read_last_entry()
        prev_chain = None
        if isinstance(last_entry, dict):
            prev_chain = last_entry.get("chain_hash")
        chain_hash = compute_chain_hash(prev_chain, content_hash)
        chunk_path = self.chunks_dir / f"{event_id}.json"
        if chunk_path.exists():
            raise FileExistsError(f"archive chunk already exists: {chunk_path}")
        self.chunks_dir.mkdir(parents=True, exist_ok=True)
        with chunk_path.open("x", encoding="utf-8") as handle:
            handle.write(payload_text)
        manifest_entry = {
            "event_id": event_id,
            "ts_ms": ts_value,
            "kind": str(kind),
            "trace_id": trace_id,
            "content_hash": content_hash,
            "chain_hash": chain_hash,
            "prev_chain_hash": prev_chain,
            "chunk_path": f"{CHUNKS_DIRNAME}/{event_id}.json",
        }
        self._append_manifest(manifest_entry)
        return manifest_entry

    def ensure_event(
        self,
        *,
        kind: str,
        request: Dict[str, Any],
        response: Dict[str, Any],
        trace_id: Optional[str],
        meta: Optional[Dict[str, Any]] = None,
        event_id: str,
        ts_ms: Optional[int] = None,
    ) -> Dict[str, Any]:
        existing = self.find_manifest_entry(event_id)
        if existing is not None:
            return existing
        try:
            return self.append_event(
                kind=kind,
                request=request,
                response=response,
                trace_id=trace_id,
                meta=meta,
                event_id=event_id,
                ts_ms=ts_ms,
            )
        except FileExistsError:
            chunk = load_chunk(self.root, event_id)
            if chunk is None:
                raise
            content_hash = compute_content_hash(chunk)
            last_entry = self._read_last_entry()
            prev_chain = None
            if isinstance(last_entry, dict):
                prev_chain = last_entry.get("chain_hash")
            chain_hash = compute_chain_hash(prev_chain, content_hash)
            ts_value = chunk.get("ts_ms")
            if ts_value is None:
                ts_value = _now_ms()
            manifest_entry = {
                "event_id": event_id,
                "ts_ms": int(ts_value),
                "kind": str(kind),
                "trace_id": trace_id,
                "content_hash": content_hash,
                "chain_hash": chain_hash,
                "prev_chain_hash": prev_chain,
                "chunk_path": f"{CHUNKS_DIRNAME}/{event_id}.json",
            }
            self._append_manifest(manifest_entry)
            return manifest_entry
