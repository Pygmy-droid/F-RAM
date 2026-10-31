# Tool Surface Evidence Anchor (2026-01-23)

Purpose
Short, publish-safe anchor capturing commit hashes and test evidence for the new
surface area (skills, eval-skills, app-server readiness, MCP, AGENTS governance).

Relevant commits
- 778a479 docs: add MCP guide guardrails and eval matrix
- defc4f3 feat: gate MCP cognitive writes
- 005cdf2 test: add failure-first capsule gate check
- 04d742e feat: add memory sanity check skill
- f43043e chore: split AGENTS overrides

Evidence matrix
- docs/proof/tool_surface_eval_matrix.md

Test evidence (targeted)
- pytest -vv tests/test_mcp_server.py (9 passed, 0:03:10)
- pytest -q tests/test_memory_capsule_retrieval.py (2 passed, 0:38.79)
- pytest -q tests/test_cognitive_logging.py::test_seq_persists_across_restarts (1 passed, 0:06.45)

Full suite
- pytest -q (278 passed, 1:23:30)
