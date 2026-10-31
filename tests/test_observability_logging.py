import asyncio
import json

from fastapi.testclient import TestClient
import pytest

from fram_serving import mcp_server, observability
from fram_serving.app import CFG, app


class _DummyContext:
    async def info(self, *args, **kwargs) -> None:
        return None

    async def debug(self, *args, **kwargs) -> None:
        return None


@pytest.mark.slow
def test_observability_logging_and_trace_lookup(tmp_path, monkeypatch):
    # Direct logging helpers still append JSONL
    obs_dir = tmp_path / "obs"
    observability.log_confidence_event(obs_dir, {"prob": 0.5, "decision": "local"})
    observability.log_latency_event(obs_dir, {"query_id": "q1", "latency_ms": {"total": 1.0}})

    conf_path = obs_dir / "confidence.jsonl"
    lat_path = obs_dir / "latency.jsonl"
    assert conf_path.exists()
    assert lat_path.exists()
    confidence_record = json.loads(conf_path.read_text().splitlines()[0])
    assert confidence_record["prob"] == 0.5

    async def _exercise_mcp():
        mcp_server._STATE = mcp_server._build_state()
        try:
            ctx = _DummyContext()
            result = await mcp_server.fram_query(ctx, query="trace demo")
            trace_uri = result["trace_uri"]
            assert trace_uri.startswith("fram://trace/")
            trace_id = trace_uri.rsplit("/", 1)[-1]
            trace_payload = await mcp_server.read_trace(trace_id)
            assert trace_id in trace_payload
            config_payload = await mcp_server.read_config()
            assert '"k0"' in config_payload
            assert await mcp_server.fram_get_trace_uri(ctx) == trace_uri
        finally:
            mcp_server._STATE = None

    asyncio.run(_exercise_mcp())

    # Wire endpoints to temporary storage for trace validation
    monkeypatch.setattr(app, "_DOC_CACHE", None, raising=False)
    monkeypatch.setattr(app, "_ORCHESTRATOR", None, raising=False)
    monkeypatch.setattr(CFG, "STORAGE_ROOT", tmp_path)

    with TestClient(app) as client:
        query_resp = client.post("/query", json={"text": "query trace demo"})
        assert query_resp.status_code == 200
        query_data = query_resp.json()
        rid2 = query_data["id"]
        assert rid2 == query_data["trace"]["query_id"]

    traces_dir = CFG.STORAGE_ROOT / CFG.STORAGE_SUBFOLDERS.get("traces", "traces")
    trace_files = list(traces_dir.glob("*.jsonl"))
    assert trace_files
    combined = "\n".join(f.read_text() for f in trace_files)
    assert rid2 in combined
