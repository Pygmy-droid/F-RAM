"""Quick calibration sanity check runner.

Runs a set of queries through `QueryOrchestrator` and flags any
probabilities that hit the configured floor/ceiling boundaries. Intended
for CI smoke checks so we catch saturated payloads early.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, List, Optional

import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fram_serving.config import FRAMConfig
from fram_core.pipeline import QueryOrchestrator


DEFAULT_QUERY_FILES = (
    Path("scripts/calibration_prompts/definitional_queries.txt"),
    Path("scripts/calibration_prompts/definitional_soft_queries.txt"),
    Path("scripts/calibration_prompts/definitional_low_conf_queries.txt"),
)


def _read_queries(paths: Iterable[Path] | None) -> List[str]:
    queries: List[str] = []
    candidates = list(paths) if paths else list(DEFAULT_QUERY_FILES)
    for path in candidates:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            queries.append(stripped)
    if not queries:
        raise SystemExit("No queries found for calibration sanity check")
    return queries


def _parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run calibration sanity checks")
    parser.add_argument(
        "--queries",
        type=Path,
        action="append",
        default=None,
        help="Optional query list file (can repeat; defaults to bundled definitional prompts)",
    )
    parser.add_argument(
        "--domain",
        type=str,
        default=None,
        help="Domain to use (defaults to FRAMConfig.default_domain)",
    )
    parser.add_argument(
        "--task",
        type=str,
        default=None,
        help="Task to use (defaults to FRAMConfig.default_task)",
    )
    parser.add_argument(
        "--reads",
        type=int,
        default=None,
        help="Reads budget (defaults to FRAMConfig.default_query_reads)",
    )
    parser.add_argument(
        "--floor",
        type=float,
        default=0.001,
        help="Probability floor (flag anything <= floor)",
    )
    parser.add_argument(
        "--ceiling",
        type=float,
        default=0.999,
        help="Probability ceiling (flag anything >= ceiling)",
    )
    parser.add_argument(
        "--expect",
        type=str,
        action="append",
        default=None,
        choices=("local", "anchors", "global"),
        help="Optional allowed decisions (repeat). If provided, decisions outside the set are flagged.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def _run_checks(args: argparse.Namespace) -> int:
    cfg = FRAMConfig.from_env()
    queries = _read_queries(args.queries)

    domain = args.domain or cfg.default_domain
    task = args.task or cfg.default_task
    reads = args.reads if args.reads is not None else int(cfg.default_query_reads)
    reads = max(1, reads)

    orchestrator = QueryOrchestrator(config=cfg)

    violations: List[str] = []

    for query in queries:
        result = orchestrator.run(query, None, reads, domain, task)
        trace = result.get("record", {}).get("trace", {})
        confidence = trace.get("confidence", {}) if isinstance(trace, dict) else {}
        calibration = confidence.get("calibration", {}) if isinstance(confidence, dict) else {}
        p_temp = float(trace.get("p_temp", 0.0)) if trace else 0.0
        decision = confidence.get("decision") if isinstance(confidence, dict) else None
        source = calibration.get("source") if isinstance(calibration, dict) else None
        print(
            f"query={query!r} decision={decision} p_temp={p_temp:.6f} "
            f"taus=({calibration.get('tau1')}, {calibration.get('tau2')}) source={source}"
        )

        if p_temp <= args.floor or p_temp >= args.ceiling:
            violations.append(
                f"{query!r} probability {p_temp:.6f} outside ({args.floor}, {args.ceiling})"
            )
        if args.expect and (decision not in args.expect):
            violations.append(f"{query!r} decision {decision!r} not in expected {args.expect}")

    if violations:
        print("\nViolations:")
        for item in violations:
            print(f" - {item}")
        return 1
    return 0


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = _parse_args(argv)
    return _run_checks(args)


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
