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


def _metric(payload: dict, mode: str, field: str, key: str) -> Optional[float]:
    try:
        return float(payload["results"][mode][field].get(key))
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


def _format_value(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.3f}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run two-pass conversation + shadow evals (probe vs low-lex) and emit a summary report."
    )
    parser.add_argument("--dataset", type=Path, default=None, help="JSONL dataset path.")
    parser.add_argument("--live", action="store_true", help="Use the live cognitive memory store.")
    parser.add_argument("--live-store-root", type=Path, default=DEFAULT_LIVE_STORE, help="Live store root.")
    parser.add_argument("--label", default=None, help="Label for output filenames.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, help="Output directory.")
    parser.add_argument("--no-stamp", action="store_true", help="Do not append a timestamp to the label.")

    parser.add_argument("--probe-field", default="probe", help="Probe field name.")
    parser.add_argument("--low-lex-field", default="probe_low_lex", help="Low-lex field name.")
    parser.add_argument(
        "--probe-query-path-mode",
        default="synthetic",
        help="Query path mode for probe field (synthetic, ifs).",
    )
    parser.add_argument(
        "--low-lex-query-path-mode",
        default="ifs",
        help="Query path mode for low-lex field (synthetic, ifs).",
    )

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

    parser.add_argument("--top1-margin", type=float, default=0.02, help="Auto-flip top1 margin.")
    parser.add_argument("--shadow-margin", type=float, default=-0.01, help="Auto-flip shadow margin.")
    parser.add_argument("--low-lex-top1-margin", type=float, default=0.02, help="Low-lex top1 margin.")
    parser.add_argument("--low-lex-shadow-margin", type=float, default=-0.01, help="Low-lex shadow margin.")
    parser.add_argument("--min-count", type=int, default=6, help="Auto-flip min count.")
    return parser.parse_args()


def _run_eval(
    *,
    script: Path,
    out_path: Path,
    dataset: Path,
    field: str,
    path_mode: str,
    args: argparse.Namespace,
) -> None:
    cmd: List[str] = [sys.executable, str(script)]
    cmd += ["--dataset", str(dataset)]
    cmd += ["--fields", field]
    cmd += ["--modes", args.modes]
    cmd += ["--k-values", args.k_values]
    _append_flag(cmd, "--kinds", args.kinds if args.kinds else None)
    _append_flag(cmd, "--pool-multiplier", args.pool_multiplier)
    _append_flag(cmd, "--fractal-alpha", args.fractal_alpha)
    _append_flag(cmd, "--fractal-trace-k", args.fractal_trace_k)
    _append_bool(cmd, "--fractal-quat", args.fractal_quat)
    _append_flag(cmd, "--fractal-quat-weight", args.fractal_quat_weight)
    _append_bool(cmd, "--fractal-quat-use-lambda", args.fractal_quat_use_lambda)
    _append_flag(cmd, "--fractal-alpha-low-lex", args.fractal_alpha_low_lex)
    _append_flag(cmd, "--fractal-low-lex-threshold", args.fractal_low_lex_threshold)
    _append_flag(cmd, "--fractal-low-lex-overlap-mode", args.fractal_low_lex_overlap_mode)
    _append_flag(cmd, "--fractal-low-lex-sim-threshold", args.fractal_low_lex_sim_threshold)
    _append_flag(cmd, "--fractal-soft-dtw-gamma", args.fractal_soft_dtw_gamma)
    _append_flag(cmd, "--fractal-soft-dtw-band", args.fractal_soft_dtw_band)
    _append_flag(cmd, "--fractal-soft-dtw-score-mode", args.fractal_soft_dtw_score_mode)
    _append_flag(cmd, "--fractal-cosine-mode", args.fractal_cosine_mode)
    _append_flag(cmd, "--fractal-trace-norm-mode", args.fractal_trace_norm_mode)
    _append_flag(cmd, "--fractal-query-path-mode", path_mode)
    _append_bool(cmd, "--live", args.live)
    if args.live:
        _append_flag(cmd, "--live-store-root", args.live_store_root)
    if script.name == "memory_shadow_eval.py":
        _append_flag(cmd, "--memory-k", args.memory_k)
    cmd += ["--out", str(out_path)]
    subprocess.run(cmd, cwd=Path(__file__).resolve().parents[1], check=True)


def _merge_payload(
    base: dict,
    override: dict,
    *,
    field: str,
    probe_field: str,
    low_lex_field: str,
    probe_mode: str,
    low_lex_mode: str,
    sources: dict,
) -> dict:
    merged = json.loads(json.dumps(base))
    merged["run_at"] = datetime.now(timezone.utc).isoformat()
    merged.setdefault("config", {})
    merged["config"]["fields"] = [probe_field, low_lex_field]
    merged["config"]["two_pass"] = {
        "probe_field": probe_field,
        "low_lex_field": low_lex_field,
        "probe_query_path_mode": probe_mode,
        "low_lex_query_path_mode": low_lex_mode,
        "sources": sources,
    }
    for mode, payload in override.get("results", {}).items():
        if mode not in merged.get("results", {}):
            continue
        merged["results"][mode][field] = payload.get(field)
    return merged


def main() -> None:
    args = parse_args()
    dataset = args.dataset
    if dataset is None:
        dataset = DEFAULT_LIVE_DATASET if args.live else DEFAULT_DATASET
    if not dataset.exists():
        raise SystemExit(f"Dataset not found: {dataset}")

    stamp = None if args.no_stamp else _stamp()
    base_label = args.label or dataset.stem or "fractal_two_pass"
    label = f"{base_label}_{stamp}" if stamp else base_label

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    probe_field = str(args.probe_field).strip()
    low_lex_field = str(args.low_lex_field).strip()
    probe_mode = str(args.probe_query_path_mode).strip().lower()
    low_lex_mode = str(args.low_lex_query_path_mode).strip().lower()

    conv_probe_out = out_dir / f"conversation_memory_eval_{label}_probe.json"
    conv_low_out = out_dir / f"conversation_memory_eval_{label}_lowlex.json"
    shadow_probe_out = out_dir / f"memory_shadow_eval_{label}_probe.json"
    shadow_low_out = out_dir / f"memory_shadow_eval_{label}_lowlex.json"

    repo_root = Path(__file__).resolve().parents[1]
    conv_script = repo_root / "scripts" / "conversation_memory_eval.py"
    shadow_script = repo_root / "scripts" / "memory_shadow_eval.py"
    autoflip_script = repo_root / "scripts" / "fractal_autoflip.py"

    _run_eval(
        script=conv_script,
        out_path=conv_probe_out,
        dataset=dataset,
        field=probe_field,
        path_mode=probe_mode,
        args=args,
    )
    _run_eval(
        script=conv_script,
        out_path=conv_low_out,
        dataset=dataset,
        field=low_lex_field,
        path_mode=low_lex_mode,
        args=args,
    )
    _run_eval(
        script=shadow_script,
        out_path=shadow_probe_out,
        dataset=dataset,
        field=probe_field,
        path_mode=probe_mode,
        args=args,
    )
    _run_eval(
        script=shadow_script,
        out_path=shadow_low_out,
        dataset=dataset,
        field=low_lex_field,
        path_mode=low_lex_mode,
        args=args,
    )

    conv_probe = json.loads(conv_probe_out.read_text(encoding="utf-8"))
    conv_low = json.loads(conv_low_out.read_text(encoding="utf-8"))
    shadow_probe = json.loads(shadow_probe_out.read_text(encoding="utf-8"))
    shadow_low = json.loads(shadow_low_out.read_text(encoding="utf-8"))

    sources = {
        "conversation": {"probe": str(conv_probe_out), "low_lex": str(conv_low_out)},
        "shadow": {"probe": str(shadow_probe_out), "low_lex": str(shadow_low_out)},
    }

    conv_out = out_dir / f"conversation_memory_eval_{label}.json"
    shadow_out = out_dir / f"memory_shadow_eval_{label}.json"
    conv_merged = _merge_payload(
        conv_probe,
        conv_low,
        field=low_lex_field,
        probe_field=probe_field,
        low_lex_field=low_lex_field,
        probe_mode=probe_mode,
        low_lex_mode=low_lex_mode,
        sources=sources,
    )
    shadow_merged = _merge_payload(
        shadow_probe,
        shadow_low,
        field=low_lex_field,
        probe_field=probe_field,
        low_lex_field=low_lex_field,
        probe_mode=probe_mode,
        low_lex_mode=low_lex_mode,
        sources=sources,
    )
    conv_out.write_text(json.dumps(conv_merged, indent=2, ensure_ascii=False), encoding="utf-8")
    shadow_out.write_text(json.dumps(shadow_merged, indent=2, ensure_ascii=False), encoding="utf-8")

    autoflip_out = out_dir / f"fractal_autoflip_{label}.json"
    report_out = out_dir / f"fractal_eval_report_{label}.md"

    autoflip_args = [
        sys.executable,
        str(autoflip_script),
        "--conversation",
        str(conv_out),
        "--shadow",
        str(shadow_out),
        "--fields",
        f"{probe_field},{low_lex_field}",
        "--low-lex-fields",
        low_lex_field,
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

    autoflip_payload = json.loads(autoflip_out.read_text(encoding="utf-8"))
    fields = conv_merged.get("config", {}).get("fields", [])
    modes = conv_merged.get("config", {}).get("modes", [])

    live_stats = conv_merged.get("config", {}).get("live")
    if isinstance(live_stats, dict):
        live_summary = (
            f"matched={live_stats.get('matched')}, missing={live_stats.get('missing')}, "
            f"ambiguous={live_stats.get('ambiguous')}"
        )
    else:
        live_summary = None

    lines: List[str] = []
    lines.append("# Fractal Eval Report")
    lines.append("")
    lines.append(f"run_at: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"dataset: {conv_merged.get('config', {}).get('dataset')}")
    lines.append("live: True")
    if live_summary:
        lines.append(f"live_stats: {live_summary}")
    lines.append(f"label: {label}")
    lines.append(f"conversation_eval: {conv_out}")
    lines.append(f"shadow_eval: {shadow_out}")
    lines.append(f"autoflip: {autoflip_out}")
    lines.append("")
    lines.append("## Conversation Eval (top1)")
    lines.append("| field | count | semantic | lexical | fractal |")
    lines.append("| --- | --- | --- | --- | --- |")
    for field in fields:
        count = _metric(conv_merged, "semantic", field, "count")
        row = [
            field,
            str(int(count)) if count is not None else "n/a",
            _format_value(_metric(conv_merged, "semantic", field, "top1")),
            _format_value(_metric(conv_merged, "lexical", field, "top1")),
            _format_value(_metric(conv_merged, "fractal", field, "top1")),
        ]
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    lines.append("## Shadow Eval (avg_delta)")
    lines.append("| field | count | semantic | lexical | fractal |")
    lines.append("| --- | --- | --- | --- | --- |")
    for field in fields:
        count = _metric(shadow_merged, "semantic", field, "count")
        row = [
            field,
            str(int(count)) if count is not None else "n/a",
            _format_value(_metric(shadow_merged, "semantic", field, "avg_delta")),
            _format_value(_metric(shadow_merged, "lexical", field, "avg_delta")),
            _format_value(_metric(shadow_merged, "fractal", field, "avg_delta")),
        ]
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    lines.append("## Auto-flip Recommendation")
    lines.append(f"decision: {'ENABLE' if autoflip_payload.get('recommend_enable') else 'KEEP_OFF'}")
    lines.append("reasons:")
    for reason in autoflip_payload.get("reasons", []) or []:
        lines.append(f"- {reason}")
    lines.append("")
    lines.append(f"modes: {', '.join(modes)}")
    report_out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(report_out)


if __name__ == "__main__":
    raise SystemExit(main())
