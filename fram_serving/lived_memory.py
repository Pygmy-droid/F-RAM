from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

import numpy as np

from fram_core.rotational_lift import LiftCapsule, recursive_lift
from fram_serving.fractal_memory import FractalGenerator, FractalSeed

LIVED_MEMORY_SCHEMA_VERSION = 1
PROJECTION_KIND = "fractal6_recursive_lift_v1"
GLOBAL_SESSION_ID = "global"


class LivedMemoryError(RuntimeError):
    """Base error for durable lived-memory operations."""


class LivedMemoryCorruptError(LivedMemoryError):
    """Raised when persisted lived-memory state fails an integrity check."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _timestamp_ms(value: str) -> int:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        parsed = datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp() * 1000)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _vector_blob(values: Sequence[float] | np.ndarray) -> bytes:
    array = np.asarray(values, dtype="<f4").ravel()
    if array.size == 0 or not np.isfinite(array).all():
        raise ValueError("memory vectors must be finite and non-empty")
    return array.tobytes(order="C")


def _vector_from_blob(value: bytes, expected_dim: int) -> np.ndarray:
    array = np.frombuffer(value, dtype="<f4").astype(float, copy=True)
    if array.size != expected_dim:
        raise LivedMemoryCorruptError(
            f"stored vector has dimension {array.size}, expected {expected_dim}"
        )
    if not np.isfinite(array).all():
        raise LivedMemoryCorruptError("stored vector contains non-finite values")
    return array


def _cosine(left: np.ndarray, right: np.ndarray) -> float:
    denom = float(np.linalg.norm(left) * np.linalg.norm(right))
    if denom <= 1e-12:
        return 0.0
    return float(np.clip(np.dot(left, right) / denom, -1.0, 1.0))


def _capsule_payload(capsules: Iterable[LiftCapsule]) -> List[Dict[str, Any]]:
    payload: List[Dict[str, Any]] = []
    for capsule in capsules:
        payload.append(
            {
                "previous_dim": int(capsule.previous_dim),
                "drop_axis": int(capsule.drop_axis),
                "rotation_plane": [int(v) for v in capsule.rotation_plane],
                "rotation_theta": float(capsule.rotation_theta),
                "rotations": [
                    {"plane": [int(v) for v in plane], "theta": float(theta)}
                    for plane, theta in capsule.rotation_sequence
                ],
                "window_rule": capsule.window_rule,
                "residual_mode": capsule.residual_mode,
                "parent_id": capsule.parent_id,
            }
        )
    return payload


class LivedMemoryStore:
    """Transactional memory for lived query/response trajectories.

    Each event keeps the actual text, source identifiers, embedding, a stable
    shared six-dimensional fractal projection, its exact recursive lift into a
    higher carrier, and an event-specific lifted fractal path. SQLite provides
    process-safe transactions and restart persistence; a digest chain preserves
    the order in which a session was lived.

    The higher projection is a derived memory view. It does not replace the
    source event or imply identity, consciousness, or authorship.
    """

    def __init__(
        self,
        root: Path,
        *,
        target_dim: int = 12,
        fractal_nodes: int = 64,
        scan_limit: int = 5000,
        state_decay: float = 0.82,
        busy_timeout_seconds: float = 5.0,
    ) -> None:
        if int(target_dim) < 6:
            raise ValueError("target_dim must be at least 6")
        if int(fractal_nodes) < 2:
            raise ValueError("fractal_nodes must be at least 2")
        if int(scan_limit) < 1:
            raise ValueError("scan_limit must be positive")
        if not 0.0 <= float(state_decay) < 1.0:
            raise ValueError("state_decay must be in [0, 1)")
        if float(busy_timeout_seconds) <= 0.0:
            raise ValueError("busy_timeout_seconds must be positive")

        self.root = Path(root)
        self.path = self.root / "lived_memory.sqlite3"
        self.target_dim = int(target_dim)
        self.fractal_nodes = int(fractal_nodes)
        self.scan_limit = int(scan_limit)
        self.state_decay = float(state_decay)
        self.busy_timeout_seconds = float(busy_timeout_seconds)
        self._schema_lock = threading.RLock()
        self._schema_ready = False

    @staticmethod
    def _session_id(value: str | None) -> str:
        normalized = str(value or "").strip()
        return normalized or GLOBAL_SESSION_ID

    def _connect(self) -> sqlite3.Connection:
        self.root.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(
            self.path,
            timeout=self.busy_timeout_seconds,
            isolation_level=None,
        )
        try:
            connection.row_factory = sqlite3.Row
            connection.execute(
                f"PRAGMA busy_timeout={int(self.busy_timeout_seconds * 1000)}"
            )
            connection.execute("PRAGMA foreign_keys=ON")
            if not self._schema_ready:
                with self._schema_lock:
                    if not self._schema_ready:
                        connection.execute("PRAGMA journal_mode=WAL")
                        self._ensure_schema(connection)
            connection.execute("PRAGMA synchronous=FULL")
        except Exception:
            connection.close()
            raise
        return connection

    def _ensure_schema(self, connection: sqlite3.Connection) -> None:
        if self._schema_ready:
            return
        with self._schema_lock:
            if self._schema_ready:
                return
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS lived_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS lived_events (
                    event_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    session_seq INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    parent_event_id TEXT,
                    episode_id TEXT,
                    trace_id TEXT,
                    domain TEXT,
                    task TEXT,
                    query_text TEXT NOT NULL,
                    answer_text TEXT NOT NULL,
                    citations_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    embedding_backend TEXT,
                    embedding_dim INTEGER NOT NULL,
                    embedding BLOB NOT NULL,
                    projection_kind TEXT NOT NULL,
                    projection_dim INTEGER NOT NULL,
                    base_projection BLOB NOT NULL,
                    higher_projection BLOB NOT NULL,
                    state_projection BLOB NOT NULL,
                    fractal_nodes INTEGER NOT NULL,
                    fractal_path BLOB NOT NULL,
                    lift_capsules_json TEXT NOT NULL,
                    previous_digest TEXT,
                    event_digest TEXT NOT NULL,
                    state_digest TEXT NOT NULL,
                    UNIQUE(session_id, session_seq)
                );

                CREATE INDEX IF NOT EXISTS lived_events_session_idx
                    ON lived_events(session_id, session_seq DESC);
                CREATE INDEX IF NOT EXISTS lived_events_created_idx
                    ON lived_events(created_at DESC);
                CREATE INDEX IF NOT EXISTS lived_events_episode_idx
                    ON lived_events(episode_id);

                CREATE TABLE IF NOT EXISTS lived_session_state (
                    session_id TEXT PRIMARY KEY,
                    last_event_id TEXT NOT NULL,
                    event_count INTEGER NOT NULL,
                    projection_dim INTEGER NOT NULL,
                    state_vector BLOB NOT NULL,
                    state_digest TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(last_event_id) REFERENCES lived_events(event_id)
                );
                """
            )
            existing_meta = {
                str(row["key"]): str(row["value"])
                for row in connection.execute(
                    "SELECT key, value FROM lived_meta"
                ).fetchall()
            }
            expected_meta = {
                "schema_version": str(LIVED_MEMORY_SCHEMA_VERSION),
                "projection_kind": PROJECTION_KIND,
                "projection_dim": str(self.target_dim),
                "fractal_nodes": str(self.fractal_nodes),
                "state_decay": format(self.state_decay, ".17g"),
            }
            for key, expected in expected_meta.items():
                observed = existing_meta.get(key)
                if observed is not None and observed != expected:
                    raise LivedMemoryCorruptError(
                        f"stored {key}={observed!r} does not match "
                        f"configured value {expected!r}; explicit migration required"
                    )

            shape = connection.execute(
                "SELECT COUNT(*) AS event_count, "
                "MIN(projection_dim) AS min_projection_dim, "
                "MAX(projection_dim) AS max_projection_dim, "
                "MIN(fractal_nodes) AS min_fractal_nodes, "
                "MAX(fractal_nodes) AS max_fractal_nodes "
                "FROM lived_events"
            ).fetchone()
            if shape is not None and int(shape["event_count"]) > 0:
                observed_dims = {
                    int(shape["min_projection_dim"]),
                    int(shape["max_projection_dim"]),
                }
                observed_nodes = {
                    int(shape["min_fractal_nodes"]),
                    int(shape["max_fractal_nodes"]),
                }
                if observed_dims != {self.target_dim}:
                    raise LivedMemoryCorruptError(
                        "stored projection dimensions do not match the configured "
                        "carrier; explicit migration required"
                    )
                if observed_nodes != {self.fractal_nodes}:
                    raise LivedMemoryCorruptError(
                        "stored fractal-node counts do not match configuration; "
                        "explicit migration required"
                    )

            for key, expected in expected_meta.items():
                if key not in existing_meta:
                    connection.execute(
                        "INSERT INTO lived_meta(key, value) VALUES(?, ?)",
                        (key, expected),
                    )
            self._schema_ready = True

    def _project_event(
        self,
        *,
        event_id: str,
        created_at: str,
        embedding: np.ndarray,
    ) -> Dict[str, Any]:
        generator = FractalGenerator(
            int(embedding.size),
            n_nodes=self.fractal_nodes,
        )
        base_projection = np.asarray(generator.project(embedding), dtype=float)
        higher, capsules = recursive_lift(
            base_projection[None, :],
            target_dim=self.target_dim,
            window_rule="whole_lived_event",
            residual_mode="exact",
        )
        seed = FractalSeed(
            episode_id=event_id,
            timestamp_ms=_timestamp_ms(created_at),
            embedding=embedding,
            metadata={"projection_kind": PROJECTION_KIND},
        )
        trace = generator.generate(seed)
        path6 = generator.retrace(trace)
        higher_path, path_capsules = recursive_lift(
            path6,
            target_dim=self.target_dim,
            window_rule="whole_fractal_path",
            residual_mode="exact",
        )
        return {
            "base": base_projection,
            "higher": higher[0],
            "path": higher_path,
            "capsules": _capsule_payload(capsules),
            "path_capsules": _capsule_payload(path_capsules),
            "trace_provenance": trace.provenance,
        }

    @staticmethod
    def _event_digest_payload(
        *,
        event_id: str,
        session_id: str,
        session_seq: int,
        created_at: str,
        parent_event_id: str | None,
        episode_id: str | None,
        trace_id: str | None,
        domain: str | None,
        task: str | None,
        query_text: str,
        answer_text: str,
        citations_json: str,
        metadata_json: str,
        embedding_backend: str | None,
        embedding_dim: int,
        projection_dim: int,
        fractal_nodes: int,
        previous_digest: str | None,
        embedding_blob: bytes,
        base_blob: bytes,
        higher_blob: bytes,
        state_blob: bytes,
        path_blob: bytes,
        capsules_json: str,
    ) -> Dict[str, Any]:
        return {
            "event_id": event_id,
            "session_id": session_id,
            "session_seq": session_seq,
            "created_at": created_at,
            "parent_event_id": parent_event_id,
            "episode_id": episode_id,
            "trace_id": trace_id,
            "domain": domain,
            "task": task,
            "query_text": query_text,
            "answer_text": answer_text,
            "citations_json": citations_json,
            "metadata_json": metadata_json,
            "embedding_backend": embedding_backend,
            "embedding_dim": embedding_dim,
            "projection_kind": PROJECTION_KIND,
            "projection_dim": projection_dim,
            "fractal_nodes": fractal_nodes,
            "previous_digest": previous_digest,
            "embedding_sha256": _sha256_bytes(embedding_blob),
            "base_projection_sha256": _sha256_bytes(base_blob),
            "higher_projection_sha256": _sha256_bytes(higher_blob),
            "state_projection_sha256": _sha256_bytes(state_blob),
            "fractal_path_sha256": _sha256_bytes(path_blob),
            "lift_capsules_json": capsules_json,
        }

    def append_experience(
        self,
        *,
        query: str,
        answer: str,
        embedding: Sequence[float],
        session_id: str | None = None,
        episode_id: str | None = None,
        trace_id: str | None = None,
        domain: str | None = None,
        task: str | None = None,
        citations: Sequence[str] | None = None,
        metadata: Dict[str, Any] | None = None,
        embedding_backend: str | None = None,
        created_at: str | None = None,
        event_id: str | None = None,
    ) -> Dict[str, Any]:
        vector = np.asarray(embedding, dtype=float).ravel()
        if vector.size == 0 or not np.isfinite(vector).all():
            raise ValueError("embedding must be finite and non-empty")
        event_id = str(event_id or uuid.uuid4().hex)
        created_at = str(created_at or _utc_now())
        normalized_session = self._session_id(session_id)
        projected = self._project_event(
            event_id=event_id,
            created_at=created_at,
            embedding=vector,
        )

        embedding_blob = _vector_blob(vector)
        base_blob = _vector_blob(projected["base"])
        higher = np.asarray(projected["higher"], dtype=float)
        higher_blob = _vector_blob(higher)
        path_blob = _vector_blob(np.asarray(projected["path"], dtype=float).ravel())
        citations_json = _canonical_json([str(value) for value in citations or []])
        metadata_payload = dict(metadata or {})
        metadata_payload.update(
            {
                "fractal_trace_provenance": projected["trace_provenance"],
                "path_lift_capsules": projected["path_capsules"],
            }
        )
        metadata_json = _canonical_json(metadata_payload)
        capsules_json = _canonical_json(projected["capsules"])

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                previous = connection.execute(
                    "SELECT last_event_id, event_count, projection_dim, state_vector, "
                    "state_digest FROM lived_session_state WHERE session_id=?",
                    (normalized_session,),
                ).fetchone()
                if previous is None:
                    parent_event_id = None
                    previous_digest = None
                    session_seq = 1
                    state = higher
                else:
                    parent_event_id = str(previous["last_event_id"])
                    previous_digest = str(previous["state_digest"])
                    session_seq = int(previous["event_count"]) + 1
                    previous_dim = int(previous["projection_dim"])
                    previous_state = _vector_from_blob(
                        previous["state_vector"], previous_dim
                    )
                    if previous_dim != self.target_dim:
                        raise LivedMemoryCorruptError(
                            "session state projection dimension changed "
                            "without migration"
                        )
                    state = (
                        self.state_decay * previous_state
                        + (1.0 - self.state_decay) * higher
                    )

                state_blob = _vector_blob(state)
                digest_payload = self._event_digest_payload(
                    event_id=event_id,
                    session_id=normalized_session,
                    session_seq=session_seq,
                    created_at=created_at,
                    parent_event_id=parent_event_id,
                    episode_id=episode_id,
                    trace_id=trace_id,
                    domain=domain,
                    task=task,
                    query_text=str(query),
                    answer_text=str(answer),
                    citations_json=citations_json,
                    metadata_json=metadata_json,
                    embedding_backend=embedding_backend,
                    embedding_dim=int(vector.size),
                    projection_dim=self.target_dim,
                    fractal_nodes=self.fractal_nodes,
                    previous_digest=previous_digest,
                    embedding_blob=embedding_blob,
                    base_blob=base_blob,
                    higher_blob=higher_blob,
                    state_blob=state_blob,
                    path_blob=path_blob,
                    capsules_json=capsules_json,
                )
                event_digest = _sha256_bytes(
                    _canonical_json(digest_payload).encode("utf-8")
                )
                state_digest = _sha256_bytes(
                    f"{event_digest}:{_sha256_bytes(state_blob)}".encode("utf-8")
                )

                connection.execute(
                    """
                    INSERT INTO lived_events(
                        event_id, session_id, session_seq, created_at,
                        parent_event_id, episode_id, trace_id, domain, task,
                        query_text, answer_text, citations_json, metadata_json,
                        embedding_backend, embedding_dim, embedding,
                        projection_kind, projection_dim, base_projection,
                        higher_projection, state_projection, fractal_nodes,
                        fractal_path, lift_capsules_json, previous_digest,
                        event_digest, state_digest
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        event_id,
                        normalized_session,
                        session_seq,
                        created_at,
                        parent_event_id,
                        episode_id,
                        trace_id,
                        domain,
                        task,
                        str(query),
                        str(answer),
                        citations_json,
                        metadata_json,
                        embedding_backend,
                        int(vector.size),
                        embedding_blob,
                        PROJECTION_KIND,
                        self.target_dim,
                        base_blob,
                        higher_blob,
                        state_blob,
                        self.fractal_nodes,
                        path_blob,
                        capsules_json,
                        previous_digest,
                        event_digest,
                        state_digest,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO lived_session_state(
                        session_id, last_event_id, event_count, projection_dim,
                        state_vector, state_digest, updated_at
                    ) VALUES(?,?,?,?,?,?,?)
                    ON CONFLICT(session_id) DO UPDATE SET
                        last_event_id=excluded.last_event_id,
                        event_count=excluded.event_count,
                        projection_dim=excluded.projection_dim,
                        state_vector=excluded.state_vector,
                        state_digest=excluded.state_digest,
                        updated_at=excluded.updated_at
                    """,
                    (
                        normalized_session,
                        event_id,
                        session_seq,
                        self.target_dim,
                        state_blob,
                        state_digest,
                        created_at,
                    ),
                )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise

        return {
            "event_id": event_id,
            "session_id": normalized_session,
            "session_seq": session_seq,
            "parent_event_id": parent_event_id,
            "episode_id": episode_id,
            "trace_id": trace_id,
            "created_at": created_at,
            "projection_kind": PROJECTION_KIND,
            "base_dim": 6,
            "projection_dim": self.target_dim,
            "fractal_nodes": self.fractal_nodes,
            "event_digest": event_digest,
            "state_digest": state_digest,
        }

    def _query_projection(self, embedding: Sequence[float]) -> np.ndarray:
        vector = np.asarray(embedding, dtype=float).ravel()
        if vector.size == 0 or not np.isfinite(vector).all():
            raise ValueError("embedding must be finite and non-empty")
        generator = FractalGenerator(vector.size, n_nodes=self.fractal_nodes)
        base = generator.project(vector)
        higher, _ = recursive_lift(
            np.asarray(base, dtype=float)[None, :],
            target_dim=self.target_dim,
            window_rule="whole_recall_query",
            residual_mode="exact",
        )
        return higher[0]

    def contains_event(self, event_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM lived_events WHERE event_id=? LIMIT 1",
                (str(event_id),),
            ).fetchone()
        return row is not None

    # Below this cosine the hashing embedding is treated as carrying no lexical
    # evidence. Measured 2026-11-01 on the 899-event store: genuine word matches
    # on long events score 0.05 to 0.25; unrelated events sit at 0.00 to 0.02.
    EMBEDDING_FLOOR = 0.02

    def search(
        self,
        embedding: Sequence[float],
        *,
        k: int = 4,
        session_id: str | None = None,
        scan_limit: int | None = None,
        collapse_duplicates: bool = True,
        exclude_session_prefixes: Sequence[str] | None = None,
        embedding_floor: float | None = None,
    ) -> List[Dict[str, Any]]:
        """Rank lived events against a query embedding.

        Routing rule (WB-0031, Rick 2026-11-01: "keep the original path and the
        shortcut, route to both from the endpoints"): the embedding is the
        original path, the 12-D projection/state is the shortcut. When any
        candidate carries lexical evidence (embedding cosine above
        ``embedding_floor``), the geometry terms are weighted by each
        candidate's evidence relative to the strongest, so the shortcut can
        only order among word matches, never outvote them. When no candidate
        carries evidence, geometry decides, exactly as before.

        ``collapse_duplicates`` folds events with identical query and answer
        text into one row carrying ``duplicates`` and ``duplicate_event_ids``.
        Nothing is removed from the store; the coil is reported as one node.
        ``exclude_session_prefixes`` drops sessions by prefix (``"seed:"``)
        from this read only.
        """
        query_embedding = np.asarray(embedding, dtype=float).ravel()
        query_projection = self._query_projection(query_embedding)
        cap = max(1, min(int(scan_limit or self.scan_limit), self.scan_limit))
        floor = float(self.EMBEDDING_FLOOR if embedding_floor is None else embedding_floor)
        prefixes = tuple(str(p) for p in (exclude_session_prefixes or ()) if p)
        params: List[Any] = []
        where = ""
        if session_id is not None:
            where = "WHERE session_id=?"
            params.append(self._session_id(session_id))
        params.append(cap)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT event_id, session_id, session_seq, created_at,
                       parent_event_id, episode_id, trace_id, domain, task,
                       query_text, answer_text, citations_json, metadata_json,
                       embedding_dim, embedding, projection_dim,
                       higher_projection, state_projection,
                       event_digest, state_digest
                FROM lived_events
                {where}
                ORDER BY created_at DESC, session_seq DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()

        measured: List[tuple[Any, float, float, float | None]] = []
        for row in rows:
            dim = int(row["projection_dim"])
            if dim != self.target_dim:
                continue
            if prefixes and str(row["session_id"]).startswith(prefixes):
                continue
            event_projection = _vector_from_blob(row["higher_projection"], dim)
            state_projection = _vector_from_blob(row["state_projection"], dim)
            stored_embedding = _vector_from_blob(
                row["embedding"], int(row["embedding_dim"])
            )
            event_similarity = _cosine(query_projection, event_projection)
            state_similarity = _cosine(query_projection, state_projection)
            if stored_embedding.size == query_embedding.size:
                embedding_similarity: float | None = _cosine(
                    query_embedding, stored_embedding
                )
            else:
                embedding_similarity = None
            measured.append(
                (row, event_similarity, state_similarity, embedding_similarity)
            )

        evidence = [e for (_, _, _, e) in measured if e is not None]
        max_evidence = max(evidence) if evidence else None
        lexical_mode = max_evidence is not None and max_evidence > floor

        scored: List[Dict[str, Any]] = []
        for row, event_similarity, state_similarity, embedding_similarity in measured:
            dim = int(row["projection_dim"])
            if embedding_similarity is None:
                gate = 1.0
                combined = 0.75 * event_similarity + 0.25 * state_similarity
            else:
                if lexical_mode:
                    span = float(max_evidence) - floor
                    gate = float(
                        np.clip((embedding_similarity - floor) / span, 0.0, 1.0)
                    ) if span > 1e-12 else 1.0
                else:
                    gate = 1.0
                combined = 0.70 * embedding_similarity + gate * (
                    0.20 * event_similarity + 0.10 * state_similarity
                )
            score = 0.5 * (combined + 1.0)
            scored.append(
                {
                    "kind": "lived",
                    "id": str(row["event_id"]),
                    "event_id": str(row["event_id"]),
                    "episode_id": row["episode_id"],
                    "trace_id": row["trace_id"],
                    "session_id": str(row["session_id"]),
                    "session_seq": int(row["session_seq"]),
                    "parent_event_id": row["parent_event_id"],
                    "time": str(row["created_at"]),
                    "last_seen": str(row["created_at"]),
                    "domain": row["domain"],
                    "task": row["task"],
                    "query": str(row["query_text"]),
                    "answer": str(row["answer_text"]),
                    "citations": json.loads(row["citations_json"]),
                    "metadata": json.loads(row["metadata_json"]),
                    "projection_kind": PROJECTION_KIND,
                    "projection_dim": dim,
                    "embedding_similarity": embedding_similarity,
                    "projection_similarity": event_similarity,
                    "state_similarity": state_similarity,
                    "geometry_gate": gate,
                    "lexical_mode": bool(lexical_mode),
                    "duplicates": 0,
                    "duplicate_event_ids": [],
                    "_score_raw": combined,
                    "_score": score,
                    "event_digest": str(row["event_digest"]),
                    "state_digest": str(row["state_digest"]),
                    "lineage": {
                        "parent_event_id": row["parent_event_id"],
                        "session_id": str(row["session_id"]),
                        "session_seq": int(row["session_seq"]),
                    },
                }
            )
        scored.sort(
            key=lambda item: (float(item["_score"]), str(item["time"])),
            reverse=True,
        )
        if collapse_duplicates:
            folded: List[Dict[str, Any]] = []
            seen: Dict[str, Dict[str, Any]] = {}
            for item in scored:
                key = hashlib.sha256(
                    f"{item['query']}\n{item['answer']}".encode("utf-8")
                ).hexdigest()
                kept = seen.get(key)
                if kept is None:
                    seen[key] = item
                    folded.append(item)
                    continue
                kept["duplicates"] = int(kept["duplicates"]) + 1
                if len(kept["duplicate_event_ids"]) < 8:
                    kept["duplicate_event_ids"].append(item["event_id"])
            scored = folded
        return scored[: max(1, int(k))]

    def session_state(self, session_id: str | None = None) -> Dict[str, Any] | None:
        normalized = self._session_id(session_id)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT session_id, last_event_id, event_count, projection_dim, "
                "state_vector, state_digest, updated_at FROM lived_session_state "
                "WHERE session_id=?",
                (normalized,),
            ).fetchone()
        if row is None:
            return None
        state = _vector_from_blob(row["state_vector"], int(row["projection_dim"]))
        return {
            "session_id": str(row["session_id"]),
            "last_event_id": str(row["last_event_id"]),
            "event_count": int(row["event_count"]),
            "projection_kind": PROJECTION_KIND,
            "projection_dim": int(row["projection_dim"]),
            "state_vector": [float(value) for value in state],
            "state_digest": str(row["state_digest"]),
            "updated_at": str(row["updated_at"]),
        }

    def status(self) -> Dict[str, Any]:
        with self._connect() as connection:
            event_count = int(
                connection.execute("SELECT COUNT(*) FROM lived_events").fetchone()[0]
            )
            session_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM lived_session_state"
                ).fetchone()[0]
            )
            latest = connection.execute(
                "SELECT event_id, session_id, created_at, event_digest "
                "FROM lived_events ORDER BY created_at DESC, session_seq DESC LIMIT 1"
            ).fetchone()
        return {
            "schema_version": LIVED_MEMORY_SCHEMA_VERSION,
            "projection_kind": PROJECTION_KIND,
            "projection_dim": self.target_dim,
            "fractal_nodes_per_event": self.fractal_nodes,
            "event_count": event_count,
            "session_count": session_count,
            "preserves_source_text": True,
            "restart_persistent": True,
            "database": str(self.path),
            "latest": dict(latest) if latest is not None else None,
        }

    def verify(self) -> Dict[str, Any]:
        errors: List[Dict[str, Any]] = []
        sessions: Dict[str, Dict[str, Any]] = {}
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM lived_events ORDER BY session_id, session_seq"
            ).fetchall()
            states = {
                str(row["session_id"]): row
                for row in connection.execute(
                    "SELECT * FROM lived_session_state"
                ).fetchall()
            }

        for row in rows:
            event_id = str(row["event_id"])
            session_id = str(row["session_id"])
            state = sessions.setdefault(
                session_id,
                {"last_event_id": None, "state_digest": None, "event_count": 0},
            )
            try:
                dim = int(row["projection_dim"])
                _vector_from_blob(row["embedding"], int(row["embedding_dim"]))
                _vector_from_blob(row["base_projection"], 6)
                _vector_from_blob(row["higher_projection"], dim)
                _vector_from_blob(row["state_projection"], dim)
                path_values = np.frombuffer(row["fractal_path"], dtype="<f4")
                expected_path = int(row["fractal_nodes"]) * dim
                if (
                    path_values.size != expected_path
                    or not np.isfinite(path_values).all()
                ):
                    raise LivedMemoryCorruptError(
                        f"fractal path has {path_values.size} values, "
                        f"expected {expected_path}"
                    )
                if row["parent_event_id"] != state["last_event_id"]:
                    raise LivedMemoryCorruptError(
                        "parent event does not match session order"
                    )
                if row["previous_digest"] != state["state_digest"]:
                    raise LivedMemoryCorruptError(
                        "previous digest does not match session chain"
                    )
                digest_payload = self._event_digest_payload(
                    event_id=event_id,
                    session_id=session_id,
                    session_seq=int(row["session_seq"]),
                    created_at=str(row["created_at"]),
                    parent_event_id=row["parent_event_id"],
                    episode_id=row["episode_id"],
                    trace_id=row["trace_id"],
                    domain=row["domain"],
                    task=row["task"],
                    query_text=str(row["query_text"]),
                    answer_text=str(row["answer_text"]),
                    citations_json=str(row["citations_json"]),
                    metadata_json=str(row["metadata_json"]),
                    embedding_backend=row["embedding_backend"],
                    embedding_dim=int(row["embedding_dim"]),
                    projection_dim=dim,
                    fractal_nodes=int(row["fractal_nodes"]),
                    previous_digest=row["previous_digest"],
                    embedding_blob=row["embedding"],
                    base_blob=row["base_projection"],
                    higher_blob=row["higher_projection"],
                    state_blob=row["state_projection"],
                    path_blob=row["fractal_path"],
                    capsules_json=str(row["lift_capsules_json"]),
                )
                event_digest = _sha256_bytes(
                    _canonical_json(digest_payload).encode("utf-8")
                )
                if event_digest != row["event_digest"]:
                    raise LivedMemoryCorruptError("event digest mismatch")
                state_digest = _sha256_bytes(
                    f"{event_digest}:{_sha256_bytes(row['state_projection'])}".encode(
                        "utf-8"
                    )
                )
                if state_digest != row["state_digest"]:
                    raise LivedMemoryCorruptError("state digest mismatch")
            except Exception as exc:
                errors.append(
                    {"event_id": event_id, "session_id": session_id, "error": str(exc)}
                )
                continue
            state["last_event_id"] = event_id
            state["state_digest"] = str(row["state_digest"])
            state["event_count"] = int(state["event_count"]) + 1

        for session_id, observed in sessions.items():
            persisted = states.get(session_id)
            if persisted is None:
                errors.append(
                    {"session_id": session_id, "error": "missing session state"}
                )
                continue
            if (
                persisted["last_event_id"] != observed["last_event_id"]
                or persisted["state_digest"] != observed["state_digest"]
                or int(persisted["event_count"]) != int(observed["event_count"])
            ):
                errors.append(
                    {"session_id": session_id, "error": "session head mismatch"}
                )

        for session_id in states:
            if session_id not in sessions:
                errors.append(
                    {"session_id": session_id, "error": "orphan session state"}
                )

        return {
            "valid": not errors,
            "schema_version": LIVED_MEMORY_SCHEMA_VERSION,
            "projection_kind": PROJECTION_KIND,
            "event_count": len(rows),
            "session_count": len(sessions),
            "errors": errors,
        }
