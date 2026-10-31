from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import fram_serving.app as app_mod
from fram_serving.config import FRAMConfig
from fram_serving.continuity import (
    ContinuityWitnessWriteError,
    ContinuityWitnessWriter,
    build_continuity_witness,
    load_latest_continuity_witness,
)
from fram_serving.memory import CognitiveMemoryStore, WorkingMemoryStore
from fram_serving.observability import TraceLogWriter
from fram_serving.query_runner import QueryContext, run_query


class _StableOrchestrator:
    def run(self, text: str, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        record = {
            "id": "trace-stable",
            "time": "2026-07-28T12:00:00+00:00",
            "query": text,
            "citations": ["doc:chosen"],
            "domain": "general",
            "task": "qa",
            "trace": {
                "trace_id": "trace-stable",
                "query_id": "trace-stable",
                "confidence": {"decision": "anchors"},
                "coverage": {},
                "selection": {
                    "origin_counts": {"document": 2},
                    "selected_ids": ["doc:chosen"],
                    "budgets": {
                        "reads": 1.0,
                        "tokens": 8.0,
                        "pairs": 0.0,
                        "cost": 1.016,
                    },
                },
                "latency_ms": {},
            },
        }
        return {
            "trace_id": record["id"],
            "answer": "bounded answer",
            "citations": list(record["citations"]),
            "coverage": {},
            "record": record,
        }


def _context(
    tmp_path: Path,
    *,
    writer: ContinuityWitnessWriter | None,
) -> QueryContext:
    cfg = FRAMConfig().model_copy(
        update={
            "STORAGE_ROOT": tmp_path / "storage",
            "cognitive_memory_k": 0,
            "memory_capsule_enabled": False,
            "fractal_enabled": False,
            "fractal_influence_enabled": False,
            "preserve_full_experience": True,
        }
    )
    cognitive_store = CognitiveMemoryStore(
        tmp_path / "storage" / "memory" / "cognitive",
        config=cfg,
    )
    trace_dir = tmp_path / "storage" / "traces"
    return QueryContext(
        cfg=cfg,
        orchestrator=_StableOrchestrator(),
        memory_store=WorkingMemoryStore(tmp_path / "storage" / "memory" / "working"),
        cognitive_store=cognitive_store,
        capsule_store=None,
        get_memory_vectorizer=lambda: None,
        encode_cognitive_text=lambda _text: (None, None),
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
        cognitive_write_enabled=False,
        continuity_witness_writer=writer,
    )


def _request() -> SimpleNamespace:
    return SimpleNamespace(
        text="private query text",
        as_of=None,
        version_id=None,
        budget_reads=None,
        memory_session=None,
        principal=None,
        domain="general",
        task="qa",
    )


def test_final_witness_is_non_interfering_and_post_write(tmp_path: Path) -> None:
    disabled_ctx = _context(tmp_path / "disabled", writer=None)
    enabled_root = tmp_path / "enabled"
    witness_writer = ContinuityWitnessWriter(
        enabled_root / "storage" / "observability" / "continuity"
    )
    enabled_ctx = _context(enabled_root, writer=witness_writer)

    disabled = run_query(_request(), disabled_ctx)
    enabled = run_query(_request(), enabled_ctx)

    assert enabled["answer"] == disabled["answer"]
    assert enabled["citations"] == disabled["citations"]
    assert enabled["trace"]["selection"] == disabled["trace"]["selection"]
    assert enabled["trace"]["confidence"] == disabled["trace"]["confidence"]
    assert not (
        enabled_root / "storage" / "memory" / "cognitive" / "episodes.jsonl"
    ).exists()

    witness = load_latest_continuity_witness(witness_writer.root)
    assert witness["state"] == "available"
    assert witness["trace_id"] == enabled["id"]
    assert witness["decision"] == "anchors"
    assert witness["selection"]["citations"] == ["doc:chosen"]
    assert witness["selection"]["selected_ids"] == ["doc:chosen"]
    assert witness["selection"]["budgets"]["reads"] == 1.0
    assert witness["writes"]["cognitive_episode"]["status"] == "skipped"
    assert witness["writes"]["memory_capsule"]["status"] == "skipped"
    assert witness["writes"]["archive"]["status"] == "skipped"
    assert "fractal_ranking" not in witness["active_gates"]

    serialized = witness_writer.path.read_text(encoding="utf-8")
    assert "private query text" not in serialized
    assert "bounded answer" not in serialized


def test_constraint_refusal_is_an_allowlisted_witness_decision() -> None:
    source = {
        "trace_id": "constraint-trace",
        "citations": [],
        "record": {
            "id": "constraint-trace",
            "time": "2026-07-28T12:00:00+00:00",
            "citations": [],
            "trace": {
                "trace_id": "constraint-trace",
                "confidence": {"decision": "constraint_refusal"},
                "selection": {
                    "origin_counts": {},
                    "selected_ids": [],
                    "budgets": {},
                },
            },
        },
    }

    witness = build_continuity_witness(
        source,
        feature_enabled=True,
        expected_trace_id="constraint-trace",
        active_gates={"continuity_witness": True},
    )

    assert witness["state"] == "available"
    assert witness["decision"] == "constraint_refusal"


def test_latest_witness_endpoint_reports_unknown_then_available(
    tmp_path: Path,
    monkeypatch,
) -> None:
    cfg = app_mod.CFG.model_copy(
        update={
            "STORAGE_ROOT": tmp_path / "storage",
            "continuity_witness_enabled": True,
        }
    )
    monkeypatch.setattr(app_mod, "CFG", cfg, raising=False)

    missing = app_mod.observability_continuity_witness()
    assert missing["available"] is False
    assert missing["state"] == "unknown"
    assert missing["reason"] == "not_found"

    observed_at = datetime.now(timezone.utc).isoformat()
    source = {
        "trace_id": "endpoint-trace",
        "citations": ["doc:endpoint"],
        "record": {
            "id": "endpoint-trace",
            "time": observed_at,
            "citations": ["doc:endpoint"],
            "trace": {
                "trace_id": "endpoint-trace",
                "confidence": {"decision": "local"},
                "selection": {
                    "origin_counts": {"document": 1},
                    "selected_ids": ["doc:endpoint"],
                    "budgets": {"reads": 1.0},
                },
            },
        },
    }
    witness = build_continuity_witness(
        source,
        feature_enabled=True,
        expected_trace_id="endpoint-trace",
        active_gates={"continuity_witness": True},
    )
    ContinuityWitnessWriter(app_mod._continuity_witness_root()).append(witness)

    available = app_mod.observability_continuity_witness()
    assert available["available"] is True
    assert available["state"] == "available"
    assert available["witness"]["trace_id"] == "endpoint-trace"


def test_latest_witness_endpoint_hides_old_log_when_feature_is_off(
    tmp_path: Path,
    monkeypatch,
) -> None:
    enabled_cfg = app_mod.CFG.model_copy(
        update={
            "STORAGE_ROOT": tmp_path / "storage",
            "continuity_witness_enabled": True,
        }
    )
    monkeypatch.setattr(app_mod, "CFG", enabled_cfg, raising=False)
    source = {
        "trace_id": "old-enabled-trace",
        "citations": [],
        "record": {
            "id": "old-enabled-trace",
            "time": datetime.now(timezone.utc).isoformat(),
            "citations": [],
            "trace": {
                "trace_id": "old-enabled-trace",
                "confidence": {"decision": "local"},
                "selection": {
                    "origin_counts": {},
                    "selected_ids": [],
                    "budgets": {},
                },
            },
        },
    }
    witness = build_continuity_witness(
        source,
        feature_enabled=True,
        expected_trace_id="old-enabled-trace",
        active_gates={"continuity_witness": True},
    )
    ContinuityWitnessWriter(app_mod._continuity_witness_root()).append(witness)

    disabled_cfg = enabled_cfg.model_copy(update={"continuity_witness_enabled": False})
    monkeypatch.setattr(app_mod, "CFG", disabled_cfg, raising=False)
    envelope = app_mod.observability_continuity_witness()

    assert envelope["available"] is False
    assert envelope["state"] == "unknown"
    assert envelope["reason"] == "feature_disabled"
    assert envelope["witness"] is None


def test_latest_witness_endpoint_marks_old_record_stale(
    tmp_path: Path,
    monkeypatch,
) -> None:
    cfg = app_mod.CFG.model_copy(
        update={
            "STORAGE_ROOT": tmp_path / "storage",
            "continuity_witness_enabled": True,
            "continuity_witness_max_age_seconds": 1.0,
        }
    )
    monkeypatch.setattr(app_mod, "CFG", cfg, raising=False)
    source = {
        "trace_id": "stale-trace",
        "citations": [],
        "record": {
            "id": "stale-trace",
            "time": "2026-01-01T00:00:00+00:00",
            "citations": [],
            "trace": {
                "trace_id": "stale-trace",
                "confidence": {"decision": "local"},
                "selection": {
                    "origin_counts": {},
                    "selected_ids": [],
                    "budgets": {},
                },
            },
        },
    }
    witness = build_continuity_witness(
        source,
        feature_enabled=True,
        expected_trace_id="stale-trace",
        active_gates={"continuity_witness": True},
    )
    ContinuityWitnessWriter(app_mod._continuity_witness_root()).append(witness)

    envelope = app_mod.observability_continuity_witness()
    assert envelope["available"] is False
    assert envelope["state"] == "stale"
    assert envelope["reason"] == "max_age_exceeded"
    assert envelope["witness"]["trace_id"] == "stale-trace"


def test_witness_write_failure_is_logged_and_non_interfering(
    tmp_path: Path,
    caplog,
) -> None:
    class _FailingWriter:
        def append(self, _witness: dict[str, Any]) -> None:
            raise ContinuityWitnessWriteError("lock busy")

    baseline = run_query(_request(), _context(tmp_path / "baseline", writer=None))
    with caplog.at_level("WARNING"):
        result = run_query(
            _request(),
            _context(tmp_path / "failing", writer=_FailingWriter()),  # type: ignore[arg-type]
        )

    assert result["answer"] == baseline["answer"]
    assert result["citations"] == baseline["citations"]
    assert "continuity witness append skipped: lock busy" in caplog.text


def test_continuity_witness_flag_is_default_off_and_env_configurable(
    monkeypatch,
) -> None:
    assert FRAMConfig().continuity_witness_enabled is False
    assert FRAMConfig().continuity_witness_max_age_seconds == 3600.0
    assert FRAMConfig().continuity_witness_lock_timeout_seconds == 0.1
    monkeypatch.setenv("FRAM_CONTINUITY_WITNESS_ENABLED", "1")
    monkeypatch.setenv("FRAM_CONTINUITY_WITNESS_MAX_AGE_SECONDS", "600")
    monkeypatch.setenv("FRAM_CONTINUITY_WITNESS_LOCK_TIMEOUT_SECONDS", "0.05")
    configured = FRAMConfig.from_env()
    assert configured.continuity_witness_enabled is True
    assert configured.continuity_witness_max_age_seconds == 600.0
    assert configured.continuity_witness_lock_timeout_seconds == 0.05
