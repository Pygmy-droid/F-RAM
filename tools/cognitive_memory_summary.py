from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_PATH = REPO_ROOT / "storage" / "observability" / "memory_cognitive.jsonl"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarise cognitive-memory search events captured under storage/observability/."
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=DEFAULT_PATH,
        help=f"Path to memory_cognitive.jsonl (default: {DEFAULT_PATH})",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit summary as JSON instead of text.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit number of events processed (0 = all).",
    )
    return parser.parse_args()


def _iter_events(path: Path, limit: int = 0) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    events: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            events.append(payload)
            if limit and len(events) >= limit:
                break
    return events


def summarise(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(events)
    backend_counts: Counter[str] = Counter()
    selected_total = 0.0
    selected_used_total = 0.0
    selected_candidate_total = 0.0
    selected_dropped_total = 0.0
    drop_events = 0
    tokens_total = 0.0
    token_budget_total = 0.0

    for event in events:
        backend = str(event.get("backend") or "unknown").lower()
        backend_counts[backend] += 1
        selected = event.get("selected")
        if not isinstance(selected, list):
            selected = []
        selected_count = event.get("selected_count")
        if not isinstance(selected_count, (int, float)):
            selected_count = len(selected)
        selected_total += float(selected_count)
        selected_candidate = event.get("selected_total")
        if not isinstance(selected_candidate, (int, float)):
            selected_candidate = selected_count
        selected_used = event.get("selected_used")
        if not isinstance(selected_used, (int, float)):
            selected_used = len(selected)
        selected_dropped = event.get("selected_dropped")
        if not isinstance(selected_dropped, (int, float)):
            selected_dropped = max(0.0, float(selected_candidate) - float(selected_used))
        selected_candidate_total += float(selected_candidate)
        selected_used_total += float(selected_used)
        selected_dropped_total += float(selected_dropped)
        if selected_dropped:
            drop_events += 1
        for item in selected:
            if not isinstance(item, dict):
                continue
            tokens = item.get("tokens")
            if isinstance(tokens, (int, float)):
                tokens_total += float(tokens)
        token_budget = event.get("token_budget")
        if isinstance(token_budget, (int, float)):
            token_budget_total += float(token_budget)

    avg_selected = selected_total / total if total else 0.0
    avg_tokens = tokens_total / total if total else 0.0
    avg_budget = token_budget_total / total if total else 0.0
    avg_candidate = selected_candidate_total / total if total else 0.0
    avg_used = selected_used_total / total if total else 0.0
    avg_dropped = selected_dropped_total / total if total else 0.0
    drop_rate = selected_dropped_total / selected_candidate_total if selected_candidate_total else 0.0
    token_util = tokens_total / token_budget_total if token_budget_total else 0.0

    return {
        "total_events": total,
        "backends": dict(backend_counts),
        "avg_selected": avg_selected,
        "avg_candidates": avg_candidate,
        "avg_used": avg_used,
        "avg_dropped": avg_dropped,
        "drop_rate": drop_rate,
        "events_with_drops": int(drop_events),
        "avg_tokens": avg_tokens,
        "avg_token_budget": avg_budget,
        "token_utilization": token_util,
    }


def emit_text(summary: Dict[str, Any]) -> None:
    total = summary.get("total_events", 0)
    print(f"Total events: {total}")
    backend_counts = summary.get("backends") or {}
    if backend_counts:
        print("Backends:")
        for backend, count in sorted(backend_counts.items()):
            print(f"  - {backend}: {count}")
    print(f"Average selected per call: {summary.get('avg_selected', 0.0):.2f}")
    print(f"Average candidates per call: {summary.get('avg_candidates', 0.0):.2f}")
    print(f"Average used per call: {summary.get('avg_used', 0.0):.2f}")
    print(f"Average dropped per call: {summary.get('avg_dropped', 0.0):.2f}")
    print(f"Drop rate: {summary.get('drop_rate', 0.0):.2%}")
    print(f"Events with drops: {summary.get('events_with_drops', 0)}")
    print(f"Average tokens pulled: {summary.get('avg_tokens', 0.0):.1f}")
    print(f"Average token budget: {summary.get('avg_token_budget', 0.0):.1f}")
    print(f"Token utilization: {summary.get('token_utilization', 0.0):.2%}")


def main() -> int:
    args = parse_args()
    events = _iter_events(args.path.expanduser(), limit=max(0, int(args.limit)))
    summary = summarise(events)
    if args.json:
        json.dump(summary, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        emit_text(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
