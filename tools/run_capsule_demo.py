"""Run a clean memory-capsule capture + falsify loop against a local server."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence
from urllib import request


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fram_serving.config import FRAMConfig


DEFAULT_ENTRIES = [
    ("user", "Let's map the trail lightly and playful for a moment."),
    ("assistant", "Playful sketch: gentle arcs and light metaphors to start."),
    ("user", "Wait, that's not right; we need the full trail, not just metaphors."),
    ("assistant", "Understood. Full trail, explicit steps, no hand-waving."),
    ("user", "We said no pruning earlier, but I suggested trimming. That's a contradiction."),
    ("assistant", "Contradiction resolved: we keep the full record and avoid pruning."),
    ("user", "From now on we preserve full transcripts without compression."),
    ("assistant", "Commitment recorded: full transcripts, no compression."),
    ("user", "Anchor: ember leaf over glass lake."),
    ("assistant", "Anchor acknowledged: ember leaf over glass lake."),
    ("user", "Tone shift: I'm anxious; let's be calm and precise."),
    ("assistant", "Switching to calm, precise mode."),
    ("user", "Decision: run falsification before enabling influence."),
    ("assistant", "Decision confirmed: falsify first, then consider influence."),
    ("user", "If we drift, return to the anchor phrase."),
    ("assistant", "Return-to-anchor rule accepted."),
]


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a memory capsule demo loop.")
    parser.add_argument("--host", default="127.0.0.1", help="Server host (default 127.0.0.1).")
    parser.add_argument("--port", type=int, default=8000, help="Server port (default 8000).")
    parser.add_argument(
        "--use-existing-server",
        action="store_true",
        help="Skip starting uvicorn; assume the server is already running.",
    )
    parser.add_argument(
        "--keep-server",
        action="store_true",
        help="Leave uvicorn running if this script starts it.",
    )
    parser.add_argument(
        "--health-timeout",
        type=int,
        default=30,
        help="Seconds to wait for /health before failing.",
    )
    parser.add_argument(
        "--query-timeout",
        type=int,
        default=300,
        help="Seconds to wait for /query response.",
    )
    parser.add_argument(
        "--budget-reads",
        type=int,
        default=1,
        help="Budget reads for the demo /query request.",
    )
    parser.add_argument(
        "--tag",
        default="demo",
        help="Tag for the falsify output filename.",
    )
    return parser.parse_args(argv)


def _base_url(host: str, port: int) -> str:
    return f"http://{host}:{port}"


def _wait_for_health(base_url: str, timeout_s: int) -> None:
    deadline = time.time() + timeout_s
    health_url = f"{base_url}/health"
    while time.time() < deadline:
        try:
            with request.urlopen(health_url, timeout=2) as resp:
                if resp.status == 200:
                    return
        except Exception:
            time.sleep(0.5)
    raise RuntimeError(f"/health did not respond within {timeout_s}s.")


def _post_json(url: str, payload: dict[str, Any], *, timeout_s: int = 30) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with request.urlopen(req, timeout=timeout_s) as resp:
        body = resp.read().decode("utf-8")
    return json.loads(body) if body else {}


def _start_server(host: str, port: int) -> subprocess.Popen:
    env = os.environ.copy()
    env["FRAM_MEMORY_CAPSULE_ENABLED"] = "1"
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "fram_serving.app:app", "--host", host, "--port", str(port)],
        env=env,
    )


def _stop_server(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def _latest_capsule(storage_root: Path) -> Path:
    capsules_dir = storage_root / "memory" / "capsules"
    if not capsules_dir.exists():
        raise RuntimeError(f"Capsules directory not found: {capsules_dir}")
    capsules = sorted(capsules_dir.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not capsules:
        raise RuntimeError("No capsule JSON files found.")
    return capsules[0]


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    base_url = _base_url(args.host, args.port)
    server_proc: subprocess.Popen | None = None
    started_here = False

    try:
        if not args.use_existing_server:
            server_proc = _start_server(args.host, args.port)
            started_here = True
        _wait_for_health(base_url, args.health_timeout)

        session_resp = _post_json(f"{base_url}/memory", {})
        session_id = (session_resp.get("session") or {}).get("id")
        if not session_id:
            raise RuntimeError("No session id returned by /memory.")

        for role, text in DEFAULT_ENTRIES:
            _post_json(
                f"{base_url}/memory/{session_id}",
                {"text": text, "metadata": {"role": role}},
            )

        _post_json(
            f"{base_url}/query",
            {
                "text": "Summarize the correction, contradiction resolution, commitment, and anchor.",
                "memory_session": session_id,
                "budget_reads": args.budget_reads,
            },
            timeout_s=args.query_timeout,
        )

        cfg = FRAMConfig.from_env()
        storage_root = Path(cfg.STORAGE_ROOT)
        capsule_path = _latest_capsule(storage_root)
        print(f"capsule_path: {capsule_path}")

        subprocess.check_call([sys.executable, "tools/inspect_capsule.py", str(capsule_path)])

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        report_path = Path("artifacts/observability") / f"capsule_falsify_{args.tag}_{timestamp}.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_json = subprocess.check_output(
            [sys.executable, "tools/falsify_capsule.py", str(capsule_path), "--json"]
        )
        report_path.write_bytes(report_json)
        print(f"falsify_path: {report_path}")
        return 0
    finally:
        if started_here and server_proc and not args.keep_server:
            _stop_server(server_proc)


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
