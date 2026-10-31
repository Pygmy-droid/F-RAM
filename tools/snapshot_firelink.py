"""Create an immutable, byte-exact Firelink snapshot and manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Sequence


def _git_head(repo: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _last_event(text: str) -> str | None:
    for line in reversed(text.splitlines()):
        if line.startswith("### "):
            return line[4:].strip()
    return None


def snapshot_firelink(
    source: Path,
    repo: Path,
    *,
    captured_at: datetime | None = None,
) -> tuple[Path, dict[str, object]]:
    """Snapshot Firelink once; refuse to overwrite an existing checkpoint."""

    source = source.resolve()
    repo = repo.resolve()
    payload = source.read_bytes()
    text = payload.decode("utf-8")
    head = _git_head(repo)
    captured_at = captured_at or datetime.now().astimezone()
    stamp = captured_at.strftime("%Y-%m-%d/%H%M")
    target_dir = repo / "artifacts" / "firelink" / f"{stamp}-{head[:8]}"
    snapshot_path = target_dir / "firelink.md"
    manifest_path = target_dir / "manifest.json"

    if target_dir.exists():
        raise FileExistsError(f"snapshot checkpoint already exists: {target_dir}")

    target_dir.mkdir(parents=True)
    snapshot_path.write_bytes(payload)

    manifest: dict[str, object] = {
        "source_path": str(source),
        "snapshot_path": snapshot_path.relative_to(repo).as_posix(),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
        "line_count": len(text.splitlines()),
        "canonical_head": head,
        "captured_at": captured_at.isoformat(),
        "last_event": _last_event(text),
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target_dir, manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Snapshot append-only Firelink into artifacts/firelink."
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)

    target, manifest = snapshot_firelink(args.source, args.repo)
    print(
        f"[firelink] snapshotted {manifest['bytes']} bytes "
        f"({manifest['line_count']} lines) to {target}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
