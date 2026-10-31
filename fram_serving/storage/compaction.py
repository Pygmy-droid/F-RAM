from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

from fram_serving.config import FRAMConfig
from fram_serving.memory.forgetting import (
    ForgetDecision,
    compute_decay_factor,
    decide_forgetting,
)
from fram_serving.memory.retention_curve import _to_datetime, compute_retention_score


def _default_active_path(config: FRAMConfig) -> Path:
    root = getattr(config, "STORAGE_ROOT", Path("./storage"))
    return Path(root) / "active" / "memory_active.jsonl"


def _iter_jsonl(path: Path) -> Iterable[Mapping[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, Mapping):
                        yield obj
                except Exception:
                    continue
    except FileNotFoundError:
        return


def _dedupe_records(records: Iterable[Mapping[str, Any]]) -> List[Mapping[str, Any]]:
    seen: set[Tuple[Any, ...]] = set()
    out: List[Mapping[str, Any]] = []
    for idx, rec in enumerate(records):
        key = rec.get("id") or rec.get("hash") or rec.get("doc_id") or f"anon-{idx}"
        key_tuple = (key,)
        if key_tuple in seen:
            continue
        seen.add(key_tuple)
        out.append(rec)
    return out


def _age_seconds(item: Mapping[str, Any]) -> float | None:
    ts = (
        item.get("last_seen")
        or item.get("timestamp")
        or item.get("created_at")
        or item.get("time")
    )
    dt = _to_datetime(ts)
    if dt is None:
        return None
    return max(0.0, (compute_now() - dt).total_seconds())


def compute_now():
    # Separated for testability.
    import datetime

    return datetime.datetime.now(datetime.timezone.utc)


def _compute_forgetting_decision(
    item: Mapping[str, Any],
    config: FRAMConfig,
    active_count: int,
) -> Tuple[ForgetDecision, float, float, float]:
    base_score = float(
        item.get("forget_score")
        or item.get("score")
        or item.get("base_score")
        or 1.0
    )
    retention_enabled = bool(getattr(config, "enable_retention_curve", False))
    decay_enabled = bool(getattr(config, "enable_decay", False))
    age_sec = _age_seconds(item) if (retention_enabled or decay_enabled) else None
    retention = (
        compute_retention_score(age_sec, config) if retention_enabled else 1.0
    )
    decay = compute_decay_factor(age_sec, config) if decay_enabled else 1.0
    forget_score = base_score
    if retention_enabled:
        forget_score *= retention
    if decay_enabled:
        forget_score *= decay
    decision = decide_forgetting(
        item,
        {
            "forget_score": forget_score,
            "retention_score": retention,
            "decay_factor": decay,
        },
        config,
        active_count=active_count,
    )
    return decision, forget_score, retention, decay


def _write_atomic(path: Path, lines: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        for line in lines:
            f.write(line)
            if not line.endswith("\n"):
                f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    # Fsync parent dir to solidify rename on POSIX.
    try:
        dir_fd = os.open(str(path.parent), os.O_DIRECTORY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except Exception:
        pass
    os.replace(tmp_path, path)


def compact_active_store(
    config: FRAMConfig,
    dry_run: bool = False,
    *,
    active_path: Path | None = None,
) -> Dict[str, Any]:
    """
    Compact the active memory store by applying Phase E/F forgetting rules.

    - Dedupes records by a stable key.
    - Uses retention/decay/forgetting thresholds for decisions.
    - Respects enable_hard_forgetting and active_store_min_items.
    - Writes atomically when dry_run is False.
    """
    path = Path(active_path) if active_path else _default_active_path(config)
    before_bytes = path.stat().st_size if path.exists() else 0
    records = list(_iter_jsonl(path))
    raw_total = len(records)
    deduped = _dedupe_records(records)
    total = len(deduped)
    floor = int(
        getattr(
            config,
            "active_store_min_items",
            getattr(config, "min_active_items", 0),
        )
    )
    hard_forget = bool(getattr(config, "enable_hard_forgetting", False))
    cfg_forget = config.model_copy(update={"min_active_items": floor})
    # No forgetting if gate is off or floor binds.
    if not hard_forget or total <= floor:
        kept = deduped
        forgotten: List[Mapping[str, Any]] = []
    else:
        kept = []
        forgotten = []
        for rec in deduped:
            decision, forget_score, retention, decay = _compute_forgetting_decision(
                rec,
                cfg_forget,
                active_count=total,
            )
            rec_copy = dict(rec)
            rec_copy["forget_score"] = forget_score
            rec_copy["retention_score"] = retention
            rec_copy["decay_factor"] = decay
            if decision == ForgetDecision.FORGET_ENFORCE:
                forgotten.append(rec_copy)
            else:
                kept.append(rec_copy)
        if len(kept) < floor:
            # Enforce floor by keeping the earliest kept + forgotten to meet the floor.
            needed = floor - len(kept)
            kept.extend(forgotten[:needed])
            forgotten = forgotten[needed:]
    replaced = False
    if not dry_run:
        lines = [json.dumps(obj, ensure_ascii=False) for obj in kept]
        _write_atomic(path, lines)
        replaced = True
    after_bytes = path.stat().st_size if path.exists() else 0
    return {
        "status": "ok",
        "dry_run": dry_run,
        "path": str(path),
        "counts": {
            "total": raw_total,
            "deduped": total,
            "kept": len(kept),
            "forgotten": len(forgotten),
        },
        "threshold": float(getattr(config, "forgetting_threshold", 0.05)),
        "active_store_min_items": floor,
        "replaced": replaced,
        "sizes": {"before_bytes": before_bytes, "after_bytes": after_bytes},
    }
