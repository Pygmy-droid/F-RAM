from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from fastapi.testclient import TestClient

from fram_serving import app
from fram_serving.semantic import CandidateFeatures, RelevanceReranker


def test_reranker_prefers_overlap():
    reranker = RelevanceReranker()
    query = "clock synchronization"
    candidates = [
        CandidateFeatures(
            id="a",
            text="Clock synchronization and offset correction.",
            tokens={"clock", "synchronization", "offset", "correction"},
            metadata={},
            entities={"clock"},
        ),
        CandidateFeatures(
            id="b",
            text="Unrelated topic about birds.",
            tokens={"unrelated", "topic", "birds"},
            metadata={},
            entities={"birds"},
        ),
    ]
    results = {r.id: r for r in reranker.rank(query, candidates)}
    assert results["a"].score >= results["b"].score
    assert results["a"].model == "heuristic"


def test_recall_report_phase_d_diagnostics(tmp_path, monkeypatch):
    original_root = app.CFG.STORAGE_ROOT
    original_phase_d = app.CFG.phase_d.model_copy()
    try:
        app.CFG.STORAGE_ROOT = tmp_path
        app.CFG.phase_d.enabled = True
        app.CFG.phase_d.debug_observability = True

        obs_dir = tmp_path / "observability"
        obs_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).isoformat()
        cognitive_event = {
            "query_id": "q2",
            "time": timestamp,
            "selected_count": 1,
            "selected": [
                {
                    "id": "cmem:bl:2",
                    "time_sensitivity": "medium",
                }
            ],
        }
        with (obs_dir / "memory_cognitive.jsonl").open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(cognitive_event) + "\n")
        fractal_event = {
            "kind": "score",
            "query_id": "q2",
            "k": 1,
            "requested": 3,
            "backend": "hashing",
            "alpha": 0.55,
            "top": [
                {
                    "episode_id": "cmem:ep:2",
                    "score": 0.52,
                }
            ],
            "time": timestamp,
        }
        with (obs_dir / "memory_fractal.jsonl").open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(fractal_event) + "\n")

        report = app.recall_report()
        assert report.phase_d is not None
        assert report.phase_d.enabled is True
        assert report.phase_d.debug is True
        assert report.phase_d.alpha_t is not None
        assert report.phase_d.alpha_color is not None
        assert report.phase_d.quat_avg is not None
        if report.fractal is not None:
            assert report.fractal.logistic_alpha_preview == report.phase_d.alpha_t
    finally:
        app.CFG.STORAGE_ROOT = original_root
        app.CFG.phase_d.enabled = original_phase_d.enabled
        app.CFG.phase_d.debug_observability = original_phase_d.debug_observability


def test_recall_report_reads_events(tmp_path, monkeypatch):
    original_root = app.CFG.STORAGE_ROOT
    try:
        app.CFG.STORAGE_ROOT = tmp_path
        app.CFG.phase_d.enable_memory_bridge = True
        obs_dir = tmp_path / "observability"
        obs_dir.mkdir(parents=True, exist_ok=True)
        event = {
            "query_id": "q1",
            "time": datetime.now(timezone.utc).isoformat(),
            "selected_count": 1,
            "selected": [
                {
                    "id": "cmem:bl:1",
                    "time_sensitivity": "high",
                }
            ],
            "phase_d_memory": {
                "enabled": True,
                "debug": False,
                "scored": 1,
                "alpha_t": 0.4,
                "alpha_color": "transition",
                "quat_avg": 0.5,
            },
        }
        with (obs_dir / "memory_cognitive.jsonl").open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(event) + "\n")
        fractal_event = {
            "kind": "score",
            "query_id": "q1",
            "k": 1,
            "requested": 3,
            "backend": "hashing",
            "alpha": 0.4,
            "top": [
                {
                    "episode_id": "cmem:ep:1",
                    "score": 0.42,
                }
            ],
            "time": event["time"],
        }
        with (obs_dir / "memory_fractal.jsonl").open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(fractal_event) + "\n")

        report = app.recall_report()
        assert report.invocations == 1
        assert pytest.approx(report.hit_rate, 1e-6) == 1.0
        assert report.time_sensitivity["high"] == 1
        assert report.fractal is not None
        assert report.fractal.events == 1
        assert pytest.approx(report.fractal.hit_rate, 1e-6) == 1.0
        assert report.fractal.recent[0].returned == 1
        assert report.fractal.top_episodes[0].episode_id == "cmem:ep:1"
        assert report.phase_d_memory is not None
        assert report.phase_d_memory.enabled is True
        assert report.phase_d_memory.scored == 1
        assert report.phase_d_memory.alpha_t == pytest.approx(0.4)
        assert report.phase_d_memory.stats is not None
        assert report.phase_d_memory.stats["events"] == 1
        assert report.phase_d_memory.stats["scored_total"] == 1
        assert report.phase_d_memory.stats["alpha_t_avg"] == pytest.approx(0.4)
        assert report.phase_d_memory.stats["alpha_missing"] == 0
        assert report.phase_d_memory.stats["missing_alpha"] is False
        assert report.phase_d_memory.stats["alpha_color_counts"].get("transition") == 1
        assert report.cognitive is not None
        assert report.cognitive.phase_d_memory is not None
    finally:
        app.CFG.STORAGE_ROOT = original_root
        app.CFG.phase_d.enable_memory_bridge = False


