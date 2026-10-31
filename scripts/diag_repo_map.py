#!/usr/bin/env python3
import os, re, json, sys
ROOT = os.path.abspath(sys.argv[1] if len(sys.argv)>1 else ".")
SKIP_DIR = (os.sep+".git", os.sep+".venv", os.sep+"venv", os.sep+"node_modules",
            os.sep+"build", os.sep+"dist", os.sep+"__pycache__")
PKG_RE = re.compile(r'^\s*from\s+([A-Za-z0-9_\.]+)\s+import|^\s*import\s+([A-Za-z0-9_\.]+)', re.M)

tree, imports, py_files = [], {}, []
for dp, dn, files in os.walk(ROOT):
    if any(s in dp for s in SKIP_DIR): continue
    for f in files:
        p = os.path.join(dp,f); rel = os.path.relpath(p, ROOT)
        tree.append(rel)
        if f.endswith(".py"): py_files.append(rel)

for rel in py_files:
    try:
        txt = open(os.path.join(ROOT, rel), "r", encoding="utf-8", errors="ignore").read()
    except Exception:
        continue
    found = []
    for m in PKG_RE.finditer(txt):
        mod = (m.group(1) or m.group(2) or "").strip()
        if mod: found.append(mod.split(".")[0])
    imports[rel] = sorted(set(found))

report = {
    "root": ROOT,
    "count_files": len(tree),
    "count_py": len(py_files),
    "files_py": py_files,
    "imports": imports,
}
os.makedirs("diag", exist_ok=True)
open("diag/repo_map.json","w",encoding="utf-8").write(json.dumps(report, indent=2))
print("Wrote diag/repo_map.json")

