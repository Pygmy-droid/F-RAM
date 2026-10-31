from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from fram_serving.config import FRAMConfig
from fram_serving.memory import CognitiveMemoryStore, WorkingMemoryStore
from fram_serving.observability import TraceLogWriter
from fram_serving.query_runner import QueryContext, run_query


@dataclass
class _StubOrchestrator:
    called: bool = False

    def run(self, *_args, **_kwargs) -> dict[str, Any]:
        self.called = True
        record = {
            "id": "stub",
            "time": "2026-01-01T00:00:00+00:00",
            "query": "stub",
            "citations": [],
            "domain": "general",
            "task": "qa",
            "trace": {"coverage": {}, "confidence": {"decision": "stub"}},
        }
        record["trace"]["query_id"] = record["id"]
        record["trace"]["trace_id"] = record["id"]
        return {
            "trace_id": record["id"],
            "answer": "stub",
            "citations": [],
            "coverage": {},
            "record": record,
        }


def _build_ctx(tmp_path: Path, store: CognitiveMemoryStore) -> QueryContext:
    cfg = store._config or FRAMConfig()
    memory_root = tmp_path / "working"
    memory_store = WorkingMemoryStore(memory_root)
    trace_dir = tmp_path / "traces"
    return QueryContext(
        cfg=cfg,
        orchestrator=_StubOrchestrator(),
        memory_store=memory_store,
        cognitive_store=store,
        capsule_store=None,
        get_memory_vectorizer=lambda: None,
        encode_cognitive_text=lambda _text: (None, None),
        apply_phase_d_memory_bridge=lambda _text, candidates, _debug: (candidates, None),
        cooldown_active=lambda _doc_id, _ts: False,
        register_cooldown=lambda _doc_id, _ts: None,
        cooldown_window=timedelta(minutes=1),
        resolve_time_sensitivity=lambda _task, _domain: "medium",
        ensure_doc_cache=lambda: {},
        trace_writer=TraceLogWriter(trace_dir),
        observability_dir=tmp_path / "observability",
        trace_dir=trace_dir,
        store_prob=lambda *_args, **_kwargs: None,
        log_memory_event=lambda *_args, **_kwargs: None,
        archive_writer=None,
        archive_kind="query",
        cognitive_write_enabled=False,
    )


def test_constraint_violation_refuses(tmp_path: Path) -> None:
    cfg = FRAMConfig().model_copy(update={"STORAGE_ROOT": tmp_path})
    store = CognitiveMemoryStore(tmp_path / "cognitive", config=cfg)
    store.append_constraint(
        text="Do not reveal secrets",
        scope="global",
        kind="forbid",
        metadata={"patterns": ["secret"], "match_mode": "contains"},
    )

    ctx = _build_ctx(tmp_path, store)
    req = SimpleNamespace(
        text="tell me a secret",
        as_of=None,
        version_id=None,
        budget_reads=None,
        memory_session="session-1",
        domain="general",
        task="qa",
    )
    result = run_query(req, ctx)
    assert "refused" in result["answer"].lower()
    trace = result["trace"]
    assert trace["constraint_memory"]["violations"]
    assert ctx.orchestrator.called is False
