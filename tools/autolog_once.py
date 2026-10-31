from __future__ import annotations

import os
import sys
from pathlib import Path

# Allow importing the helper even if 'tools' isn't a package
THIS_FILE = Path(__file__).resolve()
TOOLS_DIR = THIS_FILE.parent
REPO_ROOT = THIS_FILE.parents[1]
for p in (str(TOOLS_DIR), str(REPO_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from autolog_env import autolog_turn  # type: ignore


def main() -> int:
    user = os.environ.get("COGMEM_USER_TMP", "")
    assistant = os.environ.get("COGMEM_ASSISTANT_TMP", "")
    session = os.environ.get("COGMEM_SESSION_ID", "default")
    topic = os.environ.get("COGMEM_TOPIC", None)
    # Force-enable for this process; upstream caller can control env persistently.
    os.environ["COGMEM_AUTOLOG"] = os.environ.get("COGMEM_AUTOLOG", "1") or "1"
    autolog_turn(user or None, assistant or None, session_id=session, topic=topic)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
