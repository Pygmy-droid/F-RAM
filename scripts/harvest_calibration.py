"""Batch probe queries to append calibration samples for FRAM v2.2.

This helper loops over a list of questions, runs them through the
`QueryOrchestrator`, and reports how many calibration records were appended.
It is designed to complement the `tools/trace_probe.py` CLI.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional

import sys


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fram_serving.config import FRAMConfig
from fram_core.pipeline import QueryOrchestrator
from fram_serving.connectors import registry as connectors


DEFAULT_QUERIES: tuple[str, ...] = (
    "What is the F-RAM roadmap vision?",
    "Summarize how OrthoRoute+ calibrates confidence thresholds.",
    "What does the coverage objective optimize in FRAM v2.2?",
    "Describe the ingestion steps that populate the demo corpus.",
    "How does FRAM handle layout-aware retrieval for tables and PDFs?",
    "When do curvature-aware anchors widen, and why?",
    "Explain how domain overrides affect default query reads and thresholds.",
)


def _read_queries(path: Optional[Path]) -> List[str]:
    if path is None:
        return list(DEFAULT_QUERIES)

    if not path.exists():
        raise FileNotFoundError(f"Queries file not found: {path}")

    queries: List[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        queries.append(stripped)
    if not queries:
        raise ValueError(f"No queries found in {path}")
    return queries


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for _ in handle)


def _parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run queries to harvest calibration samples")
    parser.add_argument(
        "--queries",
        type=Path,
        default=None,
        help="Optional file containing one query per line (blank lines and # comments ignored)",
    )
    parser.add_argument(
        "--storage-root",
        type=Path,
        default=None,
        help="Override FRAM storage root (helps isolate calibration logs during testing)",
    )
    parser.add_argument(
        "--reads",
        type=int,
        default=None,
        help="Override query budget (falls back to FRAMConfig.default_query_reads)",
    )
    parser.add_argument(
        "--as-of",
        type=str,
        default=None,
        help="Optional ISO8601 timestamp to enforce as-of filtering",
    )
    parser.add_argument(
        "--domain",
        type=str,
        default="general",
        help="Domain passed to the orchestrator",
    )
    parser.add_argument(
        "--task",
        type=str,
        default="qa",
        help="Task passed to the orchestrator",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Optional path to dump the run metadata as JSON",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-query stdout (still prints summary)",
    )
    return parser.parse_args(argv)


def _parse_as_of(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError as exc:  # pragma: no cover - defensive
        raise SystemExit(f"Invalid --as-of value '{value}': {exc}") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = _parse_args(argv)
    queries = _read_queries(args.queries)
    as_of_dt = _parse_as_of(args.as_of)

    cfg = FRAMConfig.from_env()
    updates: dict[str, Path] = {}
    if args.storage_root is not None:
        updates["STORAGE_ROOT"] = args.storage_root
    if updates:
        cfg = cfg.model_copy(update=updates)

    reads = args.reads
    if reads is None:
        reads = int(getattr(cfg, "default_query_reads", 3) or 1)
    if reads <= 0:
        reads = 1

    orchestrator = QueryOrchestrator(config=cfg)

    obs_dir = cfg.STORAGE_ROOT / cfg.STORAGE_SUBFOLDERS.get("observability", "observability")
    obs_dir.mkdir(parents=True, exist_ok=True)
    calibration_log = obs_dir / "calibration.jsonl"
    before = _count_lines(calibration_log)

    run_records: list[dict] = []
    connector_counts: dict[str, int] = {}

    for question in queries:
        result = orchestrator.run(
            question,
            as_of_dt,
            budget_reads=reads,
            domain=args.domain,
            task=args.task,
        )
        trace = result.get("record", {}).get("trace", {})
        record_info = {
            "question": question,
            "trace_id": trace.get("trace_id") or result.get("trace_id"),
            "decision": trace.get("confidence", {}).get("decision") if isinstance(trace.get("confidence"), dict) else None,
            "p_temp": trace.get("p_temp"),
            "citations": list(result.get("citations", ())),
        }
        run_records.append(record_info)
        if not args.quiet:
            print(f"Ran: {question}")
            print(f"  decision={record_info['decision']} citations={', '.join(record_info['citations']) or '<none>'}")

    # Connector harvest (read-only)
    if getattr(cfg, "enable_connector_ingestion", False):
        max_items = int(getattr(cfg, "connector_max_items", 0))
        for src in connectors.list_sources():
            sid = src.get("id")
            if not sid:
                continue
            items = connectors.fetch_items(sid, max_items)
            connector_counts[sid] = len(items)

    after = _count_lines(calibration_log)
    added = max(0, after - before)
    print(f"Calibration records appended: {added} (log size: {after})")

    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "storage_root": str(cfg.STORAGE_ROOT),
            "calibration_log": str(calibration_log),
            "records_added": added,
            "runs": run_records,
            "connectors": {
                "enabled": bool(getattr(cfg, "enable_connector_ingestion", False)),
                "counts": connector_counts,
            },
        }
        args.json_out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    # Persist connector meta for observability
    connector_meta_path = obs_dir / "connectors_latest.json"
    connector_meta = {
        "enabled": bool(getattr(cfg, "enable_connector_ingestion", False)),
        "sources": [src.get("id") for src in connectors.list_sources()],
        "last_harvest_counts": connector_counts,
    }
    connector_meta_path.write_text(json.dumps(connector_meta, ensure_ascii=False, indent=2), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
