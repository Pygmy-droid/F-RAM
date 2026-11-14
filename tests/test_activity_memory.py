import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from examples.activity_memory.demo import demo
from fram_serving.activity_memory import (
    ActivityIntegrityError,
    ActivityMemory,
    EvidenceRef,
    Validation,
)


def emit(recorder, ordinal, tick, parents=(), payload=b"\x00\xff\r\n"):
    return recorder.observe(
        ordinal=ordinal,
        logical_time=tick,
        kind="send",
        source="a",
        destination="b",
        payload=payload,
        observed_parents=parents,
    )


def test_capture_reopen_and_navigation(tmp_path):
    memory = ActivityMemory(tmp_path)
    recorder = memory.start("execution", {"instrument": "test", "clock": "ticks"})
    first = emit(recorder, 0, 4)
    second = emit(recorder, 1, 4)
    assert emit(recorder, 1, 4) == second
    recorder.observe(
        ordinal=2,
        logical_time=5,
        kind="commit",
        source="b",
        destination="b",
        payload=b"result",
        observed_parents=(0, 1),
        unresolved_links=("producer of external clock signal",),
    )
    reopened = ActivityMemory(tmp_path)
    assert reopened.execution("execution")["provenance"] == {
        "instrument": "test",
        "clock": "ticks",
    }
    assert (
        bytes.fromhex(reopened.events("execution")[0]["payload_hex"]) == b"\x00\xff\r\n"
    )
    assert reopened.events("execution")[0]["digest"] == first.digest
    assert [r["ordinal"] for r in reopened.events("execution", after=0, limit=1)] == [1]
    latest = reopened.events("execution", from_time=5)
    assert [r["ordinal"] for r in latest] == [2]
    assert latest[0]["unresolved_links"] == ["producer of external clock signal"]
    assert [r["ordinal"] for r in reopened.neighbors("execution", 2, limit=1)] == [0]
    assert [r["ordinal"] for r in reopened.neighbors("execution", 2, after=0)] == [1]
    assert [
        r["ordinal"] for r in reopened.neighbors("execution", 0, downstream=True)
    ] == [2]
    assert reopened.verify() == {
        "executions": 1,
        "events": 3,
        "interpretation_versions": 0,
    }


def test_source_rejects_conflicting_retries_and_invalid_order(tmp_path):
    memory = ActivityMemory(tmp_path)
    recorder = memory.start("execution", {"instrument": "test"})
    with pytest.raises(ValueError, match="different provenance"):
        memory.start("execution", {})
    emit(recorder, 0, 1)
    with pytest.raises(ValueError, match="conflicting"):
        emit(recorder, 0, 1, payload=b"other")
    with pytest.raises(ValueError, match="contiguous"):
        emit(recorder, 2, 2)
    with pytest.raises(ValueError, match="backward"):
        emit(recorder, 1, 0)
    with pytest.raises(ValueError, match="earlier"):
        emit(recorder, 1, 1, (1,))
    assert memory.verify()["events"] == 1


def test_concurrent_identical_retry(tmp_path):
    memory = ActivityMemory(tmp_path)
    recorder = memory.start("execution", {})
    with ThreadPoolExecutor(max_workers=2) as executor:
        replies = list(executor.map(lambda _: emit(recorder, 0, 1), range(2)))
    assert replies[0] == replies[1]
    assert memory.verify()["events"] == 1


def accepted(claims, evidence):
    assert evidence[0]["provenance"] == {"instrument": "test"}
    return Validation("deterministic-test/v1", True, "Matched observed evidence.")


def test_validation_versions_abstention_and_rollback(tmp_path, monkeypatch):
    memory = ActivityMemory(tmp_path)
    ref = emit(memory.start("execution", {"instrument": "test"}), 0, 0)
    assert memory.inference("rule", "query").status == "abstain"
    with pytest.raises(ValueError, match="did not accept"):
        memory.publish(
            "rule", {"query": 1}, [ref], lambda *_: Validation("x", False, "wrong")
        )
    with pytest.raises(ActivityIntegrityError, match="missing or mismatched"):
        memory.publish(
            "rule", {"query": 1}, [EvidenceRef("execution", 0, "wrong")], accepted
        )
    assert memory.history("rule") == []
    first = memory.publish("rule", {"query": 1}, [ref], accepted)
    with pytest.raises(ValueError, match="version conflict"):
        memory.publish("rule", {"query": 9}, [ref], accepted)
    second = memory.publish(
        "rule", {"query": 2}, [ref], accepted, expected_version=first
    )
    third = memory.rollback("rule", expected_version=second, restore=first)
    assert memory.rollback("rule", expected_version=third) == 4
    reopened = ActivityMemory(tmp_path)
    assert reopened.verify()["interpretation_versions"] == 4
    with monkeypatch.context() as scoped:

        def forbid(*args):
            pytest.fail("inference reopened raw evidence")

        scoped.setattr(ActivityMemory, "_evidence", forbid)
        scoped.setattr(ActivityMemory, "events", forbid)
        assert reopened.inference("rule", "query", as_of=second).value == 2
        assert reopened.inference("rule", "query", as_of=third).value == 1
        assert reopened.inference("rule", "query", as_of=0).status == "abstain"
        assert reopened.inference("rule", "unknown", as_of=third).status == "abstain"
        assert reopened.inference("rule", "query").status == "abstain"
    assert reopened.events("execution")[0]["digest"] == ref.digest


def test_append_only_sql_and_audit_detects_rewrite(tmp_path):
    memory = ActivityMemory(tmp_path)
    emit(memory.start("execution", {}), 0, 0)
    with sqlite3.connect(memory.path) as db:
        with pytest.raises(sqlite3.IntegrityError, match="append only"):
            db.execute("DELETE FROM activity_event")
        db.execute("DROP TRIGGER immutable_activity_event_update")
        db.execute("UPDATE activity_event SET digest='rewritten'")
    with pytest.raises(ActivityIntegrityError, match="event chain"):
        memory.verify()


def test_instrumented_runtime_lifecycle(tmp_path):
    result = demo(tmp_path)
    assert result["colliding_endpoints"] == [4, 4, 4]
    assert result["first_tick_routes"]["nominal-dual"] == ["direct", "relay", "monitor"]
    assert (
        result["first_tick_routes"]["nominal-direct"]
        != result["first_tick_routes"]["nominal-relay"]
    )
    assert result["published"]["delta_for_unit_increase_on_each_lane"] == 3
    assert result["paired_delta_sum"] == result["observed_joint_delta"] == 3
    assert all(
        result[stage]["status"] == "abstain"
        for stage in ("before", "limited", "partial", "rollback")
    )
    assert result["source_exact"]
    assert result["audit"] == {
        "executions": 14,
        "events": 184,
        "interpretation_versions": 3,
    }
