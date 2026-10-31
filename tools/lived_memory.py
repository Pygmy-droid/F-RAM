from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fram_serving.cognitive_embeddings import build_cognitive_vectorizer  # noqa: E402
from fram_serving.config import FRAMConfig  # noqa: E402
from fram_serving.lived_memory import LivedMemoryStore  # noqa: E402


def _store(args: argparse.Namespace) -> LivedMemoryStore:
    return LivedMemoryStore(
        args.root,
        target_dim=args.target_dim,
        fractal_nodes=args.fractal_nodes,
        scan_limit=args.scan_limit,
        state_decay=args.state_decay,
    )


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Inspect durable F-RAM lived memory.")
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--target-dim", type=int, default=12)
    parser.add_argument("--fractal-nodes", type=int, default=64)
    parser.add_argument("--scan-limit", type=int, default=5000)
    parser.add_argument("--state-decay", type=float, default=0.82)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status")
    subparsers.add_parser("verify")
    session = subparsers.add_parser("session")
    session.add_argument("session_id")
    search = subparsers.add_parser("search")
    search.add_argument("query")
    search.add_argument("--k", type=int, default=4)
    search.add_argument("--session")
    args = parser.parse_args()

    store = _store(args)
    if args.command == "status":
        payload = store.status()
    elif args.command == "verify":
        payload = store.verify()
    elif args.command == "session":
        payload = store.session_state(args.session_id)
        if payload is None:
            print(
                json.dumps(
                    {"error": "session_not_found", "session_id": args.session_id}
                )
            )
            return 2
    else:
        cfg = FRAMConfig(
            embedding_dim=1024, cognitive_memory_embedding_backend="hashing"
        )
        vectorizer = build_cognitive_vectorizer(cfg)
        if vectorizer is None:
            raise RuntimeError("hashing vectorizer is unavailable")
        vector = np.asarray(
            vectorizer.transform([args.query]).toarray()[0], dtype=float
        )
        payload = {
            "query": args.query,
            "items": store.search(vector, k=max(1, args.k), session_id=args.session),
        }
        payload["count"] = len(payload["items"])
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if args.command == "verify" and not payload.get("valid"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
