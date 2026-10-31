#!/usr/bin/env python3
import importlib, json

modules = [
    # EDIT these names to match your packages if needed
    "fram_core", "fram_app", "fram_serving", "fram_api",
    "orthorout", "orthorout.core", "orthorout.router", "app"
]

ok, bad = [], []
for m in modules:
    try:
        importlib.import_module(m)
        ok.append(m)
    except Exception as e:
        bad.append({"module": m, "error": repr(e)})

open("diag/imports.json","w",encoding="utf-8").write(json.dumps({"ok":ok,"bad":bad}, indent=2))
print("Wrote diag/imports.json")

