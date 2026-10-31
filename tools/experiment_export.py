from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fram_serving.config import FRAMConfig
from fram_serving.memory import CognitiveMemoryStore
from tools.experiment_summary import collect_experiments


def _load_full_records(
    store: CognitiveMemoryStore,
    *,
    session_id: Optional[str] = None,
    tag: Optional[str] = None,
) -> List[Dict[str, Any]]:
    tag_value = tag.lower() if tag else None
    records: List[Dict[str, Any]] = []
    for record in store._iter_belief_records():
        if session_id and str(record.get("session_id") or "") != session_id:
            continue
        meta = record.get("metadata") or {}
        tags = [str(t).lower() for t in meta.get("tags", []) if t]
        if (meta.get("kind") != "experiment") and ("experiment" not in tags):
            continue
        if tag_value and tag_value not in tags:
            continue
        records.append(record)
    records.sort(key=lambda item: str(item.get("time") or ""), reverse=True)
    return records


def _format_section(title: str, value: str) -> str:
    if not value:
        return ""
    return f"- **{title}**: {value}"


def _render_experiment(record: Dict[str, Any]) -> str:
    meta = record.get("metadata") or {}
    title = meta.get("title") or "Untitled"
    run_id = meta.get("run_id") or record.get("id") or ""
    stamp = record.get("time") or ""
    tags = ", ".join([str(tag) for tag in meta.get("tags", []) if tag]) or "n/a"
    decision = meta.get("decision") or ""
    text = str(record.get("text") or "")

    blocks = [
        f"### {title}",
        f"- **Time**: {stamp}",
        f"- **Run ID**: {run_id}",
        f"- **Tags**: {tags}",
    ]
    if decision:
        blocks.append(f"- **Decision**: {decision}")
    if text:
        blocks.append("```\n" + text.strip() + "\n```")
    return "\n".join(blocks)


def export_markdown(
    *,
    limit: int,
    session_id: Optional[str],
    tag: Optional[str],
    out_path: Path,
) -> Path:
    cfg = FRAMConfig.from_env()
    override_root = os.getenv("COGMEM_STORAGE_ROOT")
    if override_root:
        cfg = cfg.model_copy(update={"STORAGE_ROOT": Path(override_root).expanduser().resolve()})
    root = cfg.STORAGE_ROOT / cfg.STORAGE_SUBFOLDERS.get("memory", "memory") / "cognitive"
    store = CognitiveMemoryStore(root, config=cfg)

    full_records = _load_full_records(store, session_id=session_id, tag=tag)
    summary = collect_experiments(store, session_id=session_id, tag=tag)
    header = [
        "# Experiment Digest",
        f"- Generated: {datetime.now(timezone.utc).isoformat()}",
        f"- Total experiments: {len(summary)}",
    ]
    body: List[str] = []
    for record in full_records[:limit]:
        body.append(_render_experiment(record))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n\n".join(header + [""] + body), encoding="utf-8")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Export experiments to a markdown digest.")
    parser.add_argument("--limit", type=int, default=10, help="Experiments to include.")
    parser.add_argument("--session-id", default=None, help="Filter by session id.")
    parser.add_argument("--tag", default=None, help="Filter by tag.")
    parser.add_argument("--out", type=Path, default=None, help="Output path.")
    args = parser.parse_args()

    out_path = args.out
    if out_path is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out_path = Path("artifacts") / "observability" / f"experiment_digest_{stamp}.md"

    export_markdown(
        limit=max(1, int(args.limit)),
        session_id=args.session_id,
        tag=args.tag,
        out_path=out_path,
    )
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
