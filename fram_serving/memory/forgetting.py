from __future__ import annotations

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable, Mapping, Optional

from fram_serving.config import FRAMConfig


def apply_forgetting(candidates: Sequence[Any], config: FRAMConfig) -> list[Any]:
    """
    Placeholder for Phase E forgetting/decay.

    Current behaviour: gated off by default and returns the candidates unchanged.
    """
    if not getattr(config, "enable_decay", False):
        return list(candidates)
    # Future: apply decay weights/filters before returning candidates.
    return list(candidates)


def compute_decay_factor(
    age_seconds: Optional[float],
    config: FRAMConfig,
    *,
    half_life_days: Optional[float] = None,
    min_factor: float = 0.1,
) -> float:
    """
    Soft decay multiplier (non-destructive).

    - Returns 1.0 when disabled or age is unknown.
    - Exponential drop with half-life; clamped to [min_factor, 1].
    """
    if not getattr(config, "enable_decay", False):
        return 1.0
    if age_seconds is None:
        return 1.0
    try:
        half_life = float(half_life_days if half_life_days is not None else config.forgetting_half_life_days)
    except Exception:
        half_life = float(getattr(config, "forgetting_half_life_days", 30.0))
    if half_life <= 0:
        return 1.0
    age_days = max(0.0, float(age_seconds) / 86400.0)
    factor = 0.5 ** (age_days / half_life)
    return float(max(min_factor, min(1.0, factor)))


class ForgetDecision(Enum):
    KEEP = "keep"
    FORGET_DRY = "forget_dry"
    FORGET_ENFORCE = "forget_enforce"


def decide_forgetting(
    memory_item: Mapping[str, Any] | None,
    scores: Mapping[str, Any],
    config: FRAMConfig,
    active_count: int,
) -> ForgetDecision:
    """
    Determine whether to keep or mark an item for forgetting.

    scores may include:
    - forget_score (preferred)
    - retention_score
    - decay_factor
    - base_score
    """
    if not getattr(config, "enable_hard_forgetting", False):
        return ForgetDecision.KEEP
    try:
        min_active = int(getattr(config, "min_active_items", 0))
    except Exception:
        min_active = 0
    if active_count <= max(0, min_active):
        return ForgetDecision.KEEP

    try:
        threshold = float(getattr(config, "forgetting_threshold", 0.05))
    except Exception:
        threshold = 0.05

    forget_score = scores.get("forget_score")
    if forget_score is None:
        retention = float(scores.get("retention_score", 1.0))
        decay = float(scores.get("decay_factor", 1.0))
        forget_score = retention * decay
    else:
        forget_score = float(forget_score)

    if forget_score >= threshold:
        return ForgetDecision.KEEP

    mode = str(getattr(config, "hard_forgetting_mode", "dry_run")).lower()
    if mode == "enforce":
        return ForgetDecision.FORGET_ENFORCE
    return ForgetDecision.FORGET_DRY


def apply_decay(
    scores: Sequence[float],
    timestamps: Iterable | None,
    config: FRAMConfig,
    *,
    now: Optional[datetime] = None,
) -> list[float]:
    """
    Apply decay factors to scores (non-destructive weighting).
    """
    if not getattr(config, "enable_decay", False):
        return list(scores)
    now_dt = now or datetime.now(timezone.utc)
    out: list[float] = []
    ts_iter = iter(timestamps) if timestamps is not None else iter([])
    for score in scores:
        ts = None
        try:
            ts = next(ts_iter)
        except StopIteration:
            ts = None
        dt = ts if isinstance(ts, datetime) else None
        if dt and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        age_seconds = (now_dt - dt).total_seconds() if dt else None
        factor = compute_decay_factor(age_seconds, config)
        out.append(float(score) * factor)
    return out
