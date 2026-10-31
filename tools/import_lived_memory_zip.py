from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
import zipfile
from pathlib import Path
from typing import Any, Iterable

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fram_serving.cognitive_embeddings import build_cognitive_vectorizer  # noqa: E402
from fram_serving.config import FRAMConfig  # noqa: E402
from fram_serving.lived_memory import LivedMemoryStore  # noqa: E402

EPISODES_ENTRY = "storage/memory/cognitive/episodes.jsonl"
VECTORS_ENTRY = "storage/memory/cognitive/episodes.vectors.jsonl"
VECTOR_META_ENTRY = "storage/memory/cognitive/vectors.meta.json"
LINEAGE_MODES = ("separate", "single")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _entry_map(archive: zipfile.ZipFile) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for name in archive.namelist():
        normalized = name.replace("\\", "/")
        while normalized.startswith("./"):
            normalized = normalized[2:]
        resolved[normalized] = name
    return resolved


def _read_entry(archive: zipfile.ZipFile, entries: dict[str, str], name: str) -> bytes:
    actual = entries.get(name)
    if actual is None:
        raise FileNotFoundError(f"ZIP entry not found: {name}")
    return archive.read(actual)


def _json_lines(data: bytes) -> Iterable[dict[str, Any]]:
    for raw_line in data.decode("utf-8-sig", errors="strict").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            yield payload


def _source_head(archive: zipfile.ZipFile, entries: dict[str, str]) -> str | None:
    head_name = entries.get(".git/HEAD")
    if head_name is None:
        return None
    head = archive.read(head_name).decode("ascii", errors="replace").strip()
    if not head.startswith("ref:"):
        return head or None
    ref = head.split(":", 1)[1].strip()
    ref_name = entries.get(f".git/{ref}")
    if ref_name is not None:
        return archive.read(ref_name).decode("ascii", errors="replace").strip() or None
    packed_name = entries.get(".git/packed-refs")
    if packed_name is not None:
        for line in (
            archive.read(packed_name).decode("ascii", errors="replace").splitlines()
        ):
            if line.endswith(f" {ref}"):
                return line.split(" ", 1)[0]
    return None


def _session_for_episode(
    *,
    lineage_mode: str,
    session_namespace: str,
    source_sha256: str,
    source_episode_id: str,
) -> str:
    if lineage_mode == "single":
        return session_namespace
    return f"{session_namespace}:seed:{source_sha256[:12]}:{source_episode_id}"


