from __future__ import annotations

import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tools.snapshot_firelink import snapshot_firelink


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.name", "Snapshot Test")
    _git(repo, "config", "user.email", "snapshot@example.invalid")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "base")
    return repo, _git(repo, "rev-parse", "HEAD")


def test_snapshot_is_byte_exact_and_manifested(tmp_path: Path) -> None:
    repo, head = _repo(tmp_path)
    source = tmp_path / "firelink.md"
    payload = (
        "# Firelink\n\n"
        "### 2026-07-27 18:00 SAST - first\n\n"
        "body\n"
        "### 2026-07-27 18:30 SAST - final\n"
    ).encode()
    source.write_bytes(payload)
    captured = datetime(2026, 7, 27, 16, 30, tzinfo=timezone.utc)

    target, manifest = snapshot_firelink(source, repo, captured_at=captured)

    assert target == repo / "artifacts" / "firelink" / f"2026-07-27/1630-{head[:8]}"
    assert (target / "firelink.md").read_bytes() == payload
    assert manifest["sha256"] == hashlib.sha256(payload).hexdigest()
    assert manifest["bytes"] == len(payload)
    assert manifest["line_count"] == 6
    assert manifest["canonical_head"] == head
    assert manifest["last_event"] == "2026-07-27 18:30 SAST - final"


def test_snapshot_refuses_to_overwrite_checkpoint(tmp_path: Path) -> None:
    repo, _ = _repo(tmp_path)
    source = tmp_path / "firelink.md"
    source.write_text("### event\n", encoding="utf-8")
    captured = datetime(2026, 7, 27, 16, 30, tzinfo=timezone.utc)
    snapshot_firelink(source, repo, captured_at=captured)

    with pytest.raises(FileExistsError):
        snapshot_firelink(source, repo, captured_at=captured)
