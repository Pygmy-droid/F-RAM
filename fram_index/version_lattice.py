"""Minimal version lattice utilities (spec A13) with manifest persistence."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set, Tuple


@dataclass(frozen=True)
class VersionNode:
    node_id: str
    timestamp: datetime
    parents: Tuple[str, ...] = ()
    diff: Dict[str, Any] | None = None

    @property
    def parent_id(self) -> str | None:
        return self.parents[0] if self.parents else None

    def to_record(self) -> Dict[str, Any]:
        """Serialize to a manifest record."""

        return {
            "version_id": self.node_id,
            "parent_id": self.parent_id,
            "timestamp": self.timestamp.isoformat(),
            "diff": self.diff,
        }


class VersionLattice:
    def __init__(self) -> None:
        self._nodes: Dict[str, VersionNode] = {}

    def add_node(self, node: VersionNode) -> None:
        self._nodes[node.node_id] = node

    @staticmethod
    def _base_id(node_id: str) -> str:
        if "::" in node_id:
            return node_id.split("::", 1)[0]
        if "@" in node_id:
            return node_id.split("@", 1)[0]
        return node_id

    def base_id(self, node_id: str) -> str:
        return self._base_id(node_id)

    def active_version_map(self, as_of: datetime) -> Dict[str, str]:
        """Select the newest eligible node for each logical document."""

        as_of_utc = as_of.astimezone(timezone.utc) if as_of.tzinfo else as_of.replace(tzinfo=timezone.utc)
        selected: Dict[str, VersionNode] = {}
        for node_id, node in self._nodes.items():
            if node.timestamp > as_of_utc:
                continue
            base_id = self._base_id(node_id)
            current = selected.get(base_id)
            if current is None or node.timestamp > current.timestamp:
                selected[base_id] = node
        return {base_id: node.node_id for base_id, node in selected.items()}

    def select_ids(self, as_of: datetime | None = None, version_id: str | None = None) -> Set[str]:
        """Select an explicit version or the newest eligible version per document."""

        if version_id is not None:
            return {version_id} if version_id in self._nodes else set()
        if as_of is None:
            return set(self._nodes)
        return set(self.active_version_map(as_of).values())

    def ancestors(self, node_id: str) -> Set[str]:
        """Return all ancestor ids reachable via parent links."""

        visited: Set[str] = set()
        stack: List[str] = [node_id]
        while stack:
            current = stack.pop()
            node = self._nodes.get(current)
            if node is None:
                continue
            for parent in node.parents:
                if parent not in visited:
                    visited.add(parent)
                    stack.append(parent)
        return visited

    def active_ids(self, as_of: datetime) -> Set[str]:
        as_of_utc = as_of.astimezone(timezone.utc) if as_of.tzinfo else as_of.replace(tzinfo=timezone.utc)
        return {
            node_id
            for node_id, node in self._nodes.items()
            if node.timestamp <= as_of_utc
        }

    def active_with_ancestors(self, as_of: datetime) -> Set[str]:
        """Return active ids plus their ancestors (for as-of filtering)."""

        active = self.active_ids(as_of)
        resolved: Set[str] = set(active)
        for node_id in active:
            resolved |= self.ancestors(node_id)
        return resolved

    def latest_timestamp(self) -> datetime | None:
        if not self._nodes:
            return None
        return max(node.timestamp for node in self._nodes.values())

    def __len__(self) -> int:
        return len(self._nodes)

    @classmethod
    def from_manifest(cls, path: Path) -> "VersionLattice":
        lattice = cls()
        for record in iter_manifest(path):
            timestamp_raw = record.get("timestamp")
            try:
                ts = datetime.fromisoformat(str(timestamp_raw))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
            except Exception:
                continue
            parent_id = record.get("parent_id")
            parents: Tuple[str, ...] = (str(parent_id),) if parent_id else tuple(record.get("parents", ()))
            node = VersionNode(
                node_id=str(record.get("version_id") or record.get("node_id")),
                timestamp=ts,
                parents=parents,
                diff=record.get("diff"),
            )
            lattice.add_node(node)
        return lattice


def _atomic_append_line(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as dest:
        if path.exists():
            with open(path, "r", encoding="utf-8") as src:
                dest.writelines(src.readlines())
        dest.write(line)
        dest.write(os.linesep)
    os.replace(tmp_path, path)


def append_version_record(path: Path, node: VersionNode) -> None:
    """Append a single version record to ``versions.jsonl`` (append-safe)."""

    record = node.to_record()
    _atomic_append_line(path, json.dumps(record, ensure_ascii=False))


def write_version_manifest(path: Path, lattice: VersionLattice) -> None:
    """Rewrite the manifest with the provided lattice nodes."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        for node in sorted(lattice._nodes.values(), key=lambda n: n.timestamp):
            handle.write(json.dumps(node.to_record(), ensure_ascii=False))
            handle.write("\n")


def iter_manifest(path: Path) -> Iterable[Dict[str, Any]]:
    """Yield manifest records from a JSONL file."""

    if not path.exists():
        return []
    records: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records
