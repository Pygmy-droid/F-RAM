from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from fram_serving.config import FRAMConfig
from fram_serving.memory import CognitiveMemoryStore


def compact_recent(
    *,
    storage_root: Path,
    window: int = 100,
    min_citations: int = 2,
    by: str = "segment",
) -> Dict[str, int]:
    cfg = FRAMConfig()
    memory_root = storage_root / cfg.STORAGE_SUBFOLDERS.get("memory", "memory")
    store = CognitiveMemoryStore(memory_root / "cognitive", config=cfg)

    # Load recent episodes
    recent = list(store._iter_jsonl(store.FILE_EPISODES))[-window:]
    promoted = 0
    skipped = 0
    for ep in recent:
        text = (ep.get("answer") or "").strip()
        if not text:
            skipped += 1
            continue
        citations = [c for c in (ep.get("citations") or []) if c]
        if len(citations) < min_citations:
            skipped += 1
            continue
        meta = ep.get("metadata") or {}
        # Tag with hierarchy scale nodes if available
        scales = meta.get("hierarchy_scales") or []
        scale_id: Optional[str] = None
        for entry in scales:
            if isinstance(entry, dict) and entry.get("scale") == "segment":
                nodes = entry.get("nodes") or []
                if nodes:
                    scale_id = str(nodes[0].get("id"))
                    break
        belief_meta: Dict[str, object] = {}
        if scale_id:
            belief_meta["scale_id"] = scale_id
        belief_meta["sources"] = citations
        # Promote to belief with dedupe via source episode id
        try:
            store.append_belief(
                text=text,
                source_episode=str(ep.get("id")),
                confidence=None,
                citations=citations,
                metadata=belief_meta,
            )
            promoted += 1
        except Exception:
            skipped += 1
            continue
    return {"promoted": promoted, "skipped": skipped}


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Compact recent cognitive episodes into beliefs.")
    p.add_argument("--storage-root", type=Path, default=None, help="Root storage path (defaults to FRAMConfig.STORAGE_ROOT)")
    p.add_argument("--window", type=int, default=100, help="Recent episodes to scan")
    p.add_argument("--min-citations", type=int, default=2, help="Minimum citations to promote")
    return p


def main(argv: List[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    cfg = FRAMConfig()
    root = Path(args.storage_root) if args.storage_root else Path(cfg.STORAGE_ROOT)
    out = compact_recent(storage_root=root, window=max(1, int(args.window)), min_citations=max(0, int(args.min_citations)))
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

