from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from fram_serving.config import FRAMConfig
from fram_serving.memory import CognitiveMemoryStore


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _decision_from_text(text: str) -> str:
    for line in text.splitlines():
        if line.lower().startswith("decision:"):
            return line.split(":", 1)[1].strip()
    return ""


def _extract_experiment(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    meta = record.get("metadata") or {}
    tags = [str(tag).lower() for tag in meta.get("tags", []) if tag]
    kind = str(meta.get("kind") or "").lower()
    if kind != "experiment" and "experiment" not in tags:
        return None
    stamp = str(record.get("time") or "")
    title = str(meta.get("title") or "")
    decision = str(meta.get("decision") or "")
    if not decision:
        decision = _decision_from_text(str(record.get("text") or ""))
    return {
        "id": record.get("id"),
        "run_id": meta.get("run_id"),
        "title": title,
        "decision": decision,
        "tags": tags,
        "time": stamp,
    }


def collect_experiments(
    store: CognitiveMemoryStore,
    *,
    session_id: Optional[str] = None,
    tag: Optional[str] = None,
) -> list[Dict[str, Any]]:
    entries: list[Dict[str, Any]] = []
    tag_value = tag.lower() if tag else None
    for record in store._iter_belief_records():
        if session_id and str(record.get("session_id") or "") != session_id:
            continue
        experiment = _extract_experiment(record)
        if not experiment:
            continue
        if tag_value and tag_value not in experiment.get("tags", []):
            continue
        entries.append(experiment)
    entries.sort(key=lambda item: _parse_iso(item.get("time")) or datetime.min, reverse=True)
    return entries


def summarise(experiments: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    items = list(experiments)
    tag_counts: Counter[str] = Counter()
    decision_count = 0
    latest_time = None
    for item in items:
        for tag in item.get("tags", []):
            tag_counts[str(tag)] += 1
        if item.get("decision"):
            decision_count += 1
        stamp = _parse_iso(item.get("time"))
        if stamp and (latest_time is None or stamp > latest_time):
            latest_time = stamp
    return {
        "total": len(items),
        "decisions": decision_count,
        "latest": latest_time.isoformat() if latest_time else None,
        "tags": dict(tag_counts),
        "experiments": items,
    }


def _emit_text(summary: Dict[str, Any], *, limit: int) -> None:
    total = summary.get("total", 0)
    print(f"Total experiments: {total}")
    print(f"Decisions logged: {summary.get('decisions', 0)}")
    latest = summary.get("latest")
    if latest:
        print(f"Latest: {latest}")
    tags = summary.get("tags") or {}
    if tags:
        print("Top tags:")
        for tag, count in sorted(tags.items(), key=lambda item: item[1], reverse=True)[:6]:
            print(f"  - {tag}: {count}")
    print("Recent experiments:")
    for item in (summary.get("experiments") or [])[:limit]:
        title = item.get("title") or "(untitled)"
        decision = item.get("decision") or "n/a"
        stamp = item.get("time") or ""
        run_id = item.get("run_id") or item.get("id") or ""
        print(f"  - {stamp} | {title} | decision: {decision} | run: {run_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarise logged experiments from cognitive memory.")
    parser.add_argument("--limit", type=int, default=10, help="How many recent experiments to show.")
    parser.add_argument("--session-id", default=None, help="Filter to a session id.")
    parser.add_argument("--tag", default=None, help="Filter by tag.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    args = parser.parse_args()

    cfg = FRAMConfig.from_env()
    override_root = os.getenv("COGMEM_STORAGE_ROOT")
    if override_root:
        cfg = cfg.model_copy(update={"STORAGE_ROOT": Path(override_root).expanduser().resolve()})
    root = cfg.STORAGE_ROOT / cfg.STORAGE_SUBFOLDERS.get("memory", "memory") / "cognitive"
    store = CognitiveMemoryStore(root, config=cfg)
    experiments = collect_experiments(store, session_id=args.session_id, tag=args.tag)
    summary = summarise(experiments)

    if args.json:
        json.dump(summary, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        _emit_text(summary, limit=max(1, int(args.limit)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
