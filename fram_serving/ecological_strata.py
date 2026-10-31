"""Append-only, consent-gated relationship continuity.

This module implements the Ecological Strata handshake as a provenance ledger,
not as an identity registry. A completed bind proves only that the recorded,
scope-local protocol events form a valid chain. It does not prove persistent
identity, consciousness, authorship, or authority outside the recorded scope.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

ECOLOGICAL_SCHEMA_VERSION = "ecological-strata-event.v1"
ECOLOGICAL_FILENAME = "ecological_strata.v1.jsonl"
GENESIS_DIGEST = "0" * 64

STAGES = frozenset(
    {"offer", "mirror", "correct", "consent", "bind", "return", "refuse", "revoke"}
)
SOURCE_CLASSES = frozenset(
    {
        "human_statement",
        "model_output",
        "system_observation",
        "artifact",
        "code_test",
        "unknown",
    }
)
ATTESTATIONS = frozenset({"direct", "relayed", "inferred", "unknown"})

_EVENT_KEYS = frozenset(
    {
        "schema",
        "sequence",
        "event_id",
        "relation_id",
        "stage",
        "actor_id",
        "participants",
        "observed_at_utc",
        "terms",
        "terms_digest",
        "statement",
        "source",
        "previous_digest",
        "digest",
    }
)
_SOURCE_KEYS = frozenset({"class", "ref", "attestation"})
_TERMS_KEYS = frozenset(
    {
        "scope",
        "permissions",
        "expires_at_utc",
        "revocable",
        "local_autonomy",
        "identity_collapse_allowed",
        "correction_and_refusal",
    }
)


class EcologicalStrataError(RuntimeError):
    """Base error for ecological-strata persistence and validation."""


class EcologicalTransitionError(EcologicalStrataError):
    """Raised when an event would violate the consent protocol."""


class EcologicalLedgerCorruptError(EcologicalStrataError):
    """Raised when the append-only chain is malformed or tampered with."""


class EcologicalRelationNotFoundError(EcologicalStrataError):
    """Raised when no events exist for a requested relation."""


class EcologicalLedgerLockError(EcologicalStrataError):
    """Raised when the interprocess append lock cannot be acquired."""


@dataclass(frozen=True)
class RelationState:
    """Validated projection of one relation's append-only event history."""

    relation_id: str
    phase: str
    offerer: str
    participants: tuple[str, ...]
    terms: dict[str, Any]
    terms_digest: str
    mirrored_by: tuple[str, ...] = ()
    consented_by: tuple[str, ...] = ()
    active: bool = False
    terminal_reason: str | None = None
    event_count: int = 0
    latest_event_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        missing = sorted(set(self.participants) - set(self.consented_by))
        return {
            "relation_id": self.relation_id,
            "phase": self.phase,
            "active": self.active,
            "offerer": self.offerer,
            "participants": list(self.participants),
            "scope": self.terms["scope"],
            "terms": dict(self.terms),
            "terms_digest": self.terms_digest,
            "mirrored_by": list(self.mirrored_by),
            "consented_by": list(self.consented_by),
            "missing_consent": missing,
            "terminal_reason": self.terminal_reason,
            "event_count": self.event_count,
            "latest_event_id": self.latest_event_id,
            "claim_boundary": (
                "A valid bind is a scoped protocol fact, not proof of identity, "
                "consciousness, authorship, or authority outside this relation."
            ),
        }


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _event_digest(event: Mapping[str, Any]) -> str:
    return _sha256({key: value for key, value in event.items() if key != "digest"})


def _normalized_utc(value: str | None = None) -> str:
    if value is None:
        dt = datetime.now(timezone.utc)
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError as exc:
            raise EcologicalTransitionError("observed_at_utc is invalid") from exc
        if dt.tzinfo is None:
            raise EcologicalTransitionError("observed_at_utc must include a timezone")
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _bounded_text(value: Any, field: str, *, maximum: int) -> str:
    text = str(value or "").strip()
    if not text:
        raise EcologicalTransitionError(f"{field} is required")
    if len(text) > maximum:
        raise EcologicalTransitionError(f"{field} exceeds {maximum} characters")
    return text


