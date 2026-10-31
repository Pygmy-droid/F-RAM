from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

import fram_serving.app as app_mod
from fram_serving.memory import CognitiveMemoryStore


def _coerce_storage_root(root: Optional[str]) -> None:
    if not root:
        return
    base = Path(root)
    cfg = app_mod.CFG.model_copy(update={"STORAGE_ROOT": base})
    app_mod.CFG = cfg  # type: ignore[assignment]
    try:
        app_mod._COG_STORE = CognitiveMemoryStore(  # type: ignore[attr-defined]
            cfg.STORAGE_ROOT / cfg.STORAGE_SUBFOLDERS.get("memory", "memory") / "cognitive",
            config=cfg,
        )
    except Exception:
        pass


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect fractal trace storage")
    parser.add_argument("--storage-root", dest="storage_root", default=None)
    args = parser.parse_args(argv)

    _coerce_storage_root(args.storage_root)

    store = app_mod._COG_STORE.fractal_trace_store()
    if store is None:
        print("fractal_trace_store: unavailable")
        return 1
    root = store.storage_root.resolve()
    ids = store.available_ids()
    print(f"storage_root: {root}")
    print(f"count: {len(ids)}")
    print(f"first_5: {ids[:5]}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
