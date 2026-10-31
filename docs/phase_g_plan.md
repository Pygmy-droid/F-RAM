# Phase G — Archival & Compaction (Plan)

Phase G is the first phase that may rewrite on-disk storage. Runtime scoring, retrieval, forgetting, and cognitive behaviour stay identical; only file layout changes under explicit gates.

## Boundaries
- Allowed: read/rewrite JSONL storage, move records between `storage/active/` and `storage/archive/`, emit snapshots.
- Not allowed: change scoring/ranking/forgetting semantics, alter in-memory retrieval, or mutate cognitive behaviour at runtime.
- Safety: dry-run by default; use atomic temp-file + rename; never drop below safety floors.

## Config (add to `fram_serving/config.py`)
- `enable_storage_compaction` (bool, default False): allow rewriting active JSONL with kept records.
- `enable_archival` (bool, default False): allow moving forgotten/aged records to archive.
- `archive_criteria` (mapping): age_days > N, retention_score < X, base_score < Y, optional manual include/exclude.
- `compaction_threshold_mb` (float): permit compaction only when an active file exceeds this size.
- `max_archive_size_mb` (float): soft cap; refuse archival when exceeded.
- `active_store_min_items` (int): safety floor; never compact/arch below this count (mirrors Phase F `min_active_items`).

## Storage layout (new)
```
storage/
  active/
    memory_active.jsonl        # canonical active store
  archive/
    memory_archive.jsonl       # cold/forgotten items
  snapshots/
    snapshot_YYYYMMDD.jsonl    # read-only combined dumps
```
Records keep all fields (ids, scores, timestamps) so retrieval parity is preserved if reloaded.

## Compaction (Lane G.1)
- Module: `fram_serving/storage/compaction.py`
- Function: `compact_active_store(config, *, dry_run=False)`
- Behaviour:
  - Read `storage/active/memory_active.jsonl`.
  - Evaluate eligibility with existing Phase F/E logic (retention/decay + `decide_forgetting`); only `FORGET_ENFORCE` candidates can be removed.
  - Enforce `active_store_min_items` floor; if floor binds, keep earliest/highest-score items deterministically.
  - Deterministic ordering (stable by original order or `(created_at, id)`).
  - Outputs summary `{kept, archived, dropped, size_before_mb, size_after_mb, archived_bytes}`.
  - If `dry_run=True`, do not write files.
  - If `dry_run=False`, write to a temp file and `os.replace` to avoid corruption.
- Rules: never modify archive unless `enable_archival` is True; never delete if gates are off.

## Archival (Lane G.2)
- Module: `fram_serving/storage/archival.py`
- Reads active candidates eligible for archival (same criteria + `archive_criteria`).
- Appends to `storage/archive/memory_archive.jsonl` (dedupe by id/hash), removes from active when allowed.
- Enforces `max_archive_size_mb`; if exceeded, abort archival (log and keep active intact).
- CLI: `tools/phase_g_archive.py` (supports `--dry-run`, `--json-out`).

## Snapshot (Lane G.3)
- CLI: `tools/phase_g_snapshot.py`
- Read-only: loads active + archive, writes `snapshots/snapshot_YYYYMMDD.jsonl` with metadata `{timestamp, active_count, archive_count, oldest_age_days, newest_age_days, config}`.
- No deletions; succeeds even when gates are off.

## Observability
- Add a lifecycle/storage block (e.g., in the existing memory inspector or new `/observability/memory_storage`) gated by Phase G flags:
  - `active_size_mb`, `archive_size_mb`, `last_compaction`, `last_archival`, `last_snapshot`
  - `compaction_stats` (kept/archived/dropped, size deltas)
  - `archive_stats` (total archived, capped?)
  - Visible only when storage gates are enabled; read-only when off.

## Tests
- `tests/test_phase_g_compaction.py`: dry-run no writes; `active_store_min_items` respected; deterministic ordering; size decreases after compaction; archive untouched unless enabled.
- `tests/test_phase_g_archival.py`: archival moves items (or simulates in dry-run), no field loss, dedupe enforced, max-archive cap respected.
- `tests/test_phase_g_snapshot.py`: snapshot JSON contains required keys; no mutation; works when gates off.
- Cross-check: runtime retrieval unaffected (e.g., existing cognitive tests remain green).

## Next steps / tweaks
1) File-safety rails: always write to temp + `os.replace`, include an fsync hook for the parent dir on POSIX; fail closed if a partial write is detected (size/hash mismatch).
2) Locking: add a simple file lock around compaction/archival to avoid concurrent writers (even a PID file suffices for now).
3) Dedupe keys: use `{id, hash}` from cognitive records; treat missing ids by hashing content; log collisions.
4) Criteria audit: before removing/archiving, log a JSON summary per run (counts + top reasons) to `storage/observability/memory_storage.jsonl`.
5) Threshold guard: abort compaction when `compaction_threshold_mb` is not met; emit a warning instead of rewriting.
6) Active floor priority: when the floor blocks forgetting, keep the highest `forget_score` or most recent items deterministically; test this tie-break.
7) Archive size cap: when near the cap, stop archiving and log; never delete to make room.
8) Snapshot provenance: include hash of active/archive files and config snapshot so replays can validate integrity.
9) CLI parity: add `--dry-run` to all Phase G tools by default; require `--force` to actually write.
10) Observability parity: surface the same `decision_counts` used in Phase F so dashboards can align live lifecycle vs storage actions.