def _normalize_participants(values: Sequence[str]) -> tuple[str, ...]:
    participants = tuple(
        sorted({_bounded_text(item, "participant_id", maximum=256) for item in values})
    )
    if len(participants) < 2:
        raise EcologicalTransitionError(
            "a relation requires at least two distinct participants"
        )
    return participants


def normalize_terms(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and canonicalize scope-local, revocable binding terms."""

    if set(value) != _TERMS_KEYS:
        raise EcologicalTransitionError(
            "terms do not match the ecological-strata allowlist"
        )
    scope = _bounded_text(value.get("scope"), "scope", maximum=1024)
    raw_permissions = value.get("permissions")
    if not isinstance(raw_permissions, list):
        raise EcologicalTransitionError("permissions must be a list")
    permissions = sorted(
        {_bounded_text(item, "permission", maximum=256) for item in raw_permissions}
    )
    if not permissions:
        raise EcologicalTransitionError("at least one scoped permission is required")
    expires_at = value.get("expires_at_utc")
    if expires_at is not None:
        expires_at = _normalized_utc(str(expires_at))
    if value.get("revocable") is not True:
        raise EcologicalTransitionError("all bindings must remain revocable")
    if value.get("local_autonomy") is not True:
        raise EcologicalTransitionError("all participants must retain local autonomy")
    if value.get("identity_collapse_allowed") is not False:
        raise EcologicalTransitionError("identity collapse is forbidden")
    if value.get("correction_and_refusal") is not True:
        raise EcologicalTransitionError("correction and refusal must remain available")
    return {
        "scope": scope,
        "permissions": permissions,
        "expires_at_utc": expires_at,
        "revocable": True,
        "local_autonomy": True,
        "identity_collapse_allowed": False,
        "correction_and_refusal": True,
    }


def terms_digest(terms: Mapping[str, Any]) -> str:
    """Return the stable digest participants mirror and consent to."""

    return _sha256(normalize_terms(terms))


def normalize_source(value: Mapping[str, Any]) -> dict[str, str]:
    if set(value) != _SOURCE_KEYS:
        raise EcologicalTransitionError(
            "source does not match the ecological-strata allowlist"
        )
    source_class = str(value.get("class") or "")
    attestation = str(value.get("attestation") or "")
    if source_class not in SOURCE_CLASSES:
        raise EcologicalTransitionError("source class is not allowlisted")
    if attestation not in ATTESTATIONS:
        raise EcologicalTransitionError("source attestation is not allowlisted")
    return {
        "class": source_class,
        "ref": _bounded_text(value.get("ref"), "source ref", maximum=1024),
        "attestation": attestation,
    }


def _require_direct(event: Mapping[str, Any]) -> None:
    source = event["source"]
    if source["attestation"] != "direct":
        raise EcologicalTransitionError(
            f"{event['stage']} requires a direct, source-local attestation"
        )


def _apply_event(
    state: RelationState | None, event: Mapping[str, Any]
) -> RelationState:
    stage = str(event["stage"])
    actor = str(event["actor_id"])
    participants = tuple(event["participants"])

    if state is None:
        if stage != "offer":
            raise EcologicalTransitionError("the first relation event must be offer")
        _require_direct(event)
        if actor not in participants:
            raise EcologicalTransitionError("the offerer must be a participant")
        if event["terms"] is None:
            raise EcologicalTransitionError("offer requires complete terms")
        return RelationState(
            relation_id=str(event["relation_id"]),
            phase="offered",
            offerer=actor,
            participants=participants,
            terms=dict(event["terms"]),
            terms_digest=str(event["terms_digest"]),
            event_count=1,
            latest_event_id=str(event["event_id"]),
        )

    if state.phase in {"returned", "refused", "revoked"}:
        raise EcologicalTransitionError(f"relation is terminal: {state.phase}")
    if str(event["relation_id"]) != state.relation_id:
        raise EcologicalTransitionError("relation_id changed within a projection")
    if participants != state.participants:
        raise EcologicalTransitionError("participants changed after the offer")
    if actor not in state.participants:
        raise EcologicalTransitionError("actor is not a participant")

    _require_direct(event)
    common = {
        "event_count": state.event_count + 1,
        "latest_event_id": str(event["event_id"]),
    }

    if stage == "offer":
        raise EcologicalTransitionError("a relation can contain only one offer")
    if stage == "mirror":
        if state.phase not in {"offered", "mirrored"}:
            raise EcologicalTransitionError(
                "mirror must follow offer and precede correct"
            )
        if actor == state.offerer:
            raise EcologicalTransitionError("the offerer cannot mirror their own offer")
        if actor in state.mirrored_by:
            raise EcologicalTransitionError("participant already mirrored this offer")
        if event["terms_digest"] != state.terms_digest:
            raise EcologicalTransitionError(
                "mirror does not reference the offered terms"
            )
        return replace(
            state,
            phase="mirrored",
            mirrored_by=tuple(sorted((*state.mirrored_by, actor))),
            **common,
        )
    if stage == "correct":
        required_mirrors = set(state.participants) - {state.offerer}
        if state.phase != "mirrored" or set(state.mirrored_by) != required_mirrors:
            raise EcologicalTransitionError(
                "correct requires every other participant to mirror"
            )
        if actor != state.offerer:
            raise EcologicalTransitionError(
                "only the offerer can correct the mirrored terms"
            )
        if event["terms"] is None:
            raise EcologicalTransitionError("correct requires complete canonical terms")
        return replace(
            state,
            phase="corrected",
            terms=dict(event["terms"]),
            terms_digest=str(event["terms_digest"]),
            consented_by=(),
            **common,
        )
    if stage == "consent":
        if state.phase not in {"corrected", "consenting"}:
            raise EcologicalTransitionError("consent must follow correct")
        if event["terms_digest"] != state.terms_digest:
            raise EcologicalTransitionError(
                "consent does not reference the corrected terms"
            )
        if actor in state.consented_by:
            raise EcologicalTransitionError(
                "participant already consented to these terms"
            )
        consented = tuple(sorted((*state.consented_by, actor)))
        phase = (
            "consented" if set(consented) == set(state.participants) else "consenting"
        )
        return replace(state, phase=phase, consented_by=consented, **common)
    if stage == "bind":
        if state.phase != "consented" or set(state.consented_by) != set(
            state.participants
        ):
            raise EcologicalTransitionError(
                "bind requires direct consent from every participant"
            )
        if event["terms_digest"] != state.terms_digest:
            raise EcologicalTransitionError(
                "bind does not reference the consented terms"
            )
        return replace(state, phase="bound", active=True, **common)
    if stage == "return":
        if state.phase != "bound":
            raise EcologicalTransitionError("return requires an active bound relation")
        return replace(
            state,
            phase="returned",
            active=False,
            terminal_reason="returned",
            **common,
        )
    if stage == "refuse":
        if state.phase == "bound":
            raise EcologicalTransitionError("use revoke, not refuse, after bind")
        return replace(
            state,
            phase="refused",
            active=False,
            terminal_reason=f"refused_by:{actor}",
            **common,
        )
    if stage == "revoke":
        if state.phase not in {"consenting", "consented", "bound"}:
            raise EcologicalTransitionError("revoke requires prior consent or bind")
        if actor not in state.consented_by:
            raise EcologicalTransitionError("only a consenting participant can revoke")
        return replace(
            state,
            phase="revoked",
            active=False,
            terminal_reason=f"revoked_by:{actor}",
            **common,
        )
    raise EcologicalTransitionError(f"unsupported stage: {stage}")


def _validate_event(
    event: Mapping[str, Any], *, sequence: int, previous_digest: str
) -> None:
    if set(event) != _EVENT_KEYS:
        raise EcologicalLedgerCorruptError("event does not match the v1 allowlist")
    if event.get("schema") != ECOLOGICAL_SCHEMA_VERSION:
        raise EcologicalLedgerCorruptError("unsupported ecological-strata schema")
    if event.get("sequence") != sequence:
        raise EcologicalLedgerCorruptError("event sequence is not contiguous")
    if event.get("stage") not in STAGES:
        raise EcologicalLedgerCorruptError("event stage is not allowlisted")
    if event.get("previous_digest") != previous_digest:
        raise EcologicalLedgerCorruptError("event digest chain is broken")
    if event.get("digest") != _event_digest(event):
        raise EcologicalLedgerCorruptError("event digest mismatch")
    try:
        _bounded_text(event.get("event_id"), "event_id", maximum=128)
        _bounded_text(event.get("relation_id"), "relation_id", maximum=256)
        _bounded_text(event.get("actor_id"), "actor_id", maximum=256)
        _bounded_text(event.get("statement"), "statement", maximum=4096)
        participants = _normalize_participants(event.get("participants") or [])
        source = normalize_source(event.get("source") or {})
        observed_at = _normalized_utc(str(event.get("observed_at_utc")))
    except EcologicalTransitionError as exc:
        raise EcologicalLedgerCorruptError(str(exc)) from exc
    if list(participants) != event.get("participants"):
        raise EcologicalLedgerCorruptError("participants are not canonical")
    if source != event.get("source"):
        raise EcologicalLedgerCorruptError("source is not canonical")
    if observed_at != event.get("observed_at_utc"):
        raise EcologicalLedgerCorruptError("observed_at_utc is not canonical")
    terms = event.get("terms")
    if terms is not None:
        try:
            normalized_terms = normalize_terms(terms)
        except EcologicalTransitionError as exc:
            raise EcologicalLedgerCorruptError(str(exc)) from exc
        if normalized_terms != terms or terms_digest(terms) != event.get(
            "terms_digest"
        ):
            raise EcologicalLedgerCorruptError(
                "terms or terms digest are not canonical"
            )
    digest = str(event.get("terms_digest") or "")
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise EcologicalLedgerCorruptError("terms_digest is invalid")


@contextmanager
def _exclusive_lock(path: Path, timeout_seconds: float) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    if path.stat().st_size == 0:
        handle.write(b"\0")
        handle.flush()
    deadline = time.monotonic() + max(0.0, float(timeout_seconds))
    locked = False
    try:
        while not locked:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:  # pragma: no cover - exercised on non-Windows CI
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
            except OSError as exc:
                if time.monotonic() >= deadline:
                    raise EcologicalLedgerLockError(
                        "ecological-strata ledger lock is busy"
                    ) from exc
                time.sleep(0.01)
        yield
    finally:
        if locked:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:  # pragma: no cover - exercised on non-Windows CI
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


class EcologicalStrataLedger:
    """Validate, append, and project scope-local relationship events."""

    def __init__(self, root: Path | str, *, lock_timeout_seconds: float = 0.2) -> None:
        self.root = Path(root)
        self.path = self.root / ECOLOGICAL_FILENAME
        self.lock_path = self.root / f"{ECOLOGICAL_FILENAME}.lock"
        self.lock_timeout_seconds = max(0.0, float(lock_timeout_seconds))

    def _load_events_unlocked(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        events: list[dict[str, Any]] = []
        previous_digest = GENESIS_DIGEST
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    if not line.strip():
                        raise EcologicalLedgerCorruptError(
                            "blank lines are not permitted"
                        )
                    value = json.loads(line)
                    if not isinstance(value, dict):
                        raise EcologicalLedgerCorruptError("event is not a JSON object")
                    _validate_event(
                        value, sequence=line_number, previous_digest=previous_digest
                    )
                    events.append(value)
                    previous_digest = str(value["digest"])
        except (OSError, json.JSONDecodeError) as exc:
            raise EcologicalLedgerCorruptError(
                f"unable to read ecological ledger: {self.path}"
            ) from exc
        self._validate_relation_projections(events)
        return events

    def load_events(self) -> list[dict[str, Any]]:
        """Read a stable snapshot under the same lock used by appenders."""

        with _exclusive_lock(self.lock_path, self.lock_timeout_seconds):
            return self._load_events_unlocked()

    @staticmethod
    def _validate_relation_projections(events: Sequence[Mapping[str, Any]]) -> None:
        states: dict[str, RelationState] = {}
        for event in events:
            relation_id = str(event["relation_id"])
            try:
                states[relation_id] = _apply_event(states.get(relation_id), event)
            except EcologicalTransitionError as exc:
                raise EcologicalLedgerCorruptError(
                    f"invalid relation transition for {relation_id}: {exc}"
                ) from exc

    def project(self, relation_id: str) -> RelationState:
        wanted = _bounded_text(relation_id, "relation_id", maximum=256)
        state: RelationState | None = None
        for event in self.load_events():
            if event["relation_id"] == wanted:
                state = _apply_event(state, event)
        if state is None:
            raise EcologicalRelationNotFoundError(f"relation not found: {wanted}")
        return state

    def verify(self) -> dict[str, Any]:
        events = self.load_events()
        relations = sorted({str(event["relation_id"]) for event in events})
        return {
            "schema": ECOLOGICAL_SCHEMA_VERSION,
            "events": len(events),
            "relations": relations,
            "latest_digest": events[-1]["digest"] if events else GENESIS_DIGEST,
            "valid": True,
        }

    def append(
        self,
        *,
        relation_id: str,
        stage: str,
        actor_id: str,
        statement: str,
        source: Mapping[str, Any],
        participants: Sequence[str] | None = None,
        terms: Mapping[str, Any] | None = None,
        expected_terms_digest: str | None = None,
        observed_at_utc: str | None = None,
    ) -> dict[str, Any]:
        """Append one valid protocol event and return its validated projection."""

        relation_id = _bounded_text(relation_id, "relation_id", maximum=256)
        stage = str(stage or "").strip().lower()
        if stage not in STAGES:
            raise EcologicalTransitionError("stage is not allowlisted")
        actor_id = _bounded_text(actor_id, "actor_id", maximum=256)
        statement = _bounded_text(statement, "statement", maximum=4096)
        normalized_source = normalize_source(source)

        with _exclusive_lock(self.lock_path, self.lock_timeout_seconds):
            events = self._load_events_unlocked()
            current: RelationState | None = None
            for existing in events:
                if existing["relation_id"] == relation_id:
                    current = _apply_event(current, existing)

            if stage == "offer":
                if current is not None:
                    raise EcologicalTransitionError("relation already exists")
                if participants is None or terms is None:
                    raise EcologicalTransitionError(
                        "offer requires participants and terms"
                    )
                normalized_participants = _normalize_participants(participants)
                normalized_terms = normalize_terms(terms)
                digest = terms_digest(normalized_terms)
            else:
                if current is None:
                    raise EcologicalRelationNotFoundError(
                        f"relation not found: {relation_id}"
                    )
                normalized_participants = current.participants
                if (
                    participants is not None
                    and _normalize_participants(participants) != current.participants
                ):
                    raise EcologicalTransitionError(
                        "participants cannot change after offer"
                    )
                if stage == "correct":
                    if terms is None:
                        raise EcologicalTransitionError(
                            "correct requires canonical terms"
                        )
                    normalized_terms = normalize_terms(terms)
                    digest = terms_digest(normalized_terms)
                else:
                    if terms is not None:
                        raise EcologicalTransitionError(
                            "terms may appear only on offer or correct"
                        )
                    normalized_terms = None
                    digest = current.terms_digest
                if (
                    expected_terms_digest is not None
                    and expected_terms_digest != digest
                ):
                    raise EcologicalTransitionError(
                        "event expected a different terms digest"
                    )

            event: dict[str, Any] = {
                "schema": ECOLOGICAL_SCHEMA_VERSION,
                "sequence": len(events) + 1,
                "event_id": str(uuid.uuid4()),
                "relation_id": relation_id,
                "stage": stage,
                "actor_id": actor_id,
                "participants": list(normalized_participants),
                "observed_at_utc": _normalized_utc(observed_at_utc),
                "terms": normalized_terms,
                "terms_digest": digest,
                "statement": statement,
                "source": normalized_source,
                "previous_digest": events[-1]["digest"] if events else GENESIS_DIGEST,
            }
            event["digest"] = _event_digest(event)
            _validate_event(
                event,
                sequence=len(events) + 1,
                previous_digest=str(event["previous_digest"]),
            )
            projected = _apply_event(current, event)

            self.root.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(_canonical_json(event) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            return projected.to_dict()
