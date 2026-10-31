from __future__ import annotations

import argparse
import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from fram_eval.conversation_memory_eval import _compute_trace_entries, _score_trace_entries
from fram_eval.memory_shadow_eval import _load_episode_vectors
from fram_serving.config import FRAMConfig
from fram_serving.memory import CognitiveMemoryStore

DEFAULT_OUT = Path("storage/observability/fractal_trace_identity_check.json")


def _load_raw_vectors(store: CognitiveMemoryStore) -> Dict[str, np.ndarray]:
    path = store.vector_path(kind="episode")
    if not path.exists():
        return {}
    vectors: Dict[str, np.ndarray] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            item_id = payload.get("id")
            raw_vec = payload.get("vector")
            if not item_id or raw_vec is None:
                continue
            arr = np.asarray(raw_vec, dtype=float).ravel()
            if arr.size == 0:
                continue
            vectors[str(item_id)] = arr
    return vectors


def _stable_seed(base_seed: int, episode_id: str) -> int:
    digest = hashlib.md5(episode_id.encode("utf-8")).digest()
    value = int.from_bytes(digest[:4], "little", signed=False)
    return (base_seed + value) % 2_147_483_647


def _sample_pool(
    candidate_ids: Sequence[str],
    *,
    expected_id: str,
    pool_size: int,
    seed: int,
) -> List[str]:
    if pool_size >= len(candidate_ids):
        pool = list(candidate_ids)
    else:
        rng = random.Random(seed)
        pool = rng.sample(list(candidate_ids), pool_size)
    if expected_id not in pool:
        if not pool:
            pool = [expected_id]
        else:
            pool[0] = expected_id
    return pool


def _component_delta(expected: Dict[str, Any], top: Dict[str, Any], key: str) -> float | None:
    exp_val = expected.get(key)
    top_val = top.get(key)
    if exp_val is None or top_val is None:
        return None
    try:
        return float(top_val) - float(exp_val)
    except (TypeError, ValueError):
        return None


