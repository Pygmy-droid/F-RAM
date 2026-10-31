from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Iterable, List


def _iter_events(path: Path) -> Iterable[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def _rank(entries: List[dict], key: str, reverse: bool = True) -> dict | None:
    if not entries:
        return None
    filtered = [entry for entry in entries if key in entry]
    if not filtered:
        return None
    return sorted(filtered, key=lambda item: item.get(key, 0.0), reverse=reverse)[0]


def run_ablation(events_path: Path, limit: int, output: Path | None) -> None:
    rows: List[List[str]] = []
    for idx, event in enumerate(_iter_events(events_path)):
        if limit and idx >= limit:
            break
        scores = event.get("top") or event.get("scores") or []
        if not scores:
            continue
        clock = event.get("clock")
        query_id = event.get("query_id")
        blend = _rank(scores, "score", reverse=True)
        cosine = _rank(scores, "cosine", reverse=True)
        soft = _rank(scores, "soft_dtw", reverse=True)
        for mode, winner in (
            ("blend", blend),
            ("cosine", cosine),
            ("soft_dtw", soft),
        ):
            if winner is None:
                continue
            rows.append(
                [
                    str(clock or ""),
                    str(query_id or ""),
                    mode,
                    str(winner.get("episode_id") or ""),
                    f"{winner.get('score', winner.get('cosine', 0.0)):.6f}",
                ]
            )
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["clock", "query_id", "mode", "episode_id", "score"])
            writer.writerows(rows)
    else:
        writer = csv.writer(sys.stdout)
        writer.writerow(["clock", "query_id", "mode", "episode_id", "score"])
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fractal scoring ablation helper.")
    parser.add_argument(
        "--events",
        type=Path,
        default=Path("storage/observability/memory_fractal.jsonl"),
        help="Path to memory_fractal.jsonl events.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of events to read (0 = all).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional CSV output path (stdout when omitted).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    limit = max(0, int(args.limit))
    run_ablation(args.events, limit, args.out)


if __name__ == "__main__":
    main()
