from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Iterable, List


def _iter_records(path: Path) -> Iterable[dict]:
    if not path.exists():
        raise SystemExit(f"Calibration log not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"Invalid JSON on line {line_number} of {path}: {exc}") from exc


def _bucket(prob: float, bins: int) -> int:
    if not (prob >= 0.0):
        return 0
    if prob >= 1.0:
        return bins - 1
    return min(int(prob * bins), bins - 1)


def _format_bar(count: int, scale: float) -> str:
    if count == 0:
        return ""
    length = max(int(round(count * scale)), 1)
    return "#" * length


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarise calibration histogram by (task, decision).")
    parser.add_argument(
        "--log",
        type=Path,
        default=Path("storage/observability/calibration.jsonl"),
        help="Calibration log path (default: storage/observability/calibration.jsonl)",
    )
    parser.add_argument("--bins", type=int, default=10, help="Number of histogram bins (default: 10)")
    parser.add_argument("--task", action="append", default=None, help="Filter to specific task (repeatable)")
    parser.add_argument("--domain", action="append", default=None, help="Filter to specific domain (repeatable)")
    parser.add_argument("--decision", action="append", default=None, help="Filter to decision (repeatable)")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text output")
    args = parser.parse_args(argv)

    bins = max(int(args.bins), 1)
    filters = {
        "task": set(t.lower() for t in args.task) if args.task else None,
        "domain": set(d.lower() for d in args.domain) if args.domain else None,
        "decision": set(d.lower() for d in args.decision) if args.decision else None,
    }

    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)

    for record in _iter_records(args.log):
        task = str(record.get("task", "unknown")).lower()
        domain = str(record.get("domain", "unknown")).lower()
        decision = str(record.get("decision", "unknown")).lower()
        prob = record.get("prob")
        if prob is None:
            continue

        if filters["task"] and task not in filters["task"]:
            continue
        if filters["domain"] and domain not in filters["domain"]:
            continue
        if filters["decision"] and decision not in filters["decision"]:
            continue

        key = (task or "unknown", decision or "unknown")
        grouped[key].append(float(prob))

    if not grouped:
        print("No matching calibration records found.")
        return 0

    if args.json:
        payload: dict[str, dict[str, object]] = {}
        for (task, decision), probs in grouped.items():
            hist = [0] * bins
            for value in probs:
                hist[_bucket(value, bins)] += 1
            payload[f"{task}|{decision}"] = {
                "count": len(probs),
                "min": float(min(probs)),
                "max": float(max(probs)),
                "avg": float(sum(probs) / len(probs)),
                "hist": hist,
            }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    for (task, decision), probs in sorted(grouped.items()):
        hist = [0] * bins
        for value in probs:
            hist[_bucket(value, bins)] += 1
        count = len(probs)
        avg = sum(probs) / count if count else 0.0
        min_val = min(probs) if probs else 0.0
        max_val = max(probs) if probs else 0.0
        print(f"[task={task} | decision={decision}] count={count} avg={avg:.4f} min={min_val:.4f} max={max_val:.4f}")
        max_count = max(hist) if hist else 0
        scale = (20.0 / max_count) if max_count else 0.0
        for idx, bucket_count in enumerate(hist):
            edge_low = idx / bins
            edge_high = (idx + 1) / bins
            bar = _format_bar(bucket_count, scale)
            print(f"  {edge_low:0.2f}–{edge_high:0.2f}: {bucket_count:>4} {bar}")
        print()

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

