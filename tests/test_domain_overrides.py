from fram_serving.config import FRAMConfig
from fram_core.pipeline import QueryOrchestrator


def test_domain_override_adjusts_budget_reads(tmp_path):
    cfg = FRAMConfig()
    persist_path = tmp_path / "demo_corpus"
    orchestrator = QueryOrchestrator(config=cfg, persist_path=persist_path)
    orchestrator.ensure_corpus()

    baseline = orchestrator.run(
        "What is the F-RAM roadmap vision?",
        None,
        budget_reads=cfg.default_query_reads,
        domain="general",
        task="qa",
    )
    assert baseline["record"]["trace"]["budget_reads"] == cfg.default_query_reads

    roadmap = orchestrator.run(
        "What is the F-RAM roadmap vision?",
        None,
        budget_reads=cfg.default_query_reads,
        domain="roadmap",
        task="qa",
    )
    assert roadmap["record"]["trace"]["budget_reads"] == 5.0
