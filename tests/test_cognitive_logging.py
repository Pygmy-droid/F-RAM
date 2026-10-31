from __future__ import annotations

from pathlib import Path

import pytest

from fram_serving.config import FRAMConfig
from fram_serving.memory import CognitiveMemoryStore, MemoryWriteError


def _build_store(tmp_path: Path, **overrides) -> CognitiveMemoryStore:
    cfg = FRAMConfig()
    if overrides:
        cfg = cfg.model_copy(update=overrides)
    root = tmp_path / "cognitive"
    return CognitiveMemoryStore(root, config=cfg)


def test_idempotent_upsert(tmp_path: Path) -> None:
    store = _build_store(tmp_path)
    created_at = "2025-01-01T00:00:00+00:00"

    entry1 = store.append_belief(
        text="Remember this turn",
        role="user",
        session_id="chat-1",
        pair_id="pair-1",
        seq_no=0,
        created_at=created_at,
    )
    entry2 = store.append_belief(
        text="Remember this turn",
        role="user",
        session_id="chat-1",
        pair_id="pair-1",
        seq_no=0,
        created_at=created_at,
    )

    assert entry1.get("skipped") is None
    assert entry2.get("skipped") is True

    meta = store._belief_meta()
    assert meta["total_count"] == 1
    assert meta["duplicates_skipped"] >= 1


def test_replay_guard(tmp_path: Path) -> None:
    store = _build_store(tmp_path)
    entry = store.append_belief(
        text="Replay copy",
        role="assistant",
        session_id="chat-1",
        pair_id="pair-2",
        source={"kind": "replay"},
    )
    assert entry.get("skipped") is True
    meta = store._belief_meta()
    assert meta["total_count"] == 0


def test_rollover_segments(tmp_path: Path) -> None:
    store = _build_store(
        tmp_path,
        cognitive_memory_max_segment_turns=2,
        cognitive_memory_retain_days=None,
    )

    for idx in range(3):
        store.append_belief(
            text=f"Turn {idx}",
            role="assistant",
            session_id="chat-2",
            pair_id=f"pair-{idx+10}",
            created_at=f"2025-01-01T00:00:0{idx}+00:00",
        )

    meta = store._belief_meta()
    assert len(meta["segments"]) >= 2
    assert meta["segments"][-1]["count"] == 1


def test_retain_days_preserves_full_experience(tmp_path: Path) -> None:
    store = _build_store(
        tmp_path,
        cognitive_memory_max_segment_turns=1,
        cognitive_memory_retain_segments=1,
        cognitive_memory_retain_days=1,
    )
    store.append_belief(
        text="Old turn",
        role="assistant",
        session_id="chat-4",
        pair_id="pair-old",
        created_at="2020-01-01T00:00:00+00:00",
    )
    store.append_belief(
        text="New turn",
        role="assistant",
        session_id="chat-4",
        pair_id="pair-new",
    )
    meta = store._belief_meta()
    segment_names = [entry["name"] for entry in meta["segments"]]
    segment_texts = []
    for name in segment_names:
        seg_path = store._belief_segment_path(name)
        if seg_path.exists():
            segment_texts.append(seg_path.read_text(encoding="utf-8"))
    combined = "\n".join(segment_texts)
    assert "New turn" in combined
    assert "Old turn" in combined


def test_seq_persists_across_restarts(tmp_path: Path) -> None:
    overrides = {"cognitive_memory_max_segment_turns": 10}
    store1 = _build_store(tmp_path, **overrides)
    first = store1.append_belief(
        text="First turn",
        role="assistant",
        session_id="chat-3",
        pair_id="pair-a",
        created_at="2025-01-01T00:00:00+00:00",
    )
    assert first["seq_no"] == 0

    # Recreate the store to simulate a restart.
    store2 = _build_store(tmp_path, **overrides)
    second = store2.append_belief(
        text="Second turn",
        role="assistant",
        session_id="chat-3",
        pair_id="pair-b",
        created_at="2025-01-01T00:00:01+00:00",
    )
    assert second["seq_no"] == 1


def test_episode_write_failure_logs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = FRAMConfig().model_copy(update={"STORAGE_ROOT": tmp_path})
    store = CognitiveMemoryStore(tmp_path / "cognitive", config=cfg)

    def _fail(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(store, "_append_jsonl_safe", _fail)

    with pytest.raises(MemoryWriteError):
        store.append_episode(query="hello")

    log_path = tmp_path / "observability" / "memory_cognitive.jsonl"
    assert log_path.exists()
    log_text = log_path.read_text(encoding="utf-8")
    assert "episode_write_failed" in log_text
