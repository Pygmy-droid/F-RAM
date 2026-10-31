#!/usr/bin/env python3
"""Check HTTP/MCP without printing content; memory-list may initialize metadata."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from urllib.parse import urlsplit

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def verify(base_url: str, timeout: float) -> dict:
    headers = {}
    if os.getenv("MCP_BEARER"):
        headers["Authorization"] = "Bearer " + os.environ["MCP_BEARER"]
    async with asyncio.timeout(timeout):
        async with httpx.AsyncClient(timeout=timeout, headers=headers) as http:
            health = await http.get(base_url + "/health")
            health.raise_for_status()
            if health.json().get("status") != "ok":
                raise RuntimeError("health check failed")
            config = await http.get(base_url + "/config")
            config.raise_for_status()
            if "api_key" in config.json():
                raise RuntimeError("REST config contains a secret field")
        async with streamablehttp_client(
            base_url + "/mcp/",
            headers=headers,
            timeout=timeout,
            sse_read_timeout=timeout,
        ) as (read, write, _):
            async with ClientSession(read, write) as session:
                initialized = await session.initialize()
                tools = await session.list_tools()
                listed = await session.call_tool("fram.memory_list", {})
                if listed.isError:
                    raise RuntimeError("memory-list tool failed")
                resource = await session.read_resource("fram://config")
                if not resource.contents:
                    raise RuntimeError("MCP config is missing")
                for content in resource.contents:
                    text = getattr(content, "text", None)
                    if text is None or "api_key" in json.loads(text):
                        raise RuntimeError(
                            "MCP config contains a secret field or is invalid"
                        )
                return {
                    "status": "PASS",
                    "server": initialized.serverInfo.name,
                    "protocol": initialized.protocolVersion,
                    "health": "ok",
                    "rest_config_redacted": True,
                    "mcp_config_redacted": True,
                    "memory_list": "ok (contents omitted)",
                    "tools": [
                        {
                            "name": tool.name,
                            "read_only_hint": (
                                tool.annotations.readOnlyHint
                                if tool.annotations
                                else None
                            ),
                        }
                        for tool in tools.tools
                    ],
                }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=float, default=60)
    args = parser.parse_args()
    url = urlsplit(args.base_url)
    if (
        url.scheme not in {"http", "https"}
        or not url.hostname
        or url.username
        or url.password
        or url.query
        or url.fragment
    ):
        parser.error("Use an HTTP(S) base URL without credentials, query, or fragment")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    try:
        result = asyncio.run(verify(args.base_url.rstrip("/"), args.timeout))
    except Exception as exc:
        # Upstream exceptions can contain response bodies; never echo them.
        print(json.dumps({"status": "FAIL", "error_type": type(exc).__name__}))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
