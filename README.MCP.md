# FRAM v2.2 MCP Connector

## Tools & Resources
- Tools: `fram.query`, `fram.memory_list`, `fram.memory_get`, `fram.memory_create`, `fram.memory_control`, `fram.memory_append`, `fram.memory_clear`, `fram.memory_bootstrap`, `fram.get_trace_uri`
- Resources: `fram://trace/{id}`, `fram://config`

## Configuration
- `FRAM_MEMORY_UI_BASE`: optional absolute base (e.g., `https://your-host`) used when emitting UI links from MCP tools. Defaults to `/ui/memory`.
- `FRAM_WORKING_MEMORY_DEDUPE_WINDOW_SEC`: short window (seconds) to ignore duplicate memory appends (default 2). Set to `0` to disable.
- `idempotency_key`: optional per-append key to dedupe retries. For MCP, include it in `metadata`; for REST, pass `idempotency_key` in the JSON body.

## Local Development
1. Windows: `powershell -File scripts/make_it_work.ps1`. Linux (or macOS with Bash 4.4+):
   `bash scripts/make_it_work.sh --python python3.12` (Python 3.11 also supported).
2. Setup installs the core project/development tools into a local `.venv`;
   it does not hydrate memory or start a server. Optional visual packages are separate.
3. Start with `powershell -File scripts/dev_run.ps1` or
   `bash scripts/dev_run.sh`. Both default to `http://127.0.0.1:8000`, an
   external per-user runtime, development profile off and cognitive autolog off.
4. Run `python scripts/verify_mcp.py` with that environment's Python. It checks
   HTTP health/config, MCP initialization, discovery, memory-list and config
   redaction without printing memory contents. Startup initializes runtime files;
   memory-list can materialize missing metadata in a legacy store.

See [Windows, Linux Mint and ChatGPT web](docs/portable_mcp_setup.md) for the
separate platform gates and an isolated first-run recipe. Do not copy a Windows
`.venv` to Linux. Launchers do not load `.env` automatically or synthesize a token.

## JSON-RPC Smoke Test
```bash
# Note: use `/mcp/` (trailing slash) and include `Accept: application/json, text/event-stream`.
auth_args=()
if [[ -n "${MCP_BEARER:-}" ]]; then
  auth_args=(-H "Authorization: Bearer $MCP_BEARER")
fi
curl -i -X POST http://localhost:8000/mcp/ \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  "${auth_args[@]}" \
  -d '{"jsonrpc":"2.0","id":"init","method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}'

# After the response, copy the `Mcp-Session-Id` header value into $SESSION_ID and finalize init:
curl -X POST http://localhost:8000/mcp/ \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  "${auth_args[@]}" \
  -H "Mcp-Session-Id: ${SESSION_ID}" \
  -d '{"jsonrpc":"2.0","method":"notifications/initialized","params":null}'
```

## ChatGPT Connector Setup
ChatGPT web needs a reachable MCP connection. Its documented direct auth choices
are OAuth, no auth, or mixed auth; the old instruction to paste an arbitrary
bearer token into ChatGPT was not a verified setup path. See the
[official developer-mode guide](https://developers.openai.com/api/docs/guides/developer-mode).

For private development, evaluate
[Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)
with an isolated synthetic runtime first. This avoids public inbound exposure;
account/workspace permissions and an actual ChatGPT call still need verification.
The existing static bearer verifier is not an OAuth authorization server.

The server advertises nine tools, including working-memory mutations. The
project's Codex client allowlist does not restrict a different ChatGPT client.
Only `fram.get_trace_uri` is annotated read-only. Memory list/get can initialize
missing session metadata; query and bootstrap search write telemetry. Tool
annotations describe effects; they do not enforce access.

### MCP Runbook (clean demo loop)
1. Start the server on loopback with a new synthetic runtime.
2. Create a new `/memory` session.
3. Append 5–8 entries (one append per entry; wait for response).
4. Run `/query` once with `memory_session` to trigger capsule write-through.
5. (Optional) open `/ui/memory?session=<id>` to verify the session.

## Security Notes
- `ALLOWED_ORIGINS` is a browser CORS policy, not authentication.
- Use explicit credentials for clients requiring authentication; never use `change-me`.
- Public private-data access needs scoped authentication and TLS. The full
  FastAPI application includes REST write routes outside the MCP bearer check.
- Both REST `/config` and MCP `fram://config` omit `api_key`. Trace and memory
  resources can still contain private content; config redaction is not universal sanitization.

## Memory Session UI
- Point your browser at `http://localhost:8000/ui/memory` (or the deployed host) to manage working-memory sessions.
- The page wraps the `/memory` REST endpoints and mirrors the MCP memory tools so operators can create, pause/resume/end, append, or clear sessions without issuing raw tool calls.
- Any changes log to `storage/observability/memory_sessions.jsonl`, keeping telemetry consistent with the MCP workflows.
