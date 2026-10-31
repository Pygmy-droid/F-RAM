from __future__ import annotations

import hashlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient

import fram_serving.app as app_mod
from fram_serving.config import FRAMConfig
from fram_serving.lived_memory import (
    PROJECTION_KIND,
    LivedMemoryCorruptError,
    LivedMemoryStore,
)
from fram_serving.memory import CognitiveMemoryStore, WorkingMemoryStore
from fram_serving.observability import TraceLogWriter
from fram_serving.query_runner import QueryContext, run_query


def _vector(offset: float = 0.0, dim: int = 32) -> np.ndarray:
    return np.linspace(-1.0 + offset, 1.0 + offset, dim)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_lived_memory_survives_restart_with_lineage_and_projection(
    tmp_path: Path,
) -> None:
    root = tmp_path / "lived"
    store = LivedMemoryStore(root, target_dim=12, fractal_nodes=16)

    first = store.append_experience(
        query="The hearth opens",
        answer="A source event is retained.",
        embedding=_vector(),
        session_id="hearth",
        episode_id="episode-1",
        trace_id="trace-1",
    )
    second = store.append_experience(
        query="What continues?",
        answer="The next event retains its parent.",
        embedding=_vector(0.2),
        session_id="hearth",
        episode_id="episode-2",
        trace_id="trace-2",
    )

    restarted = LivedMemoryStore(root, target_dim=12, fractal_nodes=16)
    status = restarted.status()
    state = restarted.session_state("hearth")
    results = restarted.search(_vector(0.18), k=2, session_id="hearth")
    verification = restarted.verify()

    assert first["session_seq"] == 1
    assert second["session_seq"] == 2
    assert second["parent_event_id"] == first["event_id"]
    assert status["event_count"] == 2
    assert status["restart_persistent"] is True
    assert state is not None
    assert state["event_count"] == 2
    assert state["projection_dim"] == 12
    assert len(state["state_vector"]) == 12
    assert results[0]["episode_id"] == "episode-2"
    assert results[0]["projection_kind"] == PROJECTION_KIND
    assert verification == {
        "valid": True,
        "schema_version": 1,
        "projection_kind": PROJECTION_KIND,
        "event_count": 2,
        "session_count": 1,
        "errors": [],
    }


def test_lived_memory_keeps_session_lineages_distinct(tmp_path: Path) -> None:
    store = LivedMemoryStore(tmp_path / "lived", target_dim=8, fractal_nodes=8)
    a1 = store.append_experience(
        query="A1", answer="first A", embedding=_vector(), session_id="A"
    )
    b1 = store.append_experience(
        query="B1", answer="first B", embedding=_vector(0.1), session_id="B"
    )
    a2 = store.append_experience(
        query="A2", answer="second A", embedding=_vector(0.2), session_id="A"
    )

    assert a1["parent_event_id"] is None
    assert b1["parent_event_id"] is None
    assert a2["parent_event_id"] == a1["event_id"]
    assert store.session_state("A")["event_count"] == 2  # type: ignore[index]
    assert store.session_state("B")["event_count"] == 1  # type: ignore[index]
    assert store.verify()["valid"] is True


def test_lived_memory_requires_explicit_projection_shape_migration(
    tmp_path: Path,
) -> None:
    root = tmp_path / "lived"
    store = LivedMemoryStore(root, target_dim=12, fractal_nodes=16)
    store.append_experience(
        query="shape",
        answer="sealed",
        embedding=_vector(),
        session_id="shape-session",
    )

    with pytest.raises(LivedMemoryCorruptError, match="migration required"):
        LivedMemoryStore(root, target_dim=13, fractal_nodes=16).status()
    with pytest.raises(LivedMemoryCorruptError, match="migration required"):
        LivedMemoryStore(root, target_dim=12, fractal_nodes=32).status()


