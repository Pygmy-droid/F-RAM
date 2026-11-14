"""Opt-in SQLite memory for observed runtime activity and validated interpretations."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS activity_execution (
    id TEXT PRIMARY KEY, provenance TEXT NOT NULL, digest TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS activity_event (
    execution TEXT NOT NULL REFERENCES activity_execution(id),
    ordinal INTEGER NOT NULL,
    logical_time INTEGER NOT NULL,
    body TEXT NOT NULL,
    digest TEXT NOT NULL,
    PRIMARY KEY (execution, ordinal)
);
CREATE INDEX IF NOT EXISTS activity_time
ON activity_event(execution, logical_time, ordinal);
CREATE TABLE IF NOT EXISTS observed_dependency (
    execution TEXT NOT NULL,
    parent INTEGER NOT NULL,
    child INTEGER NOT NULL,
    PRIMARY KEY (execution, parent, child),
    FOREIGN KEY (execution, parent) REFERENCES activity_event(execution, ordinal),
    FOREIGN KEY (execution, child) REFERENCES activity_event(execution, ordinal)
);
CREATE INDEX IF NOT EXISTS dependency_child
ON observed_dependency(execution, child, parent);
CREATE TABLE IF NOT EXISTS interpretation_history (
    relation TEXT NOT NULL,
    version INTEGER NOT NULL,
    active INTEGER,
    body TEXT NOT NULL,
    digest TEXT NOT NULL,
    PRIMARY KEY (relation, version)
);
"""

_TABLES = (
    "activity_execution",
    "activity_event",
    "observed_dependency",
    "interpretation_history",
)


class ActivityIntegrityError(ValueError):
    """Stored evidence, index, or version history is inconsistent."""


