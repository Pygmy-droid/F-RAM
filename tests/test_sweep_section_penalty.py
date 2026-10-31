from scripts import sweep_section_penalty as sweep

from fram_serving.config import FRAMConfig


def test_runrecord_from_trace_extracts_metrics():
    trace = {
        "confidence": {"decision": "anchors"},
        "selection": {
            "anchors": [{"id": 1}, {"id": 2}],
            "segments_diversity": 0.5,
            "coverage_delta": {"total": 0.75},
            "budgets": {"reads_used": 1.0},
        },
        "coverage": {"section_diversity": 0.6},
    }
    record = sweep.RunRecord.from_trace("query", trace, ["cite"])
    assert record.decision == "anchors"
    assert record.anchor_count == 2
    assert record.segments_diversity == 0.5
    assert record.section_diversity == 0.6
    assert record.citations == 1
    assert record.coverage_delta == 0.75
    assert record.reads_used == 1.0


def test_summarise_handles_records():
    records = [
        sweep.RunRecord(
            question="q1",
            decision="anchors",
            anchor_count=2,
            segments_diversity=0.4,
            section_diversity=0.5,
            citations=2,
            coverage_delta=0.7,
            reads_used=1.0,
        ),
        sweep.RunRecord(
            question="q2",
            decision="local",
            anchor_count=0,
            segments_diversity=0.3,
            section_diversity=0.45,
            citations=1,
            coverage_delta=0.2,
            reads_used=0.0,
        ),
    ]
    summary = sweep._summarise(records)
    assert summary["queries"] == 2
    assert summary["anchor_decisions"] == 1
    assert summary["avg_anchor_count"] > 0
    assert summary["avg_section_diversity"] > 0
    assert summary["avg_segments_diversity"] > 0
    assert summary["avg_citations"] > 0
    assert summary["avg_reads_used"] >= 0
    assert summary["avg_coverage_delta"] > 0


def test_apply_penalty_updates_overrides_domain_and_task():
    cfg = FRAMConfig()
    updated = sweep._apply_penalty_updates(
        cfg,
        domain="roadmap",
        task="diary",
        repeat_penalty=0.95,
        penalty_floor=0.55,
    )
    assert updated.section_repeat_penalty == 0.95
    assert updated.section_penalty_floor == 0.55
    assert updated.domain_overrides["roadmap"]["section_repeat_penalty"] == 0.95
    assert updated.domain_overrides["roadmap"]["section_penalty_floor"] == 0.55
    assert updated.task_overrides["diary"]["section_repeat_penalty"] == 0.95
    assert updated.task_overrides["diary"]["section_penalty_floor"] == 0.55
