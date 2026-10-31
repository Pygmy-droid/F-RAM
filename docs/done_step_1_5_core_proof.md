# DONE — Step 1.5 Core Proof Packet

Commands run:
```powershell
python tools\fractal_trace_probe.py
pytest -q -s tests\test_fractal_trace_smoke.py
```

Commands to reproduce:
```powershell
uvicorn fram_serving.app:app --reload --port 8000
curl -s http://localhost:8000/query -H "Content-Type: application/json" -d "{\"text\":\"fractal proof\"}"
curl -s "http://localhost:8000/memory/fractal_trace?limit=5"
curl -s "http://localhost:8000/observability/summary"
python tools\fractal_trace_probe.py
pytest -q -s tests\test_fractal_trace_smoke.py
```

Expected outputs (selected lines):
```
storage_root: C:\Users\Rick\Desktop\Work\FRAM_V22_Starter\fram_v22_starter\storage\memory\fractal
count: 600
first_5: ['00b234c2c93141408b5bc272e3c2edb4', '00c7330b59bc42d38aeeb92ca2ad887c', '00cdbda7e77c49879471588a61caef0a', '0244a10ea7b247d4bd42579b9af313c3', '02bd896f901048019828e6e2802c574d']
```

Exact paths:
- `C:\Users\Rick\Desktop\Work\FRAM_V22_Starter\fram_v22_starter\storage\memory\fractal`
- `C:\Users\Rick\Desktop\Work\FRAM_V22_Starter\fram_v22_starter\storage\observability\memory_fractal.jsonl`
- `C:\Users\Rick\Desktop\Work\FRAM_V22_Starter\fram_v22_starter\storage\memory\fractal\6326332ff4b74f63becb087db170c865.json`

Tests executed:
```text
pytest -q -s tests\test_fractal_trace_smoke.py
1 passed, 1 warning in 8.30s
```
