import json
import anyio
import pytest
from fastapi.testclient import TestClient
from mcp.client.session import ClientSession
import mcp.types as mcp_types

from fram_serving import mcp_server
from fram_serving.app import app
from fram_serving.config import FRAMConfig


class _DummyContext:
    async def info(self, *args, **kwargs) -> None:  # pragma: no cover - logging helper
        return None

    async def debug(self, *args, **kwargs) -> None:  # pragma: no cover - logging helper
        return None


@pytest.fixture(autouse=True)
def _reset_state(tmp_path):
    cfg = FRAMConfig().model_copy(update={"STORAGE_ROOT": tmp_path / "storage"})
    mcp_server._STATE = mcp_server._build_state(config=cfg)
    try:
        yield
    finally:
        mcp_server._STATE = None


@pytest.mark.asyncio
async def test_mcp_tools_registered():
    tools = await mcp_server.mcp.list_tools()
    names = {tool.name for tool in tools}
    assert {
        "fram.query",
        "fram.get_trace_uri",
        "fram.memory_list",
        "fram.memory_create",
        "fram.memory_bootstrap",
    }.issubset(names)


@pytest.mark.asyncio
async def test_fram_query_returns_trace_uri():
    ctx = _DummyContext()
    result = await mcp_server.fram_query(ctx, query="hello world")

    assert "answer" in result
    assert result.get("cognitive_episode_write_ok") is False
    assert "trace_uri" in result
    trace_uri = result["trace_uri"]
    assert isinstance(trace_uri, str)
    assert trace_uri.startswith("fram://trace/")

    trace_id = trace_uri.rsplit("/", 1)[-1]
    trace_payload = await mcp_server.read_trace(trace_id)
    assert trace_id in trace_payload

    last_uri = await mcp_server.fram_get_trace_uri(ctx)
    assert last_uri == trace_uri


@pytest.mark.asyncio
async def test_fram_query_persist_gate_off(tmp_path):
    cfg = FRAMConfig().model_copy(
        update={"STORAGE_ROOT": tmp_path / "storage", "mcp_cognitive_write_enabled": False}
    )
    mcp_server._STATE = mcp_server._build_state(config=cfg)
    ctx = _DummyContext()

    result = await mcp_server.fram_query(ctx, query="no persist", persist_cognitive=True)
    assert result.get("cognitive_episode_write_ok") is False

    state = mcp_server._get_state()
    episodes_path = (
        state.config.STORAGE_ROOT
        / state.config.STORAGE_SUBFOLDERS.get("memory", "memory")
        / "cognitive"
        / "episodes.jsonl"
    )
    assert not episodes_path.exists()


@pytest.mark.asyncio
async def test_fram_query_persist_gate_on(tmp_path):
    cfg = FRAMConfig().model_copy(
        update={"STORAGE_ROOT": tmp_path / "storage", "mcp_cognitive_write_enabled": True}
    )
    mcp_server._STATE = mcp_server._build_state(config=cfg)
    ctx = _DummyContext()

    result = await mcp_server.fram_query(ctx, query="persist ok", persist_cognitive=True)
    assert result.get("cognitive_episode_write_ok") is True

    state = mcp_server._get_state()
    episodes_path = (
        state.config.STORAGE_ROOT
        / state.config.STORAGE_SUBFOLDERS.get("memory", "memory")
        / "cognitive"
        / "episodes.jsonl"
    )
    assert episodes_path.exists()


@pytest.mark.asyncio
async def test_memory_tools_and_query_flow(tmp_path):
    ctx = _DummyContext()

    created = await mcp_server.fram_memory_create(ctx, session_id="cli-session")
    assert created["ui_url"].endswith("session=cli-session") or created["ui_url"].endswith("/ui/memory")
    session = created["session"]
    assert session["status"] == "active"

    entry = await mcp_server.fram_memory_append(ctx, "cli-session", text="note about FRAM")
    assert entry["text"].startswith("note")
    assert entry["ui_url"].endswith("session=cli-session") or entry["ui_url"].endswith("/ui/memory")

    paused = await mcp_server.fram_memory_control(ctx, "cli-session", action="pause")
    assert paused["session"]["status"] == "paused"
    assert paused["ui_url"].endswith("session=cli-session") or paused["ui_url"].endswith("/ui/memory")

    with pytest.raises(ValueError):
        await mcp_server.fram_memory_append(ctx, "cli-session", text="should fail")

    paused_query = await mcp_server.fram_query(ctx, query="What is saved?", memory_session="cli-session")
    assert paused_query["memory"]["status"] == "paused"
    assert paused_query["memory"]["used"] == 0
    assert paused_query["memory_ui"].endswith("session=cli-session") or paused_query["memory_ui"].endswith("/ui/memory")

    resumed = await mcp_server.fram_memory_control(ctx, "cli-session", action="resume")
    assert resumed["session"]["status"] == "active"
    assert resumed["ui_url"].endswith("session=cli-session") or resumed["ui_url"].endswith("/ui/memory")

    active_query = await mcp_server.fram_query(ctx, query="Use memory", memory_session="cli-session")
    active_memory = active_query["memory"]
    assert active_memory["status"] == "active"
    assert active_memory["used"] >= 1
    assert active_query["memory_ui"].endswith("session=cli-session") or active_query["memory_ui"].endswith("/ui/memory")

    ended = await mcp_server.fram_memory_control(ctx, "cli-session", action="end")
    assert ended["session"]["status"] == "ended"
    assert ended["ui_url"].endswith("session=cli-session") or ended["ui_url"].endswith("/ui/memory")

    ended_query = await mcp_server.fram_query(ctx, query="Ended session", memory_session="cli-session")
    assert ended_query["memory"]["status"] == "ended"
    assert ended_query["memory"]["used"] == 0
    assert ended_query["memory_ui"].endswith("session=cli-session") or ended_query["memory_ui"].endswith("/ui/memory")

    cleared = await mcp_server.fram_memory_clear(ctx, "cli-session")
    assert cleared["session"]["entry_count"] == 0
    assert cleared["ui_url"].endswith("session=cli-session") or cleared["ui_url"].endswith("/ui/memory")

    fetched = await mcp_server.fram_memory_get(ctx, "cli-session", include_entries=True)
    assert fetched["session"]["status"] == "ended"
    assert fetched.get("entries") == []
    assert fetched["ui_url"].endswith("session=cli-session") or fetched["ui_url"].endswith("/ui/memory")

    sessions = await mcp_server.fram_memory_list(ctx)
    assert any(item["id"] == "cli-session" for item in sessions)
    assert all("ui_url" in item for item in sessions)

    state = mcp_server._get_state()
    obs_root = state.config.STORAGE_ROOT / state.config.STORAGE_SUBFOLDERS.get("observability", "observability")
    log_path = obs_root / "memory_sessions.jsonl"
    records = []
    if log_path.exists():
        records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(rec.get("event") == "control" and rec.get("action") == "pause" for rec in records)
    assert any(rec.get("event") == "query" and rec.get("status") == "active" for rec in records)