def test_phase_d_memory_dashboard_gated(tmp_path):
    original_root = app.CFG.STORAGE_ROOT
    original_phase_d = app.CFG.phase_d.model_copy()
    try:
        app.CFG.STORAGE_ROOT = tmp_path
        app.CFG.phase_d.enabled = False
        app.CFG.phase_d.enable_memory_bridge = False
        client = TestClient(app.app)
        resp = client.get("/observability/phase_d_memory")
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is False
        assert data["config"]["bridge_enabled"] is False

        app.CFG.phase_d.enabled = True
        app.CFG.phase_d.enable_memory_bridge = True
        obs_dir = tmp_path / "observability"
        obs_dir.mkdir(parents=True, exist_ok=True)
        event = {
            "query_id": "qpd",
            "phase_d_memory": {"enabled": True, "scored": 2, "alpha_t": 0.3},
            "time": datetime.now(timezone.utc).isoformat(),
        }
        with (obs_dir / "memory_cognitive.jsonl").open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(event) + "\n")
        enabled_resp = client.get("/observability/phase_d_memory")
        assert enabled_resp.status_code == 200
        payload = enabled_resp.json()
        assert payload["enabled"] is True
        assert payload["events"]
        assert payload["config"]["phase_d_enabled"] is True
        assert payload["stats"]["events"] == 1
        assert payload["stats"]["scored_total"] == 2
        assert payload["stats"]["alpha_t_avg"] == pytest.approx(0.3)
    finally:
        app.CFG.STORAGE_ROOT = original_root
        app.CFG.phase_d.enabled = original_phase_d.enabled
        app.CFG.phase_d.enable_memory_bridge = original_phase_d.enable_memory_bridge
        app.CFG.phase_d.debug_observability = original_phase_d.debug_observability


def _write_cognitive_event(tmp_path, event):
    obs_dir = tmp_path / "observability"
    obs_dir.mkdir(parents=True, exist_ok=True)
    with (obs_dir / "memory_cognitive.jsonl").open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")