def test_reopened_read_operations_are_database_hash_stable(tmp_path: Path) -> None:
    root = tmp_path / "lived"
    store = LivedMemoryStore(root, target_dim=8, fractal_nodes=8)
    store.append_experience(
        query="stable read",
        answer="does not rewrite schema metadata",
        embedding=_vector(),
        session_id="hash-stability",
    )
    store.status()
    before = _sha256(store.path)

    reopened = LivedMemoryStore(root, target_dim=8, fractal_nodes=8)
    assert reopened.status()["event_count"] == 1
    assert reopened.session_state("hash-stability") is not None
    assert reopened.search(_vector(), k=1)[0]["query"] == "stable read"
    assert reopened.verify()["valid"] is True

    assert _sha256(store.path) == before


def test_lived_memory_detects_persisted_tampering(tmp_path: Path) -> None:
    store = LivedMemoryStore(tmp_path / "lived", target_dim=8, fractal_nodes=8)
    record = store.append_experience(
        query="source truth",
        answer="unaltered",
        embedding=_vector(),
        session_id="tamper-test",
    )

    with sqlite3.connect(store.path) as connection:
        connection.execute(
            "UPDATE lived_events SET answer_text=? WHERE event_id=?",
            ("silently changed", record["event_id"]),
        )

    verification = LivedMemoryStore(
        tmp_path / "lived", target_dim=8, fractal_nodes=8
    ).verify()
    assert verification["valid"] is False
    assert verification["errors"][0]["event_id"] == record["event_id"]
    assert "digest mismatch" in verification["errors"][0]["error"]


def test_lived_memory_serializes_concurrent_appends(tmp_path: Path) -> None:
    store = LivedMemoryStore(
        tmp_path / "lived",
        target_dim=8,
        fractal_nodes=8,
        busy_timeout_seconds=10.0,
    )

    def append(index: int) -> dict[str, Any]:
        return store.append_experience(
            query=f"event {index}",
            answer=f"answer {index}",
            embedding=_vector(index / 100.0),
            session_id="shared",
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(append, range(12)))

    assert sorted(record["session_seq"] for record in records) == list(range(1, 13))
    assert store.session_state("shared")["event_count"] == 12  # type: ignore[index]
    assert store.verify()["valid"] is True


