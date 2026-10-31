#!/usr/bin/env python3
try:
    import mcp  # type: ignore
    print("mcp OK")
except Exception as e:
    print("mcp MISSING", repr(e))

