from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from fram_serving.config import FRAMConfig


def compute_retention_score(
    age_seconds: Optional[float],
    config: FRAMConfig,
    *,
    half_life_days: Optional[float] = None,
    min_score: float = 1e-6,
) -> float:
    """
    Exponential decay centered on the configured half-life.

    - Returns 1.0 when disabled or age is unknown.
    - age=half_life -> 0.5, younger => closer to 1, older => approaches min_score.
    """
    if not getattr(config, "enable_retention_curve", False):
        return 1.0
    if age_seconds is None:
        return 1.0
    try:
        half_life = float(half_life_days if half_life_days is not None else config.retention_half_life_days)
    except Exception:
        half_life = float(getattr(config, "retention_half_life_days", 30.0))
    if half_life <= 0:
        return 1.0
    age_days = max(0.0, float(age_seconds) / 86400.0)
    decay_power = age_days / half_life
    score = 0.5 ** decay_power
    return float(max(min_score, min(1.0, score)))


def _to_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except Exception:
            return None
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except Exception:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def apply_retention_curve(
    scores: Sequence[float],
    timestamps: Iterable | None,
    config: FRAMConfig,
    *,
    now: Optional[datetime] = None,
) -> list[float]:
    """
    Apply the retention decay element-wise; returns input when disabled.
    """
    if not getattr(config, "enable_retention_curve", False):
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
        dt = _to_datetime(ts)
        age_seconds = (now_dt - dt).total_seconds() if dt else None
        decay = compute_retention_score(age_seconds, config)
        out.append(float(score) * decay)
    return out
