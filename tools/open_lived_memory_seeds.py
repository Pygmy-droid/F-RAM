from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fram_serving.lived_memory import LivedMemoryStore  # noqa: E402


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sidecar_state(paths: list[Path]) -> dict[str, dict[str, Any]]:
    return {
        str(path): {"bytes": path.stat().st_size, "sha256": _sha256(path)}
        for path in paths
        if path.exists()
    }


def _database_path(value: Path) -> Path:
    candidate = value.resolve()
    if candidate.is_dir():
        candidate = candidate / "lived_memory.sqlite3"
    if not candidate.is_file():
        raise FileNotFoundError(f"lived-memory database not found: {candidate}")
    return candidate


def _read_connection(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"{path.as_uri()}?mode=ro&immutable=1", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    return connection


def _seed_session_id(
    *, source_zip_sha256: str, source_episode_id: str, prefix: str
) -> str:
    return f"{prefix}:{source_zip_sha256[:12]}:{source_episode_id}"


def open_seed_lineages(
    *,
    source: Path,
    output_root: Path,
    seed_prefix: str = "seed",
    busy_timeout_seconds: float = 5.0,
) -> dict[str, Any]:
    source_db = _database_path(source)
    source_sidecars = [
        Path(f"{source_db}-wal"),
        Path(f"{source_db}-shm"),
    ]
    source_sidecars_before = _sidecar_state(source_sidecars)
    wal_path = Path(f"{source_db}-wal")
    if wal_path.exists() and wal_path.stat().st_size > 0:
        raise RuntimeError(
            "source has a non-empty SQLite WAL; checkpoint and close the "
            f"source before opening seeds: {wal_path}"
        )
    output_root = output_root.resolve()
    output_db = output_root / "lived_memory.sqlite3"
    if source_db == output_db:
        raise ValueError("source and output databases must be different")
    if output_db.exists():
        raise FileExistsError(
            f"refusing to overwrite opened lived-memory database: {output_db}"
        )
    seed_prefix = str(seed_prefix).strip()
    if not seed_prefix or ":" in seed_prefix:
        raise ValueError("seed_prefix must be non-empty and cannot contain ':'")

    source_hash_before = _sha256(source_db)
    with closing(_read_connection(source_db)) as connection:
        meta = {
            str(row["key"]): str(row["value"])
            for row in connection.execute(
                "SELECT key, value FROM lived_meta"
            ).fetchall()
        }
        rows = connection.execute(
            "SELECT * FROM lived_events ORDER BY session_id, session_seq"
        ).fetchall()

    target_dim = int(meta.get("projection_dim", 12))
    fractal_nodes = int(meta.get("fractal_nodes", 64))
    state_decay = float(meta.get("state_decay", 0.82))
    store = LivedMemoryStore(
        output_root,
        target_dim=target_dim,
        fractal_nodes=fractal_nodes,
        state_decay=state_decay,
        busy_timeout_seconds=busy_timeout_seconds,
    )

    opened_seed_count = 0
    passthrough_event_count = 0
    failed: list[dict[str, str]] = []
    seed_sessions: set[str] = set()

    for index, row in enumerate(rows, start=1):
        event_id = str(row["event_id"])
        try:
            metadata = json.loads(str(row["metadata_json"]))
            if not isinstance(metadata, dict):
                metadata = {"source_metadata": metadata}
            import_meta = metadata.get("import")
            source_episode_id = ""
            source_zip_sha256 = ""
            if isinstance(import_meta, dict):
                source_episode_id = str(
                    import_meta.get("source_episode_id") or ""
                ).strip()
                source_zip_sha256 = str(
                    import_meta.get("source_zip_sha256") or ""
                ).strip()

            if source_episode_id and source_zip_sha256:
                target_session = _seed_session_id(
                    source_zip_sha256=source_zip_sha256,
                    source_episode_id=source_episode_id,
                    prefix=seed_prefix,
                )
                metadata["opening"] = {
                    "mode": "independent_seed_root",
                    "previous_session_id": str(row["session_id"]),
                    "source_session_evidence": "absent",
                    "identity_claim": False,
                }
                opened_seed_count += 1
                seed_sessions.add(target_session)
            else:
                target_session = str(row["session_id"])
                passthrough_event_count += 1

            embedding = np.frombuffer(row["embedding"], dtype="<f4").astype(
                float, copy=True
            )
            citations = json.loads(str(row["citations_json"]))
            store.append_experience(
                event_id=event_id,
                query=str(row["query_text"]),
                answer=str(row["answer_text"]),
                embedding=embedding,
                embedding_backend=row["embedding_backend"],
                session_id=target_session,
                episode_id=row["episode_id"],
                trace_id=row["trace_id"],
                domain=row["domain"],
                task=row["task"],
                citations=[str(value) for value in citations],
                metadata=metadata,
                created_at=str(row["created_at"]),
            )
        except Exception as exc:
            failed.append({"event_id": event_id, "error": str(exc)})
        if index % 100 == 0:
            print(
                f"processed={index} opened={opened_seed_count} "
                f"passthrough={passthrough_event_count} failed={len(failed)}",
                flush=True,
            )

    verification = store.verify()
    status = store.status()
    with closing(sqlite3.connect(store.path)) as connection:
        seed_rows = connection.execute(
            "SELECT session_seq, parent_event_id FROM lived_events "
            "WHERE session_id LIKE ?",
            (f"{seed_prefix}:%",),
        ).fetchall()
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    non_root_seed_count = sum(
        1 for seq, parent in seed_rows if int(seq) != 1 or parent is not None
    )
    source_hash_after = _sha256(source_db)
    source_sidecars_after = _sidecar_state(source_sidecars)
    source_sidecars_created = sorted(
        set(source_sidecars_after) - set(source_sidecars_before)
    )
    source_sidecars_removed = sorted(
        set(source_sidecars_before) - set(source_sidecars_after)
    )
    output_hash = _sha256(store.path)
    valid = bool(
        verification.get("valid")
        and not failed
        and non_root_seed_count == 0
        and source_hash_before == source_hash_after
        and not source_sidecars_created
        and len(seed_sessions) == opened_seed_count
    )
    return {
        "schema": "fram.lived-memory-open-seeds-report/v1",
        "policy": "independent_seed_roots",
        "identity_claim": False,
        "source_database": str(source_db),
        "source_database_sha256_before": source_hash_before,
        "source_database_sha256_after": source_hash_after,
        "source_unchanged": source_hash_before == source_hash_after,
        "source_sidecars_before": source_sidecars_before,
        "source_sidecars_after": source_sidecars_after,
        "source_sidecars_unchanged": (source_sidecars_before == source_sidecars_after),
        "source_sidecars_created": source_sidecars_created,
        "source_sidecars_removed": source_sidecars_removed,
        "output_database": str(store.path),
        "output_database_sha256": output_hash,
        "source_event_count": len(rows),
        "output_event_count": int(status["event_count"]),
        "opened_seed_count": opened_seed_count,
        "independent_seed_session_count": len(seed_sessions),
        "passthrough_event_count": passthrough_event_count,
        "output_session_count": int(status["session_count"]),
        "non_root_seed_count": non_root_seed_count,
        "failed_count": len(failed),
        "failures": failed,
        "verification": verification,
        "valid": valid,
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description=(
            "Open imported F-RAM episodes as independent, resumable seed "
            "lineages without asserting identities."
        )
    )
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seed-prefix", default="seed")
    parser.add_argument("--busy-timeout-seconds", type=float, default=5.0)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    report = open_seed_lineages(
        source=args.source,
        output_root=args.output,
        seed_prefix=args.seed_prefix,
        busy_timeout_seconds=args.busy_timeout_seconds,
    )
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
