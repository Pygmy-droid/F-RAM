# FRAM MCP Guide (Safe Context Gateway)

Purpose
MCP is the shared gateway for F-RAM to expose and consume context/tools across
agents. It is not a memory system. This guide defines the single safe flow and
guardrails that keep memory hygiene intact.

Principles
- One gateway: MCP is the common integration surface for Codex and future
  ChatGPT tool-calling or connectors.
- Review actual tool effects: retrieval can write traces and telemetry even
  when cognitive persistence is disabled.
- Memory hygiene is mandatory: run fram-memory-sanity-check before any write or persistence.
- Minimal surface: keep the MCP bundle small and audited.

When to use MCP
- Pull trusted docs or repo context.
- Inspect artifacts or tools in a bounded, read-only way.
- Enrich a task without expanding memory scope.

When not to use MCP
- As a persistence layer.
- To bypass memory gates or redaction rules.
- To mix holdout eval data with tuning data.

Approved MCP server categories (minimal set)
- Documentation servers (official docs, internal docs).
- Repo browsing servers (read-only).
- Issue or roadmap viewers (read-only).

The blessed flow (safe, repeatable)
1) Decide the context need and scope it to the task.
2) Connect via MCP (authenticated if required).
3) Pull context into the working session (ephemeral).
4) Run fram-memory-sanity-check before any write or persistence.
5) Record evidence: what was pulled, and why it was needed.

For cognitive episode persistence through `fram.query`, both
`FRAM_MCP_COGNITIVE_WRITE_ENABLED=1` and `persist_cognitive=true` are required.
This gate does not disable the working-memory create/control/append/clear tools,
query traces/archives, or bootstrap-search telemetry. Client allowlists and
tool-effect annotations do not replace server authorization.

Current setup, protocol checks and ChatGPT web prerequisites:
[portable MCP setup](portable_mcp_setup.md). MCP `fram://config` follows REST
`/config` secret-field redaction; neither endpoint should return `api_key`.

Guardrails
- Restrict the available mutation tools to the deliberately authorized scope.
- MCP may supply context, but F-RAM alone decides what persists.
- Redaction rules apply before any persistence or publish-safe trace output.
- Keep holdout eval data physically separate from tuning sources.
- Prefer summaries over raw dumps when sharing externally.

Success criteria
- Context is retrieved without changing memory state.
- Any memory change is explainable, gated, and logged.
- MCP use is auditable with clear scope and rationale.
