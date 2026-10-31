from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fram_eval.conversation_memory_eval import DEFAULT_DATASET, DEFAULT_LIVE_DATASET

DEFAULT_OUT_DIR = Path("artifacts/observability")
DEFAULT_LIVE_STORE = Path("storage/memory/cognitive")
DEFAULT_STORAGE_ROOT = Path("storage/observability")


def _parse_list(raw: str) -> List[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _append_flag(args: List[str], flag: str, value: Optional[object]) -> None:
    if value is None:
        return
    args.extend([flag, str(value)])


def _append_bool(args: List[str], flag: str, enabled: bool) -> None:
    if enabled:
        args.append(flag)


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _format_value(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.3f}"
    except (TypeError, ValueError):
        return "n/a"


def _metric(payload: dict, mode: str, field: str, key: str) -> Optional[float]:
    try:
        return float(payload["results"][mode][field].get(key))
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run conversation + shadow evals and emit a summary report.")
    parser.add_argument("--dataset", type=Path, default=None, help="JSONL dataset path.")
    parser.add_argument("--live", action="store_true", help="Use the live cognitive memory store.")
    parser.add_argument("--live-store-root", type=Path, default=DEFAULT_LIVE_STORE, help="Live store root.")
    parser.add_argument("--label", default=None, help="Label for output filenames.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, help="Output directory.")
    parser.add_argument("--no-stamp", action="store_true", help="Do not append a timestamp to the label.")

    parser.add_argument("--fields", default="probe,probe_low_lex", help="Comma-separated query fields.")
    parser.add_argument("--low-lex-fields", default="probe_low_lex", help="Comma-separated low-lex fields.")
    parser.add_argument("--modes", default="semantic,lexical,fractal", help="Comma-separated modes.")
    parser.add_argument("--k-values", default="1,3", help="Comma-separated k values.")
    parser.add_argument("--kinds", default="", help="Comma-separated memory kinds (episode, belief).")
    parser.add_argument("--memory-k", type=int, default=3, help="Memory injection count (shadow eval).")
    parser.add_argument("--pool-multiplier", type=int, default=1, help="Candidate pool multiplier.")

    parser.add_argument("--fractal-alpha", type=float, default=None, help="Override fractal influence alpha.")
    parser.add_argument("--fractal-trace-k", type=int, default=None, help="Override trace-k limit.")
    parser.add_argument("--fractal-quat", action="store_true", help="Enable quaternion weighting.")
    parser.add_argument("--fractal-quat-weight", type=float, default=None, help="Quaternion weight override.")
    parser.add_argument("--fractal-quat-use-lambda", action="store_true", help="Use lambda-weighted quats.")
    parser.add_argument("--fractal-alpha-low-lex", type=float, default=None, help="Alpha for low-lex gate.")
    parser.add_argument("--fractal-low-lex-threshold", type=float, default=None, help="Overlap gate threshold.")
    parser.add_argument("--fractal-low-lex-overlap-mode", default=None, help="Overlap mode (full, answer).")
    parser.add_argument(
        "--fractal-low-lex-sim-threshold",
        type=float,
        default=None,
        help="Similarity gate threshold.",
    )
    parser.add_argument("--fractal-soft-dtw-gamma", type=float, default=None, help="Soft-DTW gamma.")
    parser.add_argument("--fractal-soft-dtw-band", type=float, default=None, help="Soft-DTW band.")
    parser.add_argument("--fractal-soft-dtw-score-mode", default=None, help="Soft-DTW score mode.")
    parser.add_argument("--fractal-cosine-mode", default=None, help="Cosine mode.")
    parser.add_argument("--fractal-trace-norm-mode", default=None, help="Trace norm mode.")
    parser.add_argument("--fractal-query-path-mode", default=None, help="Query path mode.")
    parser.add_argument(
        "--fractal-low-lex-query-path-mode",
        default=None,
        help="Query path mode to use when the low-lex gate triggers.",
    )

    parser.add_argument("--details", action="store_true", help="Include per-item details in eval outputs.")
    parser.add_argument("--details-topk", type=int, default=5, help="Top-k details for conversation eval.")

    parser.add_argument("--top1-margin", type=float, default=0.02, help="Auto-flip top1 margin.")
    parser.add_argument("--shadow-margin", type=float, default=-0.01, help="Auto-flip shadow margin.")
    parser.add_argument("--low-lex-top1-margin", type=float, default=0.02, help="Low-lex top1 margin.")
    parser.add_argument("--low-lex-shadow-margin", type=float, default=-0.01, help="Low-lex shadow margin.")
    parser.add_argument("--min-count", type=int, default=6, help="Auto-flip min count.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dataset = args.dataset
    if dataset is None:
        dataset = DEFAULT_LIVE_DATASET if args.live else DEFAULT_DATASET
    if not dataset.exists():
        raise SystemExit(f"Dataset not found: {dataset}")

    stamp = None if args.no_stamp else _stamp()
    base_label = args.label or dataset.stem or "fractal_eval"
    label = f"{base_label}_{stamp}" if stamp else base_label

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    conv_out = out_dir / f"conversation_memory_eval_{label}.json"
    shadow_out = out_dir / f"memory_shadow_eval_{label}.json"
    autoflip_out = out_dir / f"fractal_autoflip_{label}.json"
    report_out = out_dir / f"fractal_eval_report_{label}.md"

    repo_root = Path(__file__).resolve().parents[1]
    conv_script = repo_root / "scripts" / "conversation_memory_eval.py"
    shadow_script = repo_root / "scripts" / "memory_shadow_eval.py"
    autoflip_script = repo_root / "scripts" / "fractal_autoflip.py"

    common_args: List[str] = []
    _append_flag(common_args, "--dataset", dataset)
    _append_flag(common_args, "--fields", args.fields)
    _append_flag(common_args, "--modes", args.modes)
    _append_flag(common_args, "--k-values", args.k_values)
    _append_flag(common_args, "--kinds", args.kinds if args.kinds else None)
    _append_flag(common_args, "--pool-multiplier", args.pool_multiplier)
    _append_flag(common_args, "--fractal-alpha", args.fractal_alpha)
    _append_flag(common_args, "--fractal-trace-k", args.fractal_trace_k)
    _append_bool(common_args, "--fractal-quat", args.fractal_quat)
    _append_flag(common_args, "--fractal-quat-weight", args.fractal_quat_weight)
    _append_bool(common_args, "--fractal-quat-use-lambda", args.fractal_quat_use_lambda)
    _append_flag(common_args, "--fractal-alpha-low-lex", args.fractal_alpha_low_lex)
    _append_flag(common_args, "--fractal-low-lex-threshold", args.fractal_low_lex_threshold)
    _append_flag(common_args, "--fractal-low-lex-overlap-mode", args.fractal_low_lex_overlap_mode)
    _append_flag(common_args, "--fractal-low-lex-sim-threshold", args.fractal_low_lex_sim_threshold)
    _append_flag(common_args, "--fractal-soft-dtw-gamma", args.fractal_soft_dtw_gamma)
    _append_flag(common_args, "--fractal-soft-dtw-band", args.fractal_soft_dtw_band)
    _append_flag(common_args, "--fractal-soft-dtw-score-mode", args.fractal_soft_dtw_score_mode)
    _append_flag(common_args, "--fractal-cosine-mode", args.fractal_cosine_mode)
    _append_flag(common_args, "--fractal-trace-norm-mode", args.fractal_trace_norm_mode)
    _append_flag(common_args, "--fractal-query-path-mode", args.fractal_query_path_mode)
    _append_flag(
        common_args,
        "--fractal-low-lex-query-path-mode",
        args.fractal_low_lex_query_path_mode,
    )
    _append_bool(common_args, "--details", args.details)

    conv_args = [sys.executable, str(conv_script)] + common_args
    if not args.live:
        conv_store_root = DEFAULT_STORAGE_ROOT / f"conversation_eval_{label}"
        conv_args += ["--store-root", str(conv_store_root)]
    _append_bool(conv_args, "--live", args.live)
    if args.live:
        _append_flag(conv_args, "--live-store-root", args.live_store_root)
    if args.details:
        _append_flag(conv_args, "--details-topk", args.details_topk)
    conv_args += ["--out", str(conv_out)]

    shadow_args = [sys.executable, str(shadow_script)] + common_args
    _append_flag(shadow_args, "--memory-k", args.memory_k)
    _append_bool(shadow_args, "--live", args.live)
    if args.live:
        _append_flag(shadow_args, "--live-store-root", args.live_store_root)
    shadow_args += ["--out", str(shadow_out)]

    subprocess.run(conv_args, cwd=repo_root, check=True)
    subprocess.run(shadow_args, cwd=repo_root, check=True)

    autoflip_args = [
        sys.executable,
        str(autoflip_script),
        "--conversation",
        str(conv_out),
        "--shadow",
        str(shadow_out),
        "--fields",
        args.fields,
        "--low-lex-fields",
        args.low_lex_fields,
        "--top1-margin",
        str(args.top1_margin),
        "--shadow-margin",
        str(args.shadow_margin),
        "--low-lex-top1-margin",
        str(args.low_lex_top1_margin),
        "--low-lex-shadow-margin",
        str(args.low_lex_shadow_margin),
        "--min-count",
        str(args.min_count),
        "--out",
        str(autoflip_out),
    ]
    subprocess.run(autoflip_args, cwd=repo_root, check=True)

    conversation_payload = json.loads(conv_out.read_text(encoding="utf-8"))
    shadow_payload = json.loads(shadow_out.read_text(encoding="utf-8"))
    autoflip_payload = json.loads(autoflip_out.read_text(encoding="utf-8"))

    fields = _parse_list(args.fields)
    modes = _parse_list(args.modes)
    decision = "ENABLE" if autoflip_payload.get("recommend_enable") else "KEEP_OFF"

    lines: List[str] = []
    lines.append("# Fractal Eval Report")
    lines.append("")
    lines.append(f"run_at: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"dataset: {dataset}")
    lines.append(f"live: {args.live}")
    lines.append(f"label: {label}")
    lines.append(f"conversation_eval: {conv_out}")
    lines.append(f"shadow_eval: {shadow_out}")
    lines.append(f"autoflip: {autoflip_out}")
    lines.append("")
    lines.append("## Conversation Eval (top1)")
    lines.append("| field | count | semantic | lexical | fractal |")
    lines.append("| --- | --- | --- | --- | --- |")
    for field in fields:
        count = (
            _metric(conversation_payload, "fractal", field, "count")
            or _metric(conversation_payload, "semantic", field, "count")
            or _metric(conversation_payload, "lexical", field, "count")
        )
        count_text = f"{int(count)}" if count is not None else "n/a"
        sem = _format_value(_metric(conversation_payload, "semantic", field, "top1"))
        lex = _format_value(_metric(conversation_payload, "lexical", field, "top1"))
        frac = _format_value(_metric(conversation_payload, "fractal", field, "top1"))
        lines.append(f"| {field} | {count_text} | {sem} | {lex} | {frac} |")

    lines.append("")
    lines.append("## Shadow Eval (avg_delta)")
    lines.append("| field | count | semantic | lexical | fractal |")
    lines.append("| --- | --- | --- | --- | --- |")
    for field in fields:
        count = (
            _metric(shadow_payload, "fractal", field, "count")
            or _metric(shadow_payload, "semantic", field, "count")
            or _metric(shadow_payload, "lexical", field, "count")
        )
        count_text = f"{int(count)}" if count is not None else "n/a"
        sem = _format_value(_metric(shadow_payload, "semantic", field, "avg_delta"))
        lex = _format_value(_metric(shadow_payload, "lexical", field, "avg_delta"))
        frac = _format_value(_metric(shadow_payload, "fractal", field, "avg_delta"))
        lines.append(f"| {field} | {count_text} | {sem} | {lex} | {frac} |")

    lines.append("")
    lines.append("## Auto-flip Recommendation")
    lines.append(f"decision: {decision}")
    reasons = autoflip_payload.get("reasons") or []
    if reasons:
        lines.append("reasons:")
        lines.extend([f"- {reason}" for reason in reasons])
    if modes:
        lines.append("")
        lines.append(f"modes: {', '.join(modes)}")

    report_out.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
