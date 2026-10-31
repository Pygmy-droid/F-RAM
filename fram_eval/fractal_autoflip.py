from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

DEFAULT_CONVERSATION_EVAL = Path("storage/observability/conversation_memory_eval_live.json")
DEFAULT_SHADOW_EVAL = Path("storage/observability/memory_shadow_eval_live.json")
DEFAULT_OUT = Path("storage/observability/fractal_autoflip.json")

BASELINE_MODES = ("semantic", "lexical")


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _metric(payload: Dict[str, Any], mode: str, field: str, key: str) -> Optional[float]:
    try:
        return _safe_float(payload["results"][mode][field].get(key))
    except (KeyError, AttributeError, TypeError):
        return None


def _baseline_metric(
    payload: Dict[str, Any],
    field: str,
    key: str,
    modes: Sequence[str] = BASELINE_MODES,
) -> tuple[Optional[float], Dict[str, Optional[float]]]:
    values: Dict[str, Optional[float]] = {mode: _metric(payload, mode, field, key) for mode in modes}
    available = [value for value in values.values() if value is not None]
    if not available:
        return None, values
    return max(available), values


def _counts_ok(counts: Iterable[Optional[float]], min_count: int) -> bool:
    values = [count for count in counts if count is not None]
    if not values:
        return False
    return min(values) >= float(min_count)


def recommend_fractal_influence(
    conversation_payload: Dict[str, Any],
    shadow_payload: Dict[str, Any],
    *,
    fields: Sequence[str],
    low_lex_fields: Sequence[str],
    top1_margin: float = 0.02,
    shadow_margin: float = -0.01,
    low_lex_top1_margin: float = 0.02,
    low_lex_shadow_margin: float = -0.01,
    min_count: int = 6,
) -> Dict[str, Any]:
    reasons: List[str] = []
    field_reports: Dict[str, Any] = {}
    low_lex_set = {field.strip() for field in low_lex_fields}
    overall_ok = True

    for field in fields:
        field = str(field).strip()
        if not field:
            continue
        top1_req = low_lex_top1_margin if field in low_lex_set else top1_margin
        shadow_req = low_lex_shadow_margin if field in low_lex_set else shadow_margin

        conv_fractal_top1 = _metric(conversation_payload, "fractal", field, "top1")
        conv_baseline_top1, conv_baseline_modes = _baseline_metric(
            conversation_payload, field, "top1"
        )
        conv_fractal_count = _metric(conversation_payload, "fractal", field, "count")
        conv_baseline_count, conv_baseline_counts = _baseline_metric(
            conversation_payload, field, "count"
        )

        shadow_fractal_delta = _metric(shadow_payload, "fractal", field, "avg_delta")
        shadow_baseline_delta, shadow_baseline_modes = _baseline_metric(
            shadow_payload, field, "avg_delta"
        )
        shadow_fractal_count = _metric(shadow_payload, "fractal", field, "count")
        shadow_baseline_count, shadow_baseline_counts = _baseline_metric(
            shadow_payload, field, "count"
        )

        missing: List[str] = []
        if conv_fractal_top1 is None:
            missing.append("conversation.fractal.top1")
        if conv_baseline_top1 is None:
            missing.append("conversation.baseline.top1")
        if shadow_fractal_delta is None:
            missing.append("shadow.fractal.avg_delta")
        if shadow_baseline_delta is None:
            missing.append("shadow.baseline.avg_delta")

        conv_counts_ok = _counts_ok([conv_fractal_count, conv_baseline_count], min_count)
        shadow_counts_ok = _counts_ok([shadow_fractal_count, shadow_baseline_count], min_count)
        counts_ok = conv_counts_ok and shadow_counts_ok

        top1_ok = None
        if conv_fractal_top1 is not None and conv_baseline_top1 is not None:
            top1_ok = conv_fractal_top1 >= (conv_baseline_top1 + top1_req)

        shadow_ok = None
        if shadow_fractal_delta is not None and shadow_baseline_delta is not None:
            shadow_ok = shadow_fractal_delta >= (shadow_baseline_delta + shadow_req)

        ok = bool(counts_ok and top1_ok and shadow_ok)
        overall_ok = overall_ok and ok

        field_reports[field] = {
            "conversation": {
                "fractal_top1": conv_fractal_top1,
                "baseline_top1": conv_baseline_top1,
                "semantic_top1": conv_baseline_modes.get("semantic"),
                "lexical_top1": conv_baseline_modes.get("lexical"),
                "fractal_count": conv_fractal_count,
                "semantic_count": conv_baseline_counts.get("semantic"),
                "lexical_count": conv_baseline_counts.get("lexical"),
            },
            "shadow": {
                "fractal_avg_delta": shadow_fractal_delta,
                "baseline_avg_delta": shadow_baseline_delta,
                "semantic_avg_delta": shadow_baseline_modes.get("semantic"),
                "lexical_avg_delta": shadow_baseline_modes.get("lexical"),
                "fractal_count": shadow_fractal_count,
                "semantic_count": shadow_baseline_counts.get("semantic"),
                "lexical_count": shadow_baseline_counts.get("lexical"),
            },
            "thresholds": {
                "top1_margin": top1_req,
                "shadow_margin": shadow_req,
                "min_count": int(min_count),
            },
            "criteria": {
                "top1_ok": top1_ok,
                "shadow_ok": shadow_ok,
                "counts_ok": counts_ok,
                "ok": ok,
            },
            "missing": missing,
        }

        if missing:
            reasons.append(f"{field}: missing {', '.join(missing)}")
        if not counts_ok:
            reasons.append(f"{field}: counts below min_count={min_count}")

    if not field_reports:
        reasons.append("no fields provided")
        overall_ok = False
    if overall_ok and not reasons:
        reasons.append("thresholds met for all fields")
    elif not reasons:
        reasons.append("thresholds not met")

    return {
        "recommend_enable": bool(overall_ok),
        "fields": field_reports,
        "thresholds": {
            "top1_margin": float(top1_margin),
            "shadow_margin": float(shadow_margin),
            "low_lex_top1_margin": float(low_lex_top1_margin),
            "low_lex_shadow_margin": float(low_lex_shadow_margin),
            "min_count": int(min_count),
        },
        "reasons": reasons,
    }


def recommend_from_paths(
    conversation_path: Path = DEFAULT_CONVERSATION_EVAL,
    shadow_path: Path = DEFAULT_SHADOW_EVAL,
    *,
    fields: Sequence[str],
    low_lex_fields: Sequence[str],
    top1_margin: float = 0.02,
    shadow_margin: float = -0.01,
    low_lex_top1_margin: float = 0.02,
    low_lex_shadow_margin: float = -0.01,
    min_count: int = 6,
) -> Dict[str, Any]:
    conversation_payload = json.loads(conversation_path.read_text(encoding="utf-8"))
    shadow_payload = json.loads(shadow_path.read_text(encoding="utf-8"))
    recommendation = recommend_fractal_influence(
        conversation_payload,
        shadow_payload,
        fields=fields,
        low_lex_fields=low_lex_fields,
        top1_margin=top1_margin,
        shadow_margin=shadow_margin,
        low_lex_top1_margin=low_lex_top1_margin,
        low_lex_shadow_margin=low_lex_shadow_margin,
        min_count=min_count,
    )
    recommendation.update(
        {
            "run_at": datetime.now(timezone.utc).isoformat(),
            "conversation_path": str(conversation_path),
            "shadow_path": str(shadow_path),
        }
    )
    return recommendation
