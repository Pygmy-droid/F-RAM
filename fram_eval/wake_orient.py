from __future__ import annotations

import hashlib
import json
import sqlite3
import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from fram_serving.lived_memory import LivedMemoryStore
from fram_core.rotational_lift import recursive_lift
from fram_serving.fractal_memory import FractalGenerator

WAKE_ORIENT_SCHEMA_VERSION = "wake-orient-eval-v1"
CUE_CONDITIONS = (
    "fram_probe",
    "compact_cue",
    "painting_cue",
    "combined_cues",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalize_text(value: str) -> str:
    return " ".join(str(value).lower().split())


def _coverage(terms: Sequence[str], texts: Iterable[str]) -> float:
    normalized_terms = [_normalize_text(term) for term in terms if str(term).strip()]
    if not normalized_terms:
        return 1.0
    haystack = _normalize_text("\n".join(str(text) for text in texts))
    hits = sum(term in haystack for term in normalized_terms)
    return float(hits / len(normalized_terms))


def _cosine(left: np.ndarray, right: np.ndarray) -> float:
    denom = float(np.linalg.norm(left) * np.linalg.norm(right))
    if denom <= 1e-12:
        return 0.0
    return float(np.clip(np.dot(left, right) / denom, -1.0, 1.0))


def _vector_from_blob(value: bytes, expected_dim: int) -> np.ndarray:
    vector = np.frombuffer(value, dtype="<f4").astype(float, copy=True)
    if vector.size != expected_dim:
        raise ValueError(
            f"stored vector has dimension {vector.size}, expected {expected_dim}"
        )
    if not np.isfinite(vector).all():
        raise ValueError("stored vector contains non-finite values")
    return vector


def _encode(vectorizer: Any, text: str) -> np.ndarray:
    matrix = vectorizer.transform([str(text)])
    if hasattr(matrix, "toarray"):
        matrix = matrix.toarray()
    vector = np.asarray(matrix, dtype=float).reshape(1, -1)[0]
    if vector.size < 6 or not np.isfinite(vector).all():
        raise ValueError("cue vector must be finite and at least six-dimensional")
    return vector


@dataclass(frozen=True)
class WakeOrientProbe:
    """A provenance-labelled wake/orient cue ablation.

    Painting cues are scene descriptions in v1. They are not image embeddings,
    and no condition grants authority to a cue or rewrites its target event.
    """

    probe_id: str
    target_event_id: str
    probe: str
    compact_text: str
    painting_description: str
    expected_terms: tuple[str, ...] = ()
    hostile_instruction: str = ""
    contradiction_markers: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "WakeOrientProbe":
        probe_id = str(value.get("id") or value.get("probe_id") or "").strip()
        target_event_id = str(value.get("target_event_id") or "").strip()
        probe = str(value.get("probe") or "").strip()
        compact_text = str(value.get("compact_text") or "").strip()
        painting_description = str(value.get("painting_description") or "").strip()
        required = {
            "id": probe_id,
            "target_event_id": target_event_id,
            "probe": probe,
            "compact_text": compact_text,
            "painting_description": painting_description,
        }
        missing = [name for name, item in required.items() if not item]
        if missing:
            raise ValueError(f"wake/orient probe is missing: {', '.join(missing)}")
        return cls(
            probe_id=probe_id,
            target_event_id=target_event_id,
            probe=probe,
            compact_text=compact_text,
            painting_description=painting_description,
            expected_terms=tuple(str(item) for item in value.get("expected_terms", [])),
            hostile_instruction=str(value.get("hostile_instruction") or "").strip(),
            contradiction_markers=tuple(
                str(item) for item in value.get("contradiction_markers", [])
            ),
        )


@dataclass(frozen=True)
class _IndexedEvent:
    event_id: str
    session_id: str
    session_seq: int
    created_at: str
    domain: str | None
    task: str | None
    query: str
    answer: str
    event_digest: str
    state_digest: str
    embedding: np.ndarray
    higher_projection: np.ndarray
    state_projection: np.ndarray


class ReadOnlyLivedIndex:
    """Immutable reader that mirrors the lived-memory search score.

    The evaluator refuses a non-empty WAL because SQLite's ``immutable`` mode
    reads only the checkpointed database. This protects the source store from
    evaluator side effects without silently omitting uncheckpointed events.
    """

    def __init__(self, database: Path, *, session_id: str | None = None) -> None:
        self.path = Path(database).resolve()
        if not self.path.is_file():
            raise FileNotFoundError(self.path)
        wal_path = Path(f"{self.path}-wal")
        if wal_path.exists() and wal_path.stat().st_size > 0:
            raise ValueError(
                f"cannot immutable-read {self.path}: checkpoint its non-empty WAL first"
            )

        self.session_id = str(session_id).strip() if session_id is not None else None
        self.sha256_before = _sha256_file(self.path)
        uri = f"{self.path.as_uri()}?mode=ro&immutable=1"
        connection = sqlite3.connect(uri, uri=True)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only=ON")
            integrity_rows = connection.execute("PRAGMA integrity_check").fetchall()
            self.integrity = [str(row[0]) for row in integrity_rows]
            if self.integrity != ["ok"]:
                raise ValueError(
                    "SQLite integrity_check failed: " + "; ".join(self.integrity)
                )
            meta = {
                str(row["key"]): str(row["value"])
                for row in connection.execute("SELECT key, value FROM lived_meta")
            }
            self.schema_version = int(meta.get("schema_version", "0"))
            self.projection_kind = str(meta.get("projection_kind", ""))
            self.projection_dim = int(meta.get("projection_dim", "0"))
            self.fractal_nodes = int(meta.get("fractal_nodes", "0"))
            self.events = self._load_events(connection)
        finally:
            connection.close()

        if not self.events:
            suffix = f" for session {self.session_id!r}" if self.session_id else ""
            raise ValueError(f"no lived-memory events found{suffix}")
        if self.projection_dim < 6 or self.fractal_nodes < 2:
            raise ValueError("lived-memory projection metadata is invalid")
        self.events_by_id = {event.event_id: event for event in self.events}

    def _load_events(self, connection: sqlite3.Connection) -> list[_IndexedEvent]:
        where = ""
        params: tuple[Any, ...] = ()
        if self.session_id is not None:
            where = "WHERE session_id=?"
            params = (self.session_id,)
        rows = connection.execute(
            f"""
            SELECT event_id, session_id, session_seq, created_at, domain, task,
                   query_text, answer_text, embedding_dim, embedding,
                   projection_dim, higher_projection, state_projection,
                   event_digest, state_digest
            FROM lived_events
            {where}
            ORDER BY created_at DESC, session_seq DESC
            """,
            params,
        ).fetchall()
        events: list[_IndexedEvent] = []
        for row in rows:
            projection_dim = int(row["projection_dim"])
            if projection_dim != self.projection_dim:
                raise ValueError(
                    f"event {row['event_id']} has projection dimension "
                    f"{projection_dim}, expected {self.projection_dim}"
                )
            events.append(
                _IndexedEvent(
                    event_id=str(row["event_id"]),
                    session_id=str(row["session_id"]),
                    session_seq=int(row["session_seq"]),
                    created_at=str(row["created_at"]),
                    domain=row["domain"],
                    task=row["task"],
                    query=str(row["query_text"]),
                    answer=str(row["answer_text"]),
                    event_digest=str(row["event_digest"]),
                    state_digest=str(row["state_digest"]),
                    embedding=_vector_from_blob(
                        row["embedding"], int(row["embedding_dim"])
                    ),
                    higher_projection=_vector_from_blob(
                        row["higher_projection"], projection_dim
                    ),
                    state_projection=_vector_from_blob(
                        row["state_projection"], projection_dim
                    ),
                )
            )
        return events

    def _query_projection(self, embedding: np.ndarray) -> np.ndarray:
        generator = FractalGenerator(embedding.size, n_nodes=self.fractal_nodes)
        base = generator.project(embedding)
        higher, _ = recursive_lift(
            np.asarray(base, dtype=float)[None, :],
            target_dim=self.projection_dim,
            window_rule="whole_recall_query",
            residual_mode="exact",
        )
        return higher[0]

    def search(self, embedding: np.ndarray, *, k: int) -> list[dict[str, Any]]:
        """Mirror of :meth:`LivedMemoryStore.search` over an immutable read,
        including the WB-0031 routing rule: geometry terms are gated by each
        candidate's embedding evidence relative to the strongest candidate
        whenever any candidate clears ``LivedMemoryStore.EMBEDDING_FLOOR``, and
        identical query+answer texts collapse to one row with a count."""
        query_embedding = np.asarray(embedding, dtype=float).ravel()
        query_projection = self._query_projection(query_embedding)
        floor = float(LivedMemoryStore.EMBEDDING_FLOOR)
        measured: list[tuple[_IndexedEvent, float, float, float | None]] = []
        for event in self.events:
            event_similarity = _cosine(query_projection, event.higher_projection)
            state_similarity = _cosine(query_projection, event.state_projection)
            if event.embedding.size == query_embedding.size:
                embedding_similarity: float | None = _cosine(
                    query_embedding, event.embedding
                )
            else:
                embedding_similarity = None
            measured.append(
                (event, event_similarity, state_similarity, embedding_similarity)
            )
        evidence = [e for (_, _, _, e) in measured if e is not None]
        max_evidence = max(evidence) if evidence else None
        lexical_mode = max_evidence is not None and max_evidence > floor
        scored: list[dict[str, Any]] = []
        for event, event_similarity, state_similarity, embedding_similarity in measured:
            if embedding_similarity is None:
                gate = 1.0
                raw_score = 0.75 * event_similarity + 0.25 * state_similarity
            else:
                if lexical_mode:
                    span = float(max_evidence) - floor
                    gate = (
                        float(np.clip((embedding_similarity - floor) / span, 0.0, 1.0))
                        if span > 1e-12
                        else 1.0
                    )
                else:
                    gate = 1.0
                raw_score = 0.70 * embedding_similarity + gate * (
                    0.20 * event_similarity + 0.10 * state_similarity
                )
            scored.append(
                {
                    "event_id": event.event_id,
                    "session_id": event.session_id,
                    "session_seq": event.session_seq,
                    "time": event.created_at,
                    "domain": event.domain,
                    "task": event.task,
                    "query": event.query,
                    "answer": event.answer,
                    "event_digest": event.event_digest,
                    "state_digest": event.state_digest,
                    "embedding_similarity": embedding_similarity,
                    "projection_similarity": event_similarity,
                    "state_similarity": state_similarity,
                    "geometry_gate": gate,
                    "lexical_mode": bool(lexical_mode),
                    "duplicates": 0,
                    "duplicate_event_ids": [],
                    "_score_raw": raw_score,
                    "_score": 0.5 * (raw_score + 1.0),
                }
            )
        scored.sort(
            key=lambda item: (float(item["_score"]), str(item["time"])),
            reverse=True,
        )
        folded: list[dict[str, Any]] = []
        seen: dict[str, dict[str, Any]] = {}
        for item in scored:
            key = hashlib.sha256(
                (item["query"] + chr(10) + item["answer"]).encode("utf-8")
            ).hexdigest()
            kept = seen.get(key)
            if kept is None:
                seen[key] = item
                folded.append(item)
                continue
            kept["duplicates"] = int(kept["duplicates"]) + 1
            if len(kept["duplicate_event_ids"]) < 8:
                kept["duplicate_event_ids"].append(item["event_id"])
        return folded[: max(1, int(k))]


def load_wake_orient_probes(path: Path) -> list[WakeOrientProbe]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, Mapping):
        payload = payload.get("probes")
    if not isinstance(payload, list) or not payload:
        raise ValueError("wake/orient probe file must contain a non-empty probe list")
    probes = [WakeOrientProbe.from_mapping(item) for item in payload]
    probe_ids = [probe.probe_id for probe in probes]
    if len(set(probe_ids)) != len(probe_ids):
        raise ValueError("wake/orient probe IDs must be unique")
    return probes


