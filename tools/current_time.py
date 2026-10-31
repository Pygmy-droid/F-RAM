from __future__ import annotations

"""
Simple helper to report the current time.

This prints both local and UTC timestamps so F-RAM components (and the
assistant running inside the repo) can reason about "today" versus
"yesterday" without guessing.
"""

from datetime import datetime, timezone


def main() -> int:
    now_utc = datetime.now(timezone.utc)
    now_local = datetime.now()

    print("Current time (local):", now_local.isoformat())
    print("Current time (UTC):  ", now_utc.isoformat())
    print("Epoch seconds:", int(now_utc.timestamp()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