def _json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _name(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("expected a nonempty identifier")
    return value


def _nonnegative(value: int) -> int:
    if type(value) is not int or not 0 <= value < 2**63:
        raise ValueError("expected a nonnegative SQLite integer")
    return value


@dataclass(frozen=True)
class EvidenceRef:
    execution: str
    ordinal: int
    digest: str


@dataclass(frozen=True)
class Validation:
    """A trusted application verifier's verdict, not an observation."""

    validator: str
    accepted: bool
    detail: str


@dataclass(frozen=True)
class Inference:
    status: str
    version: int | None = None
    value: Any = None
    reason: str | None = None


Verifier = Callable[[dict[str, Any], tuple[dict[str, Any], ...]], Validation]


class ActivityMemory:
    """Explicitly opened by an instrumented runtime, outside query serving."""

    def __init__(self, storage_root: Path | str):
        root = Path(storage_root) / "memory" / "activity"
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / "activity.sqlite3"
        with self._connect() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, SCHEMA_VERSION):
                raise ActivityIntegrityError(f"unsupported schema version {version}")
            db.execute("PRAGMA journal_mode=WAL")
            triggers = "".join(
                f"CREATE TRIGGER IF NOT EXISTS immutable_{table}_{op.lower()} "
                f"BEFORE {op} ON {table} BEGIN SELECT RAISE(ABORT, 'append only'); END;"
                for table in _TABLES
                for op in ("UPDATE", "DELETE")
            )
            db.executescript(
                "BEGIN IMMEDIATE;"
                + _SCHEMA
                + triggers
                + f"PRAGMA user_version={SCHEMA_VERSION}; COMMIT;"
            )

    @contextmanager
    def _connect(self, *, write: bool = False) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        try:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            if write:
                db.execute("BEGIN IMMEDIATE")
            try:
                yield db
            except BaseException:
                if db.in_transaction:
                    db.rollback()
                raise
            else:
                if db.in_transaction:
                    db.commit()
        finally:
            db.close()

    def start(self, execution: str, provenance: Mapping[str, Any]) -> RuntimeRecorder:
        """Register stable run identity and provenance before observing events."""
        execution = _name(execution)
        body = _json(dict(provenance))
        digest = _digest([execution, json.loads(body)])
        with self._connect(write=True) as db:
            row = db.execute(
                "SELECT provenance, digest FROM activity_execution WHERE id=?",
                (execution,),
            ).fetchone()
            if row is None:
                db.execute(
                    "INSERT INTO activity_execution VALUES (?, ?, ?)",
                    (execution, body, digest),
                )
            elif tuple(row) != (body, digest):
                raise ValueError("execution identity already has different provenance")
        return RuntimeRecorder(self, execution)

    def _append(
        self,
        execution: str,
        ordinal: int,
        logical_time: int,
        kind: str,
        source: str,
        destination: str,
        payload: bytes,
        observed_parents: Sequence[int],
        unresolved_links: Sequence[str],
    ) -> EvidenceRef:
        _nonnegative(ordinal)
        _nonnegative(logical_time)
        if not isinstance(payload, bytes):
            raise TypeError("measured payload must be bytes")
        parents = [_nonnegative(parent) for parent in observed_parents]
        if parents != sorted(set(parents)) or any(
            parent >= ordinal for parent in parents
        ):
            raise ValueError(
                "observed parents must be unique increasing earlier ordinals"
            )
        body = {
            "execution": execution,
            "ordinal": ordinal,
            "logical_time": logical_time,
            "kind": _name(kind),
            "source": _name(source),
            "destination": _name(destination),
            "payload_hex": payload.hex(),
            "observed_parents": parents,
            "unresolved_links": [_name(link) for link in unresolved_links],
        }
        encoded = _json(body)
        with self._connect(write=True) as db:
            run = db.execute(
                "SELECT digest FROM activity_execution WHERE id=?", (execution,)
            ).fetchone()
            if run is None:
                raise ValueError("unknown execution")
            existing = db.execute(
                "SELECT body, digest FROM activity_event "
                "WHERE execution=? AND ordinal=?",
                (execution, ordinal),
            ).fetchone()
            if existing is not None:
                if existing["body"] != encoded:
                    raise ValueError("conflicting event retry")
                return EvidenceRef(execution, ordinal, existing["digest"])
            tail = db.execute(
                "SELECT ordinal, logical_time, digest FROM activity_event "
                "WHERE execution=? ORDER BY ordinal DESC LIMIT 1",
                (execution,),
            ).fetchone()
            if ordinal != (0 if tail is None else tail["ordinal"] + 1):
                raise ValueError("ordinals must be contiguous within an execution")
            if tail is not None and logical_time < tail["logical_time"]:
                raise ValueError("logical time cannot move backward")
            previous = tail["digest"] if tail is not None else run["digest"]
            digest = _digest([previous, body])
            db.execute(
                "INSERT INTO activity_event VALUES (?, ?, ?, ?, ?)",
                (execution, ordinal, logical_time, encoded, digest),
            )
            db.executemany(
                "INSERT INTO observed_dependency VALUES (?, ?, ?)",
                ((execution, parent, ordinal) for parent in parents),
            )
        return EvidenceRef(execution, ordinal, digest)

    @staticmethod
    def _record(row: sqlite3.Row) -> dict[str, Any]:
        return {**json.loads(row["body"]), "digest": row["digest"]}

    def execution(self, execution: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM activity_execution WHERE id=?", (execution,)
            ).fetchone()
            if row is None:
                raise KeyError(execution)
            return {
                "id": row["id"],
                "provenance": json.loads(row["provenance"]),
                "digest": row["digest"],
            }

    def events(
        self, execution: str, *, after: int = -1, limit: int = 1000, from_time: int = 0
    ) -> list[dict[str, Any]]:
        if not 1 <= limit <= 10_000:
            raise ValueError("limit must be between 1 and 10000")
        with self._connect() as db:
            return [
                self._record(row)
                for row in db.execute(
                    "SELECT body, digest FROM activity_event "
                    "WHERE execution=? AND ordinal>? "
                    "AND logical_time>=? ORDER BY ordinal LIMIT ?",
                    (execution, after, from_time, limit),
                )
            ]

    def neighbors(
        self,
        execution: str,
        ordinal: int,
        *,
        downstream: bool = False,
        after: int = -1,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Return one hop along directly recorded dependencies, never causal claims."""
        if not 1 <= limit <= 10_000:
            raise ValueError("limit must be between 1 and 10000")
        here, other = ("parent", "child") if downstream else ("child", "parent")
        with self._connect() as db:
            return [
                self._record(row)
                for row in db.execute(
                    "SELECT e.body, e.digest FROM observed_dependency d "
                    "JOIN activity_event e "
                    f"ON e.execution=d.execution AND e.ordinal=d.{other} "
                    f"WHERE d.execution=? AND d.{here}=? AND e.ordinal>? "
                    "ORDER BY e.ordinal LIMIT ?",
                    (execution, ordinal, after, limit),
                )
            ]

    @classmethod
    def _evidence(
        cls, db: sqlite3.Connection, refs: Sequence[EvidenceRef]
    ) -> tuple[dict[str, Any], ...]:
        items = []
        for ref in refs:
            row = db.execute(
                "SELECT e.body, e.digest, x.provenance FROM activity_event e "
                "JOIN activity_execution x ON x.id=e.execution "
                "WHERE e.execution=? AND e.ordinal=?",
                (ref.execution, ref.ordinal),
            ).fetchone()
            if row is None or row["digest"] != ref.digest:
                raise ActivityIntegrityError(
                    "validation evidence missing or mismatched"
                )
            items.append(
                {**cls._record(row), "provenance": json.loads(row["provenance"])}
            )
        return tuple(items)

    def publish(
        self,
        relation: str,
        claims: Mapping[str, Any],
        evidence: Sequence[EvidenceRef],
        validator: Verifier,
        *,
        expected_version: int = 0,
    ) -> int:
        """Validate claims on bound evidence and append a publish or supersede event.

        Claims map explicit query keys to JSON values. Missing keys abstain.
        Only the host application supplies the verifier.
        """
        _name(relation)
        _nonnegative(expected_version)
        refs = tuple(evidence)
        values = json.loads(_json(dict(claims)))
        if not refs or len(refs) != len(set(refs)) or not values:
            raise ValueError("publication needs distinct evidence and nonempty claims")
        for key in values:
            _name(key)
        with self._connect() as db:
            records = self._evidence(db, refs)
        verdict = validator(
            json.loads(_json(values)), tuple(json.loads(_json(records)))
        )
        if not isinstance(verdict, Validation) or verdict.accepted is not True:
            raise ValueError("validation did not accept the publication")
        body = {
            "action": "publish" if expected_version == 0 else "supersede",
            "claims": values,
            "evidence": [
                {
                    "execution": ref.execution,
                    "ordinal": ref.ordinal,
                    "digest": ref.digest,
                }
                for ref in refs
            ],
            "validator": _name(verdict.validator),
            "detail": _name(verdict.detail),
        }
        with self._connect(write=True) as db:
            return self._version(
                db, relation, expected_version, body, expected_version + 1
            )

    @staticmethod
    def _tail(db: sqlite3.Connection, relation: str) -> sqlite3.Row | None:
        return db.execute(
            "SELECT * FROM interpretation_history WHERE relation=? "
            "ORDER BY version DESC LIMIT 1",
            (relation,),
        ).fetchone()

    @classmethod
    def _version(
        cls,
        db: sqlite3.Connection,
        relation: str,
        expected: int,
        body: dict[str, Any],
        active: int | None,
    ) -> int:
        tail = cls._tail(db, relation)
        actual = 0 if tail is None else tail["version"]
        if actual != expected:
            raise ValueError("interpretation version conflict")
        version = actual + 1
        previous = None if tail is None else tail["digest"]
        digest = _digest([relation, version, active, previous, body])
        db.execute(
            "INSERT INTO interpretation_history VALUES (?, ?, ?, ?, ?)",
            (relation, version, active, _json(body), digest),
        )
        return version

    def rollback(
        self, relation: str, *, expected_version: int, restore: int = 0
    ) -> int:
        """Append a rollback to a previous checkpoint, including an empty view."""
        _name(relation)
        _nonnegative(restore)
        _nonnegative(expected_version)
        if restore >= expected_version:
            raise ValueError("rollback must target an earlier checkpoint")
        with self._connect(write=True) as db:
            target = None
            if restore:
                row = db.execute(
                    "SELECT active FROM interpretation_history "
                    "WHERE relation=? AND version=?",
                    (relation, restore),
                ).fetchone()
                if row is None:
                    raise ValueError("unknown checkpoint")
                target = row["active"]
            return self._version(
                db,
                relation,
                expected_version,
                {"action": "rollback", "restore": restore},
                target,
            )

    def inference(
        self, relation: str, key: str, *, as_of: int | None = None
    ) -> Inference:
        """Consult an indexed published view without opening the evidence tape."""
        if as_of is not None:
            _nonnegative(as_of)
        with self._connect() as db:
            db.execute("BEGIN")
            if as_of is None:
                head = self._tail(db, relation)
            else:
                head = db.execute(
                    "SELECT * FROM interpretation_history "
                    "WHERE relation=? AND version<=? "
                    "ORDER BY version DESC LIMIT 1",
                    (relation, as_of),
                ).fetchone()
            if head is None or head["active"] is None:
                return Inference("abstain", reason="no active verified interpretation")
            row = db.execute(
                "SELECT body FROM interpretation_history "
                "WHERE relation=? AND version=?",
                (relation, head["active"]),
            ).fetchone()
            if row is None:
                raise ActivityIntegrityError("active interpretation missing")
            values = json.loads(row["body"])["claims"]
            if key not in values:
                return Inference(
                    "abstain", head["active"], reason="unresolved query key"
                )
            return Inference("verified", head["active"], values[key])

    def history(self, relation: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            return [
                {
                    **self._record(row),
                    "version": row["version"],
                    "active": row["active"],
                }
                for row in db.execute(
                    "SELECT * FROM interpretation_history "
                    "WHERE relation=? ORDER BY version",
                    (relation,),
                )
            ]

    def verify(self) -> dict[str, int]:
        """Audit hashes, dependency indexes, source references, and version replay."""
        counts = {"executions": 0, "events": 0, "interpretation_versions": 0}
        with self._connect() as db:
            db.execute("BEGIN")
            if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise ActivityIntegrityError("foreign key violation")
            for run in db.execute("SELECT * FROM activity_execution ORDER BY id"):
                execution = run["id"]
                previous = _digest([execution, json.loads(run["provenance"])])
                if previous != run["digest"]:
                    raise ActivityIntegrityError("execution provenance changed")
                counts["executions"] += 1
                last_time = -1
                for ordinal, row in enumerate(
                    db.execute(
                        "SELECT * FROM activity_event "
                        "WHERE execution=? ORDER BY ordinal",
                        (execution,),
                    )
                ):
                    event = json.loads(row["body"])
                    digest = _digest([previous, event])
                    parents = [
                        link[0]
                        for link in db.execute(
                            "SELECT parent FROM observed_dependency "
                            "WHERE execution=? AND child=? "
                            "ORDER BY parent",
                            (execution, ordinal),
                        )
                    ]
                    if (
                        ordinal != row["ordinal"]
                        or event["ordinal"] != ordinal
                        or event["execution"] != execution
                        or digest != row["digest"]
                        or event["logical_time"] != row["logical_time"]
                        or row["logical_time"] < last_time
                        or parents != event["observed_parents"]
                        or any(parent >= ordinal for parent in parents)
                    ):
                        raise ActivityIntegrityError(
                            "event chain or dependency index changed"
                        )
                    last_time, previous = row["logical_time"], digest
                    counts["events"] += 1
            for item in db.execute(
                "SELECT DISTINCT relation FROM interpretation_history ORDER BY relation"
            ):
                relation = item["relation"]
                previous = None
                versions: dict[int, int | None] = {0: None}
                for version, row in enumerate(
                    db.execute(
                        "SELECT * FROM interpretation_history "
                        "WHERE relation=? ORDER BY version",
                        (relation,),
                    ),
                    1,
                ):
                    body = json.loads(row["body"])
                    action = body["action"]
                    if action == "rollback":
                        if body["restore"] not in versions:
                            raise ActivityIntegrityError("unknown rollback checkpoint")
                        active = versions[body["restore"]]
                    elif action == ("publish" if version == 1 else "supersede"):
                        self._evidence(
                            db, tuple(EvidenceRef(**ref) for ref in body["evidence"])
                        )
                        active = version
                    else:
                        raise ActivityIntegrityError("invalid interpretation action")
                    digest = _digest([relation, version, active, previous, body])
                    if (
                        row["version"] != version
                        or row["active"] != active
                        or row["digest"] != digest
                    ):
                        raise ActivityIntegrityError(
                            "interpretation chain or active view changed"
                        )
                    previous = digest
                    versions[version] = active
                    counts["interpretation_versions"] += 1
        return counts


@dataclass(frozen=True)
class RuntimeRecorder:
    """A run-bound sink for calls made at observation time by the runtime."""

    memory: ActivityMemory
    execution: str

    def observe(
        self,
        *,
        ordinal: int,
        logical_time: int,
        kind: str,
        source: str,
        destination: str,
        payload: bytes,
        observed_parents: Sequence[int] = (),
        unresolved_links: Sequence[str] = (),
    ) -> EvidenceRef:
        return self.memory._append(
            self.execution,
            ordinal,
            logical_time,
            kind,
            source,
            destination,
            payload,
            observed_parents,
            unresolved_links,
        )
