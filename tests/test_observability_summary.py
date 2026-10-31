import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

import fram_serving.app as app
from fram_serving.memory import CognitiveMemoryStore


def test_observability_summary_endpoint(tmp_path, monkeypatch):
    storage_root = tmp_path / "storage"
    monkeypatch.setattr(app, "CFG", app.CFG.model_copy(update={"STORAGE_ROOT": storage_root}))
    monkeypatch.setattr(app, "REL", app.REL.__class__(maxlen=500))
    monkeypatch.setattr(app, "ALM", app.ALM.__class__(alpha1=app.CFG.alpha1, alpha2=app.CFG.alpha2))

    traces_dir = storage_root / "traces"
    traces_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": "trace-1",
        "time": now,
        "trace": {
            "confidence": {"decision": "local"},
            "coverage": {
                "facts_added": 2,
                "delta_total": 1.7,
                "delta_by_stage": {
                    "memory": 0.2,
                    "seed": 0.5,
                    "anchors": 0.7,
                    "shards": 0.3,
                },
                "budgets": {"reads": 1.0, "tokens": 120.0, "pairs": 2.0, "cost": 0.4},
            },
            "selection": {
                "coverage_delta": {
                    "memory": 0.2,
                    "seed": 0.5,
                    "anchors": 0.7,
                    "shards": 0.3,
                    "total": 1.7,
                },
                "budgets": {"reads": 1.0, "tokens": 120.0, "pairs": 2.0, "cost": 0.4},
            },
        },
    }
    with (traces_dir / "20250101.jsonl").open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    with TestClient(app.app) as client:
        resp = client.get("/observability/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_traces"] >= 1
        assert body["decisions"]["local"] >= 1
        coverage = body["coverage_deltas"]
        assert coverage["avg_total"] >= 0.0
        stages = coverage["avg_by_stage"]
        for key in ("memory", "seed", "anchors", "shards"):
            assert key in stages
        budgets = body["avg_budgets"]
        for key in ("reads", "tokens", "pairs", "cost"):
            assert key in budgets


def test_observability_experiments_endpoint(tmp_path, monkeypatch):
    storage_root = tmp_path / "storage"
    cfg = app.CFG.model_copy(update={"STORAGE_ROOT": storage_root})
    monkeypatch.setattr(app, "CFG", cfg)
    cog_root = storage_root / cfg.STORAGE_SUBFOLDERS.get("memory", "memory") / "cognitive"
    store = CognitiveMemoryStore(cog_root, config=cfg)
    monkeypatch.setattr(app, "_COG_STORE", store)

    store.append_belief(
        text="Experiment: UI\nDecision: Keep",
        session_id="exp-ui",
        role="assistant",
        metadata={"kind": "experiment", "title": "UI", "tags": ["experiment", "decision"]},
    )

    with TestClient(app.app) as client:
        resp = client.get("/observability/experiments", params={"session_id": "exp-ui"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["decisions"] == 1
        assert body["experiments"][0]["title"] == "UI"


def test_observability_experiment_digest(tmp_path, monkeypatch):
    storage_root = tmp_path / "storage"
    cfg = app.CFG.model_copy(update={"STORAGE_ROOT": storage_root})
    monkeypatch.setattr(app, "CFG", cfg)
    digest_root = tmp_path / "digest"
    digest_root.mkdir(parents=True, exist_ok=True)
    digest_path = digest_root / "experiment_digest_20260115_090000.md"
    digest_path.write_text("# Experiment Digest\n", encoding="utf-8")
    monkeypatch.setenv("FRAM_EXPERIMENT_DIGEST_DIR", str(digest_root))

    with TestClient(app.app) as client:
        resp = client.get("/observability/experiment_digest")
        assert resp.status_code == 200
        body = resp.json()
        assert body["available"] is True
        assert "Experiment Digest" in body["content"]