@pytest.mark.asyncio
async def test_memory_append_dedupe_guard():
    ctx = _DummyContext()

    created = await mcp_server.fram_memory_create(ctx, session_id="dedupe-session")
    assert created["session"]["status"] == "active"

    first = await mcp_server.fram_memory_append(ctx, "dedupe-session", text="duplicate note")
    second = await mcp_server.fram_memory_append(ctx, "dedupe-session", text="duplicate note")

    assert second.get("deduped") is True
    assert second.get("id") == first.get("id")

    fetched = await mcp_server.fram_memory_get(ctx, "dedupe-session", include_entries=True)
    assert fetched["session"]["entry_count"] == 1
    assert len(fetched.get("entries", [])) == 1


@pytest.mark.asyncio
async def test_memory_bootstrap_tool(tmp_path):
    ctx = _DummyContext()
    state = mcp_server._get_state()
    state.cognitive_store.append_episode(
        query="Always-on memory progress",
        domain="general",
        task="qa",
        answer="Telemetry logging is now persisted to memory_cognitive.jsonl.",
        citations=["log.md:chunk0"],
        trace_id="telemetry-trace",
    )

    search = await mcp_server.fram_memory_bootstrap(ctx, query="always-on memory", k=3)
    assert search["mode"] == "search"
    assert search["event"]["selected_count"] >= 1
    assert isinstance(search["results"], list) and search["results"]

    log_path = mcp_server._get_state().observability_dir / "memory_cognitive.jsonl"
    assert log_path.exists()

    summary = await mcp_server.fram_memory_bootstrap(ctx, window=1)
    assert summary["mode"] == "summary"
    assert "counts" in summary
    assert summary["counts"]["episodes"] >= 1


def test_health_endpoint_available():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("status") == "ok"


@pytest.mark.asyncio
async def test_tool_call_works_without_initialized_notification(monkeypatch, tmp_path):
    cfg = FRAMConfig().model_copy(update={"STORAGE_ROOT": tmp_path / "storage"})
    original_build_state = mcp_server._build_state

    def _build_state_override(config=None):
        return original_build_state(config=cfg)

    monkeypatch.setattr(mcp_server, "_build_state", _build_state_override)

    client_to_server_send, client_to_server_receive = anyio.create_memory_object_stream(0)
    server_to_client_send, server_to_client_receive = anyio.create_memory_object_stream(0)

    server = mcp_server.mcp._mcp_server
    init_options = server.create_initialization_options()

    async with anyio.create_task_group() as tg:
        tg.start_soon(server.run, client_to_server_receive, server_to_client_send, init_options)

        async with ClientSession(server_to_client_receive, client_to_server_send) as client:
            await client.send_request(
                mcp_types.ClientRequest(
                    mcp_types.InitializeRequest(
                        params=mcp_types.InitializeRequestParams(
                            protocolVersion=mcp_types.LATEST_PROTOCOL_VERSION,
                            capabilities=mcp_types.ClientCapabilities(
                                sampling=None,
                                elicitation=None,
                                experimental=None,
                                roots=None,
                            ),
                            clientInfo=mcp_types.Implementation(name="test", version="0"),
                        )
                    )
                ),
                mcp_types.InitializeResult,
            )

            created = await client.call_tool("fram.memory_create", {"session_id": "preinit-session"})
            assert created.isError is False

            fetched = await client.call_tool(
                "fram.memory_get",
                {"session_id": "preinit-session", "include_entries": True},
            )
            assert fetched.isError is False
            assert fetched.structuredContent is not None
            assert fetched.structuredContent["session"]["id"] == "preinit-session"
            assert fetched.structuredContent.get("entries") == []

        tg.cancel_scope.cancel()
