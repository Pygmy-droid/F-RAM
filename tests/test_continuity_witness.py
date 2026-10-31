from __future__ import annotations

import copy
import json
import os
import threading
import time
from pathlib import Path

import pytest

from fram_serving.continuity import (
    ACTIVE_GATE_ALLOWLIST,
    DECISION_ALLOWLIST,
    SOURCE_STATES,
    WITNESS_SCHEMA_VERSION,
    ContinuityWitnessCorruptError,
    ContinuityWitnessLockError,
    ContinuityWitnessNotFoundError,
    ContinuityWitnessTamperedError,
    ContinuityWitnessWriteError,
    ContinuityWitnessWriter,
    build_continuity_witness,
    load_latest_continuity_witness,
    recompute_continuity_witness_digest,
    validate_continuity_witness_digest,
)


def _finalized_result() -> dict:
    return {
        "trace_id": "trace-17",
        "answer": "excluded from the witness",
        "citations": ["docs/a.md:chunk1", "docs/b.md:chunk2"],
        "record": {
            "id": "trace-17",
            "time": "2026-07-28T12:34:56+02:00",
            "query": "also excluded",
            "citations": ["record citation is not selected when the result is final"],
            "trace": {
                "trace_id": "trace-17",
                "confidence": {
                    "decision": "anchors",
                    "features": {"must": "not leak"},
                },
                "selection": {
                    "unselected_ids": ["not-selected"],
                    "memory_layers": {
                        "merged": {
                            "ids": ["doc-a", "memory-b", "doc-a"],
                            "origins": {
                                "ann": 2,
                                "cognitive_memory": 1,
                                "not_allowlisted": 999,
                            },
                        }
                    },
                    "budgets": {
                        "reads": 3,
                        "tokens": 12.5,
                        "pairs": 2,
                        "cost": 3.125,
                        "reads_limit": 99,
                        "lambda_tok": 0.001,
                    },
                },
                "active_gates": {
                    "cognitive_ann_bridge": True,
                    "fractal_ranking": False,
                    "secret_future_gate": True,
                },
                "cognitive_episode_write": {
                    "ok": True,
                    "episode_id": "episode-9",
                    "error": "must not leak",
                },
                "memory_capsule_write": {
                    "ok": False,
                    "skipped": True,
                    "reason": "disabled",
                },
                "archive_write": {
                    "ok": True,
                    "event_id": "event-4",
                    "trace_id": "trace-17",
                    "chain_hash": "must not leak",
                },
                "scores": [0.99],
            },
        },
        "unexpected": {"private": "must not leak"},
    }


