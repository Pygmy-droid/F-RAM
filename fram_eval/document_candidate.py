"""Preserve explicit document sources in a new, offline cognitive candidate.

Imported records use the episode storage schema, but are labelled documents,
not lived events. Source text is data and is never executed or promoted to belief.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def byte_chunks(payload: bytes, limit: int = 4096):
    """Partition all UTF-8 source bytes, retaining exact offsets and line endings."""
    payload.decode("utf-8")
    if limit < 64:
        raise ValueError("chunk limit must be at least 64 bytes")
    start = 0
    while start < len(payload):
        end = min(start + limit, len(payload))
        if end < len(payload):
            newline = payload.rfind(b"\n", start + limit // 2, end)
            if newline >= 0:
                end = newline + 1
            else:
                while end > start and payload[end] & 0xC0 == 0x80:
                    end -= 1
        yield start, end, payload[start:end]
        start = end


def prepare_candidate(
    sources: Sequence[Path],
    *,
    base_memory: Path,
    destination: Path,
    imported_at: str,
    chunk_bytes: int = 4096,
) -> dict:
    clock = datetime.fromisoformat(imported_at.replace("Z", "+00:00"))
    if clock.tzinfo is None:
        raise ValueError("imported_at needs a timezone")
    stamp = clock.astimezone(timezone.utc).isoformat()
    destination = Path(destination).resolve()
    base_memory = Path(base_memory).resolve()
    paths = [Path(path).resolve() for path in sources]
    if not paths or len(set(paths)) != len(paths):
        raise ValueError("provide distinct explicit source paths")
    for path in [base_memory, *paths]:
        if destination.is_relative_to(path) or path.is_relative_to(destination):
            raise ValueError("candidate output must be disjoint from all inputs")
    if destination.exists():
        raise FileExistsError("candidate destination must be new")
    contents = [path.read_bytes() for path in paths]
    partitions = [list(byte_chunks(data, chunk_bytes)) for data in contents]
    if any(not parts for parts in partitions):
        raise ValueError("empty document source")

    # Import only after path/content checks. Callers isolate FRAM_STORAGE_ROOT
    # before loading F-RAM modules; no source store constructor is used here.
    import numpy as np

    from fram_eval.production_memory_eval import snapshot_memory, tree_manifest
    from fram_serving.cognitive_embeddings import build_cognitive_vectorizer
    from fram_serving.config import FRAMConfig
    from fram_serving.fractal_memory import FractalSeed, FractalTraceStore

    memory_root = destination / "storage" / "memory"
    custody = snapshot_memory(base_memory, memory_root)
    cognitive = memory_root / "cognitive"
    cognitive.mkdir(parents=True, exist_ok=True)
    meta_path = cognitive / "vectors.meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    dim = int(meta.get("dim") or 1024)
    if meta.get("embedding_backend", "hashing") != "hashing":
        raise ValueError("document candidate requires the explicit hashing backend")
    cfg = FRAMConfig().model_copy(
        update={
            "STORAGE_ROOT": destination / "storage",
            "embedding_dim": dim,
            "cognitive_memory_embedding_backend": "hashing",
            "fractal_enabled": True,
            "fractal_influence_enabled": False,
        }
    )
    vectorizer = build_cognitive_vectorizer(cfg)
    if vectorizer is None:
        raise ValueError("hashing vectorizer unavailable")
    traces = FractalTraceStore(
        memory_root / "fractal",
        observability_root=destination / "storage" / "observability",
        embedding_dim=dim,
    )
    existing_ids = set()
    episode_path = cognitive / "episodes.jsonl"
    if episode_path.exists():
        existing_ids = {
            json.loads(line)["id"]
            for line in episode_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
    records, source_receipts, chunk_receipts = [], [], []
    vectors = []
    snapshot_root = destination / "sources"
    snapshot_root.mkdir()
    for index, (path, payload, parts) in enumerate(zip(paths, contents, partitions)):
        source_id = f"source-{index + 1:02d}"
        snapshot = snapshot_root / source_id / path.name
        snapshot.parent.mkdir()
        snapshot.write_bytes(payload)
        source_digest = sha256(payload)
        source_receipts.append(
            {
                "source_id": source_id,
                "source_path": str(path),
                "snapshot": str(snapshot.relative_to(destination)),
                "bytes": len(payload),
                "sha256": source_digest,
                "chunks": len(parts),
                "instruction_authority": "none; source content only",
            }
        )
        for chunk_index, (start, end, data) in enumerate(parts):
            identity = f"document-import-v1:{source_id}:{source_digest}:{start}:{end}"
            episode_id = sha256(identity.encode())[:32]
            if episode_id in existing_ids:
                raise ValueError("document ID collision with existing corpus")
            existing_ids.add(episode_id)
            text = data.decode("utf-8")
            label = f"Imported document {path.name}, part {chunk_index + 1}"
            vector = vectorizer.transform([label + "\n" + text])
            vector = np.asarray(
                vector.toarray() if hasattr(vector, "toarray") else vector
            ).ravel()
            if vector.size != dim or not np.isfinite(vector).all():
                raise ValueError("derived vector dimension/value mismatch")
            provenance = {
                "record_kind": "document-import",
                "self_lived": False,
                "instruction_authority": "none",
                "source_id": source_id,
                "source_path": str(path),
                "source_sha256": source_digest,
                "byte_start": start,
                "byte_end": end,
                "chunk_sha256": sha256(data),
                "imported_at": stamp,
                "source_event_time": "not inferred",
                "embedding_provenance": (
                    "derived hashing vector of label plus exact text"
                ),
                "trace_provenance": "derived synthetic IFS; not a lived trajectory",
            }
            records.append(
                {
                    "type": "episode",
                    "id": episode_id,
                    "time": stamp,
                    "query": label,
                    "answer": text,
                    "domain": "document-source",
                    "task": "source-recall",
                    "citations": [
                        f"source://{source_id}/{source_digest}#bytes={start}-{end}"
                    ],
                    "trace_id": None,
                    "calibration": {},
                    "metadata": provenance,
                }
            )
            vectors.append(
                {
                    "id": episode_id,
                    "vector": vector.tolist(),
                    "dim": dim,
                    "backend": "hashing",
                }
            )
            traces.ingest_seed(
                FractalSeed(
                    episode_id=episode_id,
                    timestamp_ms=int(clock.timestamp() * 1000),
                    embedding=vector,
                    metadata={"episode_id": episode_id, "episode_metadata": provenance},
                )
            )
            chunk_receipts.append({"episode_id": episode_id, **provenance})
        if (
            b"".join(part[2] for part in parts) != payload
            or snapshot.read_bytes() != payload
        ):
            raise ValueError("source reconstruction failed")
    for path, rows in (
        (episode_path, records),
        (cognitive / "episodes.vectors.jsonl", vectors),
    ):
        # Preserve a final non-newline record in the copied base before appending.
        needs_newline = (
            path.exists()
            and path.stat().st_size
            and not path.read_bytes().endswith(b"\n")
        )
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            if needs_newline:
                handle.write("\n")
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    if not meta_path.exists():
        meta_path.write_text(
            json.dumps(
                {"dim": dim, "embedding_backend": "hashing", "created_at": stamp}
            ),
            encoding="utf-8",
        )
    for path, payload in zip(paths, contents):
        if path.read_bytes() != payload:
            raise ValueError("source changed during import; candidate is not ready")
    if tree_manifest(base_memory) != custody["source_manifest"]:
        raise ValueError("base source changed during import")
    receipt = {
        "schema": "fram-document-candidate-v1",
        "status": "READY_FOR_EVALUATION",
        "imported_at": stamp,
        "sources": source_receipts,
        "chunks": chunk_receipts,
        "records_added": len(records),
        "source_files_unchanged": True,
        "base_custody": custody,
        "memory_manifest": tree_manifest(memory_root),
        "memory_root": str(memory_root),
        "persistent_influence_changed": False,
        "not_lived_memory": True,
    }
    (destination / "receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )
    return receipt
