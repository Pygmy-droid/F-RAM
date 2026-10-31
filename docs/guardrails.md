# Guardrails (v2.2)

`fram_serving/guardrails/hooks.py` defines three optional hooks:
- `before_memory_write(item)`
- `before_memory_read(query)`
- `before_shortlist(candidate_list)`

Each returns `(allowed: bool, reason: str|None)`. Defaults allow everything.

Config: `enable_guardrails` (default False). When enabled, blocked actions are recorded via `record_block(hook, reason)`, surfaced in observability dashboard, and callers can opt to skip writes/reads/shortlist merges.

Tests: `tests/test_guardrails_hooks.py` cover blocking rules and disabled behaviour.
