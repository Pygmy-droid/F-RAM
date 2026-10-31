from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from fram_eval.conversation_memory_eval import (
    DEFAULT_DATASET,
    DEFAULT_LIVE_DATASET,
    build_eval_store,
    build_fractal_ranker,
    build_query_vectorizer,
    evaluate_items,
    load_eval_items,
    resolve_live_id_map,
)
from fram_serving.config import FRAMConfig
from fram_serving.memory import CognitiveMemoryStore

DEFAULT_OUT = Path("storage/observability/conversation_memory_eval.json")
DEFAULT_LIVE_OUT = Path("storage/observability/conversation_memory_eval_live.json")


def _parse_list(raw: str) -> List[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Conversation memory evaluation harness.")
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
        "--modes",
        default="semantic,lexical",
        help="Comma-separated modes (semantic uses embeddings, lexical disables them).",
    )
    parser.add_argument(
        "--k-values",
        default="1,3",
        help="Comma-separated top-k values for accuracy.",
    )
    parser.add_argument(
        "--kinds",
        default="",
        help="Comma-separated memory kinds to include (episode, belief). Empty = all.",
    )
    parser.add_argument(
        "--store-root",
        type=Path,
        default=None,
        help="Optional root directory for the temporary cognitive store.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="Output JSON path.",
    )
    parser.add_argument(
        "--pool-multiplier",
        type=int,
        default=1,
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
        "--fractal-low-lex-query-path-mode",
        default=None,
        help="Query path mode to use when the low-lex gate triggers (synthetic, ifs).",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Evaluate against the live cognitive memory store (no temp store).",
    )
    parser.add_argument(
        "--live-store-root",
        type=Path,
        default=Path("storage/memory/cognitive"),
        help="Cognitive memory root for --live.",
    )
    parser.add_argument(
        "--details",
        action="store_true",
        help="Include per-probe rank details in the output.",
    )
    parser.add_argument(
        "--details-topk",
        type=int,
        default=5,
        help="How many top results to include per probe when --details is set.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    fields = _parse_list(args.fields)
    modes = _parse_list(args.modes)
    k_values = [int(value) for value in _parse_list(args.k_values)]
    kinds = _parse_list(args.kinds)
    dataset_path = args.dataset
    if args.live and dataset_path == DEFAULT_DATASET:
        dataset_path = DEFAULT_LIVE_DATASET
    items = load_eval_items(dataset_path)

    cfg = FRAMConfig.from_env()
    out_path = args.out
    if args.live and out_path == DEFAULT_OUT:
        out_path = DEFAULT_LIVE_OUT

    live_stats = None
    if args.live:
        store_root = args.live_store_root
        store = CognitiveMemoryStore(store_root, config=cfg)
        id_map, live_stats = resolve_live_id_map(items, store=store)
        vectorizer = build_query_vectorizer(cfg)
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        base_root = args.store_root or (out_path.parent / f"conversation_eval_{stamp}")
        store_root = Path(base_root) / "cognitive"
        store, id_map, vectorizer = build_eval_store(items, store_root=store_root, config=cfg)

    results = {}
    details_payload = {} if args.details else None
    fractal_stats = None
    for mode in modes:
        mode_key = mode.lower()
        results[mode_key] = {}
        ranker = None
        mode_vectorizer = vectorizer if mode_key == "semantic" else None
        if mode_key == "fractal":
            ranker = build_fractal_ranker(
                store,
                vectorizer=vectorizer,
                config=cfg,
                pool_multiplier=args.pool_multiplier,
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
                low_lex_query_path_mode=args.fractal_low_lex_query_path_mode,
                kinds=kinds or None,
            )
            mode_vectorizer = None
        for field in fields:
            detail_rows = [] if args.details else None
            metrics = evaluate_items(
                items,
                store=store,
                id_map=id_map,
                query_field=field,
                vectorizer=mode_vectorizer,
                k_values=k_values,
                ranker=ranker,
                skip_missing_expected=args.live,
                details=detail_rows,
                details_topk=args.details_topk,
                kinds=kinds or None,
            )
            results[mode_key][field] = metrics
            if args.details and detail_rows is not None:
                details_payload.setdefault(mode_key, {})[field] = {
                    "topk": args.details_topk,
                    "items": detail_rows,
                }
        if mode_key == "fractal" and ranker is not None:
            fractal_stats = getattr(ranker, "stats", None)

    payload = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "run_mode": "live" if args.live else "synthetic",
        "config": {
            "dataset": str(dataset_path),
            "fields": fields,
            "modes": modes,
            "k_values": k_values,
            "kinds": kinds,
            "store_root": str(store_root),
            "defaults": {
                "default_query_reads": cfg.default_query_reads,
                "cognitive_memory_k": cfg.cognitive_memory_k,
                "cognitive_memory_token_budget": cfg.cognitive_memory_token_budget,
                "cognitive_memory_slot_budget": getattr(cfg, "cognitive_memory_slot_budget", None),
            },
            "count": len(items),
        },
        "results": results,
    }
    if args.details and details_payload is not None:
        payload["details"] = details_payload
    if args.live:
        payload["config"]["live"] = {
            "store_root": str(store_root),
            "match_query_field": "match_query",
            "match_answer_field": "match_answer",
            "match_domain_field": "match_domain",
            "match_task_field": "match_task",
            "matched": live_stats.get("matched", 0) if live_stats else 0,
            "matched_by_id": live_stats.get("matched_by_id", 0) if live_stats else 0,
            "missing": live_stats.get("missing", 0) if live_stats else 0,
            "ambiguous": live_stats.get("ambiguous", 0) if live_stats else 0,
        }
    if "fractal" in modes:
        payload["config"]["fractal"] = {
            "pool_multiplier": args.pool_multiplier,
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
            "low_lex_query_path_mode": args.fractal_low_lex_query_path_mode,
        }
        if fractal_stats:
            payload["config"]["fractal"]["low_lex_gate"] = {
                key: value for key, value in fractal_stats.items() if not str(key).startswith("_")
            }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
