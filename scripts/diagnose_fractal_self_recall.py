"""Measure fractal-only self-recall on fixed synthetic orthogonal vectors.

This diagnoses the trace signal, not blended production retrieval or activation.
It uses current scoring defaults with 12 deterministic 64-D source vectors.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch-root", type=Path, required=True)
    parser.add_argument(
        "--scoring-mode", choices=["legacy", "source_frame"], default="legacy"
    )
    args = parser.parse_args()
    root = args.scratch_root.resolve()
    root.mkdir(parents=True, exist_ok=False)
    os.environ.update(
        FRAM_STORAGE_ROOT=str(root / "storage"),
        COGMEM_STORAGE_ROOT=str(root / "storage/memory/cognitive"),
        COGMEM_AUTOLOG="0",
        FRAM_DEV_PROFILE="0",
        FRAM_FRACTAL_INFLUENCE="0",
    )
    import numpy as np

    from fram_serving.config import FRAMConfig
    from fram_serving.fractal_memory import FractalSeed, FractalTraceStore
    from fram_serving.query_runner import _fractal_trace_scores

    count, dimension = 12, 64
    vectors = np.eye(dimension)[:count]
    identifiers = [f"synthetic-orthogonal-{i:02d}" for i in range(count)]
    traces = FractalTraceStore(
        root / "traces",
        observability_root=root / "observability",
        embedding_dim=dimension,
    )
    for identifier, vector in zip(identifiers, vectors):
        traces.ingest_seed(
            FractalSeed(
                episode_id=identifier,
                timestamp_ms=1_700_000_000_000,
                embedding=vector,
                metadata={"synthetic": True},
            )
        )
    store = SimpleNamespace(
        fractal_trace_store=lambda: traces,
        FILE_EPISODES="synthetic",
        _iter_jsonl=lambda _: iter({"id": key} for key in identifiers),
    )
    cfg = FRAMConfig().model_copy(
        update={
            "embedding_dim": dimension,
            "fractal_enabled": True,
            "fractal_influence_enabled": True,
            "fractal_scoring_mode": args.scoring_mode,
        }
    )
    rows, distances = [], []
    for identifier, query in zip(identifiers, vectors):
        scores = _fractal_trace_scores(store, query, count, cfg)
        ranked = [row["episode_id"] for row in scores]
        rows.append(
            {
                "query_id": identifier,
                "vector_top_one": identifiers[int(np.argmax(vectors @ query))],
                "fractal_top_one": ranked[0] if ranked else None,
                "fractal_self_rank": (
                    ranked.index(identifier) + 1 if identifier in ranked else None
                ),
            }
        )
        distance_key = (
            "soft_dtw_distance"
            if args.scoring_mode == "legacy"
            else "source_frame_distance"
        )
        distances.extend(row[distance_key] for row in scores)
    result = {
        "schema": "fram-synthetic-fractal-self-recall-v1",
        "activation_eligible": False,
        "scoring_mode": args.scoring_mode,
        "distance_kind": (
            "soft_dtw"
            if args.scoring_mode == "legacy"
            else "contraction_normalized_aligned_replay"
        ),
        "synthetic": True,
        "count": count,
        "dimension": dimension,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "profile": {
            name: getattr(cfg, name)
            for name in (
                "fractal_blend_alpha",
                "fractal_downsample_target",
                "fractal_quat_weight",
                "fractal_quat_influence",
                "fractal_quat_use_lambda",
            )
        },
        "vector_top_one_count": sum(
            row["query_id"] == row["vector_top_one"] for row in rows
        ),
        "fractal_top_one_count": sum(
            row["query_id"] == row["fractal_top_one"] for row in rows
        ),
        "raw_distance_min": min(distances),
        "raw_distance_max": max(distances),
        "negative_distances": sum(value < 0 for value in distances),
        "rows": rows,
    }
    (root / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "rows"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
