# DONE Step 3 — Verbatim Archive Layer

Files created/changed
- `fram_serving/archive.py`
- `fram_serving/query_runner.py`
- `fram_serving/app.py`
- `fram_serving/mcp_server.py`
- `tools/archive_probe.py`
- `tests/test_archive_layer.py`

Storage layout (append-only)
- `storage/archive/manifest.jsonl`
- `storage/archive/chunks/<event_id>.json`

Event schema
- Chunk payload keys: `event_id`, `ts_ms`, `kind`, `trace_id`, `request`, `response`, `meta`
- Manifest line keys: `event_id`, `ts_ms`, `kind`, `trace_id`, `content_hash`, `chain_hash`, `prev_chain_hash`, `chunk_path`

Commands to reproduce
```powershell
uvicorn fram_serving.app:app --reload --port 8000

curl -s -X POST http://127.0.0.1:8000/query `
  -H "Content-Type: application/json" `
  -d "{\"text\":\"Archive smoke\"}"

python tools\\archive_probe.py --tail 5 --json

# Get the last manifest line and then open its chunk file
Get-Content storage\\archive\\manifest.jsonl | Select-Object -Last 1
Get-Content storage\\archive\\chunks\\<event_id>.json
```

Tests run
```
pytest -q -s tests\test_archive_layer.py
....
4 passed, 1 warning in 9.44s
```

Stop condition confirmation
- After a live `/query`, `storage/archive/manifest.jsonl` appends a new line and `storage/archive/chunks/<event_id>.json` is created.
- The manifest line includes a non-null `trace_id`, and the chunk content hash matches `content_hash` with a valid `chain_hash`.
