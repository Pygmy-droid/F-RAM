from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Mapping, MutableMapping, Sequence

from fram_serving.config import FRAMConfig
from fram_serving.memory.forgetting import ForgetDecision, compute_decay_factor, decide_forgetting
from fram_serving.memory.retention_curve import compute_retention_score, _to_datetime


def _age_seconds(entry: Mapping[str, object], *, now: datetime) -> float | None:
    if "age_seconds" in entry:
        try:
            return max(0.0, float(entry.get("age_seconds") or 0.0))
        except Exception:
            return None
    ts = entry.get("last_seen") or entry.get("timestamp") or entry.get("created_at")
    dt = _to_datetime(ts)
    if dt is None:
        return None
    return max(0.0, (now - dt).total_seconds())


def _bucket_label(age_days: float, half_life_days: float) -> str:
    if half_life_days <= 0:
        return "<unknown>"
    if age_days < half_life_days:
        return "<1_half_life"
    if age_days < 2 * half_life_days:
        return "1-2_half_life"
    if age_days < 5 * half_life_days:
        return "2-5_half_life"
    return ">5_half_life"


def replay_lifecycle(entries: Sequence[Mapping[str, object]], config: FRAMConfig, *, now: datetime | None = None) -> MutableMapping[str, object]:
    now_dt = now or datetime.now(timezone.utc)
    retention_enabled = bool(getattr(config, "enable_retention_curve", False))
    decay_enabled = bool(getattr(config, "enable_decay", False))
    hard_forget_enabled = bool(getattr(config, "enable_hard_forgetting", False))
    hl_ret = float(getattr(config, "retention_half_life_days", 30.0))
    hl_forget = float(getattr(config, "forgetting_half_life_days", 30.0))
    threshold = float(getattr(config, "forgetting_threshold", 0.05))

    summary = {
        "config": {
            "retention_half_life_days": hl_ret,
            "forgetting_half_life_days": hl_forget,
            "forgetting_threshold": threshold,
            "min_active_items": int(getattr(config, "min_active_items", 0)),
            "enable_retention_curve": retention_enabled,
            "enable_decay": decay_enabled,
            "enable_hard_forgetting": hard_forget_enabled,
        },
        "counts": {
            "total": len(entries),
            "decisions": {
                "dry_run": {"keep": 0, "forget_dry": 0, "forget_enforce": 0},
                "enforce": {"keep": 0, "forget_dry": 0, "forget_enforce": 0},
            },
        },
        "age_buckets": {},
    }

    total_candidates = max(1, len(entries))
    bucket_counts: dict[str, dict[str, int]] = {}
    for entry in entries:
        base_score = float(entry.get("score") or entry.get("base_score") or 1.0)
        age_sec = _age_seconds(entry, now=now_dt)
        age_days = age_sec / 86400.0 if age_sec is not None else None
        retention = compute_retention_score(age_sec, config) if (retention_enabled and age_sec is not None) else 1.0
        decay = compute_decay_factor(age_sec, config) if (decay_enabled and age_sec is not None) else 1.0
        forget_score = base_score
        if retention_enabled:
            forget_score *= retention
        if decay_enabled:
            forget_score *= decay

        bucket = "<unknown>" if age_days is None else _bucket_label(age_days, hl_ret)
        bucket_counts.setdefault(bucket, {"total": 0, "forgotten_enforce": 0})
        bucket_counts[bucket]["total"] += 1

        for mode in ("dry_run", "enforce"):
            cfg_mode = config.model_copy(update={"hard_forgetting_mode": mode, "enable_hard_forgetting": True})
            decision = decide_forgetting(
                None,
                {"forget_score": forget_score, "retention_score": retention, "decay_factor": decay},
                cfg_mode,
                active_count=total_candidates,
            )
            key = "forget_enforce" if decision == ForgetDecision.FORGET_ENFORCE else ("forget_dry" if decision == ForgetDecision.FORGET_DRY else "keep")
            summary["counts"]["decisions"][mode][key] += 1
            if mode == "enforce" and decision == ForgetDecision.FORGET_ENFORCE:
                bucket_counts[bucket]["forgotten_enforce"] += 1

    summary["age_buckets"] = bucket_counts
    return summary


def _load_log(path: Path) -> List[dict]:
    if not path.exists():
        return []
    entries: List[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except Exception:
                continue
    return entries


def _synthetic_entries() -> List[dict]:
    now = datetime.now(timezone.utc).isoformat()
    return [
        {"id": "fresh_high", "score": 0.9, "last_seen": now},
        {"id": "mid_med", "score": 0.5, "age_seconds": 3 * 86400},
        {"id": "old_low", "score": 0.2, "age_seconds": 40 * 86400},
    ]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase F lifecycle replay (read-only).")
    parser.add_argument("--log", type=str, help="Path to a JSONL log (e.g., storage/observability/memory_cognitive.jsonl).")
    parser.add_argument("--synthetic", action="store_true", help="Use a small synthetic log when no file is provided.")
    parser.add_argument("--enable-retention-curve", action="store_true")
    parser.add_argument("--enable-decay", action="store_true")
    parser.add_argument("--enable-hard-forgetting", action="store_true")
    parser.add_argument("--retention-half-life-days", type=float)
    parser.add_argument("--forgetting-half-life-days", type=float)
    parser.add_argument("--forgetting-threshold", type=float)
    parser.add_argument("--min-active-items", type=int)
    args = parser.parse_args(argv)

    base_cfg = FRAMConfig.from_env()
    updates = {}
    for flag, key in (
        (args.enable_retention_curve, "enable_retention_curve"),
        (args.enable_decay, "enable_decay"),
        (args.enable_hard_forgetting, "enable_hard_forgetting"),
    ):
        if flag:
            updates[key] = True
    if args.retention_half_life_days is not None:
        updates["retention_half_life_days"] = float(args.retention_half_life_days)
    if args.forgetting_half_life_days is not None:
        updates["forgetting_half_life_days"] = float(args.forgetting_half_life_days)
    if args.forgetting_threshold is not None:
        updates["forgetting_threshold"] = float(args.forgetting_threshold)
    if args.min_active_items is not None:
        updates["min_active_items"] = int(args.min_active_items)
    config = base_cfg.model_copy(update=updates) if updates else base_cfg

    entries: List[dict] = []
    if args.log:
        entries = _load_log(Path(args.log))
    if not entries and args.synthetic:
        entries = _synthetic_entries()

    summary = replay_lifecycle(entries, config)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
