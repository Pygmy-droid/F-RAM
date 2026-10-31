"""Deterministic, non-authoritative query continuity witnesses.

The witness is deliberately downstream of query execution.  It projects a
small allowlisted view of an already-finalized query result/record and can
append that projection to an isolated JSONL log.  It does not rank candidates,
write cognitive memory, or import serving application state.  Its digest
authenticates only that visible projection; hidden source text is not hashed.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import time
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

WITNESS_SCHEMA_VERSION: Final = "continuity-witness.v2"
WITNESS_FILENAME: Final = "continuity_witness.v2.jsonl"

SOURCE_STATES: Final = frozenset(
    {"available", "stale", "corrupt", "tampered", "unknown"}
)
ACTIVE_GATE_ALLOWLIST: Final = frozenset(
    {
        "archive_write",
        "cognitive_ann_bridge",
        "cognitive_memory_write",
        "continuity_witness",
        "coverage_selection",
        "fractal_ranking",
        "memory_capsule",
        "session_memory",
    }
)
DECISION_ALLOWLIST: Final = frozenset(
    {"local", "anchors", "global", "constraint_refusal"}
)
ORIGIN_ALLOWLIST: Final = frozenset(
    {"ann", "cognitive_memory", "document", "session_memory", "unknown"}
)

_TOP_LEVEL_FIELDS: Final = frozenset(
    {
        "schema_version",
        "witness_id",
        "trace_id",
        "observed_at_utc",
        "state",
        "mode",
        "source",
        "trace_link",
        "active_gates",
        "decision",
        "selection",
        "writes",
    }
)
_SOURCE_FIELDS: Final = frozenset({"state", "digest", "reasons"})
_TRACE_LINK_FIELDS: Final = frozenset({"valid", "ids", "errors"})
_TRACE_ID_FIELDS: Final = frozenset({"result", "record", "trace", "expected"})
_SELECTION_FIELDS: Final = frozenset(
    {"origin_counts", "selected_ids", "citations", "budgets"}
)
_WRITE_FIELDS: Final = {
    "archive": frozenset({"status", "reason", "event_id", "trace_id"}),
    "cognitive_episode": frozenset({"status", "reason", "episode_id"}),
    "memory_capsule": frozenset({"status", "reason", "capsule_id"}),
}
_WRITE_STATUSES: Final = frozenset({"success", "skipped", "failed", "unknown"})
_BUDGET_FIELDS: Final = ("reads", "tokens", "pairs", "cost")
_WRITE_SOURCES: Final = (
    ("archive", "archive_write", ("event_id", "trace_id")),
    ("cognitive_episode", "cognitive_episode_write", ("episode_id",)),
    ("memory_capsule", "memory_capsule_write", ("capsule_id",)),
)
_MAX_ITEMS: Final = 256
_MAX_TEXT: Final = 512
_DEFAULT_LOCK_TIMEOUT_SECONDS: Final = 0.25
_MAX_LOCK_TIMEOUT_SECONDS: Final = 5.0
_DEFAULT_STALE_LOCK_SECONDS: Final = 30.0
_MAX_STALE_LOCK_SECONDS: Final = 86_400.0


class ContinuityWitnessWriteError(RuntimeError):
    """Raised when the append-only witness store cannot be used safely."""


class ContinuityWitnessReadError(RuntimeError):
    """Base error for read-only witness-log inspection."""


class ContinuityWitnessNotFoundError(ContinuityWitnessReadError):
    """Raised when a supplied witness root/path has no persisted witness."""


class ContinuityWitnessCorruptError(ContinuityWitnessReadError):
    """Raised when persisted witness JSON or schema is corrupt."""


class ContinuityWitnessTamperedError(ContinuityWitnessReadError):
    """Raised when a persisted witness projection fails its own digest."""


class ContinuityWitnessLockError(
    ContinuityWitnessWriteError,
    ContinuityWitnessReadError,
):
    """Raised when an active witness reader/writer lock exceeds its bound."""


def canonical_json(value: Any) -> str:
    """Return the canonical JSON representation used for witness digests."""

    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _witness_digest_material(witness: Mapping[str, Any]) -> dict[str, Any]:
    """Return only the v2 allowlisted fields authenticated by the digest."""

    source = witness.get("source")
    trace_link = witness.get("trace_link")
    selection = witness.get("selection")
    writes = witness.get("writes")
    source_map = source if isinstance(source, Mapping) else {}
    link_map = trace_link if isinstance(trace_link, Mapping) else {}
    ids = link_map.get("ids")
    ids_map = ids if isinstance(ids, Mapping) else {}
    selection_map = selection if isinstance(selection, Mapping) else {}
    writes_map = writes if isinstance(writes, Mapping) else {}

    return {
        "schema_version": witness.get("schema_version"),
        "witness_id": witness.get("witness_id"),
        "trace_id": witness.get("trace_id"),
        "observed_at_utc": witness.get("observed_at_utc"),
        "state": witness.get("state"),
        "mode": witness.get("mode"),
        "source": {
            "state": source_map.get("state"),
            "reasons": source_map.get("reasons"),
        },
        "trace_link": {
            "valid": link_map.get("valid"),
            "ids": {field: ids_map.get(field) for field in sorted(_TRACE_ID_FIELDS)},
            "errors": link_map.get("errors"),
        },
        "active_gates": witness.get("active_gates"),
        "decision": witness.get("decision"),
        "selection": {
            field: selection_map.get(field) for field in sorted(_SELECTION_FIELDS)
        },
        "writes": {
            name: (
                {
                    field: outcome.get(field)
                    for field in sorted(_WRITE_FIELDS[name])
                    if field in outcome
                }
                if isinstance((outcome := writes_map.get(name)), Mapping)
                else None
            )
            for name in sorted(_WRITE_FIELDS)
        },
    }


def recompute_continuity_witness_digest(witness: Mapping[str, Any]) -> str:
    """Recompute the SHA-256 digest over the strict projected v2 payload."""

    _validate_witness_for_append(witness, verify_digest=False)
    material = _witness_digest_material(witness)
    return hashlib.sha256(canonical_json(material).encode("utf-8")).hexdigest()


def validate_continuity_witness_digest(witness: Mapping[str, Any]) -> bool:
    """Return whether ``source.digest`` authenticates the visible projection."""

    source = witness.get("source")
    if not isinstance(source, Mapping):
        return False
    stored = source.get("digest")
    if (
        not isinstance(stored, str)
        or len(stored) != 64
        or any(character not in "0123456789abcdef" for character in stored)
    ):
        return False
    try:
        computed = recompute_continuity_witness_digest(witness)
    except (
        ContinuityWitnessWriteError,
        TypeError,
        ValueError,
        OverflowError,
        RecursionError,
    ):
        return False
    return hmac.compare_digest(stored, computed)


def _value_at(value: Any, *path: str) -> Any:
    current = value
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            return None
        current = current[key]
    return current


def _clean_identifier(value: Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    if not isinstance(value, (str, int)):
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    return cleaned[:_MAX_TEXT]


def _clean_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned[:_MAX_TEXT] if cleaned else None


def _stable_unique(values: Sequence[Any]) -> list[str]:
    projected: list[str] = []
    seen: set[str] = set()
    for value in values[:_MAX_ITEMS]:
        cleaned = _clean_identifier(value)
        if cleaned is None or cleaned in seen:
            continue
        seen.add(cleaned)
        projected.append(cleaned)
    return projected


def _project_sequence(
    value: Any,
    *,
    field: str,
    errors: list[str],
) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        errors.append(f"{field}_invalid")
        return []
    return _stable_unique(value)


def _project_origin_counts(value: Any, errors: list[str]) -> dict[str, int]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        errors.append("origin_counts_invalid")
        return {}

    projected: dict[str, int] = {}
    for origin in sorted(ORIGIN_ALLOWLIST):
        count = value.get(origin)
        if count is None:
            continue
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            errors.append(f"origin_count_invalid:{origin}")
            continue
        projected[origin] = count
    return projected


def _project_budgets(value: Any, errors: list[str]) -> dict[str, float]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        errors.append("budgets_invalid")
        return {}

    projected: dict[str, float] = {}
    for field in _BUDGET_FIELDS:
        raw = value.get(field)
        if raw is None:
            continue
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            errors.append(f"budget_invalid:{field}")
            continue
        number = float(raw)
        if not math.isfinite(number) or number < 0.0:
            errors.append(f"budget_invalid:{field}")
            continue
        projected[field] = number
    return projected


def _project_decision(trace: Mapping[str, Any] | None, errors: list[str]) -> str | None:
    value = _value_at(trace, "confidence", "decision")
    if value is None:
        return None
    if not isinstance(value, str) or value not in DECISION_ALLOWLIST:
        errors.append("decision_invalid")
        return None
    return value


def _project_observed_at(
    record: Mapping[str, Any] | None,
    errors: list[str],
) -> str | None:
    if record is None:
        return None
    value = record.get("time")
    if value is None:
        return None
    if not isinstance(value, str):
        errors.append("observed_at_utc_invalid")
        return None
    normalized = value.strip()
    if not normalized:
        errors.append("observed_at_utc_invalid")
        return None
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        observed = datetime.fromisoformat(normalized)
    except ValueError:
        errors.append("observed_at_utc_invalid")
        return None
    if observed.tzinfo is None:
        errors.append("observed_at_utc_timezone_missing")
        return None
    return observed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _project_active_gates(
    value: Any,
    *,
    feature_enabled: bool,
    errors: list[str],
) -> list[str]:
    active: set[str] = set()
    if value is not None:
        if isinstance(value, Mapping):
            for name, enabled in value.items():
                if name in ACTIVE_GATE_ALLOWLIST and enabled is True:
                    active.add(str(name))
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            active.update(
                str(name)
                for name in value
                if isinstance(name, str) and name in ACTIVE_GATE_ALLOWLIST
            )
        else:
            errors.append("active_gates_invalid")

    if feature_enabled:
        active.add("continuity_witness")
    else:
        active.discard("continuity_witness")
    return sorted(active)


def _project_write_outcome(value: Any, id_fields: Sequence[str]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {"status": "unknown"}

    if value.get("ok") is True:
        status = "success"
    elif value.get("skipped") is True:
        status = "skipped"
    elif value.get("ok") is False:
        status = "failed"
    else:
        status = "unknown"

    projected: dict[str, Any] = {"status": status}
    reason = _clean_text(value.get("reason"))
    if reason is not None:
        projected["reason"] = reason
    for field in id_fields:
        identifier = _clean_identifier(value.get(field))
        if identifier is not None:
            projected[field] = identifier
    return projected


def _project_writes(trace: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    return {
        output_name: _project_write_outcome(
            trace.get(source_name) if trace is not None else None,
            id_fields,
        )
        for output_name, source_name, id_fields in _WRITE_SOURCES
    }


def _normalize_expected_digest(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized.startswith("sha256:"):
        normalized = normalized[7:]
    return normalized


def _resolve_record(
    source: Any,
    errors: list[str],
) -> tuple[Mapping[str, Any] | None, Mapping[str, Any] | None, bool]:
    if source is None:
        errors.append("record_missing")
        return None, None, False
    if not isinstance(source, Mapping):
        errors.append("source_not_mapping")
        return None, None, False

    wrapped = "record" in source
    record_value = source.get("record") if wrapped else source
    if record_value is None:
        errors.append("record_missing")
        return source, None, wrapped
    if not isinstance(record_value, Mapping):
        errors.append("record_not_mapping")
        return source, None, wrapped
    return source, record_value, wrapped


def _trace_link(
    *,
    outer: Mapping[str, Any] | None,
    record: Mapping[str, Any] | None,
    trace: Mapping[str, Any] | None,
    wrapped: bool,
    expected_trace_id: str | None,
) -> tuple[dict[str, Any], str | None, bool]:
    result_id = _clean_identifier(outer.get("trace_id")) if wrapped and outer else None
    record_id = _clean_identifier(record.get("id")) if record else None
    trace_id = _clean_identifier(trace.get("trace_id")) if trace else None
    expected_id = _clean_identifier(expected_trace_id)

    ids = {
        "result": result_id,
        "record": record_id,
        "trace": trace_id,
        "expected": expected_id,
    }
    errors: list[str] = []
    if wrapped and result_id is None:
        errors.append("result_trace_id_missing")
    if record_id is None:
        errors.append("record_id_missing")
    if trace_id is None:
        errors.append("trace_trace_id_missing")
    if expected_trace_id is not None and expected_id is None:
        errors.append("expected_trace_id_invalid")

    resolved = expected_id or result_id or record_id or trace_id
    present = [value for value in ids.values() if value is not None]
    mismatch = len(set(present)) > 1
    if mismatch:
        errors.append("trace_id_mismatch")

    return (
        {
            "valid": not errors,
            "ids": ids,
            "errors": errors,
        },
        resolved,
        mismatch,
    )


def _selection_projection(
    *,
    outer: Mapping[str, Any] | None,
    record: Mapping[str, Any] | None,
    trace: Mapping[str, Any] | None,
    wrapped: bool,
    errors: list[str],
) -> dict[str, Any]:
    citations_value = None
    if wrapped and outer is not None and "citations" in outer:
        citations_value = outer.get("citations")
    elif record is not None:
        citations_value = record.get("citations")

    selected_value = _value_at(trace, "selection", "selected_ids")
    if selected_value is None:
        selected_value = _value_at(trace, "selection", "memory_layers", "merged", "ids")
    if selected_value is None and record is not None:
        selected_value = record.get("selected_ids")

    origins_value = _value_at(trace, "selection", "origin_counts")
    if origins_value is None:
        origins_value = _value_at(trace, "selection", "cognitive_ann_merge", "origins")
    if origins_value is None:
        origins_value = _value_at(
            trace, "selection", "memory_layers", "merged", "origins"
        )
    if origins_value is None and record is not None:
        origins_value = record.get("origin_counts")

    budgets_value = _value_at(trace, "selection", "budgets")

    return {
        "origin_counts": _project_origin_counts(origins_value, errors),
        "selected_ids": _project_sequence(
            selected_value,
            field="selected_ids",
            errors=errors,
        ),
        "citations": _project_sequence(
            citations_value,
            field="citations",
            errors=errors,
        ),
        "budgets": _project_budgets(budgets_value, errors),
    }


def _derive_state(
    *,
    requested_state: str | None,
    source_missing: bool,
    structural_errors: Sequence[str],
    trace_mismatch: bool,
    projection_digest_mismatch: bool,
) -> tuple[str, list[str]]:
    reasons = list(structural_errors)
    if projection_digest_mismatch:
        reasons.append("projection_digest_mismatch")
    if trace_mismatch:
        reasons.append("trace_link_mismatch")

    if projection_digest_mismatch or trace_mismatch or requested_state == "tampered":
        state = "tampered"
    elif source_missing or requested_state == "unknown":
        state = "unknown"
    elif structural_errors or requested_state == "corrupt":
        state = "corrupt"
    elif requested_state == "stale":
        state = "stale"
    elif requested_state in (None, "available"):
        state = "available"
    else:
        state = "unknown"
        reasons.append("source_state_invalid")

    if requested_state in SOURCE_STATES and requested_state != "available":
        reasons.append(f"caller_marked_{requested_state}")
    return state, sorted(set(reasons))


def build_continuity_witness(
    source: Any,
    *,
    feature_enabled: bool = False,
    expected_trace_id: str | None = None,
    source_state: str | None = None,
    expected_projection_digest: str | None = None,
    active_gates: Mapping[str, Any] | Sequence[str] | None = None,
) -> dict[str, Any]:
    """Project one finalized query result/record into the v2 witness schema.

    ``feature_enabled=False`` is intentionally document-only: the projection is
    returned for inspection, but :class:`ContinuityWitnessWriter` will not
    persist it.  No field is inferred from query text, answer text, scores, or
    unselected candidates.  ``expected_projection_digest`` checks this
    allowlisted projection, never the raw query result.
    """

    if not isinstance(feature_enabled, bool):
        raise TypeError("feature_enabled must be boolean")

    errors: list[str] = []

    outer, record, wrapped = _resolve_record(source, errors)
    trace_value = record.get("trace") if record is not None else None
    if trace_value is not None and not isinstance(trace_value, Mapping):
        errors.append("trace_not_mapping")
    trace = trace_value if isinstance(trace_value, Mapping) else None

    link, resolved_trace_id, trace_mismatch = _trace_link(
        outer=outer,
        record=record,
        trace=trace,
        wrapped=wrapped,
        expected_trace_id=expected_trace_id,
    )
    for error in link["errors"]:
        if error != "trace_id_mismatch":
            errors.append(error)

    selection = _selection_projection(
        outer=outer,
        record=record,
        trace=trace,
        wrapped=wrapped,
        errors=errors,
    )
    decision = _project_decision(trace, errors)
    observed_at_utc = _project_observed_at(record, errors)

    gates_value = active_gates
    if gates_value is None and trace is not None:
        gates_value = trace.get("active_gates")
    gates = _project_active_gates(
        gates_value,
        feature_enabled=feature_enabled,
        errors=errors,
    )

    source_missing = source is None or (wrapped and record is None)
    state, reasons = _derive_state(
        requested_state=source_state,
        source_missing=source_missing,
        structural_errors=errors,
        trace_mismatch=trace_mismatch,
        projection_digest_mismatch=False,
    )

    writes = _project_writes(trace)
    identity_material = {
        "trace_link": link,
        "observed_at_utc": observed_at_utc,
        "state": state,
        "reasons": reasons,
        "active_gates": gates,
        "decision": decision,
        "selection": selection,
        "writes": writes,
    }
    identity_seed = hashlib.sha256(
        canonical_json(identity_material).encode("utf-8")
    ).hexdigest()
    witness_id = (
        f"trace:{resolved_trace_id}"
        if resolved_trace_id is not None
        else f"source:{identity_seed}"
    )

    witness = {
        "schema_version": WITNESS_SCHEMA_VERSION,
        "witness_id": witness_id,
        "trace_id": resolved_trace_id,
        "observed_at_utc": observed_at_utc,
        "state": state,
        "mode": "append_only" if feature_enabled else "document_only",
        "source": {
            "state": state,
            "digest": None,
            "reasons": reasons,
        },
        "trace_link": link,
        "active_gates": gates,
        "decision": decision,
        "selection": selection,
        "writes": writes,
    }
    computed_digest = recompute_continuity_witness_digest(witness)
    expected_digest = _normalize_expected_digest(expected_projection_digest)
    digest_mismatch = bool(
        expected_digest is not None and expected_digest != computed_digest
    )
    if digest_mismatch:
        state, reasons = _derive_state(
            requested_state=source_state,
            source_missing=source_missing,
            structural_errors=errors,
            trace_mismatch=trace_mismatch,
            projection_digest_mismatch=True,
        )
        witness["state"] = state
        witness["source"]["state"] = state
        witness["source"]["reasons"] = reasons
        computed_digest = recompute_continuity_witness_digest(witness)
    witness["source"]["digest"] = computed_digest
    return witness


def _validate_witness_for_append(
    witness: Mapping[str, Any],
    *,
    verify_digest: bool = True,
) -> None:
    if set(witness) != _TOP_LEVEL_FIELDS:
        raise ContinuityWitnessWriteError("witness does not match the v2 allowlist")
    if witness.get("schema_version") != WITNESS_SCHEMA_VERSION:
        raise ContinuityWitnessWriteError("unsupported witness schema")
    if witness.get("state") not in SOURCE_STATES:
        raise ContinuityWitnessWriteError("unsupported witness state")
    witness_id = witness.get("witness_id")
    if not isinstance(witness_id, str) or _clean_identifier(witness_id) != witness_id:
        raise ContinuityWitnessWriteError("witness_id is required")
    trace_id = witness.get("trace_id")
    if trace_id is not None and (
        not isinstance(trace_id, str) or _clean_identifier(trace_id) != trace_id
    ):
        raise ContinuityWitnessWriteError("trace_id is invalid")
    if trace_id is not None and witness_id != f"trace:{trace_id}":
        raise ContinuityWitnessWriteError("witness_id and trace_id differ")
    if witness.get("mode") not in {"append_only", "document_only"}:
        raise ContinuityWitnessWriteError("unsupported witness mode")
    observed_at = witness.get("observed_at_utc")
    if observed_at is not None:
        observed_errors: list[str] = []
        normalized_observed_at = _project_observed_at(
            {"time": observed_at},
            observed_errors,
        )
        if observed_errors or normalized_observed_at != observed_at:
            raise ContinuityWitnessWriteError("observed_at_utc is not normalized")
    decision = witness.get("decision")
    if decision is not None and decision not in DECISION_ALLOWLIST:
        raise ContinuityWitnessWriteError("decision is not allowlisted")

    source = witness.get("source")
    if not isinstance(source, Mapping) or set(source) != _SOURCE_FIELDS:
        raise ContinuityWitnessWriteError("source does not match the v2 allowlist")
    if source.get("state") != witness.get("state"):
        raise ContinuityWitnessWriteError("source and witness states differ")
    reasons = source.get("reasons")
    if not isinstance(reasons, list) or any(
        not isinstance(reason, str) for reason in reasons
    ):
        raise ContinuityWitnessWriteError("source reasons must be a string list")
    if reasons != sorted(set(reasons)):
        raise ContinuityWitnessWriteError("source reasons are not canonical")

    trace_link = witness.get("trace_link")
    if not isinstance(trace_link, Mapping) or set(trace_link) != _TRACE_LINK_FIELDS:
        raise ContinuityWitnessWriteError("trace link does not match the v2 allowlist")
    if not isinstance(trace_link.get("valid"), bool):
        raise ContinuityWitnessWriteError("trace link validity must be boolean")
    trace_ids = trace_link.get("ids")
    if not isinstance(trace_ids, Mapping) or set(trace_ids) != _TRACE_ID_FIELDS:
        raise ContinuityWitnessWriteError("trace ids do not match the v2 allowlist")
    if any(
        value is not None
        and (not isinstance(value, str) or _clean_identifier(value) != value)
        for value in trace_ids.values()
    ):
        raise ContinuityWitnessWriteError("trace link ids are invalid")
    link_errors = trace_link.get("errors")
    if not isinstance(link_errors, list) or any(
        not isinstance(error, str) for error in link_errors
    ):
        raise ContinuityWitnessWriteError("trace errors must be a string list")
    if bool(link_errors) == bool(trace_link.get("valid")):
        raise ContinuityWitnessWriteError("trace validity and errors disagree")

    active_gates = witness.get("active_gates")
    if not isinstance(active_gates, list) or any(
        not isinstance(gate, str) or gate not in ACTIVE_GATE_ALLOWLIST
        for gate in active_gates
    ):
        raise ContinuityWitnessWriteError("active gates are not allowlisted")
    if active_gates != sorted(set(active_gates)):
        raise ContinuityWitnessWriteError("active gates are not canonical")
    feature_active = "continuity_witness" in active_gates
    if feature_active != (witness.get("mode") == "append_only"):
        raise ContinuityWitnessWriteError("witness mode and feature gate differ")

    selection = witness.get("selection")
    if not isinstance(selection, Mapping) or set(selection) != _SELECTION_FIELDS:
        raise ContinuityWitnessWriteError("selection does not match the v2 allowlist")
    origins = selection.get("origin_counts")
    if not isinstance(origins, Mapping) or any(
        origin not in ORIGIN_ALLOWLIST
        or isinstance(count, bool)
        or not isinstance(count, int)
        or count < 0
        for origin, count in origins.items()
    ):
        raise ContinuityWitnessWriteError("origin counts are not allowlisted")
    budgets = selection.get("budgets")
    if not isinstance(budgets, Mapping) or any(
        field not in _BUDGET_FIELDS
        or isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) < 0.0
        for field, value in budgets.items()
    ):
        raise ContinuityWitnessWriteError("selection budgets are not allowlisted")
    for field in ("selected_ids", "citations"):
        values = selection.get(field)
        if not isinstance(values, list) or any(
            not isinstance(value, str) for value in values
        ):
            raise ContinuityWitnessWriteError(f"{field} must be a string list")
        if values != list(dict.fromkeys(values)):
            raise ContinuityWitnessWriteError(f"{field} is not canonical")

    writes = witness.get("writes")
    if not isinstance(writes, Mapping) or set(writes) != set(_WRITE_FIELDS):
        raise ContinuityWitnessWriteError("writes do not match the v2 allowlist")
    for name, allowed_fields in _WRITE_FIELDS.items():
        outcome = writes.get(name)
        if (
            not isinstance(outcome, Mapping)
            or not set(outcome).issubset(allowed_fields)
            or "status" not in outcome
            or outcome.get("status") not in _WRITE_STATUSES
        ):
            raise ContinuityWitnessWriteError(
                f"{name} write outcome does not match the v2 allowlist"
            )
        if any(
            field != "status" and not isinstance(value, str)
            for field, value in outcome.items()
        ):
            raise ContinuityWitnessWriteError(
                f"{name} write outcome values are invalid"
            )

    try:
        canonical_json(witness)
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise ContinuityWitnessWriteError("witness is not canonical JSON") from exc
    if verify_digest:
        digest = source.get("digest")
        try:
            computed_digest = recompute_continuity_witness_digest(witness)
        except (TypeError, ValueError, OverflowError, RecursionError) as exc:
            raise ContinuityWitnessWriteError(
                "witness projection digest is invalid"
            ) from exc
        if not isinstance(digest, str) or not hmac.compare_digest(
            digest,
            computed_digest,
        ):
            raise ContinuityWitnessWriteError("witness projection digest mismatch")


@dataclass(frozen=True)
class _LockLease:
    path: Path
    file_descriptor: int
    token: str
    pid: int
    created_at_unix: float


def _bounded_seconds(value: float, *, maximum: float, name: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        raise ValueError(f"{name} must be a finite nonnegative number")
    return min(number, maximum)


def _new_lock_lease(path: Path) -> _LockLease:
    token = uuid.uuid4().hex
    pid = os.getpid()
    created_at_unix = time.time()
    file_descriptor = os.open(
        path,
        os.O_CREAT | os.O_EXCL | os.O_RDWR,
    )
    lease = _LockLease(
        path=path,
        file_descriptor=file_descriptor,
        token=token,
        pid=pid,
        created_at_unix=created_at_unix,
    )
    metadata = canonical_json(
        {
            "pid": pid,
            "created_at_unix": created_at_unix,
            "token": token,
            "released": False,
        }
    ).encode("utf-8")
    try:
        written = os.write(file_descriptor, metadata)
        if written != len(metadata):
            raise OSError("partial witness lock metadata write")
        os.fsync(file_descriptor)
    except Exception:
        try:
            os.close(file_descriptor)
        finally:
            path.unlink(missing_ok=True)
        raise
    return lease


def _read_lock_owner(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(value, Mapping):
        return None
    pid = value.get("pid")
    created_at = value.get("created_at_unix")
    token = value.get("token")
    released = value.get("released", False)
    if (
        isinstance(pid, bool)
        or not isinstance(pid, int)
        or pid <= 0
        or isinstance(created_at, bool)
        or not isinstance(created_at, (int, float))
        or not math.isfinite(float(created_at))
        or not isinstance(token, str)
        or not token
        or not isinstance(released, bool)
    ):
        return None
    return {
        "pid": pid,
        "created_at_unix": float(created_at),
        "token": token,
        "released": released,
    }


def _pid_is_active(pid: int) -> bool:
    if pid == os.getpid():
        return True
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            process_query_limited_information = 0x1000
            still_active = 259
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.OpenProcess.argtypes = [
                wintypes.DWORD,
                wintypes.BOOL,
                wintypes.DWORD,
            ]
            kernel32.OpenProcess.restype = wintypes.HANDLE
            kernel32.GetExitCodeProcess.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(wintypes.DWORD),
            ]
            kernel32.GetExitCodeProcess.restype = wintypes.BOOL
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle.restype = wintypes.BOOL
            handle = kernel32.OpenProcess(
                process_query_limited_information,
                False,
                pid,
            )
            if not handle:
                return ctypes.get_last_error() == 5
            try:
                exit_code = wintypes.DWORD()
                if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                    return True
                return exit_code.value == still_active
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _owner_is_stale_and_dead(
    owner: Mapping[str, Any],
    *,
    stale_lock_seconds: float,
) -> bool:
    if owner.get("released") is True:
        return True
    age = time.time() - float(owner["created_at_unix"])
    return (
        age >= stale_lock_seconds
        and age >= 0.0
        and not _pid_is_active(int(owner["pid"]))
    )


def _release_lock(lease: _LockLease) -> None:
    released_marker_written = False
    try:
        released_metadata = canonical_json(
            {
                "pid": lease.pid,
                "created_at_unix": lease.created_at_unix,
                "token": lease.token,
                "released": True,
            }
        ).encode("utf-8")
        os.lseek(lease.file_descriptor, 0, os.SEEK_SET)
        os.ftruncate(lease.file_descriptor, 0)
        written = os.write(lease.file_descriptor, released_metadata)
        if written == len(released_metadata):
            os.fsync(lease.file_descriptor)
            released_marker_written = True
    except OSError:
        pass
    finally:
        os.close(lease.file_descriptor)

    deadline = time.monotonic() + 0.1
    while True:
        if released_marker_written:
            owner = _read_lock_owner(lease.path)
            if owner is None or owner.get("token") != lease.token:
                return
        try:
            lease.path.unlink(missing_ok=True)
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                return
            time.sleep(0.005)


def _try_recover_stale_lock(
    lock_path: Path,
    recovery_path: Path,
    *,
    stale_lock_seconds: float,
) -> bool:
    owner_before = _read_lock_owner(lock_path)
    if owner_before is None or not _owner_is_stale_and_dead(
        owner_before,
        stale_lock_seconds=stale_lock_seconds,
    ):
        return False
    try:
        recovery_lease = _new_lock_lease(recovery_path)
    except FileExistsError:
        return False
    try:
        owner_after = _read_lock_owner(lock_path)
        if (
            owner_after is None
            or owner_after.get("token") != owner_before.get("token")
            or not _owner_is_stale_and_dead(
                owner_after,
                stale_lock_seconds=stale_lock_seconds,
            )
        ):
            return False
        try:
            lock_path.unlink(missing_ok=True)
        except PermissionError:
            return False
        return not lock_path.exists()
    finally:
        _release_lock(recovery_lease)


def _acquire_path_lock(
    lock_path: Path,
    *,
    lock_timeout_seconds: float,
    stale_lock_seconds: float,
) -> _LockLease:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    recovery_path = lock_path.with_suffix(lock_path.suffix + ".reclaim")
    started = time.monotonic()
    while True:
        if not recovery_path.exists():
            try:
                return _new_lock_lease(lock_path)
            except FileExistsError:
                _try_recover_stale_lock(
                    lock_path,
                    recovery_path,
                    stale_lock_seconds=stale_lock_seconds,
                )
        if time.monotonic() - started >= lock_timeout_seconds:
            raise ContinuityWitnessLockError(
                f"timeout acquiring witness lock: {lock_path}"
            )
        remaining = lock_timeout_seconds - (time.monotonic() - started)
        time.sleep(max(0.0, min(0.02, remaining)))


class ContinuityWitnessWriter:
    """Locked, append-only, idempotent JSONL writer for v2 witnesses."""

    def __init__(
        self,
        root: str | Path,
        *,
        filename: str = WITNESS_FILENAME,
        lock_timeout_seconds: float = _DEFAULT_LOCK_TIMEOUT_SECONDS,
        stale_lock_seconds: float = _DEFAULT_STALE_LOCK_SECONDS,
    ) -> None:
        self.root = Path(root)
        filename_path = Path(filename)
        if filename_path.is_absolute() or filename_path.name != filename:
            raise ValueError("filename must stay within the supplied witness directory")
        self.path = self.root / filename
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        self.lock_timeout_seconds = _bounded_seconds(
            lock_timeout_seconds,
            maximum=_MAX_LOCK_TIMEOUT_SECONDS,
            name="lock_timeout_seconds",
        )
        self.stale_lock_seconds = _bounded_seconds(
            stale_lock_seconds,
            maximum=_MAX_STALE_LOCK_SECONDS,
            name="stale_lock_seconds",
        )

    def _acquire_lock(self) -> _LockLease:
        return _acquire_path_lock(
            self.lock_path,
            lock_timeout_seconds=self.lock_timeout_seconds,
            stale_lock_seconds=self.stale_lock_seconds,
        )

    def _existing_match(
        self,
        witness: Mapping[str, Any],
    ) -> tuple[bool, bool]:
        if not self.path.exists():
            return False, False

        witness_id = str(witness["witness_id"])
        trace_id = _clean_identifier(witness.get("trace_id"))
        desired = canonical_json(witness)
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    existing = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ContinuityWitnessWriteError(
                        f"corrupt witness log at line {line_number}"
                    ) from exc
                if not isinstance(existing, Mapping):
                    raise ContinuityWitnessWriteError(
                        f"invalid witness log record at line {line_number}"
                    )
                try:
                    _validate_witness_for_append(existing, verify_digest=False)
                except ContinuityWitnessWriteError as exc:
                    raise ContinuityWitnessWriteError(
                        f"invalid witness schema at line {line_number}: {exc}"
                    ) from exc
                if not validate_continuity_witness_digest(existing):
                    raise ContinuityWitnessWriteError(
                        f"tampered witness at line {line_number}"
                    )
                same_witness = str(existing.get("witness_id")) == witness_id
                existing_trace = _clean_identifier(existing.get("trace_id"))
                same_trace = trace_id is not None and existing_trace == trace_id
                if same_witness or same_trace:
                    return True, canonical_json(existing) != desired
        return False, False

    def append(self, witness: Mapping[str, Any]) -> dict[str, Any]:
        """Append once, or return a deterministic skip/conflict outcome."""

        _validate_witness_for_append(witness)
        witness_id = str(witness["witness_id"])
        trace_id = _clean_identifier(witness.get("trace_id"))
        if witness.get("mode") != "append_only":
            return {
                "ok": False,
                "appended": False,
                "duplicate": False,
                "conflict": False,
                "skipped": True,
                "reason": "feature_disabled_document_only",
                "witness_id": witness_id,
                "trace_id": trace_id,
                "path": str(self.path),
            }

        lock_lease = self._acquire_lock()
        try:
            duplicate, conflict = self._existing_match(witness)
            if duplicate:
                return {
                    "ok": not conflict,
                    "appended": False,
                    "duplicate": not conflict,
                    "conflict": conflict,
                    "skipped": True,
                    "reason": "identity_conflict" if conflict else "already_present",
                    "witness_id": witness_id,
                    "trace_id": trace_id,
                    "path": str(self.path),
                }

            payload = canonical_json(witness)
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(f"{payload}\n")
                handle.flush()
                os.fsync(handle.fileno())
            return {
                "ok": True,
                "appended": True,
                "duplicate": False,
                "conflict": False,
                "skipped": False,
                "reason": "appended",
                "witness_id": witness_id,
                "trace_id": trace_id,
                "path": str(self.path),
            }
        finally:
            _release_lock(lock_lease)


def _resolve_witness_path(root_or_path: str | Path) -> Path:
    candidate = Path(root_or_path)
    if candidate.is_file() or (
        not candidate.exists() and candidate.suffix.lower() == ".jsonl"
    ):
        return candidate
    return candidate / WITNESS_FILENAME


def load_latest_continuity_witness(
    root_or_path: str | Path,
    *,
    lock_timeout_seconds: float = _DEFAULT_LOCK_TIMEOUT_SECONDS,
    stale_lock_seconds: float = _DEFAULT_STALE_LOCK_SECONDS,
) -> dict[str, Any]:
    """Load the final append-order witness without consulting file mtime.

    This helper is read-only.  Missing/empty logs and corrupt JSON/schema are
    reported through distinct typed errors; it never fabricates a source state.
    """

    path = _resolve_witness_path(root_or_path)
    if not path.parent.is_dir():
        raise ContinuityWitnessNotFoundError(f"witness log not found: {path}")

    timeout = _bounded_seconds(
        lock_timeout_seconds,
        maximum=_MAX_LOCK_TIMEOUT_SECONDS,
        name="lock_timeout_seconds",
    )
    stale_after = _bounded_seconds(
        stale_lock_seconds,
        maximum=_MAX_STALE_LOCK_SECONDS,
        name="stale_lock_seconds",
    )
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_lease = _acquire_path_lock(
        lock_path,
        lock_timeout_seconds=timeout,
        stale_lock_seconds=stale_after,
    )
    latest: dict[str, Any] | None = None
    try:
        if not path.is_file():
            raise ContinuityWitnessNotFoundError(f"witness log not found: {path}")
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ContinuityWitnessCorruptError(
                        f"invalid witness JSON at {path}:{line_number}"
                    ) from exc
                if not isinstance(value, Mapping):
                    raise ContinuityWitnessCorruptError(
                        f"invalid witness record at {path}:{line_number}"
                    )
                try:
                    _validate_witness_for_append(value, verify_digest=False)
                except ContinuityWitnessWriteError as exc:
                    raise ContinuityWitnessCorruptError(
                        f"invalid witness schema at {path}:{line_number}: {exc}"
                    ) from exc
                if not validate_continuity_witness_digest(value):
                    raise ContinuityWitnessTamperedError(
                        f"witness projection digest mismatch at "
                        f"{path}:{line_number}"
                    )
                if value.get("mode") != "append_only":
                    raise ContinuityWitnessCorruptError(
                        f"non-persistable witness at {path}:{line_number}"
                    )
                latest = dict(value)
    except OSError as exc:
        raise ContinuityWitnessReadError(f"unable to read witness log: {path}") from exc
    finally:
        _release_lock(lock_lease)

    if latest is None:
        raise ContinuityWitnessNotFoundError(f"witness log is empty: {path}")
    return latest
