from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from fram_serving import observability
from fram_serving.app import _aggregate_phase_d_stats, cognitive_summary_data


def summarize(path: Path) -> Dict[str, Any]:
    stats: Dict[str, Any] = {
        "events": 0,
        "phase_d_memory_events": 0,
        "phase_d_scored_total": 0,
        "latest_phase_d_memory": None,
        "phase_d_stats": {},
    }
    pd_entries: list[Dict[str, Any]] = []
    for event in observability.iter_jsonl(path):
        stats["events"] += 1
        pd_mem = event.get("phase_d_memory")
        if isinstance(pd_mem, dict) and pd_mem.get("enabled"):
            stats["phase_d_memory_events"] += 1
            try:
                scored = int(pd_mem.get("scored") or 0)
            except (TypeError, ValueError):
                scored = 0
            stats["phase_d_scored_total"] += max(0, scored)
            stats["latest_phase_d_memory"] = pd_mem
            pd_entries.append(pd_mem)
    stats["phase_d_stats"] = _aggregate_phase_d_stats(pd_entries)
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize Phase D memory bridge observability.")
    parser.add_argument(
        "--observability-root",
        type=Path,
        default=Path("storage/observability"),
        help="Path to observability root (default: storage/observability)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON output",
    )
    parser.add_argument(
        "--include-cognitive",
        action="store_true",
        help="Also print the cognitive summary using server helpers",
    )
    args = parser.parse_args()
    path = args.observability_root / "memory_cognitive.jsonl"
    stats = summarize(path)
    cog_summary = None
    if args.include_cognitive:
        try:
            cog_summary = cognitive_summary_data()
        except Exception as exc:
            cog_summary = {"error": str(exc)}
    if args.json:
        payload = {"phase_d_memory": stats}
        if cog_summary is not None:
            payload["cognitive_summary"] = cog_summary
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print("events:", stats["events"])
        print("phase_d_memory_events:", stats["phase_d_memory_events"])
        print("phase_d_scored_total:", stats["phase_d_scored_total"])
        print("phase_d_stats:", json.dumps(stats["phase_d_stats"], ensure_ascii=False))
        latest = stats["latest_phase_d_memory"]
        if latest:
            print("latest_phase_d_memory:", json.dumps(latest, ensure_ascii=False))
        if cog_summary is not None:
            print("--- cognitive_summary ---")
            print(json.dumps(cog_summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
