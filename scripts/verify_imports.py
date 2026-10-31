#!/usr/bin/env python3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def main():
    try:
        import fram_core  # type: ignore
        import fram_serving  # type: ignore
    except Exception as e:
        print("IMPORT ERROR:", repr(e))
        sys.exit(1)
    else:
        print("fram_core OK", getattr(fram_core, "__file__", "<n/a>"))
        print("fram_serving OK", getattr(fram_serving, "__file__", "<n/a>"))


if __name__ == "__main__":
    main()
