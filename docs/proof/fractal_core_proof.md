# Fractal Core Proof Packet

Storage root (absolute):
`C:\Users\Rick\Desktop\Work\FRAM_V22_Starter\fram_v22_starter\storage\memory\fractal`

Trace id:
`6326332ff4b74f63becb087db170c865`

Trace path:
`C:\Users\Rick\Desktop\Work\FRAM_V22_Starter\fram_v22_starter\storage\memory\fractal\6326332ff4b74f63becb087db170c865.json`

JSON snippet (trace_version + node0/node1):
```json
{
  "trace_version": 2,
  "node0": {
    "scale": "macro",
    "coord6": [
      -0.00142150905223337,
      -0.027350150342745155,
      0.06247596996644081,
      0.01625224206070177,
      -0.3445799353730224,
      -0.23122040869301705
    ],
    "s_arc": 0.0,
    "index": 0,
    "q": {
      "w": 0.9129668094427511,
      "x": -0.0,
      "y": 0.16454979639629735,
      "z": 0.3733831401681929
    },
    "lambda": 0.9880113481596522
  },
  "node1": {
    "scale": "micro",
    "coord6": [
      0.13383586681724402,
      0.404249425196526,
      -0.3705132250144991,
      0.5319313229882392,
      -0.11084275223758505,
      -0.09144484977925268
    ],
    "s_arc": 0.8556562314732665,
    "index": 1,
    "q": {
      "w": 0.27275493399383094,
      "x": 0.0,
      "y": -0.6991528815400221,
      "z": 0.6609008959112589
    },
    "lambda": 0.9167472775424415
  }
}
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

NOTE:
- Live runtime writes to `storage\memory\fractal` under the repo root.
- The smoke test writes to the pytest temp directory (e.g., `C:\Users\Rick\AppData\Local\Temp\pytest-of-Rick\...`).
