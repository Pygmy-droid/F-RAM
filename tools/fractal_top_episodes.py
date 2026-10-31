from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import DefaultDict, List, Tuple

DEFAULT_PATH = Path("storage/observability/memory_fractal.jsonl")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pretty-print top fractal episodes per task/domain.")
    parser.add_argument(
        "--path",
        default=str(DEFAULT_PATH),
        help="Path to memory_fractal.jsonl (default: %(default)s)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum episodes to show per task (default: %(default)s)",
    )
    return parser.parse_args()


def load_events(path: Path) -> DefaultDict[str, List[Tuple[float, str]]]:
    agg: DefaultDict[str, List[Tuple[float, str]]] = defaultdict(list)
    if not path.exists():
        return agg
    for line in path.read_text(encoding="utf-8").splitlines():
        record_raw = line.strip()
        if not record_raw:
            continue
        try:
            rec = json.loads(record_raw)
        except json.JSONDecodeError:
            continue
        metadata = rec.get("metadata") or {}
        task = metadata.get("task") or rec.get("task") or "unknown"
        score = rec.get("score")
        if score is None:
            score = rec.get("alpha", 0.0)
        try:
            score_value = float(score)
        except (TypeError, ValueError):
            score_value = 0.0

        episode_id = rec.get("episode_id")
        if not episode_id:
            top = rec.get("top")
            if isinstance(top, list) and top:
                episode_id = top[0].get("episode_id")
        if not episode_id:
            continue
        agg[task].append((score_value, str(episode_id)))
    return agg


def main() -> int:
    args = parse_args()
    path = Path(args.path)
    agg = load_events(path)
    if not agg:
        print(f"No fractal events found in {path}")
        return 0
    for task, items in agg.items():
        items.sort(key=lambda pair: pair[0], reverse=True)
        print(f"Task: {task}")
        for score, episode_id in items[: max(1, args.limit)]:
            print(f"  {episode_id:>24}  score={score:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
