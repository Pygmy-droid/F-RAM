from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

from fram_serving.config import FRAMConfig
from fram_serving.memory.forgetting import ForgetDecision
from fram_serving.memory.retention_curve import _to_datetime
from fram_serving.storage.compaction import (
    _compute_forgetting_decision,
    _dedupe_records,
    _iter_jsonl,
    _write_atomic,
)


def _default_paths(config: FRAMConfig) -> tuple[Path, Path]:
    root = getattr(config, "STORAGE_ROOT", Path("./storage"))
    active = Path(root) / "active" / "memory_active.jsonl"
    archive = Path(root) / "archive" / "memory_archive.jsonl"
    return active, archive


def _stable_key(item: Mapping[str, Any]) -> tuple[Any, Any]:
    ident = item.get("id") or item.get("hash") or item.get("doc_id")
    ts = (
        item.get("last_seen")
        or item.get("timestamp")
        or item.get("created_at")
        or ""
    )
    return (ident, ts)


def _merge_dedupe(
    records: Iterable[Mapping[str, Any]],
) -> List[Mapping[str, Any]]:
    merged: dict[tuple[Any, Any], Mapping[str, Any]] = {}
    for rec in records:
        key = _stable_key(rec)
        existing = merged.get(key)
        if existing is None:
            merged[key] = rec
            continue

        # Prefer more recent timestamp; fallback to higher score.
        def _age_seconds(r: Mapping[str, Any]) -> float:
            dt = _to_datetime(
                r.get("last_seen")
                or r.get("timestamp")
                or r.get("created_at")
                or ""
            )
            if dt is None:
                return 0.0
            from fram_serving.storage.compaction import compute_now

            return (compute_now() - dt).total_seconds()

        existing_age = _age_seconds(existing)
        rec_age = _age_seconds(rec)
        if rec_age < existing_age:
            merged[key] = rec
            continue
        if rec_age == existing_age:
            try:
                existing_score = float(
                    existing.get("score") or existing.get("forget_score") or 0.0
                )
            except Exception:
                existing_score = 0.0
            try:
                rec_score = float(
                    rec.get("score") or rec.get("forget_score") or 0.0
                )
            except Exception:
                rec_score = 0.0
            if rec_score >= existing_score:
                merged[key] = rec
    return list(merged.values())


def _active_archive_cap_reached(
    archive_path: Path,
    max_archive_size_mb: float,
) -> bool:
    if max_archive_size_mb <= 0:
        return True
    if not archive_path.exists():
        return False
    size_mb = archive_path.stat().st_size / (1024 * 1024)
    return size_mb >= max_archive_size_mb