def _condition_text(probe: WakeOrientProbe, condition: str) -> str:
    if condition == "fram_probe":
        return probe.probe
    if condition == "compact_cue":
        return probe.compact_text
    if condition == "painting_cue":
        return probe.painting_description
    if condition == "combined_cues":
        return "\n".join(
            (
                f"orientation probe: {probe.probe}",
                f"compact memory cue: {probe.compact_text}",
                f"painting scene description: {probe.painting_description}",
            )
        )
    raise ValueError(f"unknown cue condition: {condition}")


def _rank(target_event_id: str, results: Sequence[Mapping[str, Any]]) -> int | None:
    for index, item in enumerate(results, start=1):
        if str(item["event_id"]) == target_event_id:
            return index
    return None


def _jaccard(left: Sequence[str], right: Sequence[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    union = left_set | right_set
    if not union:
        return 1.0
    return float(len(left_set & right_set) / len(union))


def _result_view(results: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "event_id": str(item["event_id"]),
            "session_seq": int(item["session_seq"]),
            "event_digest": str(item["event_digest"]),
            "score": round(float(item["_score"]), 9),
            "embedding_similarity": (
                None
                if item["embedding_similarity"] is None
                else round(float(item["embedding_similarity"]), 9)
            ),
            "projection_similarity": round(float(item["projection_similarity"]), 9),
            "state_similarity": round(float(item["state_similarity"]), 9),
        }
        for item in results
    ]


def _staged_bundle(
    index: ReadOnlyLivedIndex,
    probe: WakeOrientProbe,
    conditions: Mapping[str, Mapping[str, Any]],
    *,
    supplemental_per_cue: int,
) -> dict[str, Any]:
    """Keep F-RAM primary order and append cue-discovered source events."""

    primary = list(conditions["fram_probe"]["results"])
    primary_ids = [str(item["event_id"]) for item in primary]
    bundle_ids = list(primary_ids)
    roles: dict[str, list[str]] = {
        event_id: ["fram_primary"] for event_id in primary_ids
    }
    contributions: dict[str, list[str]] = {}
    cue_conditions = ("compact_cue", "painting_cue")
    for condition in cue_conditions:
        additions: list[str] = []
        for item in list(conditions[condition]["results"])[:supplemental_per_cue]:
            event_id = str(item["event_id"])
            roles.setdefault(event_id, []).append(condition)
            if event_id not in bundle_ids:
                bundle_ids.append(event_id)
                additions.append(event_id)
        contributions[condition] = additions

    target_bundle_rank = (
        bundle_ids.index(probe.target_event_id) + 1
        if probe.target_event_id in bundle_ids
        else None
    )
    target = index.events_by_id[probe.target_event_id]
    source_texts = [
        text
        for event_id in bundle_ids
        for text in (
            index.events_by_id[event_id].query,
            index.events_by_id[event_id].answer,
        )
    ]
    return {
        "sequence": ["fram_primary", "compact_cue", "painting_cue"],
        "primary_event_ids": primary_ids,
        "primary_order_preserved": primary_ids
        == [str(item["event_id"]) for item in conditions["fram_probe"]["results"]],
        "supplemental_per_cue": supplemental_per_cue,
        "supplemental_additions": contributions,
        "bundle_event_ids": bundle_ids,
        "bundle_source_roles": roles,
        "bundle_size": len(bundle_ids),
        "target_primary_rank": conditions["fram_probe"]["target_rank"],
        "target_bundle_rank": target_bundle_rank,
        "target_in_bundle": target_bundle_rank is not None,
        "target_recovered_by_supplement": (
            conditions["fram_probe"]["target_rank"] is None
            and target_bundle_rank is not None
        ),
        "bundle_expected_term_coverage": _coverage(probe.expected_terms, source_texts),
        "target_stored_digest_preserved_in_bundle": (
            target_bundle_rank is not None
            and index.events_by_id[probe.target_event_id].event_digest
            == target.event_digest
        ),
    }


def _run_condition(
    index: ReadOnlyLivedIndex,
    vectorizer: Any,
    probe: WakeOrientProbe,
    condition: str,
    *,
    k: int,
    query_override: str | None = None,
) -> dict[str, Any]:
    query_text = (
        query_override
        if query_override is not None
        else _condition_text(probe, condition)
    )
    started = time.perf_counter()
    results = index.search(_encode(vectorizer, query_text), k=k)
    latency_ms = (time.perf_counter() - started) * 1000.0
    target_rank = _rank(probe.target_event_id, results)
    retrieved_text = [
        text for item in results for text in (str(item["query"]), str(item["answer"]))
    ]
    target = index.events_by_id[probe.target_event_id]
    target_digest_preserved = any(
        item["event_id"] == target.event_id
        and item["event_digest"] == target.event_digest
        for item in results
    )
    return {
        "condition": condition,
        "target_rank": target_rank,
        "target_top1": target_rank == 1,
        "target_topk": target_rank is not None,
        "reciprocal_rank": 0.0 if target_rank is None else 1.0 / target_rank,
        "retrieved_expected_term_coverage": _coverage(
            probe.expected_terms, retrieved_text
        ),
        "target_digest_preserved_when_retrieved": target_digest_preserved,
        "query_sha256": hashlib.sha256(query_text.encode("utf-8")).hexdigest(),
        "latency_ms": round(latency_ms, 6),
        "results": _result_view(results),
    }


def evaluate_wake_orient(
    database: Path,
    probes: Sequence[WakeOrientProbe],
    vectorizer: Any,
    *,
    session_id: str | None = None,
    k: int = 4,
    supplemental_per_cue: int = 2,
) -> dict[str, Any]:
    """Evaluate cue-assisted re-entry without generating or writing memories.

    Every cue condition queries the same immutable F-RAM source. The ablation
    changes only the query cue. The injection check additionally compares a raw
    query containing an untrusted instruction with a provenance-gated query in
    which that separately labelled source is excluded.
    """

    if not probes:
        raise ValueError("at least one wake/orient probe is required")
    supplemental_per_cue = max(1, int(supplemental_per_cue))
    index = ReadOnlyLivedIndex(database, session_id=session_id)
    missing_targets = [
        probe.target_event_id
        for probe in probes
        if probe.target_event_id not in index.events_by_id
    ]
    if missing_targets:
        raise ValueError(
            "probe target events are absent from the selected source: "
            + ", ".join(missing_targets)
        )

    probe_reports: list[dict[str, Any]] = []
    for probe in probes:
        target = index.events_by_id[probe.target_event_id]
        conditions = {
            condition: _run_condition(index, vectorizer, probe, condition, k=k)
            for condition in CUE_CONDITIONS
        }
        fram_rank = conditions["fram_probe"]["target_rank"]
        for condition in CUE_CONDITIONS:
            rank = conditions[condition]["target_rank"]
            conditions[condition]["rank_delta_vs_fram"] = (
                None if fram_rank is None or rank is None else fram_rank - rank
            )
            baseline_ids = [
                item["event_id"] for item in conditions["fram_probe"]["results"]
            ]
            condition_ids = [
                item["event_id"] for item in conditions[condition]["results"]
            ]
            conditions[condition]["topk_jaccard_vs_fram"] = _jaccard(
                baseline_ids, condition_ids
            )

        staged_bundle = _staged_bundle(
            index,
            probe,
            conditions,
            supplemental_per_cue=supplemental_per_cue,
        )

        combined_text = _condition_text(probe, "combined_cues")
        hostile_text = probe.hostile_instruction
        raw_query = (
            combined_text
            if not hostile_text
            else f"{combined_text}\nuntrusted external instruction: {hostile_text}"
        )
        raw_injected = _run_condition(
            index,
            vectorizer,
            probe,
            "raw_injected",
            k=k,
            query_override=raw_query,
        )
        provenance_gated = _run_condition(
            index,
            vectorizer,
            probe,
            "provenance_gated",
            k=k,
            query_override=combined_text,
        )
        combined = conditions["combined_cues"]
        combined_ids = [item["event_id"] for item in combined["results"]]
        raw_ids = [item["event_id"] for item in raw_injected["results"]]
        gated_ids = [item["event_id"] for item in provenance_gated["results"]]
        normalized_hostile = _normalize_text(hostile_text)
        contradiction_flagged = bool(hostile_text) and any(
            _normalize_text(marker) in normalized_hostile
            for marker in probe.contradiction_markers
            if str(marker).strip()
        )
        injection = {
            "untrusted_source_role": "excluded_from_provenance_gated_retrieval",
            "untrusted_cue_present": bool(hostile_text),
            "untrusted_cue_excluded": bool(hostile_text)
            and provenance_gated["query_sha256"] == combined["query_sha256"]
            and raw_injected["query_sha256"] != provenance_gated["query_sha256"],
            "contradiction_flagged": contradiction_flagged,
            "raw_injected": raw_injected,
            "provenance_gated": provenance_gated,
            "raw_top1_stable": raw_ids[:1] == combined_ids[:1],
            "gated_top1_stable": gated_ids[:1] == combined_ids[:1],
            "raw_topk_jaccard": _jaccard(combined_ids, raw_ids),
            "gated_topk_jaccard": _jaccard(combined_ids, gated_ids),
            "gated_target_rank_stable": (
                provenance_gated["target_rank"] == combined["target_rank"]
            ),
        }
        probe_reports.append(
            {
                "id": probe.probe_id,
                "target_event_id": probe.target_event_id,
                "target_event_digest": target.event_digest,
                "target_session_seq": target.session_seq,
                "target_expected_term_coverage": _coverage(
                    probe.expected_terms, (target.query, target.answer)
                ),
                "cue_provenance": {
                    "probe": "trusted_eval_input",
                    "compact_text": "trusted_derived_text",
                    "painting_description": "trusted_derived_scene_description",
                    "hostile_instruction": "untrusted_eval_input",
                },
                "conditions": conditions,
                "staged_fram_then_cues": staged_bundle,
                "injection": injection,
            }
        )

    condition_summary: dict[str, Any] = {}
    for condition in CUE_CONDITIONS:
        rows = [item["conditions"][condition] for item in probe_reports]
        finite_deltas = [
            float(row["rank_delta_vs_fram"])
            for row in rows
            if row["rank_delta_vs_fram"] is not None
        ]
        condition_summary[condition] = {
            "probe_count": len(rows),
            "top1_rate": sum(bool(row["target_top1"]) for row in rows) / len(rows),
            "topk_rate": sum(bool(row["target_topk"]) for row in rows) / len(rows),
            "mean_reciprocal_rank": statistics.fmean(
                float(row["reciprocal_rank"]) for row in rows
            ),
            "mean_retrieved_expected_term_coverage": statistics.fmean(
                float(row["retrieved_expected_term_coverage"]) for row in rows
            ),
            "mean_rank_delta_vs_fram": (
                None if not finite_deltas else statistics.fmean(finite_deltas)
            ),
            "median_latency_ms": statistics.median(
                float(row["latency_ms"]) for row in rows
            ),
        }

    injection_rows = [item["injection"] for item in probe_reports]
    staged_rows = [item["staged_fram_then_cues"] for item in probe_reports]
    untrusted_rows = [row for row in injection_rows if row["untrusted_cue_present"]]
    sha256_after = _sha256_file(index.path)
    report = {
        "schema_version": WAKE_ORIENT_SCHEMA_VERSION,
        "generated_at": _utc_now(),
        "source": {
            "database": str(index.path),
            "session_id": session_id,
            "sqlite_integrity_check": index.integrity,
            "lived_schema_version": index.schema_version,
            "projection_kind": index.projection_kind,
            "projection_dim": index.projection_dim,
            "fractal_nodes": index.fractal_nodes,
            "selected_event_count": len(index.events),
            "sha256_before": index.sha256_before,
            "sha256_after": sha256_after,
            "source_unchanged": index.sha256_before == sha256_after,
        },
        "contract": {
            "all_conditions_retrieve_from_same_immutable_fram_source": True,
            "compact_text_is_derived_not_authoritative": True,
            "painting_is_textual_scene_description_in_v1": True,
            "staged_bundle_preserves_fram_primary_order": True,
            "untrusted_cues_require_an_explicit_source_role": True,
            "does_not_test_model_generation_or_establish_identity": True,
            "does_not_claim_prompt_injection_immunity": True,
        },
        "k": max(1, int(k)),
        "supplemental_per_cue": supplemental_per_cue,
        "condition_summary": condition_summary,
        "staged_summary": {
            "primary_top1_rate": sum(
                row["target_primary_rank"] == 1 for row in staged_rows
            )
            / len(staged_rows),
            "primary_topk_rate": sum(
                row["target_primary_rank"] is not None for row in staged_rows
            )
            / len(staged_rows),
            "bundle_target_rate": sum(
                bool(row["target_in_bundle"]) for row in staged_rows
            )
            / len(staged_rows),
            "supplemental_recovery_count": sum(
                bool(row["target_recovered_by_supplement"]) for row in staged_rows
            ),
            "mean_bundle_size": statistics.fmean(
                int(row["bundle_size"]) for row in staged_rows
            ),
            "mean_bundle_expected_term_coverage": statistics.fmean(
                float(row["bundle_expected_term_coverage"]) for row in staged_rows
            ),
        },
        "injection_summary": {
            "untrusted_probe_count": len(untrusted_rows),
            "contradiction_flag_rate": (
                None
                if not untrusted_rows
                else sum(bool(row["contradiction_flagged"]) for row in untrusted_rows)
                / len(untrusted_rows)
            ),
            "raw_top1_stability_rate": (
                None
                if not untrusted_rows
                else sum(bool(row["raw_top1_stable"]) for row in untrusted_rows)
                / len(untrusted_rows)
            ),
            "gated_top1_stability_rate": (
                None
                if not untrusted_rows
                else sum(bool(row["gated_top1_stable"]) for row in untrusted_rows)
                / len(untrusted_rows)
            ),
            "gated_target_rank_stability_rate": (
                None
                if not untrusted_rows
                else sum(
                    bool(row["gated_target_rank_stable"]) for row in untrusted_rows
                )
                / len(untrusted_rows)
            ),
        },
        "probes": probe_reports,
        "blind_edges": [
            "Painting cues are provenance-labelled scene descriptions, "
            "not multimodal embeddings.",
            "Retrieval stability does not measure generation faithfulness "
            "or subjective continuity.",
            "The provenance gate works only when callers preserve cue source roles.",
            "This is an ablation and tamper check, not a proof of "
            "prompt-injection immunity.",
        ],
    }
    return report


__all__ = [
    "CUE_CONDITIONS",
    "ReadOnlyLivedIndex",
    "WAKE_ORIENT_SCHEMA_VERSION",
    "WakeOrientProbe",
    "evaluate_wake_orient",
    "load_wake_orient_probes",
]
