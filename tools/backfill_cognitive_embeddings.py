from __future__ import annotations

import argparse
from pathlib import Path

from fram_serving.cognitive_embeddings import build_cognitive_vectorizer, normalize_cognitive_backend
from fram_serving.config import FRAMConfig
from fram_serving.memory import CognitiveMemoryStore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill cognitive memory embeddings.")
    parser.add_argument(
        "--store-root",
        type=Path,
        default=Path("storage/memory/cognitive"),
        help="Cognitive memory root directory.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Batch size for embedding backfill.",
    )
    parser.add_argument(
        "--episodes-only",
        action="store_true",
        help="Only backfill episode vectors (skip beliefs).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg = FRAMConfig.from_env()
    backend = normalize_cognitive_backend(
        getattr(cfg, "cognitive_memory_embedding_backend", "hashing")
    )
    vectorizer = build_cognitive_vectorizer(cfg)
    if vectorizer is None:
        raise SystemExit(
            f"Embedding backend '{backend}' unavailable. "
            "Install sentence-transformers or set FRAM_COGNITIVE_MEMORY_EMBEDDING_BACKEND=hashing."
        )
    store = CognitiveMemoryStore(args.store_root, config=cfg)
    result = store.backfill_embeddings(
        vectorizer=vectorizer,
        backend=backend,
        batch_size=max(1, int(args.batch_size)),
        include_beliefs=not args.episodes_only,
    )
    print(result)


if __name__ == "__main__":
    main()
