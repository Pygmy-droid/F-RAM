from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fram_serving.config import FRAMConfig
from fram_serving.memory import CognitiveMemoryStore

import tools.closeout_guard as guard
from tools import check_closeout


def _write_doc(path: Path, stamp: datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("ok", encoding="utf-8")
    os.utime(path, (stamp.timestamp(), stamp.timestamp()))


def _make_store(tmp_path: Path) -> tuple[CognitiveMemoryStore, FRAMConfig]:
    cfg = FRAMConfig().model_copy(update={"STORAGE_ROOT": tmp_path / "storage"})
    root = cfg.STORAGE_ROOT / cfg.STORAGE_SUBFOLDERS.get("memory", "memory") / "cognitive"
    return CognitiveMemoryStore(root, config=cfg), cfg


def test_closeout_guard_pass(tmp_path: Path) -> None:
    store, cfg = _make_store(tmp_path)
    session_id = "closeout-pass"
    now = datetime.now(timezone.utc)
    store.append_belief(text="done", role="assistant", session_id=session_id, created_at=now.isoformat())

    diary = tmp_path / "docs" / "CODEX_DIARY.md"
    roadmap = tmp_path / "docs" / "F-RAM-roadmap.md"
    _write_doc(diary, now + timedelta(seconds=5))
    _write_doc(roadmap, now + timedelta(seconds=5))

    rc = guard.main(
        [
            "--session-id",
            session_id,
            "--storage-root",
            str(cfg.STORAGE_ROOT),
            "--diary",
            str(diary),
            "--roadmap",
            str(roadmap),
            "--grace-sec",
            "0",
        ]
    )
    assert rc == 0


def test_closeout_guard_fails_on_user_last(tmp_path: Path) -> None:
    store, cfg = _make_store(tmp_path)
    session_id = "closeout-fail"
    now = datetime.now(timezone.utc)
    store.append_belief(text="user only", role="user", session_id=session_id, created_at=now.isoformat())

    diary = tmp_path / "docs" / "CODEX_DIARY.md"
    roadmap = tmp_path / "docs" / "F-RAM-roadmap.md"
    _write_doc(diary, now + timedelta(seconds=5))
    _write_doc(roadmap, now + timedelta(seconds=5))

    rc = guard.main(
        [
            "--session-id",
            session_id,
            "--storage-root",
            str(cfg.STORAGE_ROOT),
            "--diary",
            str(diary),
            "--roadmap",
            str(roadmap),
            "--grace-sec",
            "0",
        ]
    )
    assert rc != 0


def test_check_closeout_passes_when_all_requirements_are_set() -> None:
    changed = {"docs/CODEX_DIARY.md", "docs/F-RAM-roadmap.md"}
    ok, message = check_closeout._check_closeout(changed, autolog_enabled=True)
    assert ok is True
    assert "Close-out guard passed" in message


def test_check_closeout_requires_autolog() -> None:
    ok, message = check_closeout._check_closeout(
        {"docs/CODEX_DIARY.md"},
        autolog_enabled=False,
    )
    assert ok is False
    assert "COGMEM_AUTOLOG" in message


def test_check_closeout_requires_both_docs() -> None:
    ok, message = check_closeout._check_closeout(set(), autolog_enabled=True)
    assert ok is False
    assert "F-RAM-roadmap.md" in message
