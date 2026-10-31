from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fram_serving.config import FRAMConfig
from fram_serving.memory import CognitiveMemoryStore
from tools.cognitive_memory_summary import _iter_events as _iter_cog_events
from tools.cognitive_memory_summary import summarise as summarise_cog
from tools.experiment_summary import collect_experiments, summarise as summarise_experiments


def _git_head() -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    return result.stdout.strip() if result.stdout else None


def _default_out_path() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return Path("artifacts") / "observability" / f"weekly_regression_{stamp}.json"


def build_snapshot(
    *,
    limit: int = 20,
    session_id: Optional[str] = None,
    tag: Optional[str] = None,
    memory_path: Optional[Path] = None,
    include_digest: bool = False,
    digest_limit: int = 10,
) -> Dict[str, Any]:
    cfg = FRAMConfig.from_env()
    override_root = os.getenv("COGMEM_STORAGE_ROOT")
    if override_root:
        cfg = cfg.model_copy(update={"STORAGE_ROOT": Path(override_root).expanduser().resolve()})

    root = cfg.STORAGE_ROOT / cfg.STORAGE_SUBFOLDERS.get("memory", "memory") / "cognitive"
    store = CognitiveMemoryStore(root, config=cfg)
    experiments = collect_experiments(store, session_id=session_id, tag=tag)
    experiments_summary = summarise_experiments(experiments)

    obs_path = memory_path or (
        cfg.STORAGE_ROOT / cfg.STORAGE_SUBFOLDERS.get("observability", "observability") / "memory_cognitive.jsonl"
    )
    cog_events = _iter_cog_events(obs_path, limit=0)
    cog_summary = summarise_cog(cog_events)

    snapshot = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "commit": _git_head(),
        "experiments": experiments_summary | {"limit": limit},
        "cognitive_memory": cog_summary,
    }
    if include_digest:
        digest_items = (experiments_summary.get("experiments") or [])[: max(1, digest_limit)]
        digest_lines = [
            f"{item.get('time') or ''} | {item.get('title') or 'untitled'} | decision: {item.get('decision') or 'n/a'}"
            for item in digest_items
        ]
        snapshot["experiment_digest"] = digest_lines
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Write a weekly regression snapshot JSON.")
    parser.add_argument("--out", type=Path, default=None, help="Output path for JSON.")
    parser.add_argument("--limit", type=int, default=20, help="Max experiments to include.")
    parser.add_argument("--session-id", default=None, help="Filter experiments by session id.")
    parser.add_argument("--tag", default=None, help="Filter experiments by tag.")
    parser.add_argument("--memory-path", type=Path, default=None, help="Override memory_cognitive.jsonl path.")
    parser.add_argument("--digest", action="store_true", help="Include a short experiment digest.")
    parser.add_argument("--digest-limit", type=int, default=10, help="Digest entries to include.")
    args = parser.parse_args()

    snapshot = build_snapshot(
        limit=max(1, int(args.limit)),
        session_id=args.session_id,
        tag=args.tag,
        memory_path=args.memory_path,
        include_digest=bool(args.digest),
        digest_limit=max(1, int(args.digest_limit)),
    )
    out_path = args.out or _default_out_path()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