def import_zip(
    *,
    zip_path: Path,
    output_root: Path,
    session_id: str,
    target_dim: int,
    fractal_nodes: int,
    scan_limit: int,
    state_decay: float,
    limit: int | None = None,
    lineage_mode: str = "separate",
) -> dict[str, Any]:
    lineage_mode = str(lineage_mode).strip().lower()
    if lineage_mode not in LINEAGE_MODES:
        raise ValueError(f"lineage_mode must be one of {', '.join(LINEAGE_MODES)}")
    session_id = str(session_id).strip()
    if not session_id:
        raise ValueError("session_id must be a non-empty namespace")
    zip_path = zip_path.resolve()
    source_sha256 = _sha256(zip_path)
    with zipfile.ZipFile(zip_path) as archive:
        entries = _entry_map(archive)
        episodes = list(_json_lines(_read_entry(archive, entries, EPISODES_ENTRY)))
        vectors_raw = list(_json_lines(_read_entry(archive, entries, VECTORS_ENTRY)))
        vector_meta = json.loads(
            _read_entry(archive, entries, VECTOR_META_ENTRY).decode("utf-8-sig")
        )
        source_head = _source_head(archive, entries)

    vectors: dict[str, tuple[np.ndarray, str]] = {}
    for record in vectors_raw:
        record_id = str(record.get("id") or "").strip()
        raw_vector = record.get("vector")
        if not record_id or not isinstance(raw_vector, list):
            continue
        vector = np.asarray(raw_vector, dtype=float).ravel()
        if vector.size == 0 or not np.isfinite(vector).all():
            continue
        vectors[record_id] = (
            vector,
            str(
                record.get("backend")
                or vector_meta.get("embedding_backend")
                or "unknown"
            ),
        )

    try:
        embedding_dim = int(
            vector_meta.get("dim") or next(iter(vectors.values()))[0].size
        )
    except (StopIteration, TypeError, ValueError) as exc:
        raise ValueError(
            "ZIP does not declare a usable cognitive embedding dimension"
        ) from exc
    config = FRAMConfig(
        embedding_dim=embedding_dim, cognitive_memory_embedding_backend="hashing"
    )
    vectorizer = build_cognitive_vectorizer(config)
    if vectorizer is None:
        raise RuntimeError("hashing vectorizer is unavailable")

    episodes.sort(
        key=lambda item: (str(item.get("time") or ""), str(item.get("id") or ""))
    )
    if limit is not None:
        episodes = episodes[: max(0, int(limit))]

    store = LivedMemoryStore(
        output_root,
        target_dim=target_dim,
        fractal_nodes=fractal_nodes,
        scan_limit=scan_limit,
        state_decay=state_decay,
    )
    imported = 0
    skipped_existing = 0
    stored_embeddings = 0
    reconstructed_embeddings = 0
    failed: list[dict[str, str]] = []

    for index, episode in enumerate(episodes, start=1):
        source_episode_id = str(episode.get("id") or "").strip()
        if not source_episode_id:
            failed.append({"source_episode_id": "", "error": "missing episode id"})
            continue
        event_id = uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"fram-lived-memory:{source_sha256}:{source_episode_id}",
        ).hex
        if store.contains_event(event_id):
            skipped_existing += 1
            continue

        vector_record = vectors.get(source_episode_id)
        if vector_record is not None:
            embedding, backend = vector_record
            embedding_origin = "stored_in_zip"
            stored_embeddings += 1
        else:
            text = (
                f"{episode.get('query') or ''}\n{episode.get('answer') or ''}".strip()
            )
            embedding = np.asarray(
                vectorizer.transform([text]).toarray()[0], dtype=float
            )
            backend = "hashing-reconstructed-from-source-text"
            embedding_origin = "derived_during_import"
            reconstructed_embeddings += 1

        try:
            resolved_session_id = _session_for_episode(
                lineage_mode=lineage_mode,
                session_namespace=session_id,
                source_sha256=source_sha256,
                source_episode_id=source_episode_id,
            )
            store.append_experience(
                event_id=event_id,
                query=str(episode.get("query") or ""),
                answer=str(episode.get("answer") or ""),
                embedding=embedding,
                embedding_backend=backend,
                session_id=resolved_session_id,
                episode_id=source_episode_id,
                trace_id=str(episode.get("trace_id") or "") or None,
                domain=str(episode.get("domain") or "") or None,
                task=str(episode.get("task") or "") or None,
                citations=[str(value) for value in episode.get("citations") or []],
                metadata={
                    "import": {
                        "source_kind": "FRAM cognitive backup ZIP",
                        "source_zip": str(zip_path),
                        "source_zip_sha256": source_sha256,
                        "source_git_head": source_head,
                        "source_episode_entry": EPISODES_ENTRY,
                        "source_vector_entry": VECTORS_ENTRY,
                        "source_episode_id": source_episode_id,
                        "embedding_origin": embedding_origin,
                        "lineage_mode": lineage_mode,
                        "session_evidence": (
                            "import_namespace_only"
                            if lineage_mode == "single"
                            else "independent_seed_root"
                        ),
                    },
                    "source_calibration": episode.get("calibration") or {},
                    "source_metadata": episode.get("metadata") or {},
                },
                created_at=str(episode.get("time") or "") or None,
            )
            imported += 1
        except Exception as exc:
            failed.append({"source_episode_id": source_episode_id, "error": str(exc)})
        if index % 100 == 0:
            print(
                f"processed={index} imported={imported} failed={len(failed)}",
                flush=True,
            )

    verification = store.verify()
    return {
        "schema": "fram.lived-memory-import-report/v1",
        "source_zip": str(zip_path),
        "source_zip_sha256": source_sha256,
        "source_git_head": source_head,
        "source_episode_count": len(episodes),
        "source_vector_count": len(vectors),
        "imported": imported,
        "skipped_existing": skipped_existing,
        "stored_embeddings": stored_embeddings,
        "reconstructed_embeddings": reconstructed_embeddings,
        "failed_count": len(failed),
        "failures": failed,
        "session_namespace": session_id,
        "lineage_mode": lineage_mode,
        "identity_claim": False,
        "output": str(store.path),
        "status": store.status(),
        "verification": verification,
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description=(
            "Import a full F-RAM backup ZIP into durable lived-experience memory."
        )
    )
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--session", default="backup-2025-12-18")
    parser.add_argument(
        "--lineage-mode",
        choices=LINEAGE_MODES,
        default="separate",
        help=(
            "separate keeps every source episode as an independent root; "
            "single reproduces one inferred chronological import lineage"
        ),
    )
    parser.add_argument("--target-dim", type=int, default=12)
    parser.add_argument("--fractal-nodes", type=int, default=64)
    parser.add_argument("--scan-limit", type=int, default=5000)
    parser.add_argument("--state-decay", type=float, default=0.82)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    report = import_zip(
        zip_path=args.zip,
        output_root=args.output,
        session_id=args.session,
        target_dim=args.target_dim,
        fractal_nodes=args.fractal_nodes,
        scan_limit=args.scan_limit,
        state_decay=args.state_decay,
        limit=args.limit,
        lineage_mode=args.lineage_mode,
    )
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return (
        0 if report["verification"].get("valid") and not report["failed_count"] else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
