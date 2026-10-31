import json

from fram_eval.ablations import (
    ABLATION_LADDER,
    EvaluationOutcome,
    run_ablation,
)
from fram_eval.datasets import synthetic_layout_cases


def test_ablation_ladder_matches_spec_order():
    assert [variant.stage for variant in ABLATION_LADDER] == list(range(1, 9))
    assert ABLATION_LADDER[0].label == "Flat HNSW + reranker"
    assert ABLATION_LADDER[-1].label == "Version lattice + delta policy"
    assert "layout_constraints" in ABLATION_LADDER[6].enabled_features


def test_outcome_normalizes_query_orchestrator_shape():
    outcome = EvaluationOutcome.from_mapping(
        {
            "answer": "answer",
            "citations": ["doc.md:chunk1"],
            "record": {
                "trace": {
                    "confidence": {"decision": "anchors"},
                    "coverage": {"budgets": {"reads": 4, "tokens": 32}},
                    "latency_ms": {"total": 12.5},
                }
            },
        }
    )
    assert outcome.retrieved_ids == ("doc.md:chunk1",)
    assert outcome.citations == ("doc.md:chunk1",)
    assert outcome.route == "anchors"
    assert outcome.vector_reads == 4
    assert outcome.tokens == 32
    assert outcome.latency_ms == 12.5


def test_tiny_ablation_writes_json_metrics(tmp_path):
    cases = synthetic_layout_cases()

    def runner(case, variant):
        return EvaluationOutcome(
            retrieved_ids=(case.relevant_ids[0], "noise"),
            answer=str(case.expected_answer),
            citations=case.expected_citations,
            evidence_found=True,
            latency_ms=float(variant.stage * 10),
            vector_reads=variant.stage,
            tokens=20,
            index_size_bytes=1024,
        )

    output = tmp_path / "reports" / "ablation.json"
    report = run_ablation(
        cases,
        runner,
        variants=ABLATION_LADDER[:2],
        wall_time_budget_s=1.0,
        output_path=output,
    )

    assert len(report.results) == 2
    assert all(result.cases_evaluated == len(cases) for result in report.results)
    assert all(result.metrics["recall_at_1"] == 1.0 for result in report.results)
    assert all(result.metrics["mrr"] == 1.0 for result in report.results)
    assert all(result.metrics["citation_f1"] == 1.0 for result in report.results)
    assert all(
        result.metrics["mean_index_size_bytes"] == 1024.0 for result in report.results
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["equal_wall_time_budget_s"] == 1.0
    assert payload["results"][0]["variant"]["key"] == "flat_hnsw_reranker"
