import json
import pytest

from fastapi.testclient import TestClient

import fram_serving.app as app
from fram_serving.memory import CognitiveMemoryStore, WorkingMemoryStore


def _log_records(tmp_path):
    obs_root = tmp_path / "storage" / app.CFG.STORAGE_SUBFOLDERS.get("observability", "observability")
    log_path = obs_root / "memory_sessions.jsonl"
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_memory_session_create_list_clear(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "CFG", app.CFG.model_copy(update={"STORAGE_ROOT": tmp_path / "storage"}))
    monkeypatch.setattr(app, "_MEMORY_STORE", WorkingMemoryStore(tmp_path / "memory"))

    with TestClient(app.app) as client:
        resp = client.post("/memory", json={})
        assert resp.status_code == 200
        created_payload = resp.json()
        session = created_payload["session"]
        session_id = session["id"]
        assert created_payload["created"] is True
        assert session["status"] == "active"

        resp = client.post(f"/memory/{session_id}", json={"text": "remember this"})
        assert resp.status_code == 200
        entry_id = resp.json()["id"]

        resp = client.get(f"/memory/{session_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["session"]["status"] == "active"
        assert body["session"]["entry_count"] == 1
        assert body["entries"] and body["entries"][0]["id"] == entry_id

        resp = client.get("/memory")
        sessions = resp.json()["sessions"]
        assert any(item["id"] == session_id and item["entry_count"] == 1 for item in sessions)

        resp = client.delete(f"/memory/{session_id}")
        assert resp.status_code == 200
        assert resp.json()["session"]["entry_count"] == 0

    records = _log_records(tmp_path)
    events = {rec.get("event") for rec in records}
    assert {"create", "append", "clear"}.issubset(events)


@pytest.mark.slow
def test_memory_session_lifecycle_controls(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "CFG", app.CFG.model_copy(update={"STORAGE_ROOT": tmp_path / "storage"}))
    monkeypatch.setattr(app, "_MEMORY_STORE", WorkingMemoryStore(tmp_path / "memory"))
    monkeypatch.setattr(app, "_DOC_CACHE", None, raising=False)
    monkeypatch.setattr(app, "_ORCHESTRATOR", None, raising=False)

    with TestClient(app.app) as client:
        create_resp = client.post("/memory", json={"session_id": "test-session"})
        session_id = create_resp.json()["session"]["id"]
        client.post(f"/memory/{session_id}", json={"text": "memory snippet about OrthoRoute"})

        resp = client.post(f"/memory/{session_id}/control", json={"action": "pause"})
        assert resp.status_code == 200
        assert resp.json()["session"]["status"] == "paused"

        resp = client.post(f"/memory/{session_id}", json={"text": "should not append"})
        assert resp.status_code == 409

        paused_query = client.post("/query", json={"text": "What is in memory?", "memory_session": session_id})
        assert paused_query.status_code == 200
        paused_trace = paused_query.json()["trace"]["memory"]
        assert paused_trace["status"] == "paused"
        assert paused_trace["used"] == 0
        assert paused_trace["available"] >= 1

        resp = client.post(f"/memory/{session_id}/control", json={"action": "resume"})
        assert resp.status_code == 200
        assert resp.json()["session"]["status"] == "active"

        active_query = client.post("/query", json={"text": "What is in memory now?", "memory_session": session_id})
        assert active_query.status_code == 200
        active_payload = active_query.json()
        active_trace = active_payload["trace"]["memory"]
        assert active_trace["status"] == "active"
        assert active_trace["used"] >= 1
        assert any(citation.startswith(f"memory:{session_id}") for citation in active_payload["citations"])
        assert "OrthoRoute" in active_payload["answer"]

        resp = client.post(f"/memory/{session_id}/control", json={"action": "end"})
        assert resp.status_code == 200
        assert resp.json()["session"]["status"] == "ended"

        ended_query = client.post("/query", json={"text": "What about ended?", "memory_session": session_id})
        assert ended_query.status_code == 200
        ended_trace = ended_query.json()["trace"]["memory"]
        assert ended_trace["status"] == "ended"
        assert ended_trace["used"] == 0

        resp = client.post(f"/memory/{session_id}", json={"text": "still blocked"})
        assert resp.status_code == 409

    records = _log_records(tmp_path)
    assert any(rec.get("event") == "control" and rec.get("action") == "pause" for rec in records)
    assert any(rec.get("event") == "query" and rec.get("status") == "active" for rec in records)
    assert any(rec.get("event") == "query" and rec.get("status") == "ended" for rec in records)


def test_cognitive_memory_surfaces_across_runs(tmp_path, monkeypatch):
    cfg = app.CFG.model_copy(
        update={
            "STORAGE_ROOT": tmp_path / "storage",
            "cognitive_memory_k": 3,
            "cognitive_memory_embedding_backend": "hashing",
        }
    )
    monkeypatch.setattr(app, "CFG", cfg)
    monkeypatch.setattr(app, "_MEMORY_STORE", WorkingMemoryStore(tmp_path / "memory"))
    monkeypatch.setattr(
        app,
        "_COG_STORE",
        CognitiveMemoryStore(
            tmp_path / "storage" / "memory" / "cognitive",
            config=cfg,
        ),
    )
    monkeypatch.setattr(app, "_MEMORY_VECTORIZER", None, raising=False)
    monkeypatch.setattr(app, "_MEMORY_BACKEND", None, raising=False)
    monkeypatch.setattr(app, "_DOC_CACHE", None, raising=False)
    monkeypatch.setattr(app, "_ORCHESTRATOR", None, raising=False)

    episode = app._COG_STORE.append_episode(
        query="What is the beacon phrase?",
        answer="The beacon phrase is night-sparrow.",
        domain="general",
        task="qa",
        citations=["beacon.md:chunk0"],
        trace_id="prior-session",
    )
    episode_id = episode["id"]

    with TestClient(app.app) as client:
        resp = client.post("/query", json={"text": "Recall the beacon phrase."})
        assert resp.status_code == 200
        payload = resp.json()
        selected = payload["trace"]["cognitive_memory"]["selected"]
        selected_ids = {item["id"] for item in selected}
        assert f"cmem:ep:{episode_id}" in selected_ids
        assert any(
            citation.startswith(f"cmem:ep:{episode_id}:chunk")
            for citation in payload.get("citations", [])
        )
        assert "night-sparrow" in payload["answer"]


def test_memory_append_dedupe_window(tmp_path, monkeypatch):
    cfg = app.CFG.model_copy(
        update={"STORAGE_ROOT": tmp_path / "storage", "working_memory_dedupe_window_sec": 60}
    )
    monkeypatch.setattr(app, "CFG", cfg)
    monkeypatch.setattr(
        app,
        "_MEMORY_STORE",
        WorkingMemoryStore(tmp_path / "memory", dedupe_window_seconds=60),
    )

    with TestClient(app.app) as client:
        resp = client.post("/memory", json={})
        session_id = resp.json()["session"]["id"]

        first = client.post(f"/memory/{session_id}", json={"text": "dedupe me"})
        assert first.status_code == 200
        first_id = first.json()["id"]

        second = client.post(f"/memory/{session_id}", json={"text": "dedupe me"})
        assert second.status_code == 200
        second_payload = second.json()
        assert second_payload.get("deduped") is True
        assert second_payload["id"] == first_id

        detail = client.get(f"/memory/{session_id}").json()
        assert detail["session"]["entry_count"] == 1
        assert len(detail["entries"]) == 1


def test_memory_append_idempotency_key(tmp_path, monkeypatch):
    cfg = app.CFG.model_copy(
        update={"STORAGE_ROOT": tmp_path / "storage", "working_memory_dedupe_window_sec": 0}
    )
    monkeypatch.setattr(app, "CFG", cfg)
    monkeypatch.setattr(
        app,
        "_MEMORY_STORE",
        WorkingMemoryStore(tmp_path / "memory", dedupe_window_seconds=0),
    )

    with TestClient(app.app) as client:
        resp = client.post("/memory", json={})
        session_id = resp.json()["session"]["id"]

        first = client.post(
            f"/memory/{session_id}",
            json={"text": "first", "idempotency_key": "idemp-1"},
        )
        assert first.status_code == 200
        first_id = first.json()["id"]

        second = client.post(
            f"/memory/{session_id}",
            json={"text": "second", "idempotency_key": "idemp-1"},
        )
        assert second.status_code == 200
        second_payload = second.json()
        assert second_payload.get("deduped") is True
        assert second_payload["id"] == first_id

        detail = client.get(f"/memory/{session_id}").json()
        assert detail["session"]["entry_count"] == 1
        assert len(detail["entries"]) == 1


def test_memory_link_endpoint(tmp_path, monkeypatch):
    cfg = app.CFG.model_copy(update={"STORAGE_ROOT": tmp_path / "storage"})
    monkeypatch.setattr(app, "CFG", cfg)
    monkeypatch.setattr(
        app,
        "_COG_STORE",
        CognitiveMemoryStore(
            tmp_path / "storage" / "memory" / "cognitive",
            config=cfg,
        ),
    )
    monkeypatch.setattr(app, "_MEMORY_VECTORIZER", None, raising=False)
    monkeypatch.setattr(app, "_MEMORY_BACKEND", None, raising=False)

    with TestClient(app.app) as client:
        first = client.post("/memory/belief", json={"text": "Belief alpha"})
        assert first.status_code == 200
        second = client.post("/memory/belief", json={"text": "Belief beta"})
        assert second.status_code == 200
        first_id = first.json()["id"]
        second_id = second.json()["id"]

        link_resp = client.post(
            "/memory/link",
            json={"src_id": first_id, "dst_id": second_id, "link_type": "supports"},
        )
        assert link_resp.status_code == 200
        link_payload = link_resp.json()
        assert link_payload["src"] == first_id
        assert link_payload["dst"] == second_id
        assert link_payload["link_type"] == "supports"

        summary = client.get("/observability/memory/summary?window=5").json()
        assert summary["counts"]["links"] == 1
        assert summary["recent"]["links"][-1]["src"] == first_id

        invalid = client.post(
            "/memory/link",
            json={"src_id": first_id, "dst_id": second_id, "link_type": "related"},
        )
        assert invalid.status_code == 400
