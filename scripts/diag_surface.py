#!/usr/bin/env python3
import os, re, json, sys
ROOT = os.path.abspath(sys.argv[1] if len(sys.argv)>1 else ".")
SKIP_DIR = (os.sep+".git", os.sep+".venv", os.sep+"venv", os.sep+"node_modules",
            os.sep+"build", os.sep+"dist", os.sep+"__pycache__")

cli_patterns = [r'argparse\.ArgumentParser', r'@click\.command', r'@click\.group',
                r'if __name__ == ["\']__main__["\']']
http_patterns = [r'@app\.(get|post|put|patch|delete)\(["\']([^"\']+)["\']',
                 r'@router\.(get|post|put|patch|delete)\(["\']([^"\']+)["\']',
                 r'FastAPI\(', r'flask\.Flask\(']

cli_hits, http_hits = [], []
for dp, dn, files in os.walk(ROOT):
    if any(s in dp for s in SKIP_DIR): continue
    for f in files:
        if not f.endswith(".py"): continue
        rel = os.path.relpath(os.path.join(dp,f), ROOT)
        try:
            txt = open(os.path.join(ROOT, rel), "r", encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        if any(re.search(p, txt) for p in cli_patterns): cli_hits.append(rel)
        for pat in http_patterns:
            for m in re.finditer(pat, txt):
                http_hits.append({"file": rel, "match": m.group(0)})

report = {"cli_files": sorted(set(cli_hits)), "http_routes": http_hits}
os.makedirs("diag", exist_ok=True)
open("diag/surface.json","w",encoding="utf-8").write(json.dumps(report, indent=2))
print("Wrote diag/surface.json")

