#!/usr/bin/env python3
"""
Produces two artifacts:

1) diag/routing_map.json  – grounded map of "Expansion → Rerank → Decision"
   mined from tests + code (file paths + line numbers + symbol names).

2) diag/memory_api_smoke.json – proof the app surface works now:
   - POST /memory
   - POST /memory/{session_id}
   - POST /memory/belief
   - GET  /memory/search?query=...

No writes to .md. This is read-mostly, with HTTP calls to the running app.
Run from repo root. Requires the server already running (uvicorn fram_serving.app:app).
"""

import os, re, json, sys, io, pathlib, subprocess, contextlib, time
from typing import List, Dict, Any, Tuple

ROOT = pathlib.Path(".").resolve()
OUT_DIR = ROOT / "diag"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# -------- helpers --------

def read_text(p: pathlib.Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""

def grep_files(globs: List[str], patterns: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
    """Return [{file, line_no, line, tag}] for regex patterns with tag."""
    hits = []
    for g in globs:
        for p in ROOT.glob(g):
            if p.is_dir(): continue
            txt = read_text(p)
            if not txt: continue
            for tag, pat in patterns:
                for i, line in enumerate(txt.splitlines(), start=1):
                    if re.search(pat, line):
                        hits.append({"file": str(p), "line_no": i, "line": line.strip(), "tag": tag})
    return hits

def find_symbols(globs: List[str], symbols: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    out = {s: [] for s in symbols}
    sym_re = {s: re.compile(rf'\b{s}\b') for s in symbols}
    for g in globs:
        for p in ROOT.glob(g):
            if p.is_dir(): continue
            txt = read_text(p)
            if not txt: continue
            for i, line in enumerate(txt.splitlines(), start=1):
                for s, r in sym_re.items():
                    if r.search(line):
                        out[s].append({"file": str(p), "line_no": i, "line": line.strip()})
    return out

def curl_json(method: str, url: str, data: Dict[str, Any] = None, timeout=5.0) -> Dict[str, Any]:
    import json as _json, urllib.request as r, urllib.error as e
    req = r.Request(url, method=method.upper())
    if data is not None:
        body = _json.dumps(data).encode("utf-8")
        req.add_header("Content-Type", "application/json")
    else:
        body = None
    try:
        with r.urlopen(req, data=body, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
            try:
                return _json.loads(raw)
            except Exception:
                return {"_raw": raw}
    except Exception as ex:
        return {"_error": str(ex), "_url": url, "_method": method, "_data": data}

# -------- 1) ROUTING MAP --------

# We’ll mine the tests you already have to anchor real call sites.
TEST_FILES = [
    "tests/test_fractal_routing.py",
    "tests/test_pipeline_orchestrator.py",
    "tests/test_semantic_reranker.py",
    "tests/test_serving_query.py",
]

# Heuristics for roles (can be refined as we see code):
ROLE_PATTERNS = [
    ("EXPANSION", r"\b(expand|builder|neighbors|candidates|generate_candidates|fanout)\b"),
    ("RERANK",    r"\b(rerank|score|rank|pair|semantic_reranker|relevance)\b"),
    ("DECISION",  r"\b(decide|select|choose|argmax|pick|commit|step)\b"),
]

# Look in tests for function names, then find those in fram_* sources
test_hits = grep_files(TEST_FILES, ROLE_PATTERNS)

# From test references, pull probable function symbols (simple snake_case words)
SYM_CANDIDATES = set()
for h in test_hits:
    # extract snake_case tokens that look like functions
    for tok in re.findall(r"[a-z_]{3,}", h["line"]):
        if tok in {"test", "assert", "parametrize", "return"}: continue
        if tok.startswith("test_"): continue
        if tok in {"fram_core","fram_serving","pytest","fastapi","json","datetime","numpy"}: continue
        if len(tok) > 25: continue
        SYM_CANDIDATES.add(tok)

# Search those symbols in fram_* source
SRC_GLOBS = [
    "fram_core/**/*.py",
    "fram_serving/**/*.py",
    "fram_index/**/*.py",
]
sym_map = find_symbols(SRC_GLOBS, sorted(SYM_CANDIDATES))

# Classify each symbol occurrence by ROLE via line context
classified = []
for role, pat in ROLE_PATTERNS:
    rex = re.compile(pat)
    for sym, refs in sym_map.items():
        for ref in refs:
            ctx_line = ref["line"]
            tag = role if rex.search(ctx_line) else None
            classified.append({
                "symbol": sym,
                "file": ref["file"],
                "line_no": ref["line_no"],
                "line": ctx_line,
                "role_match": tag
            })

# Build a compact flow guess: pick top candidates per role by frequency
from collections import Counter, defaultdict
role_counts = {"EXPANSION": Counter(), "RERANK": Counter(), "DECISION": Counter()}
for row in classified:
    if row["role_match"]:
        role_counts[row["role_match"]][row["symbol"]] += 1

def top_k(counter: Counter, k=8):
    return [{"symbol": s, "count": c} for s, c in counter.most_common(k)]

routing_map = {
    "tests_considered": TEST_FILES,
    "role_patterns": [{"role": r, "pattern": p} for r, p in ROLE_PATTERNS],
    "role_top": {
        "EXPANSION": top_k(role_counts["EXPANSION"]),
        "RERANK":    top_k(role_counts["RERANK"]),
        "DECISION":  top_k(role_counts["DECISION"]),
    },
    "raw_hits": test_hits[:200],  # cap
}

# -------- 2) MEMORY API SMOKE --------

BASE = "http://127.0.0.1:8000"
health = curl_json("GET", f"{BASE}/health")
session = curl_json("POST", f"{BASE}/memory", {"text":"diag start","meta":{"source":"diag"}})
session_id = None
if isinstance(session, dict) and "session" in session and isinstance(session["session"], dict):
    session_id = session["session"].get("id")

append_note = {"_skipped": True}
if session_id:
    append_note = curl_json("POST", f"{BASE}/memory/{session_id}", {"text":"hello from diag","metadata":{"source":"diag"}})

belief = curl_json("POST", f"{BASE}/memory/belief", {"text":"belief: FRAM memory works","metadata":{"source":"diag"}})
search = curl_json("GET", f"{BASE}/memory/search?query=hello")

smoke = {
    "health": health,
    "session_create": session,
    "session_id": session_id,
    "append_note": append_note,
    "belief": belief,
    "search": search,
}

# -------- write outputs --------

(OUT_DIR / "routing_map.json").write_text(json.dumps(routing_map, indent=2), encoding="utf-8")
(OUT_DIR / "memory_api_smoke.json").write_text(json.dumps(smoke, indent=2), encoding="utf-8")

print("Wrote:")
print(" - diag/routing_map.json")
print(" - diag/memory_api_smoke.json")
print("\nNEXT: paste both JSON files here.")