def archive_from_active_store(
    config: FRAMConfig,
    dry_run: bool = False,
    *,
    active_path: Path | None = None,
    archive_path: Path | None = None,
) -> Dict[str, Any]:
    """
    Archive FORGET_ENFORCE candidates from the active store into the archive store.

    - Uses retention/decay/forgetting math (Phase E/F) and archive criteria.
    - Respects enable_hard_forgetting, enable_archival, and active_store_min_items.
    - Dedupe by stable key, preferring more recent/higher score entries.
    - Atomic replace for active/archive when not dry_run.
    """
    active_p, archive_p = _default_paths(config)
    if active_path:
        active_p = Path(active_path)
    if archive_path:
        archive_p = Path(archive_path)
    before_active_bytes = active_p.stat().st_size if active_p.exists() else 0
    before_archive_bytes = archive_p.stat().st_size if archive_p.exists() else 0
    active_records = list(_iter_jsonl(active_p))
    raw_total = len(active_records)
    active_records = _dedupe_records(active_records)
    total = len(active_records)

    floor = int(
        getattr(
            config,
            "active_store_min_items",
            getattr(config, "min_active_items", 0),
        )
    )
    hard_forget = bool(getattr(config, "enable_hard_forgetting", False))
    archival_enabled = bool(getattr(config, "enable_archival", False))
    if not hard_forget or not archival_enabled or total <= floor:
        keep = active_records
        archive_new: list[Mapping[str, Any]] = []
        cap_hit = False
    else:
        cfg_forget = config.model_copy(update={"min_active_items": floor})
        archive_new = []
        keep = []
        for rec in active_records:
            decision, forget_score, retention, decay = _compute_forgetting_decision(
                rec,
                cfg_forget,
                active_count=total,
            )
            rec_copy = dict(rec)
            rec_copy["forget_score"] = forget_score
            rec_copy["retention_score"] = retention
            rec_copy["decay_factor"] = decay
            archive_criteria = getattr(config, "archive_criteria", {}) or {}
            min_age_days = float(archive_criteria.get("min_age_days", 0))
            max_retention = archive_criteria.get("max_retention_score")
            max_base = archive_criteria.get("max_base_score")
            age_seconds = None
            if min_age_days > 0:
                from fram_serving.storage.compaction import _age_seconds

                age_seconds = _age_seconds(rec_copy)
            meets_age = True
            if min_age_days > 0 and age_seconds is not None:
                meets_age = age_seconds >= min_age_days * 86400.0
            meets_retention = True
            if max_retention is not None:
                try:
                    meets_retention = float(retention) <= float(max_retention)
                except Exception:
                    meets_retention = True
            meets_base = True
            if max_base is not None:
                try:
                    meets_base = float(
                        rec_copy.get("score")
                        or rec_copy.get("base_score")
                        or forget_score
                    ) <= float(max_base)
                except Exception:
                    meets_base = True
            eligible = (
                decision == ForgetDecision.FORGET_ENFORCE
                and meets_age
                and meets_retention
                and meets_base
            )
            if eligible:
                archive_new.append(rec_copy)
            else:
                keep.append(rec_copy)
        if len(keep) < floor:
            needed = floor - len(keep)
            keep.extend(archive_new[:needed])
            archive_new = archive_new[needed:]
        cap_hit = False
        max_archive_mb = float(getattr(config, "max_archive_size_mb", 1024.0))
        if _active_archive_cap_reached(archive_p, max_archive_mb):
            cap_hit = True
            archive_new = []

    replaced_active = False
    replaced_archive = False
    if not dry_run:
        keep_lines = [json.dumps(obj, ensure_ascii=False) for obj in keep]
        _write_atomic(active_p, keep_lines)
        replaced_active = True
        archive_existing = list(_iter_jsonl(archive_p))
        archive_combined = _merge_dedupe([*archive_existing, *archive_new])
        archive_lines = [
            json.dumps(obj, ensure_ascii=False) for obj in archive_combined
        ]
        _write_atomic(archive_p, archive_lines)
        replaced_archive = True
        obs_dir = Path(getattr(config, "STORAGE_ROOT", Path("./storage"))) / (
            "observability"
        )
        obs_dir.mkdir(parents=True, exist_ok=True)
        (obs_dir / "archive_latest.json").write_text(
            json.dumps(
                {
                    "status": "ok",
                    "archived": len(archive_new),
                    "kept": len(keep),
                    "cap_hit": cap_hit,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    after_active_bytes = active_p.stat().st_size if active_p.exists() else 0
    after_archive_bytes = archive_p.stat().st_size if archive_p.exists() else 0
    return {
        "status": "ok",
        "dry_run": dry_run,
        "paths": {"active": str(active_p), "archive": str(archive_p)},
        "counts": {
            "total": raw_total,
            "deduped": total,
            "kept": len(keep),
            "archived": len(archive_new),
        },
        "cap_hit": cap_hit if archival_enabled else False,
        "threshold": float(getattr(config, "forgetting_threshold", 0.05)),
        "active_store_min_items": floor,
        "sizes": {
            "active_before_bytes": before_active_bytes,
            "active_after_bytes": after_active_bytes,
            "archive_before_bytes": before_archive_bytes,
            "archive_after_bytes": after_archive_bytes,
        },
        "replaced": {
            "active": replaced_active,
            "archive": replaced_archive,
        },
    }
