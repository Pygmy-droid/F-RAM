#!/usr/bin/env python3
import os, re, json, sys
ROOT = os.path.abspath(sys.argv[1] if len(sys.argv)>1 else ".")
SKIP_DIR = (os.sep+".git", os.sep+".venv", os.sep+"venv", os.sep+"node_modules",
            os.sep+"build", os.sep+"dist", os.sep+"__pycache__")

WRITE_PATS = [r'open\(\s*[^,]+,\s*[\'\"]w[\'\"]', r'open\(\s*[^,]+,\s*[\'\"]a[\'\"]']
MD_LIT = re.compile(r'["\']([^"\']+\.md)["\']')

hits = []
for dp, dn, files in os.walk(ROOT):
    if any(s in dp for s in SKIP_DIR): continue
    for f in files:
        if not f.endswith(".py"): continue
        rel = os.path.relpath(os.path.join(dp,f), ROOT)
        try:
            txt = open(os.path.join(ROOT, rel), "r", encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        if ".md" not in txt: continue
        md_targets = MD_LIT.findall(txt)
        for pat in WRITE_PATS:
            for m in re.finditer(pat, txt):
                start = max(0, m.start()-140); end = min(len(txt), m.end()+140)
                hits.append({"file": rel, "context": txt[start:end], "md_literals": md_targets})

os.makedirs("diag", exist_ok=True)
open("diag/md_writes.json","w",encoding="utf-8").write(json.dumps(hits, indent=2))
print(f"Wrote diag/md_writes.json with {len(hits)} sites")