class _StableOrchestrator:
    def run(self, text: str, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        record = {
            "id": f"trace-{text}",
            "time": "2026-08-11T12:00:00+00:00",
            "query": text,
            "citations": ["doc:source"],
            "domain": "general",
            "task": "qa",
            "trace": {
                "trace_id": f"trace-{text}",
                "query_id": f"trace-{text}",
                "confidence": {"decision": "anchors"},
                "coverage": {},
                "selection": {
                    "origin_counts": {"document": 1},
                    "selected_ids": ["doc:source"],
                    "budgets": {"reads": 1.0, "tokens": 8.0, "pairs": 0.0, "cost": 1.0},
                },
                "latency_ms": {},
            },
        }
        return {
            "trace_id": record["id"],
            "answer": f"answer for {text}",
            "citations": list(record["citations"]),
            "coverage": {},
            "record": record,
        }


def _runtime_context(tmp_path: Path) -> QueryContext:
    cfg = FRAMConfig().model_copy(
        update={
            "STORAGE_ROOT": tmp_path / "storage",
            "cognitive_memory_k": 4,
            "lived_memory_enabled": True,
            "lived_memory_target_dim": 8,
            "lived_memory_fractal_nodes": 8,
            "memory_capsule_enabled": False,
            "fractal_enabled": False,
            "fractal_influence_enabled": False,
        }
    )
    trace_dir = tmp_path / "storage" / "traces"
    lived_store = LivedMemoryStore(
        tmp_path / "storage" / "memory" / "lived",
        target_dim=8,
        fractal_nodes=8,
    )
    return QueryContext(
        cfg=cfg,
        orchestrator=_StableOrchestrator(),
        memory_store=WorkingMemoryStore(tmp_path / "storage" / "memory" / "working"),
        cognitive_store=CognitiveMemoryStore(
            tmp_path / "storage" / "memory" / "cognitive", config=cfg
        ),
        capsule_store=None,
        get_memory_vectorizer=lambda: None,
        encode_cognitive_text=lambda text: (
            [float(value) for value in _vector(len(text) / 1000.0, dim=32)],
            "test",
        ),
        apply_phase_d_memory_bridge=lambda _text, candidates, _debug: (
            candidates,
            None,
        ),
        cooldown_active=lambda _doc_id, _ts: False,
        register_cooldown=lambda _doc_id, _ts: None,
        cooldown_window=timedelta(minutes=1),
        resolve_time_sensitivity=lambda _task, _domain: "medium",
        ensure_doc_cache=lambda: {},
        trace_writer=TraceLogWriter(trace_dir),
        observability_dir=tmp_path / "storage" / "observability",
        trace_dir=trace_dir,
        store_prob=lambda *_args, **_kwargs: None,
        log_memory_event=lambda *_args, **_kwargs: None,
        archive_writer=None,
        archive_kind="query",
        lived_memory_store=lived_store,
    )


def _request(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        text=text,
        as_of=None,
        version_id=None,
        budget_reads=None,
        memory_session="living-session",
        principal=None,
        domain="general",
        task="qa",
    )


def test_query_runtime_writes_and_recalls_lived_memory(tmp_path: Path) -> None:
    ctx = _runtime_context(tmp_path)
    first = run_query(_request("first"), ctx)
    second = run_query(_request("second"), ctx)

    assert first["lived_memory_write_ok"] is True
    assert second["lived_memory_write_ok"] is True
    assert second["trace"]["lived_memory_write"]["session_seq"] == 2
    assert ctx.lived_memory_store is not None
    assert ctx.lived_memory_store.status()["event_count"] == 2
    assert ctx.lived_memory_store.verify()["valid"] is True
    recalled = ctx.lived_memory_store.search(_vector(0.004), k=2)
    assert {item["query"] for item in recalled} == {"first", "second"}


def test_lived_memory_api_exposes_persisted_state(tmp_path: Path, monkeypatch) -> None:
    cfg = app_mod.CFG.model_copy(
        update={
            "STORAGE_ROOT": tmp_path / "storage",
            "embedding_dim": 32,
            "cognitive_memory_embedding_backend": "hashing",
            "lived_memory_enabled": True,
            "lived_memory_target_dim": 8,
            "lived_memory_fractal_nodes": 8,
        }
    )
    store = LivedMemoryStore(
        tmp_path / "storage" / "memory" / "lived",
        target_dim=8,
        fractal_nodes=8,
    )
    monkeypatch.setattr(app_mod, "CFG", cfg)
    monkeypatch.setattr(app_mod, "_LIVED_STORE", store)
    monkeypatch.setattr(app_mod, "_MEMORY_VECTORIZER", None)
    monkeypatch.setattr(app_mod, "_MEMORY_BACKEND", None)
    embedding, backend = app_mod._encode_cognitive_text("remember the ember")
    assert embedding is not None
    store.append_experience(
        query="remember the ember",
        answer="it persists",
        embedding=embedding,
        embedding_backend=backend,
        session_id="api-session",
    )

    with TestClient(app_mod.app) as client:
        status = client.get("/memory/lived/status")
        search = client.get(
            "/memory/lived/search",
            params={"query": "remember the ember", "k": 1},
        )
        session = client.get("/memory/lived/session/api-session")
        verify = client.get("/memory/lived/verify")

    assert status.status_code == 200
    assert status.json()["event_count"] == 1
    assert search.status_code == 200
    assert search.json()["items"][0]["query"] == "remember the ember"
    assert session.status_code == 200
    assert session.json()["projection_dim"] == 8
    assert verify.status_code == 200
    assert verify.json()["valid"] is True
