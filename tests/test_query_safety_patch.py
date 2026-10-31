import pytest
from fastapi.testclient import TestClient

import fram_serving.app as app


@pytest.mark.slow
def test_query_accepts_budget_alias_and_records_clock():
    with TestClient(app.app) as client:
        resp = client.post("/query", json={"text": "budget alias test", "budget": 2})
        assert resp.status_code == 200
        payload = resp.json()

    budgets = payload["trace"]["selection"]["budgets"]
    assert budgets["reads_limit"] == pytest.approx(2.0)

    clock = payload["trace"].get("clock")
    assert isinstance(clock, dict)
    assert "utc_iso" in clock


@pytest.mark.slow
def test_query_reports_cognitive_episode_write_failure(monkeypatch):
    def _boom(*args, **kwargs):
        raise RuntimeError("forced failure")

    monkeypatch.setattr(app._COG_STORE, "append_episode", _boom)
    with TestClient(app.app) as client:
        resp = client.post("/query", json={"text": "persist failure test"})
        assert resp.status_code == 200
        payload = resp.json()

    assert payload["cognitive_episode_write_ok"] is False
    trace_block = payload["trace"].get("cognitive_episode_write")
    assert isinstance(trace_block, dict)
    assert trace_block.get("ok") is False
    assert "error" in trace_block

