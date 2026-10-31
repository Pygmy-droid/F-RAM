"""Sweep section diversity penalty settings across a query set.

This helper makes it easy to compare how the section repeat penalty and
floor influence anchor recall and section coverage. It runs configured
queries for each combination of penalty values and prints a compact
summary; optionally it can dump the full measurements to JSON for
offline inspection.
"""

from __future__ import annotations

import argparse
import json
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Mapping, Optional, Sequence

import sys


CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fram_serving.config import FRAMConfig
from fram_core.pipeline import QueryOrchestrator


DEFAULT_QUERIES: tuple[str, ...] = (
    "What is the F-RAM roadmap vision?",
    "How does FRAM replay session memory for roadmap prompts?",
    "Summarize the section-aware coverage metrics introduced in September 2025.",
    "Explain how curvature anchors interact with section diversity penalties.",
)

DEFAULT_REPEAT_GRID: tuple[float, ...] = (0.7, 0.85, 1.0)
DEFAULT_FLOOR_GRID: tuple[float, ...] = (0.25, 0.35, 0.5)


@dataclass
class RunRecord:
    question: str
    decision: Optional[str]
    anchor_count: int
    segments_diversity: float
    section_diversity: float
    citations: int
    coverage_delta: float
    reads_used: float

    @classmethod
    def from_trace(
        cls,
        question: str,
        trace: Mapping[str, object] | None,
        citations: Sequence[str],
    ) -> "RunRecord":
        selection = trace.get("selection", {}) if isinstance(trace, Mapping) else {}
        coverage = trace.get("coverage", {}) if isinstance(trace, Mapping) else {}
        decision = None
        confidence = trace.get("confidence") if isinstance(trace, Mapping) else None
        if isinstance(confidence, Mapping):
            raw_decision = confidence.get("decision")
            if isinstance(raw_decision, str):
                decision = raw_decision

        anchors = selection.get("anchors") if isinstance(selection, Mapping) else []
        if not isinstance(anchors, Sequence):
            anchor_count = 0
        else:
            anchor_count = sum(1 for _ in anchors)

        segments_diversity = 0.0
        if isinstance(selection, Mapping):
            value = selection.get("segments_diversity", 0.0)
            try:
                segments_diversity = float(value)
            except (TypeError, ValueError):  # pragma: no cover - defensive
                segments_diversity = 0.0

        section_diversity = 0.0
        if isinstance(coverage, Mapping):
            value = coverage.get("section_diversity", 0.0)
            try:
                section_diversity = float(value)
            except (TypeError, ValueError):  # pragma: no cover - defensive
                section_diversity = 0.0

        coverage_delta = 0.0
        if isinstance(selection, Mapping):
            delta = selection.get("coverage_delta")
            if isinstance(delta, Mapping):
                value = delta.get("total", 0.0)
                try:
                    coverage_delta = float(value)
                except (TypeError, ValueError):  # pragma: no cover - defensive
                    coverage_delta = 0.0

        reads_used = 0.0
        if isinstance(selection, Mapping):
            budgets = selection.get("budgets")
            if isinstance(budgets, Mapping):
                value = budgets.get("reads_used", 0.0)
                try:
                    reads_used = float(value)
                except (TypeError, ValueError):  # pragma: no cover - defensive
                    reads_used = 0.0

        return cls(
            question=question,
            decision=decision,
            anchor_count=anchor_count,
            segments_diversity=segments_diversity,
            section_diversity=section_diversity,
            citations=len(list(citations)),
            coverage_delta=coverage_delta,
            reads_used=reads_used,
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


def _parse_grid(raw: Optional[str], *, default: Sequence[float]) -> List[float]:
    if raw is None:
        return list(default)
    values: List[float] = []
    for piece in raw.split(","):
        stripped = piece.strip()
        if not stripped:
            continue
        try:
            values.append(float(stripped))
        except ValueError as exc:  # pragma: no cover - defensive
            raise SystemExit(f"Invalid grid value '{stripped}': {exc}") from exc
    if not values:
        raise SystemExit("No numeric values parsed for grid")
    return values


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


def _summarise(records: Sequence[RunRecord]) -> dict[str, float]:
    if not records:
        return {
            "queries": 0,
            "anchor_decisions": 0,
            "avg_anchor_count": 0.0,
            "avg_segments_diversity": 0.0,
            "avg_section_diversity": 0.0,
            "avg_citations": 0.0,
            "avg_reads_used": 0.0,
            "avg_coverage_delta": 0.0,
        }

    def _mean(values: Sequence[float]) -> float:
        if not values:
            return 0.0
        return float(statistics.fmean(values))

    anchor_decisions = sum(1 for record in records if record.decision == "anchors")
    return {
        "queries": len(records),
        "anchor_decisions": anchor_decisions,
        "avg_anchor_count": _mean([record.anchor_count for record in records]),
        "avg_segments_diversity": _mean([record.segments_diversity for record in records]),
        "avg_section_diversity": _mean([record.section_diversity for record in records]),
        "avg_citations": _mean([record.citations for record in records]),
        "avg_reads_used": _mean([record.reads_used for record in records]),
        "avg_coverage_delta": _mean([record.coverage_delta for record in records]),
    }


def _apply_penalty_updates(
    cfg: FRAMConfig,
    domain: Optional[str],
    task: Optional[str],
    repeat_penalty: float,
    penalty_floor: float,
) -> FRAMConfig:
    update_payload: dict[str, object] = {
        "section_repeat_penalty": repeat_penalty,
        "section_penalty_floor": penalty_floor,
    }

    domain_overrides = dict(cfg.domain_overrides)
    if domain:
        domain_data = dict(domain_overrides.get(domain, {}))
        domain_data["section_repeat_penalty"] = repeat_penalty
        domain_data["section_penalty_floor"] = penalty_floor
        domain_overrides[domain] = domain_data
        update_payload["domain_overrides"] = domain_overrides

    task_overrides = dict(cfg.task_overrides)
    if task:
        task_data = dict(task_overrides.get(task, {}))
        task_data["section_repeat_penalty"] = repeat_penalty
        task_data["section_penalty_floor"] = penalty_floor
        task_overrides[task] = task_data
        update_payload["task_overrides"] = task_overrides

    return cfg.model_copy(update=update_payload)


def _run_queries(
    base_cfg: FRAMConfig,
    queries: Sequence[str],
    as_of: Optional[datetime],
    domain: str,
    task: str,
    reads: int,
    repeat_penalty: float,
    penalty_floor: float,
    *,
    preserve_session: bool,
) -> List[RunRecord]:
    cfg = _apply_penalty_updates(base_cfg, domain, task, repeat_penalty, penalty_floor)
    orchestrator = QueryOrchestrator(config=cfg)

    records: List[RunRecord] = []
    for question in queries:
        if not preserve_session:
            orchestrator._session_memory = []  # type: ignore[attr-defined]
        result = orchestrator.run(
            question,
            as_of,
            budget_reads=reads,
            domain=domain,
            task=task,
        )
        trace = result.get("record", {}).get("trace") if isinstance(result, Mapping) else None
        citations = result.get("citations", []) if isinstance(result, Mapping) else []
        records.append(RunRecord.from_trace(question, trace, citations))
    return records


def _parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sweep section diversity penalties across queries")
    parser.add_argument("--queries", type=Path, default=None, help="Optional file with one query per line")
    parser.add_argument("--repeat-grid", type=str, default=None, help="Comma separated repeat penalty values (0-1]")
    parser.add_argument("--floor-grid", type=str, default=None, help="Comma separated penalty floor values [0-1]")
    parser.add_argument("--reads", type=int, default=None, help="Override read budget per query")
    parser.add_argument("--as-of", type=str, default=None, help="ISO8601 timestamp for as-of filtering")
    parser.add_argument("--domain", type=str, default="roadmap", help="Domain passed to the orchestrator")
    parser.add_argument("--task", type=str, default="qa", help="Task passed to the orchestrator")
    parser.add_argument("--storage-root", type=Path, default=None, help="Optional storage root override")
    parser.add_argument("--json-out", type=Path, default=None, help="Dump full sweep results as JSON")
    parser.add_argument(
        "--preserve-session",
        action="store_true",
        help="Keep session memory between queries (default clears before each run)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-combination summaries (useful when only writing JSON)",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = _parse_args(argv)
    queries = _read_queries(args.queries)
    repeat_grid = _parse_grid(args.repeat_grid, default=DEFAULT_REPEAT_GRID)
    floor_grid = _parse_grid(args.floor_grid, default=DEFAULT_FLOOR_GRID)
    as_of = _parse_as_of(args.as_of)

    cfg = FRAMConfig.from_env()
    updates: dict[str, object] = {}
    if args.storage_root is not None:
        updates["STORAGE_ROOT"] = args.storage_root
    if updates:
        cfg = cfg.model_copy(update=updates)

    reads = args.reads
    if reads is None:
        reads = int(getattr(cfg, "default_query_reads", 3) or 1)
    if reads <= 0:
        reads = 1

    sweep_results: list[dict[str, object]] = []

    for repeat_penalty in repeat_grid:
        for penalty_floor in floor_grid:
            records = _run_queries(
                cfg,
                queries,
                as_of,
                args.domain,
                args.task,
                reads,
                repeat_penalty,
                penalty_floor,
                preserve_session=args.preserve_session,
            )
            summary = _summarise(records)
            sweep_results.append(
                {
                    "section_repeat_penalty": repeat_penalty,
                    "section_penalty_floor": penalty_floor,
                    "summary": summary,
                    "records": [record.__dict__ for record in records],
                }
            )
            if not args.quiet:
                print(
                    (
                        "repeat={repeat:.3f} floor={floor:.3f} "
                        "anchors={anchors}/{queries} avg_anchor_count={avg_anchor:.2f} "
                        "avg_section_diversity={sec_div:.3f} avg_segments_diversity={seg_div:.3f} "
                        "avg_citations={cites:.2f} avg_reads_used={reads_used:.2f}"
                    ).format(
                        repeat=repeat_penalty,
                        floor=penalty_floor,
                        anchors=summary["anchor_decisions"],
                        queries=summary["queries"],
                        avg_anchor=summary["avg_anchor_count"],
                        sec_div=summary["avg_section_diversity"],
                        seg_div=summary["avg_segments_diversity"],
                        cites=summary["avg_citations"],
                        reads_used=summary["avg_reads_used"],
                    )
                )

    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "queries": queries,
            "repeat_grid": repeat_grid,
            "floor_grid": floor_grid,
            "domain": args.domain,
            "task": args.task,
            "reads": reads,
            "preserve_session": args.preserve_session,
            "results": sweep_results,
        }
        args.json_out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())

