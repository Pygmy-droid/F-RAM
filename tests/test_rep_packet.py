from __future__ import annotations

from pathlib import Path

from fram_serving.archive import ArchiveWriter, load_chunk
from fram_serving.rep import (
    REP_MAX_ANCHORS,
    REP_MAX_BYTES,
    load_rep,
    update_rep,
)


def _write_event(writer: ArchiveWriter, event_id: str, trace_id: str, ts_ms: int) -> None:
    writer.append_event(
        kind="query",
        request={"text": f"seed-{event_id}"},
        response={"answer": "ok"},
        trace_id=trace_id,
        meta={"query_id": event_id},
        event_id=event_id,
        ts_ms=ts_ms,
    )


def test_rep_deterministic_update(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    archive_root = storage_root / "archive"
    writer = ArchiveWriter(archive_root)
    _write_event(writer, "event-a", "trace-a", 1000)
    _write_event(writer, "event-b", "trace-b", 2000)

    first = update_rep(storage_root=storage_root).payload
    second = update_rep(storage_root=storage_root).payload
    assert first == second

    rep_path = storage_root / "rep" / "rep.json"
    assert rep_path.exists()


def test_rep_pointers_resolve(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    archive_root = storage_root / "archive"
    writer = ArchiveWriter(archive_root)
    _write_event(writer, "event-1", "trace-1", 1000)

    rep_payload = update_rep(storage_root=storage_root).payload
    recent_ids = rep_payload["archive_pointers"]["recent_event_ids"]
    milestone_ids = rep_payload["archive_pointers"]["milestones"].values()

    for event_id in list(recent_ids) + list(milestone_ids):
        assert load_chunk(archive_root, event_id) is not None

    assert len(rep_payload["anchors"]) <= REP_MAX_ANCHORS


def test_rep_size_guard(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    archive_root = storage_root / "archive"
    writer = ArchiveWriter(archive_root)
    _write_event(writer, "event-1", "trace-1", 1000)

    update_rep(storage_root=storage_root)
    rep_path = storage_root / "rep" / "rep.json"
    assert rep_path.exists()
    assert rep_path.stat().st_size <= REP_MAX_BYTES


def test_rep_trace_link_latest(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    archive_root = storage_root / "archive"
    writer = ArchiveWriter(archive_root)
    _write_event(writer, "event-a", "trace-a", 1000)
    _write_event(writer, "event-b", "trace-b", 2000)

    rep_payload = update_rep(storage_root=storage_root).payload
    trace_link = rep_payload["trace_link"]
    assert trace_link["trace_id"] == "trace-b"
    assert trace_link["event_id"] == "event-b"

    loaded = load_rep(storage_root)
    assert loaded is not None
