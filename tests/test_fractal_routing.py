from __future__ import annotations

from datetime import datetime

from fram_core.pipeline import QueryOrchestrator
from fram_serving.config import FRAMConfig


def test_fractal_segment_hierarchy_in_trace():
    cfg = FRAMConfig()
    cfg = cfg.model_copy(update={"fractal_enabled": True, "default_query_reads": 2})
    orch = QueryOrchestrator(config=cfg)

    result = orch.run("What is FRAM?", as_of=None, budget_reads=2, domain="general", task="qa")
    record = result["record"]
    trace = record["trace"]

    # Baseline: still includes per-chunk hierarchy list
    assert "hierarchy" in trace

    # Fractal (segment) scale nodes are recorded
    scales = trace.get("hierarchy_scales")
    assert isinstance(scales, list)
    # When enabled, we expect at least one scale entry with 'segment'
    assert any(entry.get("scale") == "segment" and isinstance(entry.get("nodes"), list) for entry in scales)

