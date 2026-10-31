# Tool Surface Eval Matrix (2026-01-23)

Goal: show falsifiable evidence that new tool surfaces are gated, auditable, and
do not silently persist memory by default.

Skills (memory hygiene)
- Evidence: `skills/fram-memory-sanity-check/SKILL.md`
- Failure-first evals:
  - `tests/test_memory_capsule_retrieval.py::test_query_skips_memory_capsule_when_gate_off`
  - `tests/test_mcp_server.py::test_fram_query_persist_gate_off`
- Pass criteria: gate OFF => no retrieval/write, explicit skip in trace or file absence.

Eval-skills (regression discipline)
- Evidence: failure-first tests above plus standard MCP tool coverage in `tests/test_mcp_server.py`.
- Pass criteria: explicit refusal or skip when rules are violated; no silent writes.

App-server lifecycle (readiness check)
- Evidence:
  - `tests/test_cognitive_logging.py::test_seq_persists_across_restarts`
  - `tests/test_mcp_server.py::test_memory_tools_and_query_flow`
- Pass criteria: restart/resume keeps session state intact; no corruption across reload.

MCP gateway (ephemeral by default)
- Evidence:
  - `tests/test_mcp_server.py::test_fram_query_persist_gate_off`
  - `tests/test_mcp_server.py::test_fram_query_persist_gate_on`
- Pass criteria:
  - Default: no cognitive episode file written.
  - Gate ON + explicit request: episode file written.

AGENTS governance (invariants vs overrides)
- Evidence: `AGENTS.md` + `AGENTS.override.md`
- Pass criteria: invariants and workflow knobs are separated and audit-friendly.
