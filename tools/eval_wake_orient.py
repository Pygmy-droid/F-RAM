#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fram_eval.wake_orient import (  # noqa: E402
    evaluate_wake_orient,
    load_wake_orient_probes,
)
from fram_serving.cognitive_embeddings import (  # noqa: E402
    build_cognitive_vectorizer,
)
from fram_serving.config import FRAMConfig  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run a read-only cue ablation over a checkpointed F-RAM lived-memory store."
        )
    )
    parser.add_argument("--db", required=True, type=Path, help="lived_memory.sqlite3")
    parser.add_argument("--probes", required=True, type=Path, help="probe JSON")
    parser.add_argument("--output", required=True, type=Path, help="report JSON")
    parser.add_argument("--session", default=None, help="optional lived session ID")
    parser.add_argument("--k", type=int, default=4, help="retrieval depth")
    parser.add_argument(
        "--supplemental-per-cue",
        type=int,
        default=2,
        help="compact and painting results appended after the F-RAM primary set",
    )
    parser.add_argument(
        "--embedding-dim",
        type=int,
        default=1024,
        help="hashing-vectorizer dimension used by the source events",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = FRAMConfig().model_copy(
        update={
            "embedding_dim": int(args.embedding_dim),
            "cognitive_memory_embedding_backend": "hashing",
        }
    )
    vectorizer = build_cognitive_vectorizer(config)
    if vectorizer is None:
        raise RuntimeError("hashing vectorizer is unavailable")
    probes = load_wake_orient_probes(args.probes)
    report = evaluate_wake_orient(
        args.db,
        probes,
        vectorizer,
        session_id=args.session,
        k=max(1, int(args.k)),
        supplemental_per_cue=max(1, int(args.supplemental_per_cue)),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "source_unchanged": report["source"]["source_unchanged"],
                "condition_summary": report["condition_summary"],
                "staged_summary": report["staged_summary"],
                "injection_summary": report["injection_summary"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
