from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence

from fram_eval.conversation_memory_eval import (
    _compute_trace_entries,
    _embed_text,
    _score_trace_entries,
    build_fractal_ranker,
    build_query_vectorizer,
    load_eval_items,
    resolve_live_id_map,
)
from fram_serving.config import FRAMConfig
from fram_serving.memory import CognitiveMemoryStore

DEFAULT_DATASET = Path("fram_eval/data/conversation_memory_live_paraphrase_hard_micro_v3.jsonl")
DEFAULT_OUT = Path("storage/observability/fractal_trace_ablation_report.json")


def _parse_list(raw: str) -> List[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _component_delta(expected: Dict[str, Any], top: Dict[str, Any], key: str) -> float | None:
    exp_val = expected.get(key)
    top_val = top.get(key)
    if exp_val is None or top_val is None:
        return None
    try:
        return float(top_val) - float(exp_val)
    except (TypeError, ValueError):
        return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Per-probe trace ablation report (expected vs top scores/components)."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
        help=f"JSONL dataset path (default: {DEFAULT_DATASET}).",
    )
    parser.add_argument(
        "--fields",
        default="probe,probe_low_lex",
        help="Comma-separated query fields to evaluate.",
    )
    parser.add_argument(
        "--k-max",
        type=int,
        default=5,
        help="Top-k depth to use for candidate pool sizing.",
    )
    parser.add_argument(
        "--kinds",
        default="episode",
        help="Comma-separated memory kinds to include (episode, belief).",
    )
    parser.add_argument(
        "--pool-multiplier",
        type=int,
        default=3,
        help="Multiplier for candidate pool size (fractal mode).",
    )
    parser.add_argument(
        "--fractal-alpha",
        type=float,
        default=None,
        help="Override fractal influence alpha in fractal mode.",
    )
    parser.add_argument(
        "--fractal-trace-k",
        type=int,
        default=None,
        help="Override cognitive_memory_trace_k in fractal mode.",
    )
    parser.add_argument(
        "--fractal-quat",
        action="store_true",
        default=None,
        help="Enable quaternion weighting in fractal mode.",
    )
    parser.add_argument(
        "--fractal-quat-weight",
        type=float,
        default=None,
        help="Override FRAM_FRACTAL_QUAT_WEIGHT in fractal mode.",
    )
    parser.add_argument(
        "--fractal-quat-use-lambda",
        action="store_true",
        default=None,
        help="Use lambda-weighted quaternion alignment in fractal mode.",
    )
    parser.add_argument(
        "--fractal-alpha-low-lex",
        type=float,
        default=None,
        help="Override fractal influence alpha for low-lex queries.",
    )
    parser.add_argument(
        "--fractal-low-lex-threshold",
        type=float,
        default=None,
        help="Token overlap threshold for low-lex gating (0-1).",
    )
    parser.add_argument(
        "--fractal-low-lex-overlap-mode",
        default=None,
        help="Overlap mode for low-lex gating (full, answer).",
    )
    parser.add_argument(
        "--fractal-low-lex-sim-threshold",
        type=float,
        default=None,
        help="Semantic similarity threshold for low-lex gating (cosine).",
    )
    parser.add_argument(
        "--fractal-soft-dtw-gamma",
        type=float,
        default=None,
        help="Override soft-DTW gamma for fractal trace scoring.",
    )
    parser.add_argument(
        "--fractal-soft-dtw-band",
        type=float,
        default=None,
        help="Override soft-DTW band for fractal trace scoring.",
    )
    parser.add_argument(
        "--fractal-soft-dtw-score-mode",
        default=None,
        help="Soft-DTW score transform (inverse, exp).",
    )
    parser.add_argument(
        "--fractal-cosine-mode",
        default=None,
        help="Cosine target for trace scoring (composite, centroid, delta, turn_hist, lag_dist, radius_hist, curvature_hist).",
    )
    parser.add_argument(
        "--fractal-trace-norm-mode",
        default=None,
        help="Trace normalization mode (minmax, percentile).",
    )
    parser.add_argument(
        "--fractal-query-path-mode",
        default=None,
        help="Query path mode for trace scoring (synthetic, ifs).",
    )
    parser.add_argument(
        "--live-store-root",
        type=Path,
        default=Path("storage/memory/cognitive"),
        help="Cognitive memory root for live evals.",
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
    fields = _parse_list(args.fields)
    kinds = _parse_list(args.kinds)
    pool_multiplier = max(1, int(args.pool_multiplier))
    k_max = max(1, int(args.k_max))
    cfg = FRAMConfig.from_env()
    items = load_eval_items(args.dataset)
    store = CognitiveMemoryStore(args.live_store_root, config=cfg)
    id_map, live_stats = resolve_live_id_map(items, store=store)
    vectorizer = build_query_vectorizer(cfg)
    ranker = build_fractal_ranker(
        store,
        vectorizer=vectorizer,
        config=cfg,
        pool_multiplier=pool_multiplier,
        trace_limit=args.fractal_trace_k,
        influence_alpha=args.fractal_alpha,
        quat_enabled=args.fractal_quat,
        quat_weight=args.fractal_quat_weight,
        quat_use_lambda=args.fractal_quat_use_lambda,
        low_lex_alpha=args.fractal_alpha_low_lex,
        low_lex_threshold=args.fractal_low_lex_threshold,
        low_lex_similarity_threshold=args.fractal_low_lex_sim_threshold,
        low_lex_overlap_mode=args.fractal_low_lex_overlap_mode,
        soft_dtw_gamma=args.fractal_soft_dtw_gamma,
        soft_dtw_band=args.fractal_soft_dtw_band,
        soft_dtw_score_mode=args.fractal_soft_dtw_score_mode,
        cosine_mode=args.fractal_cosine_mode,
        trace_norm_mode=args.fractal_trace_norm_mode,
        query_path_mode=args.fractal_query_path_mode,
        kinds=kinds or None,
    )
    filters = {"kinds": kinds} if kinds else None
    payload: Dict[str, Any] = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "dataset": str(args.dataset),
        "fields": fields,
        "pool_multiplier": pool_multiplier,
        "k_max": k_max,
        "kinds": kinds,
        "live": {
            "store_root": str(args.live_store_root),
            "matched": live_stats.get("matched", 0),
            "matched_by_id": live_stats.get("matched_by_id", 0),
            "missing": live_stats.get("missing", 0),
            "ambiguous": live_stats.get("ambiguous", 0),
        },
        "fractal": {
            "alpha": args.fractal_alpha if args.fractal_alpha is not None else cfg.fractal_influence_alpha,
            "trace_k": args.fractal_trace_k,
            "trace_k_default": cfg.cognitive_memory_trace_k,
            "quat_enabled": bool(args.fractal_quat) if args.fractal_quat is not None else cfg.fractal_quat_influence,
            "quat_weight": args.fractal_quat_weight if args.fractal_quat_weight is not None else cfg.fractal_quat_weight,
            "quat_use_lambda": (
                bool(args.fractal_quat_use_lambda)
                if args.fractal_quat_use_lambda is not None
                else cfg.fractal_quat_use_lambda
            ),
            "low_lex_alpha": args.fractal_alpha_low_lex,
            "low_lex_threshold": args.fractal_low_lex_threshold,
            "low_lex_similarity_threshold": args.fractal_low_lex_sim_threshold,
            "low_lex_overlap_mode": args.fractal_low_lex_overlap_mode,
            "soft_dtw_gamma": args.fractal_soft_dtw_gamma,
            "soft_dtw_band": args.fractal_soft_dtw_band,
            "soft_dtw_score_mode": args.fractal_soft_dtw_score_mode,
            "cosine_mode": args.fractal_cosine_mode,
            "trace_norm_mode": args.fractal_trace_norm_mode,
            "query_path_mode": args.fractal_query_path_mode,
        },
        "items": [],
    }
    for item in items:
        item_id = str(item.get("id") or "")
        expected_id = id_map.get(item_id)
        if not expected_id:
            continue
        for field in fields:
            query = str(item.get(field) or "")
            if not query:
                continue
            query_vector = _embed_text(query, vectorizer=vectorizer)
            if not query_vector:
                continue
            pool_size = max(1, k_max * pool_multiplier)
            base_results = store.search(
                query,
                k=pool_size,
                filters=filters,
                vectorizer=vectorizer,
            )
            candidate_ids = [str(result.get("id")) for result in base_results if result.get("id")]
            entries = _compute_trace_entries(
                store,
                candidate_ids=candidate_ids,
                query_vector=query_vector,
                config=cfg,
                soft_dtw_gamma=args.fractal_soft_dtw_gamma,
                soft_dtw_band=args.fractal_soft_dtw_band,
                soft_dtw_score_mode=args.fractal_soft_dtw_score_mode,
                cosine_mode=args.fractal_cosine_mode,
                query_path_mode=args.fractal_query_path_mode,
            )
            entry_map = {str(entry.get("episode_id")): entry for entry in entries}
            ranked = ranker(query, k_max)
            top_id = str(ranked[0].get("id")) if ranked else None
            expected_entry = entry_map.get(str(expected_id)) or {}
            top_entry = entry_map.get(str(top_id)) if top_id else {}
            score_map = _score_trace_entries(
                entries,
                alpha=float(getattr(cfg, "fractal_blend_alpha", 0.4)),
                quat_enabled=bool(
                    args.fractal_quat if args.fractal_quat is not None else cfg.fractal_quat_influence
                ),
                quat_weight=float(
                    args.fractal_quat_weight
                    if args.fractal_quat_weight is not None
                    else cfg.fractal_quat_weight
                ),
                quat_use=bool(
                    args.fractal_quat_use_lambda
                    if args.fractal_quat_use_lambda is not None
                    else cfg.fractal_quat_use_lambda
                ),
                trace_norm_mode=str(args.fractal_trace_norm_mode or "minmax"),
            )
            expected_score = score_map.get(str(expected_id))
            top_score = score_map.get(str(top_id)) if top_id else None
            expected_rank = None
            for idx, result in enumerate(ranked):
                if str(result.get("id")) == str(expected_id):
                    expected_rank = idx
                    break
            payload["items"].append(
                {
                    "id": item_id,
                    "field": field,
                    "query": query,
                    "expected_id": expected_id,
                    "top_id": top_id,
                    "expected_rank": expected_rank,
                    "candidate_count": len(candidate_ids),
                    "trace_count": len(entries),
                    "scores": {
                        "expected": expected_score,
                        "top": top_score,
                        "gap": (top_score - expected_score) if (expected_score is not None and top_score is not None) else None,
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
                            "turn_hist_raw": _component_delta(expected_entry, top_entry, "turn_hist_raw"),
                            "lag_dist_raw": _component_delta(expected_entry, top_entry, "lag_dist_raw"),
                            "radius_hist_raw": _component_delta(expected_entry, top_entry, "radius_hist_raw"),
                            "curvature_hist_raw": _component_delta(expected_entry, top_entry, "curvature_hist_raw"),
                            "soft_raw": _component_delta(expected_entry, top_entry, "soft_raw"),
                            "soft_dist": _component_delta(expected_entry, top_entry, "soft_dist"),
                            "quat_raw": _component_delta(expected_entry, top_entry, "quat_raw"),
                            "quat_lambda_raw": _component_delta(expected_entry, top_entry, "quat_lambda_raw"),
                        },
                    },
                }
            )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
