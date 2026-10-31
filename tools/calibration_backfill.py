"""Backfill domain/task metadata in FRAM calibration logs."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import sys

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fram_serving.config import FRAMConfig


ROADMAP_KEYWORDS = ("roadmap", "f_ram_roadmap")
DIARY_KEYWORDS = ("diary", "journal")
SPEC_KEYWORDS = ("spec", "specification", "framv2_2_spec")
SUMMARY_KEYWORDS = ("summary", "summarize", "recap", "overview")


def _default_log_path(cfg: FRAMConfig, storage_root: Path) -> Path:
    obs_dir = cfg.STORAGE_SUBFOLDERS.get("observability", "observability")
    return storage_root / obs_dir / "calibration.jsonl"


@dataclass
class Defaults:
    domain: str
    task: str
    budget_reads: int | None


@dataclass
class Options:
    infer_domain: bool
    overwrite_domain: bool
    infer_task: bool
    overwrite_task: bool
    overwrite_budget: bool


@dataclass
class BackfillSummary:
    total: int = 0
    updated: int = 0
    domain_set: int = 0
    domain_inferred: int = 0
    domain_defaulted: int = 0
    domain_overwritten: int = 0
    task_set: int = 0
    task_inferred: int = 0
    task_defaulted: int = 0
    task_overwritten: int = 0
    budget_set: int = 0


def _iter_records(path: Path) -> Iterable[tuple[dict, int]]:
    if not path.exists():
        raise SystemExit(f"Calibration log not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise SystemExit(
                    f"Invalid JSON on line {line_no} of {path}: {exc}"
                ) from exc
            yield record, line_no


def _normalize(value: object | None) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _contains(texts: Iterable[str], keywords: Iterable[str]) -> bool:
    return any(keyword in text for text in texts if text for keyword in keywords)


def _infer_domain(record: dict) -> str:
    doc = _normalize(record.get("doc_id")).lower()
    query = _normalize(record.get("query")).lower()
    texts = (doc, query)
    if _contains(texts, ROADMAP_KEYWORDS):
        return "roadmap"
    if _contains(texts, DIARY_KEYWORDS):
        return "diary"
    if _contains(texts, SPEC_KEYWORDS):
        return "spec"
    return ""


def _infer_task(record: dict) -> str:
    query = _normalize(record.get("query")).lower()
    if _contains((query,), SUMMARY_KEYWORDS):
        return "summary"
    return ""


def _assign_field(
    record: dict,
    key: str,
    value: str,
    overwrite: bool,
    summary: BackfillSummary,
    *,
    inferred: bool,
    defaulted: bool,
    overwrite_counter_attr: str,
    set_counter_attr: str,
    inferred_counter_attr: str,
    default_counter_attr: str,
) -> bool:
    if not value:
        return False
    existing = _normalize(record.get(key))
    overwritten = False
    if existing:
        if not overwrite and existing:
            return False
        if existing == value:
            return False
        overwritten = True
    record[key] = value
    setattr(summary, set_counter_attr, getattr(summary, set_counter_attr) + 1)
    if inferred:
        setattr(summary, inferred_counter_attr, getattr(summary, inferred_counter_attr) + 1)
    if defaulted:
        setattr(summary, default_counter_attr, getattr(summary, default_counter_attr) + 1)
    if overwritten:
        setattr(summary, overwrite_counter_attr, getattr(summary, overwrite_counter_attr) + 1)
    return True


def _backfill_record(
    record: dict,
    defaults: Defaults,
    options: Options,
    summary: BackfillSummary,
) -> None:
    summary.total += 1
    changed = False

    domain_value = ""
    domain_inferred = False
    if options.infer_domain:
        inferred = _infer_domain(record)
        if inferred:
            domain_value = inferred
            domain_inferred = True
    if not domain_value and defaults.domain:
        domain_value = defaults.domain
    domain_changed = _assign_field(
        record,
        "domain",
        domain_value,
        options.overwrite_domain,
        summary,
        inferred=domain_inferred,
        defaulted=not domain_inferred and bool(domain_value),
        overwrite_counter_attr="domain_overwritten",
        set_counter_attr="domain_set",
        inferred_counter_attr="domain_inferred",
        default_counter_attr="domain_defaulted",
    )
    changed = changed or domain_changed

    task_value = ""
    task_inferred = False
    if options.infer_task:
        inferred_task = _infer_task(record)
        if inferred_task:
            task_value = inferred_task
            task_inferred = True
    if not task_value and defaults.task:
        task_value = defaults.task
    task_changed = _assign_field(
        record,
        "task",
        task_value,
        options.overwrite_task,
        summary,
        inferred=task_inferred,
        defaulted=not task_inferred and bool(task_value),
        overwrite_counter_attr="task_overwritten",
        set_counter_attr="task_set",
        inferred_counter_attr="task_inferred",
        default_counter_attr="task_defaulted",
    )
    changed = changed or task_changed

    existing_budget = record.get("budget_reads")
    if defaults.budget_reads is not None and (existing_budget is None or options.overwrite_budget):
        if existing_budget != defaults.budget_reads:
            record["budget_reads"] = defaults.budget_reads
            summary.budget_set += 1
            changed = True

    if changed:
        summary.updated += 1


def _write_records(path: Path, records: Iterable[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill missing metadata in FRAM calibration logs.",
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
        "--output",
        type=Path,
        default=None,
        help="Optional output path (defaults to in-place overwrite)",
    )
    parser.add_argument(
        "--default-domain",
        type=str,
        default="general",
        help="Domain to assign when missing (default: general)",
    )
    parser.add_argument(
        "--default-task",
        type=str,
        default="qa",
        help="Task to assign when missing (default: qa)",
    )
    parser.add_argument(
        "--default-budget",
        type=int,
        default=None,
        help="Budget value to assign when missing (omit to skip)",
    )
    parser.add_argument(
        "--infer-domain",
        action="store_true",
        help="Infer domain from doc_id/query keywords before applying defaults",
    )
    parser.add_argument(
        "--overwrite-domain",
        action="store_true",
        help="Allow overwriting existing domain values when inference/defaults provide a value",
    )
    parser.add_argument(
        "--infer-task",
        action="store_true",
        help="Infer task from query keywords before applying defaults",
    )
    parser.add_argument(
        "--overwrite-task",
        action="store_true",
        help="Allow overwriting existing task values when inference/defaults provide a value",
    )
    parser.add_argument(
        "--overwrite-budget",
        action="store_true",
        help="Allow overwriting existing budget values with the default",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show summary without writing changes",
    )
    parser.add_argument(
        "--backup",
        type=Path,
        default=None,
        help="Optional backup path to write the original log before modifications",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    cfg = FRAMConfig.from_env()
    storage_root = (
        Path(args.storage_root)
        if args.storage_root is not None
        else Path(cfg.STORAGE_ROOT)
    )
    log_path = Path(args.log) if args.log is not None else _default_log_path(cfg, storage_root)
    output_path = Path(args.output) if args.output is not None else log_path

    defaults = Defaults(
        domain=args.default_domain.strip(),
        task=args.default_task.strip(),
        budget_reads=args.default_budget,
    )
    options = Options(
        infer_domain=args.infer_domain,
        overwrite_domain=args.overwrite_domain,
        infer_task=args.infer_task,
        overwrite_task=args.overwrite_task,
        overwrite_budget=args.overwrite_budget,
    )

    summary = BackfillSummary()
    records: list[dict] = []
    for record, _ in _iter_records(log_path):
        _backfill_record(record, defaults, options, summary)
        records.append(record)

    if args.dry_run:
        print(json.dumps(summary.__dict__, indent=2))
        return 0

    if args.backup is not None:
        backup_path = Path(args.backup)
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        backup_path.write_text(log_path.read_text(encoding="utf-8"), encoding="utf-8")

    if output_path != log_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    _write_records(output_path, records)
    print(json.dumps(summary.__dict__, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