def _score_config(cfg: FRAMConfig, args: argparse.Namespace) -> Tuple[float, bool, float, bool, str]:
    alpha = args.fractal_alpha if args.fractal_alpha is not None else cfg.fractal_blend_alpha
    quat_enabled = (
        bool(args.fractal_quat) if args.fractal_quat is not None else cfg.fractal_quat_influence
    )
    quat_weight = (
        float(args.fractal_quat_weight)
        if args.fractal_quat_weight is not None
        else cfg.fractal_quat_weight
    )
    quat_use = (
        bool(args.fractal_quat_use_lambda)
        if args.fractal_quat_use_lambda is not None
        else cfg.fractal_quat_use_lambda
    )
    trace_norm_mode = str(args.fractal_trace_norm_mode or "minmax")
    return float(alpha), quat_enabled, quat_weight, quat_use, trace_norm_mode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Identity check: score each episode's trace against its own stored embedding."
        )
    )
    parser.add_argument(
        "--live-store-root",
        type=Path,
        default=Path("storage/memory/cognitive"),
        help="Cognitive memory root for live evals.",
    )
    parser.add_argument(
        "--k-max",
        type=int,
        default=10,
        help="Base k used to size the candidate pool.",
    )
    parser.add_argument(
        "--pool-multiplier",
        type=int,
        default=5,
        help="Multiplier for candidate pool size (pool = k_max * pool_multiplier).",
    )
    parser.add_argument(
        "--max-episodes",
        type=int,
        default=200,
        help="Max episodes to evaluate (0 for all).",
    )
    parser.add_argument(
        "--sample-seed",
        type=int,
        default=11,
        help="Seed for sampling episodes and candidate pools.",
    )
    parser.add_argument(
        "--fractal-alpha",
        type=float,
        default=None,
        help="Override alpha for trace scoring.",
    )
    parser.add_argument(
        "--fractal-quat",
        action="store_true",
        default=None,
        help="Enable quaternion weighting in trace scoring.",
    )
    parser.add_argument(
        "--fractal-quat-weight",
        type=float,
        default=None,
        help="Override FRAM_FRACTAL_QUAT_WEIGHT in trace scoring.",
    )
    parser.add_argument(
        "--fractal-quat-use-lambda",
        action="store_true",
        default=None,
        help="Use lambda-weighted quaternion alignment in trace scoring.",
    )
    parser.add_argument(
        "--fractal-soft-dtw-gamma",
        type=float,
        default=None,
        help="Override soft-DTW gamma for trace scoring.",
    )
    parser.add_argument(
        "--fractal-soft-dtw-band",
        type=float,
        default=None,
        help="Override soft-DTW band for trace scoring.",
    )
    parser.add_argument(
        "--fractal-soft-dtw-score-mode",
        default=None,
        help="Soft-DTW score transform (inverse, exp).",
    )
    parser.add_argument(
        "--fractal-cosine-mode",
        default=None,
        help=(
            "Cosine target for trace scoring (composite, centroid, delta, "
            "turn_hist, lag_dist, radius_hist, curvature_hist)."
        ),
    )
    parser.add_argument(
        "--fractal-trace-norm-mode",
        default=None,
        help="Trace normalization mode (minmax, percentile).",
    )
    parser.add_argument(
        "--query-path-mode",
        default=None,
        help="Query path mode (synthetic, ifs).",
    )
    parser.add_argument(
        "--raw-vectors",
        action="store_true",
        help="Use raw stored embeddings instead of normalized vectors.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="Output JSON path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg = FRAMConfig.from_env()
    store = CognitiveMemoryStore(args.live_store_root, config=cfg)
    trace_store = store.fractal_trace_store()
    if trace_store is None:
        raise SystemExit("Fractal trace store unavailable; check config.")
    if args.raw_vectors:
        vectors = _load_raw_vectors(store)
        vector_mode = "raw"
    else:
        vectors = _load_episode_vectors(store)
        vector_mode = "normalized"
    trace_ids = set(trace_store.available_ids())
    candidate_ids = sorted(set(vectors.keys()) & trace_ids)
    if not candidate_ids:
        raise SystemExit("No episodes with both vectors and traces.")
    vector_dim: Optional[int] = None
    if vectors:
        sample_vec = next(iter(vectors.values()))
        vector_dim = int(sample_vec.shape[0]) if isinstance(sample_vec, np.ndarray) else None
    trace_dim = getattr(trace_store.generator, "embedding_dim", None)
    dim_match = None
    if vector_dim is not None and trace_dim is not None:
        dim_match = bool(vector_dim == trace_dim)

    max_episodes = int(args.max_episodes)
    if max_episodes <= 0 or max_episodes >= len(candidate_ids):
        eval_ids = list(candidate_ids)
    else:
        rng = random.Random(int(args.sample_seed))
        eval_ids = rng.sample(candidate_ids, max_episodes)

    pool_size = max(1, int(args.k_max) * int(args.pool_multiplier))
    alpha, quat_enabled, quat_weight, quat_use, trace_norm_mode = _score_config(cfg, args)

    summary: Dict[str, Any] = {
        "total": 0,
        "missing_expected": 0,
        "missing_score": 0,
        "top1": 0,
        "mean_rank": None,
        "mean_percentile": None,
        "mean_gap": None,
    }
    rank_sum = 0.0
    percentile_sum = 0.0
    gap_sum = 0.0

    items: List[Dict[str, Any]] = []
    for episode_id in eval_ids:
        expected_vec = vectors.get(str(episode_id))
        if expected_vec is None:
            summary["missing_expected"] += 1
            continue
        pool_seed = _stable_seed(int(args.sample_seed), str(episode_id))
        pool_ids = _sample_pool(
            candidate_ids,
            expected_id=str(episode_id),
            pool_size=pool_size,
            seed=pool_seed,
        )
        entries = _compute_trace_entries(
            store,
            candidate_ids=pool_ids,
            query_vector=expected_vec.tolist(),
            config=cfg,
            soft_dtw_gamma=args.fractal_soft_dtw_gamma,
            soft_dtw_band=args.fractal_soft_dtw_band,
            soft_dtw_score_mode=args.fractal_soft_dtw_score_mode,
            cosine_mode=args.fractal_cosine_mode,
            query_path_mode=args.query_path_mode,
        )
        if not entries:
            summary["missing_score"] += 1
            continue
        score_map = _score_trace_entries(
            entries,
            alpha=alpha,
            quat_enabled=quat_enabled,
            quat_weight=quat_weight,
            quat_use=quat_use,
            trace_norm_mode=trace_norm_mode,
        )
        if str(episode_id) not in score_map:
            summary["missing_score"] += 1
            continue
        ranked = sorted(score_map.items(), key=lambda item: (item[1], item[0]), reverse=True)
        top_id, top_score = ranked[0]
        expected_score = score_map.get(str(episode_id))
        expected_rank = next(
            (idx for idx, (item_id, _) in enumerate(ranked) if item_id == str(episode_id)),
            None,
        )
        if expected_rank is None:
            summary["missing_score"] += 1
            continue
        summary["total"] += 1
        rank_sum += expected_rank
        denom = max(1, len(ranked) - 1)
        percentile = 1.0 if denom == 0 else 1.0 - (expected_rank / denom)
        percentile_sum += percentile
        gap = None
        if expected_score is not None and top_score is not None:
            gap = float(top_score) - float(expected_score)
            gap_sum += gap
        if expected_rank == 0:
            summary["top1"] += 1

        entry_map = {str(entry.get("episode_id")): entry for entry in entries}
        expected_entry = entry_map.get(str(episode_id)) or {}
        top_entry = entry_map.get(str(top_id)) or {}
        items.append(
            {
                "episode_id": str(episode_id),
                "candidate_count": len(pool_ids),
                "trace_count": len(entries),
                "top_id": str(top_id),
                "expected_rank": expected_rank,
                "scores": {
                    "expected": expected_score,
                    "top": top_score,
                    "gap": gap,
                },
                "components": {
                    "expected": {
                        "cosine_raw": expected_entry.get("cosine_raw"),
                        "turn_hist_raw": expected_entry.get("turn_hist_raw"),
                        "lag_dist_raw": expected_entry.get("lag_dist_raw"),
                        "radius_hist_raw": expected_entry.get("radius_hist_raw"),
                        "curvature_hist_raw": expected_entry.get("curvature_hist_raw"),
                        "soft_raw": expected_entry.get("soft_raw"),
                        "soft_dist": expected_entry.get("soft_dist"),
                        "quat_raw": expected_entry.get("quat_raw"),
                        "quat_lambda_raw": expected_entry.get("quat_lambda_raw"),
                    },
                    "top": {
                        "cosine_raw": top_entry.get("cosine_raw"),
                        "turn_hist_raw": top_entry.get("turn_hist_raw"),
                        "lag_dist_raw": top_entry.get("lag_dist_raw"),
                        "radius_hist_raw": top_entry.get("radius_hist_raw"),
                        "curvature_hist_raw": top_entry.get("curvature_hist_raw"),
                        "soft_raw": top_entry.get("soft_raw"),
                        "soft_dist": top_entry.get("soft_dist"),
                        "quat_raw": top_entry.get("quat_raw"),
                        "quat_lambda_raw": top_entry.get("quat_lambda_raw"),
                    },
                    "delta": {
                        "cosine_raw": _component_delta(expected_entry, top_entry, "cosine_raw"),
                        "turn_hist_raw": _component_delta(
                            expected_entry, top_entry, "turn_hist_raw"
                        ),
                        "lag_dist_raw": _component_delta(
                            expected_entry, top_entry, "lag_dist_raw"
                        ),
                        "radius_hist_raw": _component_delta(
                            expected_entry, top_entry, "radius_hist_raw"
                        ),
                        "curvature_hist_raw": _component_delta(
                            expected_entry, top_entry, "curvature_hist_raw"
                        ),
                        "soft_raw": _component_delta(expected_entry, top_entry, "soft_raw"),
                        "soft_dist": _component_delta(expected_entry, top_entry, "soft_dist"),
                        "quat_raw": _component_delta(expected_entry, top_entry, "quat_raw"),
                        "quat_lambda_raw": _component_delta(
                            expected_entry, top_entry, "quat_lambda_raw"
                        ),
                    },
                },
            }
        )

    total = max(1, summary["total"])
    summary["top1"] = summary["top1"] / total if summary["total"] else 0.0
    summary["mean_rank"] = rank_sum / total if summary["total"] else None
    summary["mean_percentile"] = percentile_sum / total if summary["total"] else None
    summary["mean_gap"] = gap_sum / total if summary["total"] else None

    payload: Dict[str, Any] = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "store_root": str(args.live_store_root),
        "pool_size": pool_size,
        "max_episodes": max_episodes,
        "sample_seed": int(args.sample_seed),
        "candidate_count": len(candidate_ids),
        "vector_mode": vector_mode,
        "dims": {
            "vector_dim": vector_dim,
            "trace_dim": trace_dim,
            "match": dim_match,
        },
        "fractal": {
            "alpha": alpha,
            "quat_enabled": quat_enabled,
            "quat_weight": quat_weight,
            "quat_use_lambda": quat_use,
            "soft_dtw_gamma": args.fractal_soft_dtw_gamma,
            "soft_dtw_band": args.fractal_soft_dtw_band,
            "soft_dtw_score_mode": args.fractal_soft_dtw_score_mode,
            "cosine_mode": args.fractal_cosine_mode,
            "trace_norm_mode": trace_norm_mode,
            "query_path_mode": args.query_path_mode,
        },
        "summary": summary,
        "items": items,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
