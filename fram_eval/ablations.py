"""Deterministic evaluation-ablation ladder for F-RAM spec section 15."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from fram_eval.datasets import EvaluationCase
from fram_eval.metrics import (
    as_of_accuracy,
    citation_precision_recall_f1,
    latency_percentiles,
    mean_reciprocal_rank,
    misrouting_rate,
    missed_evidence_rate,
    qa_exact_match,
    qa_token_f1,
    recall_at_k,
)


@dataclass(frozen=True)
class AblationVariant:
    """One ordered rung in the section-15 evaluation ladder."""

    stage: int
    key: str
    label: str
    enabled_features: tuple[str, ...]


ABLATION_LADDER: tuple[AblationVariant, ...] = (
    AblationVariant(
        1,
        "flat_hnsw_reranker",
        "Flat HNSW + reranker",
        ("flat_hnsw", "reranker"),
    ),
    AblationVariant(
        2,
        "prototype_routing",
        "Prototype routing",
        ("prototype_routing", "reranker"),
    ),
    AblationVariant(
        3,
        "tied_projection",
        "Tied projection",
        ("prototype_routing", "tied_projection", "reranker"),
    ),
    AblationVariant(
        4,
        "calibrated_thresholds",
        "Calibrated tau1/tau2 (no delta-cost)",
        ("prototype_routing", "tied_projection", "calibrated_thresholds", "reranker"),
    ),
    AblationVariant(
        5,
        "delta_cost_anchors",
        "Delta-cost anchors",
        (
            "prototype_routing",
            "tied_projection",
            "calibrated_thresholds",
            "delta_cost_anchors",
            "reranker",
        ),
    ),
    AblationVariant(
        6,
        "claim_delta_cost_shards",
        "Claim extraction + delta-cost shards with concave coverage",
        (
            "prototype_routing",
            "tied_projection",
            "calibrated_thresholds",
            "delta_cost_anchors",
            "claim_extraction",
            "delta_cost_shards",
            "concave_coverage",
            "reranker",
        ),
    ),
    AblationVariant(
        7,
        "layout_constraints",
        "Layout constraints",
        (
            "prototype_routing",
            "tied_projection",
            "calibrated_thresholds",
            "delta_cost_anchors",
            "claim_extraction",
            "delta_cost_shards",
            "concave_coverage",
            "layout_constraints",
            "reranker",
        ),
    ),
    AblationVariant(
        8,
        "version_lattice_delta_policy",
        "Version lattice + delta policy",
        (
            "prototype_routing",
            "tied_projection",
            "calibrated_thresholds",
            "delta_cost_anchors",
            "claim_extraction",
            "delta_cost_shards",
            "concave_coverage",
            "layout_constraints",
            "version_lattice",
            "delta_policy",
            "reranker",
        ),
    ),
)


def _result_ids(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    ids: list[str] = []
    for item in value:
        if isinstance(item, Mapping):
            item_id = (
                item.get("id")
                or item.get("s_id")
                or item.get("chunk_id")
                or item.get("claim_id")
            )
            if item_id is not None:
                ids.append(str(item_id))
        else:
            ids.append(str(item))
    return tuple(ids)


def _nested(mapping: Mapping[str, Any], *path: str) -> Any:
    current: Any = mapping
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


@dataclass(frozen=True)
class EvaluationOutcome:
    """Normalized output from an orchestrator or synthetic ablation runner."""

    retrieved_ids: tuple[str, ...] = ()
    answer: str | None = None
    citations: tuple[str, ...] = ()
    route: str | None = None
    evidence_found: bool | None = None
    latency_ms: float = 0.0
    vector_reads: int = 0
    tokens: int = 0
    index_size_bytes: int = 0
    as_of_correct: bool | None = None
    delta_snippet_correct: bool | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "EvaluationOutcome":
        """Normalize common QueryOrchestrator and evaluation-runner result fields."""
        record = payload.get("record") if isinstance(payload.get("record"), Mapping) else {}
        citations = payload.get("citations") or record.get("citations") or ()
        retrieved = (
            payload.get("retrieved_ids")
            or payload.get("selected_ids")
            or payload.get("selected_shards")
            or payload.get("selected")
            or payload.get("results")
            or citations
            or ()
        )
        trace_value = payload.get("trace") or record.get("trace")
        trace = trace_value if isinstance(trace_value, Mapping) else {}
        route = payload.get("route") or _nested(trace, "confidence", "decision")
        latency = (
            payload.get("latency_ms")
            or _nested(trace, "latency_ms", "total")
            or 0.0
        )
        reads = (
            payload.get("vector_reads")
            or _nested(trace, "budgets", "reads")
            or _nested(trace, "coverage", "budgets", "reads")
            or _nested(trace, "selection", "budgets", "reads")
            or 0
        )
        tokens = (
            payload.get("tokens")
            or _nested(trace, "budgets", "tokens")
            or _nested(trace, "coverage", "budgets", "tokens")
            or _nested(trace, "selection", "budgets", "tokens")
            or 0
        )
        return cls(
            retrieved_ids=_result_ids(retrieved),
            answer=(str(payload["answer"]) if payload.get("answer") is not None else None),
            citations=_result_ids(citations),
            route=str(route) if route is not None else None,
            evidence_found=(
                bool(payload["evidence_found"])
                if payload.get("evidence_found") is not None
                else None
            ),
            latency_ms=float(latency),
            vector_reads=int(reads),
            tokens=int(tokens),
            index_size_bytes=int(payload.get("index_size_bytes") or 0),
            as_of_correct=(
                bool(payload["as_of_correct"])
                if payload.get("as_of_correct") is not None
                else None
            ),
            delta_snippet_correct=(
                bool(payload["delta_snippet_correct"])
                if payload.get("delta_snippet_correct") is not None
                else None
            ),
            metadata=dict(payload.get("metadata") or {}),
        )


Runner = Callable[
    [EvaluationCase, AblationVariant], EvaluationOutcome | Mapping[str, Any]
]


@dataclass(frozen=True)
class AblationResult:
    variant: AblationVariant
    metrics: dict[str, float]
    cases_evaluated: int
    elapsed_s: float
    wall_time_budget_s: float | None
    budget_exhausted: bool


@dataclass(frozen=True)
class AblationReport:
    generated_at: str
    total_cases: int
    equal_wall_time_budget_s: float | None
    results: tuple[AblationResult, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "total_cases": self.total_cases,
            "equal_wall_time_budget_s": self.equal_wall_time_budget_s,
            "results": [asdict(result) for result in self.results],
        }


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _aggregate_metrics(
    cases: Sequence[EvaluationCase], outcomes: Sequence[EvaluationOutcome]
) -> dict[str, float]:
    rankings = [outcome.retrieved_ids for outcome in outcomes]
    relevant = [case.relevant_ids for case in cases]
    metrics: dict[str, float] = {
        "recall_at_1": _mean(
            [recall_at_k(ranking, expected, 1) for ranking, expected in zip(rankings, relevant)]
        ),
        "recall_at_5": _mean(
            [recall_at_k(ranking, expected, 5) for ranking, expected in zip(rankings, relevant)]
        ),
        "recall_at_20": _mean(
            [recall_at_k(ranking, expected, 20) for ranking, expected in zip(rankings, relevant)]
        ),
        "mrr": mean_reciprocal_rank(rankings, relevant),
        "mean_vector_reads": _mean([float(outcome.vector_reads) for outcome in outcomes]),
        "mean_tokens": _mean([float(outcome.tokens) for outcome in outcomes]),
        "mean_index_size_bytes": _mean(
            [float(outcome.index_size_bytes) for outcome in outcomes]
        ),
    }
    metrics.update(latency_percentiles([outcome.latency_ms for outcome in outcomes]))

    route_pairs = [
        (outcome.route or "", case.expected_route)
        for case, outcome in zip(cases, outcomes)
        if case.expected_route is not None
    ]
    metrics["misrouting_rate"] = (
        misrouting_rate(
            [predicted for predicted, _ in route_pairs],
            [str(expected) for _, expected in route_pairs],
        )
        if route_pairs
        else 0.0
    )

    evidence_checks: list[bool] = []
    for case, outcome in zip(cases, outcomes):
        if outcome.evidence_found is not None:
            evidence_checks.append(outcome.evidence_found)
        elif case.relevant_ids:
            evidence_checks.append(bool(set(case.relevant_ids) & set(outcome.retrieved_ids)))
    metrics["missed_evidence_rate"] = missed_evidence_rate(evidence_checks)
    for route in ("local", "anchors", "global"):
        route_checks: list[bool] = []
        for case, outcome in zip(cases, outcomes):
            if outcome.route != route:
                continue
            if outcome.evidence_found is not None:
                route_checks.append(outcome.evidence_found)
            elif case.relevant_ids:
                route_checks.append(
                    bool(set(case.relevant_ids) & set(outcome.retrieved_ids))
                )
        metrics[f"missed_evidence_rate_{route}"] = missed_evidence_rate(route_checks)

    answer_pairs = [
        (outcome.answer or "", case.expected_answer)
        for case, outcome in zip(cases, outcomes)
        if case.expected_answer is not None
    ]
    metrics["qa_exact_match"] = _mean(
        [qa_exact_match(prediction, expected) for prediction, expected in answer_pairs]
    )
    metrics["qa_token_f1"] = _mean(
        [qa_token_f1(prediction, expected) for prediction, expected in answer_pairs]
    )

    citation_scores = [
        citation_precision_recall_f1(outcome.citations, case.expected_citations)
        for case, outcome in zip(cases, outcomes)
        if case.expected_citations
    ]
    metrics["citation_precision"] = _mean(
        [score["precision"] for score in citation_scores]
    )
    metrics["citation_recall"] = _mean([score["recall"] for score in citation_scores])
    metrics["citation_f1"] = _mean([score["f1"] for score in citation_scores])

    version_checks = [
        bool(outcome.as_of_correct)
        for case, outcome in zip(cases, outcomes)
        if case.as_of is not None and outcome.as_of_correct is not None
    ]
    metrics["as_of_accuracy"] = as_of_accuracy(version_checks)
    delta_checks = [
        bool(outcome.delta_snippet_correct)
        for outcome in outcomes
        if outcome.delta_snippet_correct is not None
    ]
    metrics["delta_snippet_accuracy"] = as_of_accuracy(delta_checks)
    return metrics


def run_ablation(
    cases: Iterable[EvaluationCase],
    runner: Runner,
    *,
    variants: Sequence[AblationVariant] = ABLATION_LADDER,
    wall_time_budget_s: float | None = None,
    output_path: str | Path | None = None,
) -> AblationReport:
    """Run every variant with the same per-variant wall-time budget.

    The runner owns configuration of the real or synthetic orchestrator. It
    receives the case and the explicit feature contract for the current rung.
    """
    case_list = list(cases)
    if wall_time_budget_s is not None and wall_time_budget_s <= 0:
        raise ValueError("wall_time_budget_s must be > 0")
    if not variants:
        raise ValueError("variants must not be empty")

    results: list[AblationResult] = []
    for variant in variants:
        started = time.perf_counter()
        evaluated_cases: list[EvaluationCase] = []
        outcomes: list[EvaluationOutcome] = []
        for case in case_list:
            if (
                wall_time_budget_s is not None
                and time.perf_counter() - started >= wall_time_budget_s
            ):
                break
            raw_outcome = runner(case, variant)
            outcome = (
                raw_outcome
                if isinstance(raw_outcome, EvaluationOutcome)
                else EvaluationOutcome.from_mapping(raw_outcome)
            )
            evaluated_cases.append(case)
            outcomes.append(outcome)
        elapsed = time.perf_counter() - started
        results.append(
            AblationResult(
                variant=variant,
                metrics=_aggregate_metrics(evaluated_cases, outcomes),
                cases_evaluated=len(evaluated_cases),
                elapsed_s=elapsed,
                wall_time_budget_s=wall_time_budget_s,
                budget_exhausted=len(evaluated_cases) < len(case_list),
            )
        )

    report = AblationReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        total_cases=len(case_list),
        equal_wall_time_budget_s=wall_time_budget_s,
        results=tuple(results),
    )
    if output_path is not None:
        write_ablation_report(report, output_path)
    return report


def write_ablation_report(report: AblationReport, path: str | Path) -> Path:
    """Write a stable, diffable JSON evaluation artifact."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output_path


def plot_metric_curve(
    report: AblationReport, metric: str, path: str | Path
) -> Path:
    """Optionally plot one ladder metric when matplotlib is installed."""
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("plotting ablation curves requires matplotlib") from exc

    labels = [result.variant.label for result in report.results]
    values = [result.metrics.get(metric, 0.0) for result in report.results]
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(max(8, len(labels) * 1.2), 4.5))
    axis.plot(range(len(labels)), values, marker="o")
    axis.set_xticks(range(len(labels)), labels, rotation=35, ha="right")
    axis.set_ylabel(metric)
    axis.set_title(f"F-RAM ablation ladder: {metric}")
    figure.tight_layout()
    figure.savefig(output_path)
    plt.close(figure)
    return output_path


__all__ = [
    "ABLATION_LADDER",
    "AblationReport",
    "AblationResult",
    "AblationVariant",
    "EvaluationOutcome",
    "plot_metric_curve",
    "run_ablation",
    "write_ablation_report",
]
