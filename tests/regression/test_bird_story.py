from __future__ import annotations

import os
from typing import Generator

import pytest

from fram_serving.config import FRAMConfig
from fram_core.pipeline import QueryOrchestrator


@pytest.fixture(scope="module")
def engine() -> QueryOrchestrator:
    config = FRAMConfig()
    return QueryOrchestrator(config=config)


def _p_temp(trace: dict) -> float:
    value = trace.get("p_temp")
    assert value is not None
    return float(value)


def test_aria_resting_spot(engine: QueryOrchestrator) -> None:
    result = engine.run("Where does Aria rest in spring?", None, engine.config.default_query_reads, "general", "qa")
    answer = (result.get("answer") or "").lower()
    assert "platte river" in answer or "niobrara river" in answer
    assert result.get("citations"), "expected citations for Aria answer"


def test_qa_fallback_env_guard(monkeypatch: pytest.MonkeyPatch, engine: QueryOrchestrator) -> None:
    monkeypatch.setenv("FRAM_STRICT_QA_FALLBACK", "1")
    try:
        result = engine.run("Where does Aria rest in spring?", None, engine.config.default_query_reads, "general", "qa")
    finally:
        monkeypatch.delenv("FRAM_STRICT_QA_FALLBACK", raising=False)

    decision = result["record"]["trace"]["confidence"]["decision"]
    assert decision == "global"


def test_puffins_qa_confidence(engine: QueryOrchestrator) -> None:
    result = engine.run("Where do puffins winter?", None, engine.config.default_query_reads, "general", "qa")
    p_temp = _p_temp(result["record"]["trace"])
    assert p_temp <= 0.60


def test_puffins_definitional_anchored(engine: QueryOrchestrator) -> None:
    result = engine.run("Where do puffins winter?", None, engine.config.default_query_reads, "general", "definitional")
    trace = result["record"]["trace"]
    decision = trace.get("confidence", {}).get("decision")
    assert decision in {"anchors", "global"}
