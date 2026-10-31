from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

try:  # Optional ANN dependency (scikit-learn)
    from sklearn.neighbors import NearestNeighbors
except Exception:  # pragma: no cover - optional dependency not guaranteed
    NearestNeighbors = None  # type: ignore[assignment]

try:  # Optional FAISS ANN dependency
    import faiss  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - optional dependency not guaranteed
    faiss = None  # type: ignore[assignment]

from fram_core.claims import extract_claims
from fram_core.pipeline import tokenize_text
from fram_serving import observability
from fram_serving.cognitive_embeddings import normalize_cognitive_backend

try:
    from fram_serving.fractal_memory import FractalSeed, FractalTraceStore
except Exception:  # pragma: no cover - optional dependency
    FractalSeed = None  # type: ignore[assignment]
    FractalTraceStore = None  # type: ignore[assignment]


_CONFLICT_QUEUE: deque[Dict[str, Any]] = deque()


def register_conflict(
    belief_id: str,
    claim: str,
    evidence_for: Iterable[str] | None = None,
    evidence_against: Iterable[str] | None = None,
) -> None:
    _CONFLICT_QUEUE.append(
        {
            "belief_id": belief_id,
            "claim": claim,
            "evidence_for": list(evidence_for or []),
            "evidence_against": list(evidence_against or []),
            "status": "pending",
        }
    )
    if len(_CONFLICT_QUEUE) > 100:
        _CONFLICT_QUEUE.popleft()


def list_conflicts() -> List[Dict[str, Any]]:
    return list(_CONFLICT_QUEUE)


def _ann_backend_from_env() -> Optional[str]:
    env_value = os.getenv("FRAM_ANN_BACKEND")
    if not env_value:
        return None
    candidate = env_value.strip().lower()
    if candidate in {"faiss", "sklearn"}:
        return candidate
    return None


def _resolve_ann_backend() -> str:
    preferred = _ann_backend_from_env()
    if preferred == "faiss" and faiss is not None:
        return "faiss"
    if preferred == "sklearn":
        return "sklearn"
    if faiss is not None:
        return "faiss"
    return "sklearn"


@dataclass
class _AnnCacheEntry:
    embedding_backend: str
    index_backend: str
    file_mtime: float
    file_size: int
    ids: List[str]
    id_to_index: Dict[str, int]
    matrix: np.ndarray
    index: Any


class MemorySessionError(RuntimeError):
    """Raised when a working-memory session cannot fulfill an operation."""

    def __init__(self, session_id: str, status: str, message: str) -> None:
        super().__init__(message)
        self.session_id = session_id
        self.status = status


class MemoryWriteError(RuntimeError):
    """Raised when cognitive memory cannot persist a record safely."""

    def __init__(self, message: str, *, logged: bool = False) -> None:
        super().__init__(message)
        self.logged = logged


