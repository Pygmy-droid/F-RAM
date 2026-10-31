# DONE Step 4 — REP (Re-Entry Packet)

Files created/changed
- `fram_serving/rep.py`
- `fram_serving/archive.py`
- `fram_serving/query_runner.py`
- `tools/rep_probe.py`
- `tests/test_rep_packet.py`

REP storage path
- `storage/rep/rep.json`

Commands to verify (live end-to-end)
```powershell
uvicorn fram_serving.app:app --reload --port 8000

curl -s -X POST http://127.0.0.1:8000/query `
  -H "Content-Type: application/json" `
  -d "{\"text\":\"REP live smoke\"}"

# Confirm archive grew
Get-Content storage\\archive\\manifest.jsonl | Select-Object -Last 1

# Open the new chunk (replace <event_id> from the manifest line)
Get-Content storage\\archive\\chunks\\<event_id>.json

# Confirm REP references the new archive event id
python tools\\rep_probe.py --json
# or
Get-Content storage\\rep\\rep.json
```

Expected checks
- `manifest.jsonl` appends a new line for the live query.
- The chunk JSON contains `request`, `response`, and a non-null `trace_id`.
- `storage/rep/rep.json` includes the new `event_id` under `archive_pointers.recent_event_ids`.

Tests run
```
pytest -q -s tests\test_rep_packet.py
```

Stop condition confirmation
- Live interaction → archive manifest + chunk → REP pointer to the new archive event id.
