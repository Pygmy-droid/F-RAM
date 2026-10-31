from __future__ import annotations

import os
import sys

import httpx


def main() -> int:
    url = os.environ.get("FRAM_URL", "http://127.0.0.1:8000")
    text = os.environ.get("FRAM_TEXT", "What is FRAM?")
    session = os.environ.get("FRAM_SESSION", os.environ.get("COGMEM_SESSION_ID", "dev"))
    payload = {"text": text, "memory_session": session}
    with httpx.Client(timeout=30) as client:
        r = client.post(f"{url}/query", json=payload)
        print(r.status_code)
        # Robust Windows console printing
        out = (r.text or "").encode("utf-8", errors="ignore")
        sys.stdout.buffer.write(out)
        sys.stdout.buffer.write(b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