def test_projection_is_deterministic_versioned_and_strictly_allowlisted() -> None:
    source = _finalized_result()

    first = build_continuity_witness(source, feature_enabled=True)
    second = build_continuity_witness(copy.deepcopy(source), feature_enabled=True)

    assert first == second
    assert first["schema_version"] == WITNESS_SCHEMA_VERSION
    assert first["state"] == "available"
    assert first["source"]["digest"] == recompute_continuity_witness_digest(first)
    assert validate_continuity_witness_digest(first) is True
    assert set(first) == {
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
    encoded = json.dumps(first)
    for forbidden in (
        "excluded from the witness",
        "also excluded",
        "private",
        "secret_future_gate",
        "must not leak",
        "scores",
    ):
        assert forbidden not in encoded


def test_hidden_raw_source_fields_do_not_change_the_projection_or_digest() -> None:
    source = _finalized_result()
    control = build_continuity_witness(source, feature_enabled=True)

    source["answer"] = float("nan")
    source["record"]["query"] = {"not_json": {1, 2, 3}}
    source["unexpected"] = object()
    changed = build_continuity_witness(source, feature_enabled=True)

    assert changed == control
    assert changed["source"]["digest"] == control["source"]["digest"]


def test_trace_edge_resolution_schema_gates_origins_and_writes() -> None:
    witness = build_continuity_witness(
        _finalized_result(),
        feature_enabled=True,
        expected_trace_id="trace-17",
        active_gates={
            "archive_write": True,
            "continuity_witness": False,
            "memory_capsule": True,
            "not_allowlisted": True,
        },
    )

    assert witness["trace_link"] == {
        "valid": True,
        "ids": {
            "result": "trace-17",
            "record": "trace-17",
            "trace": "trace-17",
            "expected": "trace-17",
        },
        "errors": [],
    }
    assert witness["active_gates"] == [
        "archive_write",
        "continuity_witness",
        "memory_capsule",
    ]
    assert set(witness["active_gates"]) <= ACTIVE_GATE_ALLOWLIST
    assert witness["decision"] == "anchors"
    assert witness["decision"] in DECISION_ALLOWLIST
    assert witness["observed_at_utc"] == "2026-07-28T10:34:56Z"
    assert witness["selection"]["origin_counts"] == {
        "ann": 2,
        "cognitive_memory": 1,
    }
    assert witness["selection"]["selected_ids"] == ["doc-a", "memory-b"]
    assert witness["selection"]["budgets"] == {
        "reads": 3.0,
        "tokens": 12.5,
        "pairs": 2.0,
        "cost": 3.125,
    }
    assert witness["writes"] == {
        "archive": {
            "status": "success",
            "event_id": "event-4",
            "trace_id": "trace-17",
        },
        "cognitive_episode": {
            "status": "success",
            "episode_id": "episode-9",
        },
        "memory_capsule": {
            "status": "skipped",
            "reason": "disabled",
        },
    }


def test_direct_finalized_record_resolves_without_a_result_wrapper() -> None:
    record = copy.deepcopy(_finalized_result()["record"])

    witness = build_continuity_witness(record, expected_trace_id="trace-17")

    assert witness["state"] == "available"
    assert witness["trace_id"] == "trace-17"
    assert witness["trace_link"] == {
        "valid": True,
        "ids": {
            "result": None,
            "record": "trace-17",
            "trace": "trace-17",
            "expected": "trace-17",
        },
        "errors": [],
    }
    assert witness["selection"]["citations"] == [
        "record citation is not selected when the result is final"
    ]


def test_unselected_candidates_are_not_promoted_to_selected_ids_or_citations() -> None:
    source = _finalized_result()
    source["record"]["trace"]["selection"]["unselected_ids"] = [
        "negative-a",
        "docs/negative.md:chunk8",
    ]

    witness = build_continuity_witness(source)

    assert witness["selection"]["selected_ids"] == ["doc-a", "memory-b"]
    assert witness["selection"]["citations"] == [
        "docs/a.md:chunk1",
        "docs/b.md:chunk2",
    ]
    assert "negative-a" not in witness["selection"]["selected_ids"]
    assert "docs/negative.md:chunk8" not in witness["selection"]["citations"]


def test_invalid_decision_budget_and_record_time_are_omitted_and_mark_corrupt() -> None:
    source = _finalized_result()
    trace = source["record"]["trace"]
    trace["confidence"]["decision"] = "secret-policy"
    trace["selection"]["budgets"] = {
        "reads": float("inf"),
        "tokens": -1,
        "pairs": True,
        "cost": 4,
    }
    source["record"]["time"] = "2026-07-28 12:34:56"

    witness = build_continuity_witness(source)

    assert witness["state"] == "corrupt"
    assert witness["decision"] is None
    assert witness["observed_at_utc"] is None
    assert witness["selection"]["budgets"] == {"cost": 4.0}
    assert {
        "decision_invalid",
        "budget_invalid:reads",
        "budget_invalid:tokens",
        "budget_invalid:pairs",
        "observed_at_utc_timezone_missing",
    }.issubset(witness["source"]["reasons"])


def test_missing_corrupt_and_tampered_sources_resolve_explicitly() -> None:
    missing = build_continuity_witness(None)
    corrupt = build_continuity_witness(["not", "a", "record"])
    tampered_digest = build_continuity_witness(
        _finalized_result(),
        expected_projection_digest="0" * 64,
    )
    mismatched = _finalized_result()
    mismatched["record"]["trace"]["trace_id"] = "other-trace"
    tampered_link = build_continuity_witness(mismatched)

    assert missing["state"] == "unknown"
    assert "record_missing" in missing["source"]["reasons"]
    assert corrupt["state"] == "corrupt"
    assert "source_not_mapping" in corrupt["source"]["reasons"]
    assert tampered_digest["state"] == "tampered"
    assert "projection_digest_mismatch" in tampered_digest["source"]["reasons"]
    assert validate_continuity_witness_digest(tampered_digest) is True
    assert tampered_link["state"] == "tampered"
    assert tampered_link["trace_link"]["valid"] is False
    assert "trace_id_mismatch" in tampered_link["trace_link"]["errors"]
    assert SOURCE_STATES == {
        "available",
        "stale",
        "corrupt",
        "tampered",
        "unknown",
    }


@pytest.mark.parametrize(
    ("requested", "expected"),
    [
        ("available", "available"),
        ("stale", "stale"),
        ("corrupt", "corrupt"),
        ("tampered", "tampered"),
        ("unknown", "unknown"),
        ("not-a-state", "unknown"),
    ],
)
def test_all_source_states_are_explicit(requested: str, expected: str) -> None:
    witness = build_continuity_witness(
        _finalized_result(),
        source_state=requested,
    )
    assert witness["state"] == expected
    assert witness["source"]["state"] == expected


def test_feature_off_is_document_only_and_writer_does_not_create_log(tmp_path) -> None:
    witness = build_continuity_witness(_finalized_result(), feature_enabled=False)
    writer = ContinuityWitnessWriter(tmp_path)

    outcome = writer.append(witness)

    assert witness["mode"] == "document_only"
    assert "continuity_witness" not in witness["active_gates"]
    assert outcome["skipped"] is True
    assert outcome["reason"] == "feature_disabled_document_only"
    assert not writer.path.exists()


def test_append_only_writer_is_idempotent_by_witness_and_trace_id(tmp_path) -> None:
    witness = build_continuity_witness(_finalized_result(), feature_enabled=True)
    writer = ContinuityWitnessWriter(tmp_path)

    first = writer.append(witness)
    second = writer.append(copy.deepcopy(witness))

    assert first["appended"] is True
    assert second["appended"] is False
    assert second["duplicate"] is True
    lines = writer.path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == witness
    assert not writer.lock_path.exists()


def test_v2_sidecar_never_reads_rewrites_or_deletes_historical_v1_log(
    tmp_path: Path,
) -> None:
    historical_v1 = tmp_path / "continuity_witness.v1.jsonl"
    historical_bytes = b'{"schema_version":"continuity-witness.v1"}\n'
    historical_v1.write_bytes(historical_bytes)
    witness = build_continuity_witness(_finalized_result(), feature_enabled=True)
    writer = ContinuityWitnessWriter(tmp_path)

    assert writer.path.name == "continuity_witness.v2.jsonl"
    assert witness["schema_version"] == "continuity-witness.v2"
    assert writer.append(witness)["appended"] is True
    assert load_latest_continuity_witness(tmp_path) == witness
    assert historical_v1.read_bytes() == historical_bytes


def test_tampered_projection_is_rejected_for_write_and_classified_on_read(
    tmp_path: Path,
) -> None:
    witness = build_continuity_witness(_finalized_result(), feature_enabled=True)
    tampered = copy.deepcopy(witness)
    tampered["selection"]["citations"][0] = "docs/tampered.md:chunk9"

    assert validate_continuity_witness_digest(tampered) is False
    writer = ContinuityWitnessWriter(tmp_path)
    with pytest.raises(ContinuityWitnessWriteError):
        writer.append(tampered)
    assert not writer.path.exists()

    writer.path.write_text(json.dumps(tampered) + "\n", encoding="utf-8")
    with pytest.raises(ContinuityWitnessTamperedError):
        load_latest_continuity_witness(writer.path)


def test_stale_orphan_lock_is_safely_recovered(tmp_path: Path) -> None:
    witness = build_continuity_witness(_finalized_result(), feature_enabled=True)
    writer = ContinuityWitnessWriter(
        tmp_path,
        lock_timeout_seconds=0.2,
        stale_lock_seconds=0.01,
    )
    writer.root.mkdir(parents=True, exist_ok=True)
    writer.lock_path.write_text(
        json.dumps(
            {
                "pid": 2_147_483_000,
                "created_at_unix": time.time() - 60.0,
                "token": "orphan-lock",
            }
        ),
        encoding="utf-8",
    )

    outcome = writer.append(witness)

    assert outcome["appended"] is True
    assert not writer.lock_path.exists()


def test_active_lock_is_never_deleted_and_times_out_quickly(
    tmp_path: Path,
) -> None:
    witness = build_continuity_witness(_finalized_result(), feature_enabled=True)
    writer = ContinuityWitnessWriter(
        tmp_path,
        lock_timeout_seconds=0.03,
        stale_lock_seconds=0.001,
    )
    writer.root.mkdir(parents=True, exist_ok=True)
    active_metadata = {
        "pid": os.getpid(),
        "created_at_unix": time.time() - 60.0,
        "token": "active-lock",
    }
    writer.lock_path.write_text(
        json.dumps(active_metadata),
        encoding="utf-8",
    )

    with pytest.raises(ContinuityWitnessLockError):
        writer.append(witness)

    assert json.loads(writer.lock_path.read_text(encoding="utf-8")) == active_metadata
    writer.lock_path.unlink()


def test_reader_waits_for_concurrent_writer_and_never_observes_mid_update(
    tmp_path: Path,
) -> None:
    first_source = _finalized_result()
    first = build_continuity_witness(first_source, feature_enabled=True)
    writer = ContinuityWitnessWriter(tmp_path, lock_timeout_seconds=1.0)
    assert writer.append(first)["appended"] is True

    second_source = _finalized_result()
    second_source["trace_id"] = "trace-18"
    second_source["record"]["id"] = "trace-18"
    second_source["record"]["trace"]["trace_id"] = "trace-18"
    second = build_continuity_witness(second_source, feature_enabled=True)
    writer_has_lock = threading.Event()
    permit_writer = threading.Event()
    reader_done = threading.Event()
    results: dict[str, object] = {}

    class BlockingWriter(ContinuityWitnessWriter):
        def _existing_match(self, witness):
            writer_has_lock.set()
            assert permit_writer.wait(timeout=1.0)
            return super()._existing_match(witness)

    blocking_writer = BlockingWriter(tmp_path, lock_timeout_seconds=1.0)

    def write_second() -> None:
        results["write"] = blocking_writer.append(second)

    def read_latest() -> None:
        try:
            results["read"] = load_latest_continuity_witness(
                tmp_path,
                lock_timeout_seconds=1.0,
            )
        finally:
            reader_done.set()

    writer_thread = threading.Thread(target=write_second)
    writer_thread.start()
    assert writer_has_lock.wait(timeout=1.0)
    reader_thread = threading.Thread(target=read_latest)
    reader_thread.start()
    time.sleep(0.05)
    assert reader_done.is_set() is False

    permit_writer.set()
    writer_thread.join(timeout=2.0)
    reader_thread.join(timeout=2.0)

    assert writer_thread.is_alive() is False
    assert reader_thread.is_alive() is False
    assert results["write"]["appended"] is True
    assert results["read"] == second


def test_read_only_loader_returns_last_append_order_witness_from_root_or_path(
    tmp_path: Path,
) -> None:
    writer = ContinuityWitnessWriter(tmp_path)
    first_source = _finalized_result()
    first = build_continuity_witness(first_source, feature_enabled=True)
    assert writer.append(first)["appended"] is True

    second_source = _finalized_result()
    second_source["trace_id"] = "trace-18"
    second_source["record"]["id"] = "trace-18"
    second_source["record"]["trace"]["trace_id"] = "trace-18"
    second_source["record"]["time"] = "2026-07-28T11:00:00Z"
    second = build_continuity_witness(second_source, feature_enabled=True)
    assert writer.append(second)["appended"] is True

    assert load_latest_continuity_witness(tmp_path) == second
    assert load_latest_continuity_witness(writer.path) == second


def test_read_only_loader_has_typed_missing_empty_and_corrupt_errors(
    tmp_path: Path,
) -> None:
    with pytest.raises(ContinuityWitnessNotFoundError):
        load_latest_continuity_witness(tmp_path)

    path = tmp_path / "manual.jsonl"
    path.write_text("\n", encoding="utf-8")
    with pytest.raises(ContinuityWitnessNotFoundError):
        load_latest_continuity_witness(path)

    path.write_text('{"schema_version":', encoding="utf-8")
    with pytest.raises(ContinuityWitnessCorruptError):
        load_latest_continuity_witness(path)

    path.write_text('{"schema_version":"wrong"}\n', encoding="utf-8")
    with pytest.raises(ContinuityWitnessCorruptError):
        load_latest_continuity_witness(path)

    document_only = build_continuity_witness(_finalized_result())
    path.write_text(json.dumps(document_only) + "\n", encoding="utf-8")
    with pytest.raises(ContinuityWitnessCorruptError):
        load_latest_continuity_witness(path)


def test_same_trace_with_different_projection_is_a_non_appending_conflict(
    tmp_path,
) -> None:
    source = _finalized_result()
    first_witness = build_continuity_witness(source, feature_enabled=True)
    writer = ContinuityWitnessWriter(tmp_path)
    assert writer.append(first_witness)["appended"] is True

    source["citations"] = ["docs/changed.md:chunk3"]
    changed_witness = build_continuity_witness(source, feature_enabled=True)
    outcome = writer.append(changed_witness)

    assert outcome["conflict"] is True
    assert outcome["appended"] is False
    assert len(writer.path.read_text(encoding="utf-8").splitlines()) == 1


def test_projection_never_mutates_the_finalized_source() -> None:
    source = _finalized_result()
    before = copy.deepcopy(source)

    build_continuity_witness(
        source,
        feature_enabled=True,
        active_gates={"archive_write": True},
    )

    assert source == before
