"""Filter and summarize FRAM calibration logs by domain/task metadata."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Mapping, Sequence

import sys


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fram_serving.config import FRAMConfig


def _default_log_path(cfg: FRAMConfig, storage_root: Path) -> Path:
    obs_dir = cfg.STORAGE_SUBFOLDERS.get("observability", "observability")
    return storage_root / obs_dir / "calibration.jsonl"


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError as exc:  # pragma: no cover - defensive
        raise SystemExit(f"Invalid ISO8601 timestamp: {value}") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt


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
            except json.JSONDecodeError as exc:  # pragma: no cover - defensive
                raise SystemExit(
                    f"Invalid JSON on line {line_number} of {path}: {exc}"
                ) from exc


def _matches(
    record: Mapping[str, object],
    args: argparse.Namespace,
    after: datetime | None,
    before: datetime | None,
) -> bool:
    if args.domain and str(record.get("domain") or "").lower() not in args.domain:
        return False
    if args.task and str(record.get("task") or "").lower() not in args.task:
        return False
    if args.decision and str(record.get("decision") or "").lower() not in args.decision:
        return False
    if args.label is not None:
        label = record.get("label")
        if label is None or int(label) != args.label:
            return False
    if args.query_contains:
        query = str(record.get("query") or "")
        if args.query_contains.lower() not in query.lower():
            return False

    timestamp = record.get("time")
    if (after or before) and timestamp:
        try:
            record_dt = datetime.fromisoformat(str(timestamp))
        except ValueError:
            record_dt = None
        else:
            if record_dt.tzinfo is None:
                record_dt = record_dt.replace(tzinfo=timezone.utc)
            else:
                record_dt = record_dt.astimezone(timezone.utc)
        if after and (record_dt is None or record_dt < after):
            return False
        if before and (record_dt is None or record_dt > before):
            return False
    return True


def _normalize_key(value: object, fallback: str = "unknown") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text.lower() if text else fallback


def _summarize(records: Sequence[Mapping[str, object]]) -> dict:
    total = len(records)
    positives = sum(1 for rec in records if int(rec.get("label", 0)) == 1)

    by_decision: Counter[str] = Counter()
    by_domain: Counter[str] = Counter()
    by_task: Counter[str] = Counter()
    decision_positive: Counter[str] = Counter()

    for rec in records:
        decision_key = _normalize_key(rec.get("decision"))
        domain_key = _normalize_key(rec.get("domain"))
        task_key = _normalize_key(rec.get("task"))
        by_decision[decision_key] += 1
        by_domain[domain_key] += 1
        by_task[task_key] += 1
        if int(rec.get("label", 0)) == 1:
            decision_positive[decision_key] += 1

    positive_rate = float(positives / total) if total else 0.0

    decisions_summary = {
        key: {
            "count": count,
            "positive": decision_positive.get(key, 0),
            "positive_rate": (
                float(decision_positive.get(key, 0) / count) if count else 0.0
            ),
        }
        for key, count in sorted(by_decision.items())
    }

    domains_summary = {key: count for key, count in sorted(by_domain.items())}
    tasks_summary = {key: count for key, count in sorted(by_task.items())}

    times: List[datetime] = []
    for rec in records:
        stamp = rec.get("time")
        if not stamp:
            continue
        try:
            dt = datetime.fromisoformat(str(stamp))
        except ValueError:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        times.append(dt)
    time_range = None
    if times:
        time_range = {
            "start": min(times).isoformat(),
            "end": max(times).isoformat(),
        }

    queries = [str(rec.get("query") or "") for rec in records]
    unique_queries = len({q for q in queries if q})
    recent_examples = [
        {
            "time": rec.get("time"),
            "query": rec.get("query"),
            "domain": rec.get("domain"),
            "task": rec.get("task"),
            "decision": rec.get("decision"),
            "label": rec.get("label"),
        }
        for rec in records[-5:]
    ]

    return {
        "total": total,
        "positive": positives,
        "positive_rate": positive_rate,
        "unique_queries": unique_queries,
        "by_decision": decisions_summary,
        "by_domain": domains_summary,
        "by_task": tasks_summary,
        "time_range": time_range,
        "recent_examples": recent_examples,
    }


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Filter calibration samples for FRAM confidence calibration",
    )
    parser.add_argument(
        "--storage-root",
        type=Path,
        default=None,
        help="Override FRAM storage root (defaults to FRAMConfig.STORAGE_ROOT)",
    )
    parser.add_argument(
        "--log",
        type=Path,
        default=None,
        help="Explicit calibration log path (defaults to storage/observability/calibration.jsonl)",
    )
    parser.add_argument(
        "--domain",
        action="append",
        default=None,
        help="Filter by domain (case-insensitive, repeatable)",
    )
    parser.add_argument(
        "--task",
        action="append",
        default=None,
        help="Filter by task (case-insensitive, repeatable)",
    )
    parser.add_argument(
        "--decision",
        action="append",
        default=None,
        help="Filter by decision policy (local|anchors|global)",
    )
    parser.add_argument(
        "--label",
        type=int,
        choices=(0, 1),
        default=None,
        help="Filter by calibration label (0 or 1)",
    )
    parser.add_argument(
        "--after",
        type=str,
        default=None,
        help="Only include records on/after this ISO timestamp",
    )
    parser.add_argument(
        "--before",
        type=str,
        default=None,
        help="Only include records on/before this ISO timestamp",
    )
    parser.add_argument(
        "--query-contains",
        type=str,
        default=None,
        help="Filter to queries containing this substring",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit the number of records after filtering (most recent)",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Write the filtered summary as JSON to this path",
    )
    parser.add_argument(
        "--include-records",
        action="store_true",
        help="Include matching raw records in the output payload",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)

    cfg = FRAMConfig.from_env()
    storage_root = (
        Path(args.storage_root)
        if args.storage_root is not None
        else Path(cfg.STORAGE_ROOT)
    )

    log_path = Path(args.log) if args.log is not None else _default_log_path(cfg, storage_root)

    after = _parse_time(args.after)
    before = _parse_time(args.before)

    args.domain = [d.lower() for d in args.domain] if args.domain else None
    args.task = [t.lower() for t in args.task] if args.task else None
    args.decision = [d.lower() for d in args.decision] if args.decision else None

    records: List[dict] = []
    for record in _iter_records(log_path):
        if _matches(record, args, after, before):
            records.append(record)

    if args.limit is not None and args.limit > 0:
        records = records[-args.limit :]

    summary = _summarize(records)
    payload = {
        "log": str(log_path),
        "filters": {
            "domain": args.domain,
            "task": args.task,
            "decision": args.decision,
            "label": args.label,
            "after": args.after,
            "before": args.before,
            "query_contains": args.query_contains,
            "limit": args.limit,
        },
        "summary": summary,
    }
    if args.include_records:
        payload["records"] = records

    data = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(data, encoding="utf-8")
    else:
        print(data)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
