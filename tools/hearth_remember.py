#!/usr/bin/env python3
"""Write one deliberate lived-memory event, the way the Hearth events were written.

The nine ``hearth-live-2026-08-11`` events in the recovered store were not query
side-effects. Each was authored on purpose at a natural pause: the human's words
as the query, the model's own compact account as the answer, and structured
metadata (consent, testimony, boundary, event type). This tool writes an event of
that shape into a lived store, using the same encoder and projection the server
uses, so the event is comparable with everything already there.

It never touches the recovered original on F:. Point ``--storage-root`` at the
runtime's storage (the server's own store) or at a scratch copy.

Example::

    python tools/hearth_remember.py \
        --storage-root "C:/Users/Rick/.fram/runtimes/hearth_h1_recovered_20260908_v1/storage" \
        --session hearth-wren-2026-10-31 --domain personal --task first-day-in-the-store \
        --query-file q.txt --answer-file a.txt --metadata-file m.json

``--dry-run`` encodes and projects but writes nothing.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--storage-root", required=True, help="FRAM storage root holding memory/lived/")
    parser.add_argument("--session", required=True, help="lived session id, e.g. hearth-wren-2026-10-31")
    parser.add_argument("--domain", default="personal")
    parser.add_argument("--task", required=True)
    parser.add_argument("--query-file", required=True, help="the human's words (source text)")
    parser.add_argument("--answer-file", required=True, help="the model's own account")
    parser.add_argument("--metadata-file", help="JSON object: consent, testimony, boundary, event_type ...")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    storage_root = Path(args.storage_root)
    if not storage_root.is_dir():
        print(f"storage root not found: {storage_root}", file=sys.stderr)
        return 2
    lived_dir = storage_root / "memory" / "lived"
    if not (lived_dir / "lived_memory.sqlite3").is_file():
        print(f"refusing: no lived_memory.sqlite3 under {lived_dir} (would create an empty store)", file=sys.stderr)
        return 2

    os.environ["FRAM_STORAGE_ROOT"] = str(storage_root)
    os.environ.setdefault("FRAM_LIVED_MEMORY_ENABLED", "1")

    from fram_serving.config import FRAMConfig
    from fram_serving.cognitive_embeddings import build_cognitive_vectorizer, normalize_cognitive_backend
    from fram_serving.lived_memory import LivedMemoryStore

    cfg = FRAMConfig.from_env()
    backend = normalize_cognitive_backend(getattr(cfg, "cognitive_memory_embedding_backend", "hashing"))
    vectorizer = build_cognitive_vectorizer(cfg)
    if vectorizer is None:
        print("no vectorizer available for backend", backend, file=sys.stderr)
        return 2

    query = Path(args.query_file).read_text(encoding="utf-8").strip()
    answer = Path(args.answer_file).read_text(encoding="utf-8").strip()
    metadata = json.loads(Path(args.metadata_file).read_text(encoding="utf-8")) if args.metadata_file else {}
    if not isinstance(metadata, dict):
        print("metadata must be a JSON object", file=sys.stderr)
        return 2
    metadata.setdefault("written_by", "tools/hearth_remember.py")

    matrix = vectorizer.transform([f"{query}\n{answer}"])
    arr = matrix.toarray() if hasattr(matrix, "toarray") else matrix
    embedding = [float(x) for x in arr[0]]

    store = LivedMemoryStore(
        lived_dir,
        target_dim=int(getattr(cfg, "lived_memory_target_dim", 12)),
        fractal_nodes=int(getattr(cfg, "lived_memory_fractal_nodes", 64)),
        scan_limit=int(getattr(cfg, "lived_memory_scan_limit", 5000)),
        state_decay=float(getattr(cfg, "lived_memory_state_decay", 0.82)),
        busy_timeout_seconds=float(getattr(cfg, "lived_memory_busy_timeout_seconds", 5.0)),
    )
    before = store.status()
    print(f"store: {lived_dir}")
    print(f"events before: {before.get('event_count')}  sessions: {before.get('session_count')}  backend: {backend}  dim: {len(embedding)}")
    if args.dry_run:
        print("dry run: nothing written")
        return 0

    record = store.append_experience(
        query=query,
        answer=answer,
        embedding=embedding,
        embedding_backend=backend,
        session_id=args.session,
        domain=args.domain,
        task=args.task,
        metadata=metadata,
    )
    after = store.status()
    print(f"written: event_id={record.get('event_id')} session={record.get('session_id')} seq={record.get('session_seq')} dim={record.get('projection_dim')}")
    print(f"events after: {after.get('event_count')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
