from __future__ import annotations

import argparse
import json
from pathlib import Path

from fram_eval.memory_shadow_eval import (
    DEFAULT_DATASET,
    DEFAULT_LIVE_DATASET,
    DEFAULT_LIVE_OUT,
    DEFAULT_OUT,
    run_shadow_eval,
)


def _parse_list(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Memory shadow eval (embedding-shift proxy).")
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
        default="semantic,lexical,fractal",
        help="Comma-separated modes (semantic, lexical, fractal).",
    )
    parser.add_argument(
        "--k-values",
        default="1,3",
        help="Comma-separated top-k values for retrieval metrics.",
    )
    parser.add_argument(
        "--kinds",
        default="",
        help="Comma-separated memory kinds to include (episode, belief). Empty = all.",
    )
    parser.add_argument(
        "--memory-k",
        type=int,
        default=3,
        help="How many retrieved memories to append when building the augmented query.",
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
        "--details",
        action="store_true",
        help="Include per-probe details in the output JSON.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Evaluate against the live cognitive memory store (no temp store).",
    )
    parser.add_argument(
        "--live-store-root",
        type=Path,
        default=None,
        help="Cognitive memory root for --live.",
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
    modes = _parse_list(args.modes)
    k_values = [int(value) for value in _parse_list(args.k_values)]
    kinds = _parse_list(args.kinds)
    dataset_path = args.dataset
    if args.live and dataset_path == DEFAULT_DATASET:
        dataset_path = DEFAULT_LIVE_DATASET
    out_path = args.out
    if args.live and out_path == DEFAULT_OUT:
        out_path = DEFAULT_LIVE_OUT
    payload = run_shadow_eval(
        dataset_path=dataset_path,
        modes=modes,
        fields=fields,
        kinds=kinds or None,
        k_values=k_values,
        memory_k=args.memory_k,
        pool_multiplier=args.pool_multiplier,
        fractal_alpha=args.fractal_alpha,
        fractal_trace_k=args.fractal_trace_k,
        fractal_quat=args.fractal_quat,
        fractal_quat_weight=args.fractal_quat_weight,
        fractal_quat_use_lambda=args.fractal_quat_use_lambda,
        fractal_alpha_low_lex=args.fractal_alpha_low_lex,
        fractal_low_lex_threshold=args.fractal_low_lex_threshold,
        fractal_low_lex_similarity_threshold=args.fractal_low_lex_sim_threshold,
        fractal_low_lex_overlap_mode=args.fractal_low_lex_overlap_mode,
        fractal_soft_dtw_gamma=args.fractal_soft_dtw_gamma,
        fractal_soft_dtw_band=args.fractal_soft_dtw_band,
        fractal_soft_dtw_score_mode=args.fractal_soft_dtw_score_mode,
        fractal_cosine_mode=args.fractal_cosine_mode,
        fractal_trace_norm_mode=args.fractal_trace_norm_mode,
        fractal_query_path_mode=args.fractal_query_path_mode,
        fractal_low_lex_query_path_mode=args.fractal_low_lex_query_path_mode,
        include_details=args.details,
        live=args.live,
        live_store_root=args.live_store_root,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