def test_cognitive_summary_bridge_off(tmp_path):
    original_root = app.CFG.STORAGE_ROOT
    original_phase_d = app.CFG.phase_d.model_copy()
    try:
        app.CFG.STORAGE_ROOT = tmp_path
        app.CFG.phase_d.enabled = False
        app.CFG.phase_d.enable_memory_bridge = False
        event = {
            "query_id": "q-cog",
            "selected_count": 2,
            "selected": [{"id": "cmem:1", "kind": "belief"}],
            "phase_d_memory": {"enabled": True, "scored": 1},
        }
        _write_cognitive_event(tmp_path, event)
        client = TestClient(app.app)
        resp = client.get("/observability/cognitive_summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["invocations"] == 1
        assert "phase_d_memory" not in data
        assert data["recent"][0].get("phase_d_memory") is None
        assert data["config"]["bridge_enabled"] is False
        assert "bridge_activity" not in data
    finally:
        app.CFG.STORAGE_ROOT = original_root
        app.CFG.phase_d.enabled = original_phase_d.enabled
        app.CFG.phase_d.enable_memory_bridge = original_phase_d.enable_memory_bridge


def test_cognitive_summary_bridge_on(tmp_path):
    original_root = app.CFG.STORAGE_ROOT
    original_phase_d = app.CFG.phase_d.model_copy()
    try:
        app.CFG.STORAGE_ROOT = tmp_path
        app.CFG.phase_d.enabled = True
        app.CFG.phase_d.enable_memory_bridge = True
        event = {
            "query_id": "q-cog",
            "selected_count": 1,
            "selected": [{"id": "cmem:1", "kind": "belief"}],
            "phase_d_memory": {"enabled": True, "scored": 1, "alpha_t": 0.5},
        }
        _write_cognitive_event(tmp_path, event)
        client = TestClient(app.app)
        resp = client.get("/observability/cognitive_summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["phase_d_memory"]["events"] == 1
        assert data["recent"][0]["phase_d_memory"]["scored"] == 1
        assert data["config"]["bridge_enabled"] is True
        assert data["config"]["phase_d_alpha_t"] == pytest.approx(0.5)
        assert data["bridge_activity"]["phase_d_events"] == 1
        assert data["bridge_activity"]["phase_c_events"] == 0
        assert data["phase_d_memory"]["stats"]["scored_total"] == 1
        assert data["phase_d_memory"]["stats"]["alpha_t_avg"] == pytest.approx(0.5)
        assert data["phase_d_memory"]["stats"]["alpha_missing"] == 0
        assert data["phase_d_memory"]["stats"]["missing_alpha"] is False
    finally:
        app.CFG.STORAGE_ROOT = original_root
        app.CFG.phase_d.enabled = original_phase_d.enabled
        app.CFG.phase_d.enable_memory_bridge = original_phase_d.enable_memory_bridge


def test_cognitive_summary_html(tmp_path):
    original_root = app.CFG.STORAGE_ROOT
    original_phase_d = app.CFG.phase_d.model_copy()
    try:
        app.CFG.STORAGE_ROOT = tmp_path
        app.CFG.phase_d.enabled = True
        app.CFG.phase_d.enable_memory_bridge = True
        event = {
            "query_id": "q-html",
            "selected_count": 0,
            "selected": [],
        }
        _write_cognitive_event(tmp_path, event)
        client = TestClient(app.app)
        resp = client.get("/observability/cognitive_summary?html=1")
        assert resp.status_code == 200
        assert "<table" in resp.text
        assert "<style>" in resp.text
    finally:
        app.CFG.STORAGE_ROOT = original_root
        app.CFG.phase_d.enabled = original_phase_d.enabled
        app.CFG.phase_d.enable_memory_bridge = original_phase_d.enable_memory_bridge


def test_phase_d_memory_stats_missing_alpha(tmp_path):
    original_root = app.CFG.STORAGE_ROOT
    original_phase_d = app.CFG.phase_d.model_copy()
    try:
        app.CFG.STORAGE_ROOT = tmp_path
        app.CFG.phase_d.enabled = True
        app.CFG.phase_d.enable_memory_bridge = True
        event = {
            "query_id": "q-miss-alpha",
            "time": datetime.now(timezone.utc).isoformat(),
            "selected_count": 1,
            "selected": [{"id": "cmem:x", "kind": "episode"}],
            "phase_d_memory": {
                "enabled": True,
                "debug": True,
                "scored": 1,
            },
        }
        _write_cognitive_event(tmp_path, event)
        client = TestClient(app.app)
        resp = client.get("/observability/cognitive_summary")
        assert resp.status_code == 200
        data = resp.json()
        stats = data["phase_d_memory"]["stats"]
        assert stats["alpha_missing"] == 1
        assert stats["missing_alpha"] is True
    finally:
        app.CFG.STORAGE_ROOT = original_root
        app.CFG.phase_d.enabled = original_phase_d.enabled
        app.CFG.phase_d.enable_memory_bridge = original_phase_d.enable_memory_bridge


def test_cognitive_summary_empty(tmp_path):
    original_root = app.CFG.STORAGE_ROOT
    try:
        app.CFG.STORAGE_ROOT = tmp_path
        client = TestClient(app.app)
        resp = client.get("/observability/cognitive_summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["invocations"] == 0
        assert data["recent"] == []
    finally:
        app.CFG.STORAGE_ROOT = original_root