class WorkingMemoryStore:
    """Persist simple working-memory entries per session."""

    STATUS_ACTIVE = "active"
    STATUS_PAUSED = "paused"
    STATUS_ENDED = "ended"

    def __init__(self, root: Path, *, dedupe_window_seconds: float | None = None) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, List[dict]] = {}
        self._meta_cache: dict[str, dict] = {}
        if dedupe_window_seconds is not None and float(dedupe_window_seconds) > 0:
            self._dedupe_window = timedelta(seconds=float(dedupe_window_seconds))
        else:
            self._dedupe_window = None
        self._dedupe_cache: dict[str, tuple[datetime, dict]] = {}

    def _session_path(self, session_id: str) -> Path:
        return self.root / f"{session_id}.jsonl"

    def _meta_path(self, session_id: str) -> Path:
        return self.root / f"{session_id}.meta.json"

    def _session_id_from_meta(self, filename: str) -> Optional[str]:
        suffix = ".meta.json"
        if not filename.endswith(suffix):
            return None
        return filename[: -len(suffix)]

    def _default_meta(self, session_id: str) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        return {
            "id": session_id,
            "status": self.STATUS_ACTIVE,
            "created": now,
            "updated": now,
            "metadata": {},
        }

    def _load_meta(self, session_id: str) -> dict:
        if session_id in self._meta_cache:
            return dict(self._meta_cache[session_id])
        path = self._meta_path(session_id)
        if path.exists():
            try:
                with path.open("r", encoding="utf-8") as handle:
                    data = json.load(handle)
            except json.JSONDecodeError:
                data = self._default_meta(session_id)
        else:
            data = self._default_meta(session_id)
            self._save_meta(session_id, data)
        self._meta_cache[session_id] = dict(data)
        return dict(data)

    def _save_meta(self, session_id: str, payload: dict) -> None:
        path = self._meta_path(session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        self._meta_cache[session_id] = dict(payload)

    def _load(self, session_id: str) -> List[dict]:
        if session_id in self._cache:
            return self._cache[session_id]
        path = self._session_path(session_id)
        entries: List[dict] = []
        if path.exists():
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        if "last_seen" not in entry:
                            entry["last_seen"] = entry.get("time")
                        entries.append(entry)
                    except json.JSONDecodeError:
                        continue
        self._cache[session_id] = entries
        return entries

    def _dedupe_key(self, session_id: str, text: str, metadata: Dict[str, Any] | None) -> str:
        meta_payload = json.dumps(metadata or {}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        raw = f"{session_id}\n{text}\n{meta_payload}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _dedupe_lookup(self, key: str, now: datetime) -> dict | None:
        if self._dedupe_window is None:
            return None
        cached = self._dedupe_cache.get(key)
        if cached is None:
            return None
        stamp, entry = cached
        if now - stamp <= self._dedupe_window:
            return entry
        self._dedupe_cache.pop(key, None)
        return None

    def _dedupe_remember(self, key: str, now: datetime, entry: dict) -> None:
        if self._dedupe_window is None:
            return
        self._dedupe_cache[key] = (now, dict(entry))

    def _prune_dedupe_cache(self, now: datetime) -> None:
        if self._dedupe_window is None or not self._dedupe_cache:
            return
        cutoff = now - self._dedupe_window
        stale_keys = [key for key, (stamp, _) in self._dedupe_cache.items() if stamp < cutoff]
        for key in stale_keys:
            self._dedupe_cache.pop(key, None)
        if len(self._dedupe_cache) > 2048:
            self._dedupe_cache.clear()

    def list(self, session_id: str) -> List[dict]:
        return list(self._load(session_id))

    def ensure_session(self, session_id: str) -> dict:
        return self._load_meta(session_id)

    def session_info(self, session_id: str) -> dict:
        meta = self.ensure_session(session_id)
        info = dict(meta)
        info["entry_count"] = len(self._load(session_id))
        return info

    def create(self, session_id: Optional[str] = None, *, metadata: Optional[Dict[str, Any]] = None) -> dict:
        session = session_id or uuid.uuid4().hex
        meta_path = self._meta_path(session)
        existed = meta_path.exists()
        meta = self.ensure_session(session)
        if metadata is not None:
            meta = dict(meta)
            meta["metadata"] = dict(metadata)
            meta["updated"] = datetime.now(timezone.utc).isoformat()
            self._save_meta(session, meta)
        info = self.session_info(session)
        info["created"] = not existed
        return info

    def set_status(self, session_id: str, status: str) -> dict:
        status_norm = status.lower()
        if status_norm == "continue":
            status_norm = self.STATUS_ACTIVE
        if status_norm not in {self.STATUS_ACTIVE, self.STATUS_PAUSED, self.STATUS_ENDED}:
            raise ValueError(f"invalid status '{status}'")
        meta = self.ensure_session(session_id)
        if meta.get("status") == status_norm:
            return self.session_info(session_id)
        meta = dict(meta)
        meta["status"] = status_norm
        meta["updated"] = datetime.now(timezone.utc).isoformat()
        self._save_meta(session_id, meta)
        return self.session_info(session_id)

    def append(self, session_id: str, text: str, metadata: Dict[str, Any] | None = None) -> dict:
        meta = self.ensure_session(session_id)
        status = meta.get("status", self.STATUS_ACTIVE)
        if status == self.STATUS_PAUSED:
            raise MemorySessionError(session_id, status, "session is paused")
        if status == self.STATUS_ENDED:
            raise MemorySessionError(session_id, status, "session is ended")
        idempotency_key = None
        if metadata:
            raw_key = metadata.get("idempotency_key") or metadata.get("idempotencyKey")
            if raw_key is not None:
                idempotency_key = str(raw_key)
        now = datetime.now(timezone.utc)
        self._prune_dedupe_cache(now)
        entries = self._load(session_id)
        if idempotency_key:
            for entry in reversed(entries):
                entry_meta = entry.get("metadata") or {}
                entry_key = entry_meta.get("idempotency_key") or entry_meta.get("idempotencyKey")
                if entry_key is not None and str(entry_key) == idempotency_key:
                    payload = dict(entry)
                    payload["deduped"] = True
                    return payload
        if self._dedupe_window is not None:
            key = self._dedupe_key(session_id, text, metadata)
            cached = self._dedupe_lookup(key, now)
            if cached is not None:
                payload = dict(cached)
                payload["deduped"] = True
                return payload
        stamp = now.isoformat()
        entry = {
            "id": uuid.uuid4().hex,
            "time": stamp,
            "text": text,
            "metadata": metadata or {},
            "last_seen": stamp,
        }
        entries.append(entry)
        path = self._session_path(session_id)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        if self._dedupe_window is not None:
            self._dedupe_remember(self._dedupe_key(session_id, text, metadata), now, entry)
        meta = dict(meta)
        meta["updated"] = stamp
        self._save_meta(session_id, meta)
        return entry

    def clear(self, session_id: str) -> None:
        self._cache.pop(session_id, None)
        path = self._session_path(session_id)
        if path.exists():
            path.unlink()
        meta = self.ensure_session(session_id)
        meta = dict(meta)
        meta["updated"] = datetime.now(timezone.utc).isoformat()
        self._save_meta(session_id, meta)

    def sessions(self) -> Iterable[str]:
        seen: set[str] = set()
        for path in self.root.glob("*.jsonl"):
            session_id = path.stem
            seen.add(session_id)
            yield session_id
        for path in self.root.glob("*.meta.json"):
            session_id = self._session_id_from_meta(path.name)
            if session_id and session_id not in seen:
                yield session_id

    def session_summaries(self) -> Iterable[dict]:
        for session_id in self.sessions():
            yield self.session_info(session_id)

    def _persist_entries(self, session_id: str, entries: List[dict]) -> None:
        path = self._session_path(session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            for entry in entries:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._cache[session_id] = entries

    def session_chunks(self, session_id: str, entries: Optional[List[dict]] = None) -> List[dict]:
        if entries is None:
            entries = self.list(session_id)
        chunks: List[dict] = []
        touched = False
        for idx, entry in enumerate(entries):
            text = str(entry.get("text", ""))
            tokens = tokenize_text(text)
            claims = extract_claims(text, doc_id=f"memory:{session_id}", chunk_id=idx)
            last_seen_stamp = datetime.now(timezone.utc).isoformat()
            entry["last_seen"] = last_seen_stamp
            touched = True
            chunks.append(
                {
                    "file": f"memory:{session_id}",
                    "chunk_id": idx,
                    "text": text,
                    "tokens": tokens,
                    "timestamp": entry.get("time"),
                    "last_seen": last_seen_stamp,
                    "claims": claims,
                    "source": "session_memory",
                    "hierarchy": {
                        "cluster": f"memory:{session_id}",
                        "segment": f"memory:{session_id}:item:{idx}",
                        "chunk": f"chunk:{idx}",
                    },
                }
            )
        if touched:
            self._persist_entries(session_id, entries)
        return chunks


class CognitiveMemoryStore:
    """Durable cognitive memory store for episodes/beliefs/links.

    Segment writer implements idempotent logging, replay guards, and
    schema/version tagging so conversational memory can persist without
    duplication.
    """

    FILE_EPISODES = "episodes.jsonl"
    FILE_BELIEFS = "beliefs.jsonl"  # legacy single-file fallback
    FILE_LINKS = "links.jsonl"
    FILE_CONSTRAINTS = "constraints.jsonl"
    FILE_EPISODE_VECTORS = "episodes.vectors.jsonl"
    FILE_BELIEF_VECTORS = "beliefs.vectors.jsonl"
    FILE_VECTOR_META = "vectors.meta.json"
    BELIEF_META = "beliefs.meta.json"
    BELIEF_SEGMENT_PREFIX = "beliefs"
    BELIEF_SCHEMA_VERSION = "cogmem-1"
    DEFAULT_MAX_SEGMENT_TURNS = 5000

    def __init__(self, root: Path, *, config: Any | None = None) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._config = config
        self._belief_meta_cache: Dict[str, Any] | None = None
        self._vector_meta_cache: Dict[str, Dict[str, Any]] = {}
        self._ann_cache: Dict[str, _AnnCacheEntry] = {}
        self._fractal_enabled = FractalTraceStore is not None and FractalSeed is not None
        self._fractal_store: FractalTraceStore | None = None
        self._fractal_embedding_dim: Optional[int] = None
        self._fractal_storage_root = self._resolve_fractal_storage_root()
        self._fractal_observability_root = self._resolve_observability_root()
        self._observability_root = self._resolve_observability_root()
        self._preserve_full_experience = bool(
            self._config_value("preserve_full_experience", True)
        )
        self._load_belief_meta()

    # -- persistence primitives --
    def _path(self, name: str) -> Path:
        return self.root / name

    def _backend_key(self, backend: Optional[str]) -> str:
        raw = backend
        if raw is None:
            raw = getattr(self._config, "cognitive_memory_embedding_backend", "hashing")
        key = normalize_cognitive_backend(raw)
        return key or "hashing"

    @staticmethod
    def _sanitize_backend_label(label: str) -> str:
        return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in label)

    def _vector_suffix(self, backend: Optional[str]) -> str:
        key = self._backend_key(backend)
        if key in {"", "hashing"}:
            return ""
        safe = self._sanitize_backend_label(key)
        return f".{safe}"

    def _vector_name(self, base: str, backend: Optional[str]) -> str:
        suffix = self._vector_suffix(backend)
        if not suffix:
            return base
        if base.endswith(".jsonl"):
            return f"{base[:-6]}{suffix}.jsonl"
        if base.endswith(".json"):
            return f"{base[:-5]}{suffix}.json"
        return f"{base}{suffix}"

    def _vector_meta_path(self, backend: Optional[str] = None) -> Path:
        return self._path(self._vector_name(self.FILE_VECTOR_META, backend))

    def vector_path(self, *, kind: str, backend: Optional[str] = None) -> Path:
        kind_key = str(kind or "").strip().lower()
        if kind_key == "episode":
            base = self.FILE_EPISODE_VECTORS
        elif kind_key == "belief":
            base = self.FILE_BELIEF_VECTORS
        else:
            raise ValueError(f"unsupported vector kind: {kind}")
        return self._path(self._vector_name(base, backend))

    @staticmethod
    def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.flush()
            os.replace(tmp_path, path)
        finally:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    @staticmethod
    def _atomic_append_line(path: Path, line: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as dest:
                if path.exists():
                    with path.open("r", encoding="utf-8") as src:
                        shutil.copyfileobj(src, dest)
                dest.write(line)
                dest.write("\n")
                dest.flush()
            os.replace(tmp_path, path)
        finally:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    @staticmethod
    def _lock_path(path: Path) -> Path:
        return path.with_suffix(path.suffix + ".lock")

    def _append_jsonl_safe(self, path: Path, line: str, *, timeout_sec: float = 2.0) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self._lock_path(path)
        lock_fd: int | None = None
        start = time.monotonic()
        while True:
            try:
                lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                break
            except FileExistsError as exc:
                if (time.monotonic() - start) >= timeout_sec:
                    raise MemoryWriteError(
                        f"timeout acquiring lock for {path}"
                    ) from exc
                time.sleep(0.05)
        try:
            payload = line if line.endswith("\n") else f"{line}\n"
            with path.open("a", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            if lock_fd is not None:
                try:
                    os.close(lock_fd)
                except Exception:
                    pass
            try:
                lock_path.unlink(missing_ok=True)
            except Exception:
                pass

    def _log_cognitive_write_failure(
        self,
        *,
        record_type: str,
        record_id: str | None,
        path: Path,
        error: Exception,
    ) -> None:
        observability.log_cognitive_memory_event(
            self._observability_root,
            {
                "kind": f"{record_type}_write_failed",
                "record_type": record_type,
                "record_id": record_id,
                "path": str(path),
                "error": str(error),
            },
        )

    def _append_jsonl_or_raise(
        self,
        *,
        name: str,
        obj: Dict[str, Any],
        record_type: str,
    ) -> None:
        path = self._path(name)
        record_id = obj.get("id")
        try:
            self._append_jsonl_safe(path, json.dumps(obj, ensure_ascii=False))
        except Exception as exc:
            self._log_cognitive_write_failure(
                record_type=record_type,
                record_id=str(record_id) if record_id is not None else None,
                path=path,
                error=exc,
            )
            raise MemoryWriteError(
                f"failed to append {record_type} record",
                logged=True,
            ) from exc

    def _append_jsonl_best_effort(
        self,
        *,
        name: str,
        obj: Dict[str, Any],
        record_type: str,
    ) -> bool:
        path = self._path(name)
        record_id = obj.get("id")
        try:
            self._append_jsonl_safe(path, json.dumps(obj, ensure_ascii=False))
            return True
        except Exception as exc:
            self._log_cognitive_write_failure(
                record_type=record_type,
                record_id=str(record_id) if record_id is not None else None,
                path=path,
                error=exc,
            )
            return False

    def _append_vector_entry(
        self,
        name: str,
        *,
        item_id: str,
        vector: Sequence[float],
        backend: Optional[str] = None,
    ) -> None:
        payload: Dict[str, Any] = {
            "id": item_id,
            "vector": [float(v) for v in vector],
            "dim": int(len(vector)),
        }
        if backend:
            payload["backend"] = backend
        self._append_jsonl_best_effort(name=name, obj=payload, record_type="vector")

    def _iter_jsonl(self, name: str) -> Iterable[Dict[str, Any]]:
        path = self._path(name)
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue

    # -- models (dict-based for lightness) --
    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _parse_iso(value: Any) -> Optional[datetime]:
        if value is None:
            return None
        try:
            dt = datetime.fromisoformat(str(value))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None

    # --- belief meta helpers ---
    def _belief_meta_path(self) -> Path:
        return self._path(self.BELIEF_META)

    @staticmethod
    def _belief_segment_name(index: int) -> str:
        return f"{CognitiveMemoryStore.BELIEF_SEGMENT_PREFIX}.{index:05d}.jsonl"

    def _belief_segment_path(self, name: str) -> Path:
        return self._path(name)

    def _config_value(self, attr: str, default: Any) -> Any:
        if self._config is not None and hasattr(self._config, attr):
            return getattr(self._config, attr)
        return default

    def _resolve_fractal_storage_root(self) -> Path:
        try:
            base = self.root.parent
        except AttributeError:
            base = Path(".")
        backend = self._backend_key(None)
        if backend and backend not in {"hashing", ""}:
            safe = self._sanitize_backend_label(backend)
            return base / f"fractal_{safe}"
        return base / "fractal"

    def _resolve_observability_root(self) -> Path:
        if self._config is not None:
            storage_root = getattr(self._config, "STORAGE_ROOT", None)
            subfolders = getattr(self._config, "STORAGE_SUBFOLDERS", {}) or {}
            if storage_root is not None:
                observability_name = subfolders.get("observability", "observability")
                return Path(storage_root) / observability_name
        try:
            parent = self.root.parents[1]
        except IndexError:
            parent = self.root.parent if hasattr(self.root, "parent") else Path(".")
        return parent / "observability"

    def _load_vector_meta(self, backend: Optional[str] = None) -> Dict[str, Any]:
        key = self._backend_key(backend)
        cached = self._vector_meta_cache.get(key)
        if cached is not None:
            return cached
        path = self._vector_meta_path(key)
        if path.exists():
            try:
                meta = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                meta = {}
        else:
            meta = {}
        meta.setdefault("embedding_backend", key)
        meta.setdefault("dim", None)
        meta.setdefault("created_at", self._now_iso())
        self._vector_meta_cache[key] = meta
        return meta

    def _save_vector_meta(self, payload: Dict[str, Any], backend: Optional[str] = None) -> None:
        key = self._backend_key(backend)
        self._atomic_write_json(self._vector_meta_path(key), payload)
        self._vector_meta_cache[key] = dict(payload)

    def _ensure_vector_meta(self, *, dim: int, backend: Optional[str]) -> str:
        resolved_backend = self._backend_key(backend)
        meta = dict(self._load_vector_meta(resolved_backend))
        existing_dim = meta.get("dim")
        if existing_dim is not None and int(existing_dim) != dim:
            raise ValueError(
                f"incompatible cognitive-memory embedding dimension (expected {existing_dim}, received {dim})"
            )
        meta["dim"] = int(dim)
        meta["embedding_backend"] = resolved_backend
        meta["updated_at"] = self._now_iso()
        self._save_vector_meta(meta, backend=resolved_backend)
        return resolved_backend

    def _load_vector_map(self, name: str) -> Dict[str, np.ndarray]:
        path = self._path(name)
        vectors: Dict[str, np.ndarray] = {}
        if not path.exists():
            return vectors
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                item_id = payload.get("id")
                raw_vec = payload.get("vector")
                if not item_id or raw_vec is None:
                    continue
                arr = np.asarray(raw_vec, dtype=float)
                norm = float(np.linalg.norm(arr))
                if norm <= 0.0:
                    continue
                vectors[str(item_id)] = arr / norm
        return vectors

    def _load_episode_vectors_array(self, backend_key: str) -> tuple[List[str], np.ndarray]:
        path = self.vector_path(kind="episode", backend=backend_key)
        ids: List[str] = []
        vectors: List[np.ndarray] = []
        if not path.exists():
            return ids, np.zeros((0, 0), dtype=float)
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                item_id = payload.get("id")
                raw_vec = payload.get("vector")
                if not item_id or raw_vec is None:
                    continue
                arr = np.asarray(raw_vec, dtype=float).ravel()
                if arr.size == 0:
                    continue
                norm = float(np.linalg.norm(arr))
                if norm <= 0.0:
                    continue
                ids.append(str(item_id))
                vectors.append(arr / norm)
        if not vectors:
            return ids, np.zeros((0, 0), dtype=float)
        try:
            matrix = np.vstack(vectors)
        except ValueError:
            return [], np.zeros((0, 0), dtype=float)
        return ids, matrix

    def _ensure_episode_ann_index(self, backend_key: str) -> tuple[_AnnCacheEntry | None, Dict[str, Any]]:
        diag: Dict[str, Any] = {"enabled": False}
        path = self.vector_path(kind="episode", backend=backend_key)
        if not path.exists():
            diag["reason"] = "missing_vectors"
            return None, diag
        if NearestNeighbors is None and faiss is None:
            diag["reason"] = "ann_unavailable"
            return None, diag
        try:
            stat = path.stat()
            file_mtime = float(stat.st_mtime)
            file_size = int(stat.st_size)
        except Exception:
            file_mtime = 0.0
            file_size = 0

        index_backend = _resolve_ann_backend()
        cached = self._ann_cache.get(backend_key)
        if (
            cached is not None
            and cached.file_mtime == file_mtime
            and cached.file_size == file_size
            and cached.index_backend == index_backend
        ):
            diag.update(
                {
                    "enabled": True,
                    "index_backend": cached.index_backend,
                    "index_size": len(cached.ids),
                    "cached": True,
                }
            )
            return cached, diag

        ids, matrix = self._load_episode_vectors_array(backend_key)
        if matrix.size == 0 or not ids:
            diag["reason"] = "empty_vectors"
            return None, diag
        if index_backend == "faiss" and faiss is None:
            index_backend = "sklearn"
        if index_backend == "faiss":
            try:
                index = faiss.IndexFlatIP(matrix.shape[1])
                index.add(matrix.astype(np.float32))
            except Exception as exc:
                diag["reason"] = f"faiss_error:{exc}"
                return None, diag
        else:
            if NearestNeighbors is None:
                diag["reason"] = "sklearn_missing"
                return None, diag
            ann = NearestNeighbors(metric="cosine", algorithm="brute")
            ann.fit(matrix)
            index = ann

        entry = _AnnCacheEntry(
            embedding_backend=backend_key,
            index_backend=index_backend,
            file_mtime=file_mtime,
            file_size=file_size,
            ids=ids,
            id_to_index={item_id: idx for idx, item_id in enumerate(ids)},
            matrix=matrix,
            index=index,
        )
        self._ann_cache[backend_key] = entry
        diag.update(
            {
                "enabled": True,
                "index_backend": index_backend,
                "index_size": len(ids),
                "cached": False,
            }
        )
        return entry, diag

    def _ann_query(
        self,
        query_vec: np.ndarray,
        *,
        backend_key: str,
        k: int,
    ) -> tuple[List[str], List[float], Dict[str, Any]]:
        diag: Dict[str, Any] = {
            "enabled": False,
            "index_backend": None,
            "index_size": 0,
            "requested": 0,
            "returned": 0,
        }
        try:
            requested = int(k)
        except (TypeError, ValueError):
            requested = 0
        if requested <= 0:
            diag["reason"] = "requested_zero"
            return [], [], diag
        cache, cache_diag = self._ensure_episode_ann_index(backend_key)
        diag.update(cache_diag)
        if cache is None or not cache_diag.get("enabled"):
            diag.setdefault("reason", "index_unavailable")
            return [], [], diag
        if query_vec.size == 0:
            diag["reason"] = "empty_query"
            return [], [], diag
        if cache.matrix.shape[1] != query_vec.size:
            diag["reason"] = "dim_mismatch"
            diag["expected_dim"] = int(cache.matrix.shape[1])
            diag["query_dim"] = int(query_vec.size)
            return [], [], diag
        count = min(requested, len(cache.ids))
        if count <= 0:
            diag["reason"] = "empty_index"
            return [], [], diag

        ids: List[str] = []
        sims: List[float] = []
        try:
            if cache.index_backend == "faiss" and faiss is not None:
                scores, indices = cache.index.search(
                    query_vec.astype(np.float32).reshape(1, -1),
                    count,
                )
                if scores.size and indices.size:
                    for idx, score in zip(indices[0], scores[0]):
                        if idx < 0 or idx >= len(cache.ids):
                            continue
                        ids.append(cache.ids[int(idx)])
                        sims.append(float(score))
            elif cache.index_backend == "sklearn" and NearestNeighbors is not None:
                distances, indices = cache.index.kneighbors(
                    query_vec.reshape(1, -1),
                    n_neighbors=count,
                )
                if distances.size and indices.size:
                    for idx, dist in zip(indices[0], distances[0]):
                        if idx < 0 or idx >= len(cache.ids):
                            continue
                        ids.append(cache.ids[int(idx)])
                        sims.append(float(1.0 - dist))
        except Exception as exc:
            diag["reason"] = f"ann_query_error:{exc}"
            return [], [], diag

        diag["requested"] = count
        diag["returned"] = len(ids)
        return ids, sims, diag

    def _load_belief_meta(self) -> Dict[str, Any]:
        return self._belief_meta()

    def _belief_meta(self) -> Dict[str, Any]:
        if self._belief_meta_cache is not None:
            return self._belief_meta_cache
        meta_path = self._belief_meta_path()
        if meta_path.exists():
            try:
                with meta_path.open("r", encoding="utf-8") as handle:
                    meta = json.load(handle)
            except json.JSONDecodeError:
                meta = {}
        else:
            meta = {}
        meta.setdefault("schema_version", self.BELIEF_SCHEMA_VERSION)
        meta.setdefault("segments", [])
        meta.setdefault("active_segment", "")
        meta.setdefault("total_count", 0)
        meta.setdefault("next_seq_by_session", {})
        meta.setdefault("last_entries", {})
        meta.setdefault("max_segment_turns", self._config_value("cognitive_memory_max_segment_turns", self.DEFAULT_MAX_SEGMENT_TURNS))
        retain_segments = self._config_value("cognitive_memory_retain_segments", None)
        retain_days = self._config_value("cognitive_memory_retain_days", None)
        if self._preserve_full_experience:
            retain_segments = None
            retain_days = None
        meta.setdefault("retain_segments", retain_segments)
        meta.setdefault("retain_days", retain_days)
        meta.setdefault("writes", 0)
        meta.setdefault("duplicates_skipped", 0)
        if not meta["segments"]:
            self._initialise_belief_segments(meta)
        else:
            self._ensure_segments_exist(meta)
        self._belief_meta_cache = meta
        return meta

    def _initialise_belief_segments(self, meta: Dict[str, Any]) -> None:
        legacy_path = self._path(self.FILE_BELIEFS)
        first_segment = self._belief_segment_name(1)
        seg_path = self._belief_segment_path(first_segment)
        seg_path.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        if legacy_path.exists():
            if not seg_path.exists():
                legacy_path.rename(seg_path)
            else:
                # merge legacy content then remove
                with legacy_path.open("r", encoding="utf-8") as src:
                    tmp_fd, tmp_name = tempfile.mkstemp(dir=str(seg_path.parent), prefix=seg_path.name, suffix=".tmp")
                    tmp_path = Path(tmp_name)
                    try:
                        with os.fdopen(tmp_fd, "w", encoding="utf-8") as dest:
                            if seg_path.exists():
                                with seg_path.open("r", encoding="utf-8") as existing:
                                    shutil.copyfileobj(existing, dest)
                            shutil.copyfileobj(src, dest)
                            dest.flush()
                        os.replace(tmp_path, seg_path)
                    finally:
                        if tmp_path.exists():
                            tmp_path.unlink(missing_ok=True)
                legacy_path.unlink(missing_ok=True)
        if seg_path.exists():
            count = sum(1 for _ in self._iter_jsonl_segment(seg_path))
        meta["segments"] = [{"name": first_segment, "count": count, "created_at": self._now_iso()}]
        meta["active_segment"] = first_segment
        meta["total_count"] = count
        self._atomic_write_json(self._belief_meta_path(), meta)

    def _ensure_segments_exist(self, meta: Dict[str, Any]) -> None:
        for entry in meta.get("segments", []):
            seg_path = self._belief_segment_path(entry["name"])
            seg_path.parent.mkdir(parents=True, exist_ok=True)
            if not seg_path.exists():
                seg_path.touch()
            entry.setdefault("created_at", self._now_iso())
        if not meta.get("active_segment") and meta["segments"]:
            meta["active_segment"] = meta["segments"][-1]["name"]

    def _save_belief_meta(self, meta: Dict[str, Any]) -> None:
        self._belief_meta_cache = meta
        self._atomic_write_json(self._belief_meta_path(), meta)

    def _belief_active_segment(self, meta: Dict[str, Any]) -> Dict[str, Any]:
        active = meta.get("active_segment")
        for entry in meta.get("segments", []):
            if entry["name"] == active:
                return entry
        if not meta.get("segments"):
            self._initialise_belief_segments(meta)
            return self._belief_active_segment(meta)
        meta["active_segment"] = meta["segments"][-1]["name"]
        return meta["segments"][-1]

    def _belief_segment_index(self, meta: Dict[str, Any]) -> int:
        if not meta.get("segments"):
            return 1
        last = meta["segments"][-1]["name"]
        try:
            return int(last.split(".")[1]) + 1
        except (IndexError, ValueError):
            return len(meta["segments"]) + 1

    def _iter_jsonl_segment(self, path: Path) -> Iterable[Dict[str, Any]]:
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue

    def _iter_belief_records(self) -> Iterable[Dict[str, Any]]:
        meta = self._belief_meta()
        segments = meta.get("segments", [])
        if segments:
            for entry in segments:
                seg_path = self._belief_segment_path(entry["name"])
                yield from self._iter_jsonl_segment(seg_path)
            return
        yield from self._iter_jsonl(self.FILE_BELIEFS)

    @staticmethod
    def _turn_hash(pair_id: Optional[str], role: Optional[str], text: str, created_at: str) -> str:
        blob = json.dumps([pair_id or "", role or "", text, created_at], ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]

    def _session_key(self, session_id: Optional[str]) -> str:
        return session_id or "__global__"

    def _assign_seq_no(self, meta: Dict[str, Any], session_id: Optional[str], explicit: Optional[int]) -> int:
        if explicit is not None:
            seq = int(explicit)
            key = self._session_key(session_id)
            meta["next_seq_by_session"][key] = max(meta["next_seq_by_session"].get(key, 0), seq + 1)
            return seq
        key = self._session_key(session_id)
        seq = meta["next_seq_by_session"].get(key, 0)
        meta["next_seq_by_session"][key] = seq + 1
        return seq

    def _rollover_if_needed(self, meta: Dict[str, Any]) -> None:
        segment = self._belief_active_segment(meta)
        max_turns = int(meta.get("max_segment_turns") or self.DEFAULT_MAX_SEGMENT_TURNS)
        if segment["count"] < max_turns:
            return
        next_index = self._belief_segment_index(meta)
        new_name = self._belief_segment_name(next_index)
        new_path = self._belief_segment_path(new_name)
        new_path.parent.mkdir(parents=True, exist_ok=True)
        if not new_path.exists():
            new_path.touch()
        meta["segments"].append({"name": new_name, "count": 0, "created_at": self._now_iso()})
        meta["active_segment"] = new_name
        self._apply_segment_retention(meta)

    def _apply_segment_retention(self, meta: Dict[str, Any]) -> None:
        if self._preserve_full_experience:
            return
        segments = meta.get("segments", [])
        retain_segments = meta.get("retain_segments")
        if retain_segments is not None:
            try:
                retain_segments = int(retain_segments)
            except (TypeError, ValueError):
                retain_segments = None
        if retain_segments is not None and retain_segments > 0:
            while len(segments) > retain_segments:
                entry = segments.pop(0)
                seg_path = self._belief_segment_path(entry["name"])
                if seg_path.exists():
                    seg_path.unlink(missing_ok=True)
                meta["total_count"] = max(0, meta.get("total_count", 0) - entry.get("count", 0))
            if segments:
                meta["active_segment"] = segments[-1]["name"]

        retain_days = meta.get("retain_days")
        if retain_days is not None:
            try:
                retain_days = int(retain_days)
            except (TypeError, ValueError):
                retain_days = None
        if retain_days and retain_days > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(days=retain_days)
            kept_segments: List[Dict[str, Any]] = []
            for entry in meta.get("segments", []):
                created_at = self._parse_iso(entry.get("created_at")) or datetime.now(timezone.utc)
                if created_at >= cutoff or entry["name"] == meta.get("active_segment"):
                    kept_segments.append(entry)
                    continue
                seg_path = self._belief_segment_path(entry["name"])
                if seg_path.exists():
                    seg_path.unlink(missing_ok=True)
                meta["total_count"] = max(0, meta.get("total_count", 0) - entry.get("count", 0))
            if kept_segments:
                meta["segments"] = kept_segments
                meta["active_segment"] = kept_segments[-1]["name"]

    @staticmethod
    def _is_replay(source: Optional[Dict[str, Any]]) -> bool:
        if not source:
            return False
        return str(source.get("kind", "")).lower() == "replay"

    def _log_fractal_event(self, kind: str, payload: Dict[str, Any]) -> None:
        if not self._fractal_enabled:
            return
        event = dict(payload)
        event["kind"] = kind
        observability.log_fractal_memory_event(self._fractal_observability_root, event)

    def _log_fractal_error(self, episode_id: Optional[str], message: str) -> None:
        self._log_fractal_event("error", {"episode_id": episode_id, "message": message})

    def _ensure_fractal_store(self, embedding_dim: Optional[int]) -> None:
        if not self._fractal_enabled or embedding_dim is None or embedding_dim <= 0:
            return
        if self._fractal_store is not None and self._fractal_embedding_dim == embedding_dim:
            return
        try:
            self._fractal_store = FractalTraceStore(
                self._fractal_storage_root,
                observability_root=self._fractal_observability_root,
                embedding_dim=int(embedding_dim),
            )
            self._fractal_embedding_dim = int(embedding_dim)
        except Exception as exc:  # pragma: no cover - best effort logging
            self._fractal_store = None
            self._fractal_embedding_dim = None
            self._log_fractal_error(None, f"fractal store setup failed: {exc}")

    def _maybe_record_fractal_trace(
        self,
        payload: Dict[str, Any],
        embedding: Optional[Sequence[float]],
        backend: Optional[str],
    ) -> None:
        if not self._fractal_enabled or embedding is None:
            return
        vector = np.asarray(embedding, dtype=float).ravel()
        if vector.size == 0:
            return
        if not np.isfinite(vector).all():
            return
        self._ensure_fractal_store(vector.size)
        if self._fractal_store is None:
            return
        created_at = self._parse_iso(payload.get("time"))
        timestamp_ms = int(created_at.timestamp() * 1000) if created_at else 0
        meta: Dict[str, Any] = {
            "domain": payload.get("domain"),
            "task": payload.get("task"),
            "trace_id": payload.get("trace_id"),
            "citations": list(payload.get("citations", []) or []),
        }
        if backend:
            meta["backend"] = backend
        payload_meta = payload.get("metadata")
        if isinstance(payload_meta, dict) and payload_meta:
            meta["episode_metadata"] = payload_meta
        try:
            seed = FractalSeed(
                episode_id=payload["id"],
                timestamp_ms=timestamp_ms,
                embedding=vector,
                metadata=meta,
            )
            self._fractal_store.ingest_seed(seed)
        except Exception as exc:  # pragma: no cover - best effort logging
            self._log_fractal_error(payload.get("id"), f"ingest failed: {exc}")

    def _episode_vector_entry(
        self,
        episode_id: str,
        *,
        backend: Optional[str] = None,
    ) -> tuple[np.ndarray | None, Optional[str]]:
        path = self._path(self._vector_name(self.FILE_EPISODE_VECTORS, backend))
        if not path.exists():
            return None, None
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if str(payload.get("id")) != str(episode_id):
                        continue
                    vector = payload.get("vector")
                    if vector is None:
                        return None, None
                    arr = np.asarray(vector, dtype=float).ravel()
                    backend = payload.get("backend")
                    return arr, backend
        except Exception:
            return None, None
        return None, None

    def _load_episode_record(self, episode_id: str) -> Optional[Dict[str, Any]]:
        for record in self._iter_jsonl(self.FILE_EPISODES):
            if str(record.get("id")) == str(episode_id):
                return record
        return None

    def ensure_fractal_trace(self, episode_id: str) -> bool:
        if not self._fractal_enabled:
            return False
        if not episode_id:
            return False
        backend_key = self._backend_key(None)
        meta = self._load_vector_meta(backend_key)
        dim_value = meta.get("dim")
        try:
            dim_int = int(dim_value) if dim_value is not None else None
        except (TypeError, ValueError):
            dim_int = None
        if self._fractal_store is not None and self._fractal_store.load_raw(episode_id) is not None:
            return True
        vector, backend = self._episode_vector_entry(episode_id, backend=backend_key)
        if vector is None or vector.size == 0:
            self._log_fractal_event("backfill_skipped", {"episode_id": episode_id, "reason": "missing_vector"})
            return False
        if dim_int is None:
            dim_int = int(vector.size)
        self._ensure_fractal_store(dim_int)
        if self._fractal_store is None:
            return False
        if self._fractal_store.load_raw(episode_id) is not None:
            return True
        record = self._load_episode_record(episode_id)
        if record is None:
            self._log_fractal_event("backfill_skipped", {"episode_id": episode_id, "reason": "missing_episode"})
            return False
        timestamp = self._parse_iso(record.get("time"))
        timestamp_ms = int(timestamp.timestamp() * 1000) if timestamp else 0
        meta_payload: Dict[str, Any] = {
            "domain": record.get("domain"),
            "task": record.get("task"),
            "trace_id": record.get("trace_id"),
            "citations": list(record.get("citations", []) or []),
            "backend": backend,
        }
        episode_meta = record.get("metadata")
        if isinstance(episode_meta, dict) and episode_meta:
            meta_payload["episode_metadata"] = episode_meta
        try:
            seed = FractalSeed(
                episode_id=str(episode_id),
                timestamp_ms=timestamp_ms,
                embedding=vector,
                metadata=meta_payload,
            )
            line = self._fractal_store.ingest_seed(seed)
            self._log_fractal_event(
                "backfill",
                {"episode_id": episode_id, "nodes": len(line.nodes)},
            )
            return True
        except Exception as exc:
            self._log_fractal_error(episode_id, f"backfill failed: {exc}")
            return False

    def append_episode(
        self,
        *,
        query: str,
        domain: Optional[str] = None,
        task: Optional[str] = None,
        answer: str | None = None,
        citations: List[str] | None = None,
        trace_id: Optional[str] = None,
        calibration: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        embedding: Optional[Sequence[float]] = None,
        embedding_backend: Optional[str] = None,
    ) -> Dict[str, Any]:
        eid = uuid.uuid4().hex
        payload = {
            "type": "episode",
            "id": eid,
            "time": self._now_iso(),
            "query": str(query),
            "domain": (domain or "").strip() or None,
            "task": (task or "").strip() or None,
            "answer": answer or "",
            "citations": list(citations or []),
            "trace_id": trace_id,
            "calibration": calibration or {},
            "metadata": metadata or {},
        }
        self._append_jsonl_or_raise(
            name=self.FILE_EPISODES,
            obj=payload,
            record_type="episode",
        )
        backend: Optional[str] = None
        if embedding is not None:
            backend = self._ensure_vector_meta(dim=len(embedding), backend=embedding_backend)
            self._append_vector_entry(
                self._vector_name(self.FILE_EPISODE_VECTORS, backend),
                item_id=eid,
                vector=embedding,
                backend=backend,
            )
        self._maybe_record_fractal_trace(payload, embedding, backend)
        return dict(payload)

    def fractal_trace_store(self) -> Optional[FractalTraceStore]:
        if not self._fractal_enabled:
            return None
        if self._fractal_store is None:
            meta = self._load_vector_meta(self._backend_key(None))
            dim_value = meta.get("dim")
            try:
                dim_int = int(dim_value) if dim_value is not None else None
            except (TypeError, ValueError):
                dim_int = None
            self._ensure_fractal_store(dim_int)
        return self._fractal_store

    def append_belief(
        self,
        *,
        text: str,
        source_episode: Optional[str] = None,
        confidence: Optional[float] = None,
        citations: List[str] | None = None,
        metadata: Optional[Dict[str, Any]] = None,
        role: Optional[str] = None,
        session_id: Optional[str] = None,
        pair_id: Optional[str] = None,
        seq_no: Optional[int] = None,
        created_at: Optional[str] = None,
        source: Optional[Dict[str, Any]] = None,
        hash_value: Optional[str] = None,
        schema_version: str = BELIEF_SCHEMA_VERSION,
        embedding: Optional[Sequence[float]] = None,
        embedding_backend: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not text:
            raise ValueError("belief text must be non-empty")
        if self._is_replay(source):
            return {
                "type": "belief",
                "id": None,
                "skipped": True,
                "reason": "replay",
            }
        meta = self._belief_meta()
        payload_meta = dict(metadata or {})
        sources_meta = payload_meta.get("sources")
        conflict_claim = payload_meta.get("conflict_claim")
        evidence_for = payload_meta.get("evidence_for")
        evidence_against = payload_meta.get("evidence_against")
        if session_id is None and "session_id" in payload_meta:
            session_id = str(payload_meta.pop("session_id"))
        if pair_id is None and "pair_id" in payload_meta:
            pair_id = str(payload_meta.pop("pair_id"))
        if role is None and "speaker" in payload_meta:
            role = str(payload_meta.pop("speaker"))
        if seq_no is None and "seq_no" in payload_meta:
            try:
                seq_no = int(payload_meta.pop("seq_no"))
            except (TypeError, ValueError):
                seq_no = None
        created_at_iso = created_at or self._now_iso()
        assigned_seq = self._assign_seq_no(meta, session_id, seq_no)
        role_value = role or "assistant"
        pair_key = pair_id or uuid.uuid4().hex
        turn_hash = hash_value or self._turn_hash(pair_key, role_value, text, created_at_iso)
        last_entries = meta.setdefault("last_entries", {})
        dedupe_key = f"{pair_key}:{role_value}"
        last_entry = last_entries.get(dedupe_key)
        if last_entry and last_entry.get("hash") == turn_hash:
            meta["duplicates_skipped"] = meta.get("duplicates_skipped", 0) + 1
            self._save_belief_meta(meta)
            return {
                "type": "belief",
                "id": last_entry.get("id"),
                "time": last_entry.get("time"),
                "hash": turn_hash,
                "skipped": True,
            }
        bid = uuid.uuid4().hex
        record_source = dict(source or {"kind": "live"})
        if source_episode is not None:
            record_source["episode_id"] = source_episode
        record = {
            "type": "belief",
            "schema_version": schema_version,
            "id": bid,
            "time": created_at_iso,
            "session_id": session_id,
            "pair_id": pair_key,
            "seq_no": assigned_seq,
            "role": role_value,
            "text": str(text),
            "hash": turn_hash,
            "source": record_source,
            "confidence": None if confidence is None else float(confidence),
            "citations": list(citations or []),
            "metadata": payload_meta,
        }
        combined_sources: List[str] = []
        if isinstance(sources_meta, (list, tuple, set)):
            combined_sources.extend(str(src) for src in sources_meta if src)
        combined_sources.extend(str(cite) for cite in record["citations"] if cite)
        unique_sources = [src for src in {src for src in combined_sources if src}]
        if unique_sources:
            record["sources"] = unique_sources
        if conflict_claim:
            register_conflict(bid, str(conflict_claim), evidence_for, evidence_against)
        active_segment = self._belief_active_segment(meta)
        segment_path = self._belief_segment_path(active_segment["name"])
        try:
            self._append_jsonl_safe(segment_path, json.dumps(record, ensure_ascii=False))
        except Exception as exc:
            self._log_cognitive_write_failure(
                record_type="belief",
                record_id=bid,
                path=segment_path,
                error=exc,
            )
            raise MemoryWriteError("failed to append belief record", logged=True) from exc
        active_segment["count"] += 1
        segment_created_at = self._parse_iso(active_segment.get("created_at"))
        record_created_at = self._parse_iso(created_at_iso)
        if record_created_at is not None:
            if segment_created_at is None or record_created_at < segment_created_at:
                active_segment["created_at"] = created_at_iso
        meta["total_count"] = meta.get("total_count", 0) + 1
        meta["writes"] = meta.get("writes", 0) + 1
        last_entries[dedupe_key] = {"hash": turn_hash, "id": bid, "time": created_at_iso, "seq_no": assigned_seq}
        self._rollover_if_needed(meta)
        self._save_belief_meta(meta)
        if embedding is not None:
            backend = self._ensure_vector_meta(dim=len(embedding), backend=embedding_backend)
            self._append_vector_entry(
                self._vector_name(self.FILE_BELIEF_VECTORS, backend),
                item_id=bid,
                vector=embedding,
                backend=backend,
            )
        return dict(record)

    def append_link(
        self,
        *,
        src_id: str,
        dst_id: str,
        link_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        lid = uuid.uuid4().hex
        payload = {
            "type": "link",
            "id": lid,
            "time": self._now_iso(),
            "src": str(src_id),
            "dst": str(dst_id),
            "link_type": str(link_type),
            "metadata": metadata or {},
        }
        self._append_jsonl_or_raise(
            name=self.FILE_LINKS,
            obj=payload,
            record_type="link",
        )
        return dict(payload)

    def append_constraint(
        self,
        *,
        text: str,
        scope: str = "global",
        kind: str = "forbid",
        status: str = "active",
        session_id: Optional[str] = None,
        principal: Optional[str] = None,
        supersedes_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        source_episode: Optional[str] = None,
        created_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        cleaned = (text or "").strip()
        if not cleaned:
            raise ValueError("constraint text must be non-empty")
        scope_value = (scope or "global").strip().lower()
        if scope_value not in {"global", "personal", "session"}:
            raise ValueError("constraint scope must be global, personal, or session")
        kind_value = (kind or "forbid").strip().lower()
        if kind_value not in {"forbid", "require", "caveat"}:
            raise ValueError("constraint kind must be forbid, require, or caveat")
        status_value = (status or "active").strip().lower()
        if status_value not in {"active", "disabled", "retracted"}:
            raise ValueError("constraint status must be active, disabled, or retracted")
        payload_meta = dict(metadata or {})
        record_source = {
            "kind": "constraint",
            "session_id": session_id,
            "principal": principal,
        }
        if source_episode:
            record_source["episode_id"] = source_episode
        record = {
            "type": "constraint",
            "id": uuid.uuid4().hex,
            "time": created_at or self._now_iso(),
            "scope": scope_value,
            "kind": kind_value,
            "status": status_value,
            "text": cleaned,
            "session_id": session_id,
            "principal": principal,
            "supersedes_id": supersedes_id,
            "metadata": payload_meta,
            "source": record_source,
        }
        self._append_jsonl_or_raise(
            name=self.FILE_CONSTRAINTS,
            obj=record,
            record_type="constraint",
        )
        observability.log_cognitive_memory_event(
            self._observability_root,
            {
                "kind": "constraint_write",
                "constraint_id": record["id"],
                "scope": scope_value,
                "status": status_value,
                "constraint_kind": kind_value,
            },
        )
        return dict(record)

    def list_constraints(self) -> List[Dict[str, Any]]:
        return list(self._iter_jsonl(self.FILE_CONSTRAINTS))

    @staticmethod
    def _constraint_active(record: Dict[str, Any]) -> bool:
        status = str(record.get("status") or "active").strip().lower()
        return status == "active"

    def constraints_for_request(
        self,
        *,
        session_id: Optional[str] = None,
        principal: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        records = list(self._iter_jsonl(self.FILE_CONSTRAINTS))
        superseded: set[str] = set()
        for record in records:
            sup_id = record.get("supersedes_id")
            if sup_id:
                superseded.add(str(sup_id))
        applicable: List[Dict[str, Any]] = []
        for record in records:
            record_id = str(record.get("id") or "")
            if record_id in superseded:
                continue
            if not self._constraint_active(record):
                continue
            scope_value = str(record.get("scope") or "global").strip().lower()
            if scope_value == "global":
                applicable.append(record)
                continue
            if scope_value == "session":
                record_session = record.get("session_id") or (record.get("source") or {}).get("session_id")
                if session_id and record_session == session_id:
                    applicable.append(record)
                continue
            if scope_value == "personal":
                record_principal = record.get("principal") or (record.get("source") or {}).get("principal")
                if principal and record_principal == principal:
                    applicable.append(record)
        return applicable

    # -- search/summarize --
    @staticmethod
    def _score_overlap(q_tokens: List[str], text: str) -> float:
        t_tokens = set(tokenize_text(text))
        if not t_tokens:
            return 0.0
        q = set(q_tokens)
        inter = len(q & t_tokens)
        union = len(q | t_tokens)
        return float(inter) / float(union) if union else 0.0

    @staticmethod
    def _score_query_recall(q_tokens: Sequence[str], text: str) -> float:
        q = set(q_tokens)
        if not q:
            return 0.0
        t_tokens = set(tokenize_text(text))
        if not t_tokens:
            return 0.0
        inter = len(q & t_tokens)
        return float(inter) / float(len(q)) if q else 0.0

    def search(
        self,
        query: str,
        *,
        k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        vectorizer: Any | None = None,
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        filters = filters or {}
        episode_entries: List[Dict[str, Any]] = []
        belief_entries: List[Dict[str, Any]] = []
        now = datetime.now(timezone.utc)
        _raw_half_life = getattr(self._config, "cognitive_memory_half_life_hours", None)
        # `or 12.0` here would silently override an explicit, meaningful
        # half_life=0.0 (maximal decay - clamped to a tiny positive scale
        # below, not a divide-by-zero) back to the default; only fall back
        # when the config genuinely has no value at all.
        half_life = float(_raw_half_life) if _raw_half_life is not None else 12.0
        backend_key = self._backend_key(None)
        vector_meta = self._load_vector_meta(backend_key)
        expected_dim = vector_meta.get("dim")
        try:
            expected_dim = int(expected_dim) if expected_dim is not None else None
        except (TypeError, ValueError):
            expected_dim = None
        episode_vectors = self._load_vector_map(
            self._vector_name(self.FILE_EPISODE_VECTORS, backend_key)
        )
        belief_vectors = self._load_vector_map(
            self._vector_name(self.FILE_BELIEF_VECTORS, backend_key)
        )
        q_tokens = tokenize_text(query)
        try:
            recall_weight = float(
                getattr(self._config, "cognitive_memory_query_recall_weight", 0.0) or 0.0
            )
        except Exception:
            recall_weight = 0.0
        recall_weight = max(0.0, min(1.0, recall_weight))

        def _recency_weight(record: Dict[str, Any]) -> float:
            stamp = record.get("last_seen") or record.get("time")
            dt = self._parse_iso(stamp)
            if dt is None:
                return 1.0
            age_hours = max((now - dt).total_seconds() / 3600.0, 0.0)
            if age_hours <= 0:
                return 1.0
            scale = max(half_life, 1e-3)
            return 1.0 / (1.0 + age_hours / scale)

        kind_filter = filters.get("kinds") or filters.get("kind")
        allowed_kinds: set[str] | None = None
        if kind_filter:
            if isinstance(kind_filter, str):
                allowed_kinds = {kind_filter.strip().lower()}
            elif isinstance(kind_filter, (list, tuple, set)):
                allowed_kinds = {str(value).strip().lower() for value in kind_filter if str(value).strip()}
            else:
                allowed_kinds = {str(kind_filter).strip().lower()}
            if not allowed_kinds:
                allowed_kinds = None

        def _passes(record: Dict[str, Any], *, kind: str | None = None) -> bool:
            if allowed_kinds is not None:
                if kind is None or kind.strip().lower() not in allowed_kinds:
                    return False
            if "domain" in filters and filters["domain"]:
                if record.get("domain") != filters["domain"]:
                    return False
            if "task" in filters and filters["task"]:
                if record.get("task") != filters["task"]:
                    return False
            return True

        for ep in self._iter_jsonl(self.FILE_EPISODES):
            if not _passes(ep, kind="episode"):
                continue
            text = ((ep.get("query") or "") + "\n" + (ep.get("answer") or "")).strip()
            if not text:
                continue
            episode_entries.append({"kind": "episode", "record": dict(ep), "text": text})

        for bl in self._iter_belief_records():
            text = str(bl.get("text") or "").strip()
            if not text:
                continue
            if not _passes(bl, kind="belief"):
                continue
            belief_entries.append({"kind": "belief", "record": dict(bl), "text": text})

        if not episode_entries and not belief_entries:
            return []

        scored: List[tuple[float, Dict[str, Any]]] = []
        k = max(1, int(k))
        query_vec: Optional[np.ndarray] = None
        if vectorizer is not None:
            try:
                q_mat = vectorizer.transform([query])
                if hasattr(q_mat, "toarray"):
                    q_dense = q_mat.toarray()[0]
                else:
                    q_dense = np.asarray(q_mat, dtype=float).ravel()
                if q_dense.size > 0 and (expected_dim is None or q_dense.size == expected_dim):
                    q_norm = np.linalg.norm(q_dense)
                    if q_norm > 0:
                        query_vec = q_dense / q_norm
            except Exception:
                query_vec = None

        fallback_entries: List[tuple[Dict[str, Any], Dict[str, Any]]] = []
        ann_ids: List[str] = []
        ann_sims: List[float] = []
        ann_diag: Dict[str, Any] = {"enabled": False, "reason": "not_attempted"}

        if query_vec is not None:
            if episode_entries and (allowed_kinds is None or "episode" in allowed_kinds):
                filters_active = bool(filters.get("domain") or filters.get("task"))
                pool = max(k * (6 if filters_active else 4), 40)
                pool = min(len(episode_entries), pool)
                ann_ids, ann_sims, ann_diag = self._ann_query(
                    query_vec, backend_key=backend_key, k=pool
                )
            else:
                ann_diag = {"enabled": False, "reason": "no_episode_candidates", "requested": 0, "returned": 0}

            if diagnostics is not None:
                diagnostics.update(
                    {
                        "ann_enabled": bool(ann_diag.get("enabled")),
                        "ann_backend": ann_diag.get("index_backend"),
                        "ann_returned": ann_diag.get("returned", 0),
                        "ann_requested": ann_diag.get("requested", 0),
                        "ann_index_size": ann_diag.get("index_size", 0),
                        "ann_reason": ann_diag.get("reason"),
                    }
                )

            episode_by_id = {
                str(item["record"].get("id")): item for item in episode_entries
            }
            used_episode_ids: set[str] = set()

            if ann_ids:
                for eid, sim in zip(ann_ids, ann_sims):
                    item = episode_by_id.get(str(eid))
                    if item is None:
                        continue
                    record = dict(item["record"])
                    record["kind"] = "episode"
                    raw_score = float(sim)
                    score = raw_score
                    if recall_weight > 0.0:
                        query_text = str(record.get("query") or "")
                        if query_text:
                            recall = self._score_query_recall(q_tokens, query_text)
                            if recall > 0.0:
                                score = (1.0 - recall_weight) * score + recall_weight * recall
                                record["_score_query_recall"] = recall
                                record["_score_query_recall_weight"] = recall_weight
                    if score > 0.0:
                        weight = _recency_weight(record)
                        weighted = score * weight
                        record["_score_raw"] = raw_score
                        record["_recency_weight"] = weight
                        try:
                            meta = record.get("metadata") or {}
                            scales = meta.get("hierarchy_scales") or []
                            scale_ids: list[str] = []
                            for entry in scales:
                                if isinstance(entry, dict) and entry.get("scale") == "segment":
                                    nodes = entry.get("nodes") or []
                                    for n in nodes:
                                        sid = (n or {}).get("id")
                                        if isinstance(sid, str):
                                            scale_ids.append(sid)
                            if scale_ids:
                                record["lineage"] = {"episode_id": record.get("id"), "scale_ids": scale_ids}
                        except Exception:
                            pass
                        record["_score"] = weighted
                        scored.append((weighted, record))
                    used_episode_ids.add(str(eid))
            else:
                for item in episode_entries:
                    record = dict(item["record"])
                    record["kind"] = "episode"
                    stored_vec = episode_vectors.get(record.get("id"))
                    if stored_vec is not None and stored_vec.size > 0:
                        if expected_dim is not None and stored_vec.size != expected_dim:
                            fallback_entries.append((item, record))
                            continue
                        raw_score = float(np.dot(query_vec, stored_vec))
                        score = raw_score
                        if recall_weight > 0.0:
                            query_text = str(record.get("query") or "")
                            if query_text:
                                recall = self._score_query_recall(q_tokens, query_text)
                                if recall > 0.0:
                                    score = (1.0 - recall_weight) * score + recall_weight * recall
                                    record["_score_query_recall"] = recall
                                    record["_score_query_recall_weight"] = recall_weight
                        if score > 0.0:
                            weight = _recency_weight(record)
                            weighted = score * weight
                            record["_score_raw"] = raw_score
                            record["_recency_weight"] = weight
                            try:
                                meta = record.get("metadata") or {}
                                scales = meta.get("hierarchy_scales") or []
                                scale_ids: list[str] = []
                                for entry in scales:
                                    if isinstance(entry, dict) and entry.get("scale") == "segment":
                                        nodes = entry.get("nodes") or []
                                        for n in nodes:
                                            sid = (n or {}).get("id")
                                            if isinstance(sid, str):
                                                scale_ids.append(sid)
                                if scale_ids:
                                    record["lineage"] = {"episode_id": record.get("id"), "scale_ids": scale_ids}
                            except Exception:
                                pass
                            record["_score"] = weighted
                            scored.append((weighted, record))
                            continue
                    fallback_entries.append((item, record))

            for item in belief_entries:
                record = dict(item["record"])
                record["kind"] = "belief"
                stored_vec = belief_vectors.get(record.get("id"))
                if stored_vec is not None and stored_vec.size > 0:
                    if expected_dim is not None and stored_vec.size != expected_dim:
                        fallback_entries.append((item, record))
                        continue
                    raw_score = float(np.dot(query_vec, stored_vec))
                    score = raw_score
                    if score > 0.0:
                        weight = _recency_weight(record)
                        weighted = score * weight
                        record["_score_raw"] = raw_score
                        record["_recency_weight"] = weight
                        try:
                            meta_b = record.get("metadata") or {}
                            scale_id = meta_b.get("scale_id")
                            sources = record.get("sources") or record.get("citations") or []
                            src = record.get("source") or {}
                            ep_id = src.get("episode_id")
                            lineage: Dict[str, Any] = {}
                            if scale_id:
                                lineage["scale_id"] = scale_id
                            if ep_id:
                                lineage["episode_id"] = ep_id
                            if sources:
                                lineage["sources"] = list(sources)
                            if lineage:
                                record["lineage"] = lineage
                        except Exception:
                            pass
                        record["_score"] = weighted
                        scored.append((weighted, record))
                        continue
                fallback_entries.append((item, record))

            if ann_ids and len(scored) < k:
                for item in episode_entries:
                    record = dict(item["record"])
                    record["kind"] = "episode"
                    if record.get("id") in used_episode_ids:
                        continue
                    fallback_entries.append((item, record))
        else:
            for item in episode_entries + belief_entries:
                record = dict(item["record"])
                record["kind"] = item["kind"]
                fallback_entries.append((item, record))

        if diagnostics is not None and query_vec is None:
            diagnostics.update(
                {
                    "ann_enabled": False,
                    "ann_backend": None,
                    "ann_returned": 0,
                    "ann_requested": 0,
                    "ann_index_size": 0,
                    "ann_reason": "missing_query_vector",
                }
            )

        if fallback_entries or not scored:
            q_tokens = tokenize_text(query)
            if not fallback_entries:
                fallback_entries = []
                for entry in episode_entries + belief_entries:
                    record = dict(entry["record"])
                    record["kind"] = entry["kind"]
                    fallback_entries.append((entry, record))
            for item, record in fallback_entries:
                text = item["text"]
                score = self._score_overlap(q_tokens, text)
                if score <= 0.0:
                    lower = text.lower()
                    if any(tok in lower for tok in q_tokens):
                        score = 0.05
                if score > 0.0:
                    weight = _recency_weight(record)
                    weighted = score * weight
                    record["_score_raw"] = score
                    record["_recency_weight"] = weight
                    # Attach lineage in fallback path too
                    try:
                        if record.get("kind") == "episode":
                            meta = record.get("metadata") or {}
                            scales = meta.get("hierarchy_scales") or []
                            scale_ids: list[str] = []
                            for entry in scales:
                                if isinstance(entry, dict) and entry.get("scale") == "segment":
                                    nodes = entry.get("nodes") or []
                                    for n in nodes:
                                        sid = (n or {}).get("id")
                                        if isinstance(sid, str):
                                            scale_ids.append(sid)
                            if scale_ids:
                                record["lineage"] = {"episode_id": record.get("id"), "scale_ids": scale_ids}
                        elif record.get("kind") == "belief":
                            meta_b = record.get("metadata") or {}
                            scale_id = meta_b.get("scale_id")
                            sources = record.get("sources") or record.get("citations") or []
                            src = record.get("source") or {}
                            ep_id = src.get("episode_id")
                            lineage: Dict[str, Any] = {}
                            if scale_id:
                                lineage["scale_id"] = scale_id
                            if ep_id:
                                lineage["episode_id"] = ep_id
                            if sources:
                                lineage["sources"] = list(sources)
                            if lineage:
                                record["lineage"] = lineage
                    except Exception:
                        pass
                    record["_score"] = weighted
                    scored.append((weighted, record))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [item for _, item in scored[:k]]

    def backfill_embeddings(
        self,
        *,
        vectorizer: Any,
        backend: Optional[str] = None,
        batch_size: int = 32,
        include_beliefs: bool = True,
    ) -> Dict[str, int]:
        if vectorizer is None:
            raise ValueError("vectorizer is required for backfill")
        backend_key = self._backend_key(backend)
        episode_vectors = self._load_vector_map(
            self._vector_name(self.FILE_EPISODE_VECTORS, backend_key)
        )
        belief_vectors = self._load_vector_map(
            self._vector_name(self.FILE_BELIEF_VECTORS, backend_key)
        )
        episode_targets: List[Tuple[str, str]] = []
        for record in self._iter_jsonl(self.FILE_EPISODES):
            item_id = str(record.get("id") or "")
            if not item_id or item_id in episode_vectors:
                continue
            query = str(record.get("query") or "")
            answer = str(record.get("answer") or "")
            text = f"{query}\n{answer}".strip() or query.strip()
            if not text:
                continue
            episode_targets.append((item_id, text))

        belief_targets: List[Tuple[str, str]] = []
        if include_beliefs:
            for record in self._iter_belief_records():
                item_id = str(record.get("id") or "")
                if not item_id or item_id in belief_vectors:
                    continue
                text = str(record.get("text") or "").strip()
                if not text:
                    continue
                belief_targets.append((item_id, text))

        def _vectorize(texts: List[str]) -> np.ndarray:
            matrix = vectorizer.transform(texts)
            if hasattr(matrix, "toarray"):
                arr = matrix.toarray()
            else:
                arr = np.asarray(matrix, dtype=float)
            arr = np.asarray(arr, dtype=float)
            if arr.ndim == 1:
                arr = arr.reshape(1, -1)
            return arr

        def _write_batch(
            items: List[Tuple[str, str]],
            *,
            vector_file: str,
        ) -> int:
            written = 0
            for start in range(0, len(items), max(1, batch_size)):
                batch = items[start : start + max(1, batch_size)]
                texts = [text for _, text in batch]
                vectors = _vectorize(texts)
                for (item_id, _), vec in zip(batch, vectors):
                    vec = np.asarray(vec, dtype=float).ravel()
                    if vec.size == 0:
                        continue
                    resolved_backend = self._ensure_vector_meta(
                        dim=int(vec.size), backend=backend_key
                    )
                    self._append_vector_entry(
                        vector_file,
                        item_id=item_id,
                        vector=vec.tolist(),
                        backend=resolved_backend,
                    )
                    written += 1
            return written

        episode_written = _write_batch(
            episode_targets,
            vector_file=self._vector_name(self.FILE_EPISODE_VECTORS, backend_key),
        )
        belief_written = 0
        if include_beliefs:
            belief_written = _write_batch(
                belief_targets,
                vector_file=self._vector_name(self.FILE_BELIEF_VECTORS, backend_key),
            )
        return {
            "episodes_written": episode_written,
            "episodes_total": len(episode_targets),
            "beliefs_written": belief_written,
            "beliefs_total": len(belief_targets),
            "backend": backend_key,
        }

    def cognitive_ann_candidates(
        self,
        query: str,
        *,
        vectorizer: Any | None,
        top_k: int = 0,
        weight: float = 1.0,
        floor_boost: float = 0.01,
        budget_cap: int | None = None,
    ) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Return ranked ANN candidates across persisted episodes and beliefs."""
        obs: Dict[str, Any] = {
            "enabled": bool(self._config_value("enable_cognitive_ann_bridge", False)),
            "bridge_disabled_reason": "unknown",
            "budget_exhausted": False,
            "applied": False,
        }
        if not obs["enabled"]:
            obs["bridge_disabled_reason"] = "bridge_disabled"
            return [], obs
        if vectorizer is None:
            obs["bridge_disabled_reason"] = "missing_vectorizer"
            return [], obs
        try:
            top_k = int(top_k)
        except (TypeError, ValueError):
            top_k = 0
        if top_k <= 0:
            obs["bridge_disabled_reason"] = "top_k_disabled"
            return [], obs
        requested_top_k = top_k
        cap_value: int | None = None
        if budget_cap is not None:
            try:
                cap_value = int(budget_cap)
            except (TypeError, ValueError):
                cap_value = requested_top_k
        if cap_value is not None and cap_value <= 0:
            obs["bridge_disabled_reason"] = "budget_exhausted"
            obs["budget_exhausted"] = True
            return [], obs

        backend_key = self._backend_key(None)
        vector_meta = self._load_vector_meta(backend_key)
        fingerprint = (
            getattr(vectorizer, "fingerprint_", None)
            or getattr(vectorizer, "vocabulary_", None)
            or vectorizer.__class__.__name__
        )
        meta_fingerprint = vector_meta.get("fingerprint")
        if (
            meta_fingerprint is not None
            and fingerprint is not None
            and meta_fingerprint != fingerprint
        ):
            obs["bridge_disabled_reason"] = "fingerprint_mismatch"
            return [], obs
        expected_dim = vector_meta.get("dim")
        try:
            expected_dim = int(expected_dim) if expected_dim is not None else None
        except (TypeError, ValueError):
            expected_dim = None
        episode_vectors = self._load_vector_map(
            self._vector_name(self.FILE_EPISODE_VECTORS, backend_key)
        )
        belief_vectors = self._load_vector_map(
            self._vector_name(self.FILE_BELIEF_VECTORS, backend_key)
        )
        if not episode_vectors and not belief_vectors:
            obs["bridge_disabled_reason"] = "missing_vectors"
            obs["backend"] = backend_key
            obs["vector_count"] = 0
            return [], obs

        try:
            q_mat = vectorizer.transform([query])
            if hasattr(q_mat, "toarray"):
                q_dense = q_mat.toarray()[0]
            else:
                q_dense = np.asarray(q_mat, dtype=float).ravel()
            q_dense = np.asarray(q_dense, dtype=float).ravel()
        except Exception:
            obs["bridge_disabled_reason"] = "vectorizer_error"
            return [], obs
        if q_dense.size == 0:
            obs["bridge_disabled_reason"] = "empty_query_vector"
            return [], obs
        if expected_dim is not None and q_dense.size != expected_dim:
            obs["bridge_disabled_reason"] = "dim_mismatch"
            obs["expected_dim"] = expected_dim
            obs["query_dim"] = int(q_dense.size)
            return [], obs
        q_norm = float(np.linalg.norm(q_dense))
        if q_norm <= 0.0:
            obs["bridge_disabled_reason"] = "zero_query_norm"
            return [], obs
        q_vec = q_dense / q_norm

        try:
            weight_value = float(weight)
        except (TypeError, ValueError):
            weight_value = 1.0
        weight_value = max(0.0, weight_value)
        try:
            floor_value = float(floor_boost)
        except (TypeError, ValueError):
            floor_value = 0.0
        floor_value = max(0.0, floor_value)

        ann_ids, ann_sims, ann_diag = self._ann_query(
            q_vec, backend_key=backend_key, k=requested_top_k
        )
        scored_ids: List[tuple[str, float]] = []
        ann_used = bool(ann_ids)
        if ann_ids:
            for eid, sim in zip(ann_ids, ann_sims):
                scored_ids.append((f"cmem:ep:{eid}", float(sim)))
        else:
            for eid, vec in episode_vectors.items():
                scored_ids.append((f"cmem:ep:{eid}", float(np.dot(q_vec, vec))))
        for belief_id, vec in belief_vectors.items():
            if vec.size == q_vec.size:
                scored_ids.append((f"cmem:bl:{belief_id}", float(np.dot(q_vec, vec))))

        candidates: List[Dict[str, Any]] = []
        for doc_id, similarity in scored_ids:
            if similarity <= 0.0:
                continue
            combined = similarity * weight_value + floor_value
            candidates.append(
                {
                    "doc_id": doc_id,
                    "candidate_id": doc_id,
                    "version_id": doc_id,
                    "ann_similarity": similarity,
                    "combined_score": combined,
                    "score": combined,
                    "source": "cognitive_ann",
                    "origin": "cognitive_memory",
                }
            )
        candidates.sort(
            key=lambda candidate: (
                -float(candidate["combined_score"]),
                -float(candidate["ann_similarity"]),
                str(candidate["doc_id"]),
            )
        )
        candidates = candidates[:requested_top_k]
        if cap_value is not None and cap_value >= 0:
            obs["budget_exhausted"] = len(candidates) > cap_value
            candidates = candidates[:cap_value]

        obs = {
            "enabled": True,
            "backend": backend_key,
            "index_backend": ann_diag.get("index_backend"),
            "index_size": ann_diag.get("index_size"),
            "ann_requested": ann_diag.get("requested", top_k),
            "ann_returned": ann_diag.get("returned", 0),
            "ann_reason": ann_diag.get("reason"),
            "ann_used": ann_used,
            "ann_fallback": None if ann_used else "linear",
            "bridge_disabled_reason": None if candidates else ann_diag.get("reason"),
            "top_k": requested_top_k,
            "weight": weight_value,
            "floor_boost": floor_value,
            "vector_count": len(episode_vectors) + len(belief_vectors),
            "returned": len(candidates),
            "candidates": candidates,
            "budget_exhausted": bool(obs.get("budget_exhausted", False)),
            "applied": bool(candidates),
            "vectorizer_fingerprint": fingerprint,
            "meta_fingerprint": meta_fingerprint,
        }
        return candidates, obs

    def summarize(self, window: int = 50) -> Dict[str, Any]:
        eps = list(self._iter_jsonl(self.FILE_EPISODES))
        beliefs = list(self._iter_belief_records())
        links = list(self._iter_jsonl(self.FILE_LINKS))
        constraints = list(self._iter_jsonl(self.FILE_CONSTRAINTS))
        return {
            "counts": {
                "episodes": len(eps),
                "beliefs": len(beliefs),
                "links": len(links),
                "constraints": len(constraints),
            },
            "recent": {
                "episodes": eps[-window:],
                "beliefs": beliefs[-window:],
                "links": links[-window:],
                "constraints": constraints[-window:],
            },
        }
