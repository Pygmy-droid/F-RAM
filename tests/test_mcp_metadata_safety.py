import json
from types import SimpleNamespace

import pytest

from fram_serving import mcp_server
from fram_serving.config import FRAMConfig
from fram_serving.memory import WorkingMemoryStore


@pytest.mark.asyncio
async def test_mcp_annotations_distinguish_reads_from_telemetry_and_mutations():
    tools = {tool.name: tool for tool in await mcp_server.mcp.list_tools()}
    assert len(tools) == 9
    readonly = {"fram.get_trace_uri"}
    for name, tool in tools.items():
        assert tool.annotations is not None
        assert tool.annotations.readOnlyHint is (name in readonly)
    assert tools["fram.memory_clear"].annotations.destructiveHint is True
    assert tools["fram.query"].annotations.idempotentHint is False
    assert tools["fram.memory_bootstrap"].annotations.idempotentHint is False


@pytest.mark.asyncio
@pytest.mark.parametrize("model_config", [True, False])
async def test_mcp_config_omits_secret_without_modifying_source(
    monkeypatch, model_config
):
    secret = "synthetic-test-only-config-secret"
    cfg = (
        FRAMConfig(api_key=secret)
        if model_config
        else SimpleNamespace(api_key=secret, k0=32)
    )
    monkeypatch.setattr(mcp_server, "_get_state", lambda: SimpleNamespace(config=cfg))
    encoded = await mcp_server.read_config()
    payload = json.loads(encoded)
    assert "api_key" not in payload
    assert secret not in encoded
    assert payload["k0"] == 32
    assert cfg.api_key == secret


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["get", "list"])
async def test_memory_read_names_can_materialize_metadata(
    monkeypatch, tmp_path, method
):
    store = WorkingMemoryStore(tmp_path)
    monkeypatch.setattr(
        mcp_server, "_get_state", lambda: SimpleNamespace(memory_store=store)
    )

    class Context:
        async def debug(self, message):
            pass

    if method == "get":
        await mcp_server.fram_memory_get(Context(), "probe")
    else:
        (tmp_path / "probe.jsonl").write_text("", encoding="utf-8")
        await mcp_server.fram_memory_list(Context())
    assert (tmp_path / "probe.meta.json").exists()
