from __future__ import annotations

import json
import uuid

from fastapi.testclient import TestClient

import fram_serving.app as app_mod
import fram_serving.memory as memory_mod
from fram_serving.memory import CognitiveMemoryStore, WorkingMemoryStore


def _reset_app_state(tmp_path, monkeypatch) -> tuple[app_mod.FRAMConfig, str]:
    fixed_uuid = uuid.UUID("00000000-0000-0000-0000-000000000001")
    monkeypatch.setattr(memory_mod.uuid, "uuid4", lambda: fixed_uuid)
    monkeypatch.setattr(
        memory_mod.CognitiveMemoryStore,
        "_now_iso",
        staticmethod(lambda: "2025-01-01T00:00:00+00:00"),
        raising=False,
    )
    cfg = app_mod.CFG.model_copy(
        update={
            "STORAGE_ROOT": tmp_path / "storage",
            "fractal_enabled": True,
            "default_query_reads": 1,
            "cognitive_memory_k": 1,
        }
    )
    monkeypatch.setattr(app_mod, "CFG", cfg, raising=False)
    monkeypatch.setattr(app_mod, "_ORCHESTRATOR", None, raising=False)
    monkeypatch.setattr(
        app_mod,
        "_MEMORY_STORE",
        WorkingMemoryStore(cfg.STORAGE_ROOT / cfg.STORAGE_SUBFOLDERS.get("memory", "memory")),
        raising=False,
    )
    monkeypatch.setattr(
        app_mod,
        "_COG_STORE",
        CognitiveMemoryStore(
            cfg.STORAGE_ROOT / cfg.STORAGE_SUBFOLDERS.get("memory", "memory") / "cognitive",
            config=cfg,
        ),
        raising=False,
    )
    return cfg, fixed_uuid.hex


def test_fractal_trace_smoke(tmp_path, monkeypatch) -> None:
    cfg, expected_id = _reset_app_state(tmp_path, monkeypatch)
    with TestClient(app_mod.app) as client:
        resp = client.post("/query", json={"text": "Fractal trace smoke"})
        assert resp.status_code == 200

    fractal_root = cfg.STORAGE_ROOT / cfg.STORAGE_SUBFOLDERS.get("memory", "memory") / "fractal"
    trace_path = fractal_root / f"{expected_id}.json"
    assert trace_path.exists()

    raw = json.loads(trace_path.read_text(encoding="utf-8"))
    assert raw.get("trace_version") == 2
    nodes = raw.get("nodes")
    assert isinstance(nodes, list)
    assert nodes
    for node in nodes:
        coord6 = node.get("coord6")
        assert isinstance(coord6, list)
        assert len(coord6) == 6
        q = node.get("q")
        assert isinstance(q, dict)
        assert {"w", "x", "y", "z"}.issubset(q.keys())
        lambda_value = float(node.get("lambda"))
        assert 0.0 < lambda_value < 1.0

    snippet = {"node0": nodes[0], "node1": nodes[1] if len(nodes) > 1 else nodes[0]}
    print(f"trace_path={trace_path.resolve()}")
    print(json.dumps(snippet, indent=2))
