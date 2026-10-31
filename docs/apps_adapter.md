# ChatGPT Apps Adapter (v2.2)

`fram_serving/apps/sdk_adapter.py` provides a thin bridge for ChatGPT Apps to persist events into the cognitive store.

- `ingest_app_event(event, config=None, root=None)`: writes an episode with `event.text` and optional metadata.
- `ingest_app_memory(key, value, config=None, root=None)`: writes a belief (`key: value`).
- Guardrails: if `enable_guardrails=True`, writes run through `guardrails/hooks.py` (`before_memory_write`). Blocked writes return `{status: "blocked"}` and record the block reason.
- Default behaviour is safe, deterministic, and read-only outside the cognitive store; ANN recall continues to work via the stored vectors.
- Tests: `tests/test_apps_sdk_adapter.py` cover ingest, gating, and recall.
