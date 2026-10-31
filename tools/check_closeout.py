from __future__ import annotations

import argparse
import os
import subprocess
import sys
from typing import Iterable, Optional, Set, Tuple

TARGET_FILES = ["docs/CODEX_DIARY.md", "docs/F-RAM-roadmap.md"]


def _git_changed(paths: Iterable[str]) -> Optional[Set[str]]:
    """Return the set of paths with pending changes (None when git is unavailable)."""
    try:
        cmd = ["git", "status", "--porcelain", "--"] + list(paths)
        output = subprocess.check_output(cmd, text=True)
    except Exception:
        return None
    changed: Set[str] = set()
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            continue
        path = parts[1].strip().strip('"').replace("\\", "/")
        changed.add(path)
    return changed


def _check_closeout(changed: Optional[Set[str]], autolog_enabled: bool) -> Tuple[bool, str]:
    """Evaluate guardrail conditions; returns (ok, message)."""
    if not autolog_enabled:
        return False, "COGMEM_AUTOLOG must be set to 1 so chat turns are logged."
    if changed is None:
        return False, "Unable to inspect git status; run inside the repo and ensure git is available."

    missing = [path for path in TARGET_FILES if path not in changed]
    if missing:
        missing_str = ", ".join(missing)
        return False, f"Update required before close-out: {missing_str}."
    return True, "Close-out guard passed: diary/roadmap updated and autologging enabled."


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Guardrail: fail if the diary/roadmap were not updated or autologging is off."
    )
    args = parser.parse_args()

    autolog_enabled = os.getenv("COGMEM_AUTOLOG") == "1"
    changed = _git_changed(TARGET_FILES)
    ok, message = _check_closeout(changed, autolog_enabled)
    stream = sys.stdout if ok else sys.stderr
    print(message, file=stream)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
