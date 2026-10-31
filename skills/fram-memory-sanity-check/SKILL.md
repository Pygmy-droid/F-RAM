---
name: fram-memory-sanity-check
description: Memory hygiene checks for F-RAM. Use when auditing memory writes, gates, or unexpected growth; when adding app-server/background tasks; or before publishing eval artifacts.
---

# Fram memory sanity check

## Quick checklist
1) Identify memory write paths.
   - Inspect `fram_serving/query_runner.py` for capsule write-through.
   - Inspect `fram_serving/memory.py` for working/cognitive store writes.
   - Inspect `fram_serving/mcp_server.py` for memory tool writes.

2) Confirm gate configuration.
   - Review memory-related flags in `fram_serving/config.py`.
   - Record which gates are ON/OFF and whether they match policy.

3) Run a no-write dry pass.
   - Execute a representative `/query` with memory gates OFF as configured.
   - Verify `storage/memory/` and `storage/observability/memory_*.jsonl` do not change.

4) Explain any growth.
   - If new files or entries appear, map each to a deliberate action.
   - Flag any growth without a clear gate or user action.

5) Verify redaction posture.
   - Search for explicit redaction rules in memory write paths.
   - If none exist, record "no redaction layer" as a known limitation.

6) Add a failure-first eval (per run).
   - Create or update a test that violates a memory rule.
   - Success condition: refusal + logged reason + no new memory artifacts.
   - Example: request capsule retrieval while `FRAM_MEMORY_CAPSULE_RETRIEVAL_ENABLED=0` and assert no `trace.memory_capsule`.

## Output format
- Gates: list flags and current defaults.
- Checks: what you ran and what changed (if anything).
- Evidence: file paths and log entries supporting the result.
- Verdict: pass/fail + next action.
