from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from collections import OrderedDict
import json
import os
import time
import copy

import numpy as np
import pytest
from fastapi.testclient import TestClient

import fram_core.pipeline as pipeline_mod
import fram_core.confidence as conf
from fram_core.pipeline import QueryOrchestrator, CalibrationPayload
from fram_core.claims import Claim, ClaimType
from fram_serving.config import FRAMConfig
from fram_serving import observability
import fram_serving.app as app_mod


DATA_ROOT = Path(__file__).resolve().parents[1] / "examples" / "data"


class _StubTracer:
    def __init__(self) -> None:
        self.records: dict[str, dict] = {}

    def write(self, payload):  # type: ignore[no-untyped-def]
        trace_id = payload.get("id")
        if not trace_id:
            trace_id = datetime.now(timezone.utc).isoformat()
            payload["id"] = trace_id
        self.records[str(trace_id)] = dict(payload)
        return str(trace_id)


@pytest.fixture()
def orchestrator():
    tracer = _StubTracer()
    config = FRAMConfig()
    return QueryOrchestrator(config=config, tracer=tracer), tracer


def test_query_orchestrator_returns_trace(orchestrator):
    engine, tracer = orchestrator
    result = engine.run("OrthoRoute confidence", None, 2000, "general", "qa")

    assert result["answer"], "expected non-empty answer"
    assert result["citations"], "expected at least one citation"
    trace_id = result["trace_id"]
    assert trace_id in tracer.records
    record = tracer.records[trace_id]
    coverage = record["trace"]["coverage"]
    selection = record["trace"]["selection"]
    assert coverage["selected_claims"] >= 0
    assert "value_start" in coverage and "value_final" in coverage
    assert coverage["value_final"] >= coverage["value_start"]
    coverage_delta = selection.get("coverage_delta", {})
    assert {"memory", "seed", "anchors", "shards", "total"}.issubset(coverage_delta)
    total_delta = (
        coverage_delta["memory"]
        + coverage_delta["seed"]
        + coverage_delta["anchors"]
        + coverage_delta["shards"]
    )
    assert pytest.approx(total_delta) == pytest.approx(coverage_delta["total"])
    coverage_budgets = coverage.get("budgets", {})
    assert {"reads", "tokens", "pairs", "cost"}.issubset(coverage_budgets)
    assert selection.get("segments")
    assert all("segment" in item and "count" in item for item in selection.get("segments", []))
    assert isinstance(coverage.get("sections"), list)
    assert isinstance(coverage.get("segment_counts"), dict)
    assert 0.0 <= selection.get("segments_diversity", 0.0) <= 1.0
    assert 0.0 <= coverage.get("section_diversity", 0.0) <= 1.0
    for group in ("anchors", "shards"):
        for entry in selection.get(group, []):
            assert "diversity_multiplier" in entry
            assert 0.0 < entry["diversity_multiplier"] <= 1.0


def test_query_orchestrator_as_of_filters_all(orchestrator):
    engine, _ = orchestrator
    ancient = datetime(1900, 1, 1, tzinfo=timezone.utc)
    result = engine.run("memory", ancient, 2000, "general", "qa")
    assert result["citations"] == []
    assert result["answer"] == ""


def test_query_orchestrator_versioning_trace(orchestrator):
    engine, _ = orchestrator
    as_of = datetime.now(timezone.utc)
    result = engine.run("memory", as_of, 2, "general", "qa")
    versioning = result["record"]["trace"].get("versioning")
    assert versioning is not None
    assert versioning.get("as_of") is not None
    assert isinstance(versioning.get("active_versions"), dict)


def test_calibration_logging(monkeypatch, orchestrator):
    engine, _ = orchestrator
    captured: list[tuple[Path, dict]] = []

    def fake_append(root, record):
        captured.append((root, dict(record)))

    monkeypatch.setattr(pipeline_mod, "_append_calibration_record", fake_append)

    result = engine.run("calibration check", None, 2000, "general", "qa")

    assert captured, "expected calibration logging"
    root, record = captured[0]
    assert root == engine.config.STORAGE_ROOT
    assert record["domain"] == "general"
    assert record["task"] == "qa"
    assert record["budget_reads"] == pytest.approx(2000.0)
    assert record["trace_id"] == result["trace_id"]
    assert "features" in record and "label" in record
    assert set(record["features"].keys()) == {"Delta_d_z", "rho_pos", "mhd", "d_c_z", "fresh"}


def test_deserialize_calibration_rejects_sign_inverting_centroid_distance() -> None:
    payload = {
        "logistic_coefs": {
            "a": 0.1,
            "b": 0.1,
            "c": 0.1,
            "g": -0.1,
            "h": 0.1,
            "d": 0.0,
        },
        "temperature": 1.0,
        "tau1": 0.8,
        "tau2": 0.5,
    }

    with pytest.raises(ValueError, match="centroid distance cannot increase confidence"):
        pipeline_mod._deserialize_calibration(payload, FRAMConfig())


def test_query_orchestrator_tfidf_backend(tmp_path):
    storage_root = tmp_path / "storage"
    cfg = FRAMConfig().model_copy(update={"STORAGE_ROOT": storage_root, "embedding_backend": "tfidf"})
    engine = QueryOrchestrator(config=cfg, tracer=None, data_root=DATA_ROOT)
    result = engine.run("tfidf query", None, 2, "general", "qa")
    assert result["citations"] is not None



def test_get_embeddings_for_shortlist_shapes(tmp_path):
    storage_root = tmp_path / "storage"
    cfg = FRAMConfig().model_copy(update={"STORAGE_ROOT": storage_root})
    engine = QueryOrchestrator(config=cfg, tracer=None, data_root=DATA_ROOT)

    shortlist = [{"text": "alpha"}, {"content": "beta"}]
    query_vec, episode_vecs = engine.get_embeddings_for_shortlist("phase d shortlist", shortlist)
    cache = engine.ensure_corpus()
    dim = cache.chunk_vecs.shape[1]

    assert dim > 0
    assert len(query_vec) == dim
    assert len(episode_vecs) == len(shortlist)
    assert all(len(vec) == dim for vec in episode_vecs)


def test_get_embeddings_for_shortlist_empty_cache(monkeypatch):
    cfg = FRAMConfig()
    engine = QueryOrchestrator(config=cfg, tracer=None)

    class _EmptyCache:
        chunk_vecs = np.array([])
        vocab: dict[str, int] = {}

    monkeypatch.setattr(engine, "ensure_corpus", lambda: _EmptyCache())
    query_vec, episode_vecs = engine.get_embeddings_for_shortlist("noop", [{"text": "x"}])

    assert query_vec == []
    assert episode_vecs == []


def test_budget_reads_limits_selection(orchestrator):
    engine, _ = orchestrator
    result = engine.run("budget check", None, 1, "legal", "summary")

    assert len(result["citations"]) <= 1
    record = result["record"]
    trace = record["trace"]
    selection = trace["selection"]
    budgets = selection["budgets"]

    assert budgets["reads_limit"] == pytest.approx(1.0)
    assert budgets["reads_used"] <= 1.0
    assert trace["domain"] == "legal"
    assert trace["task"] == "summary"
    assert trace["budget_reads"] == pytest.approx(1.0)
    assert record["domain"] == "legal"
    assert record["task"] == "summary"


def test_budget_zero_returns_empty(orchestrator):
    engine, _ = orchestrator
    result = engine.run("budget zero", None, 0, "general", "qa")

    assert result["citations"] == []
    assert result["answer"] == ""
    record = result["record"]
    budgets = record["trace"]["selection"]["budgets"]
    assert budgets["reads_limit"] == pytest.approx(0.0)
    assert budgets["reads_used"] == pytest.approx(0.0)


def test_ann_index_persisted(tmp_path):
    storage_root = tmp_path / "storage"
    cfg = FRAMConfig().model_copy(update={"STORAGE_ROOT": storage_root})
    engine = QueryOrchestrator(config=cfg, tracer=None)
    engine.run("ingest", None, 1, "general", "qa")

    index_dir = storage_root / cfg.STORAGE_SUBFOLDERS.get("index", "index") / "demo_corpus"
    ann_path = index_dir / "ann_index.joblib"
    assert ann_path.exists()

    engine2 = QueryOrchestrator(config=cfg, tracer=None)
    engine2.run("ingest", None, 1, "general", "qa")
    assert engine2._ann_loaded_from_disk is True


def test_persisted_corpus_is_stale_when_missing(tmp_path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    (data_root / "doc.txt").write_text("hello", encoding="utf-8")
    persist_path = tmp_path / "persist"
    persist_path.mkdir()

    assert pipeline_mod._persisted_corpus_is_stale(persist_path, data_root)


def test_persisted_corpus_is_stale_when_data_newer(tmp_path):
    data_root = tmp_path / "data"
    data_root.mkdir()
    doc = data_root / "doc.txt"
    doc.write_text("hello", encoding="utf-8")

    persist_path = tmp_path / "persist"
    persist_path.mkdir()
    for path in pipeline_mod._required_persist_files(persist_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == ".npy":
            path.write_bytes(b"\x93NUMPY")
        else:
            path.write_text("{}", encoding="utf-8")

    old = time.time() - 1000
    for path in pipeline_mod._required_persist_files(persist_path):
        os.utime(path, (old, old))

    now = time.time()
    os.utime(doc, (now, now))

    assert pipeline_mod._persisted_corpus_is_stale(persist_path, data_root)


def test_orchestrator_refreshes_stale_persisted(tmp_path, monkeypatch):
    cfg = FRAMConfig().model_copy(update={"STORAGE_ROOT": tmp_path / "storage"})
    data_root = DATA_ROOT
    persist_path = tmp_path / "persist"

    save_calls = {"count": 0}
    export_calls = {"count": 0}

    original_save = pipeline_mod.save_corpus_cache

    def wrapped_save(cache, dest):
        save_calls["count"] += 1
        return original_save(cache, dest)

    def fake_export(cache, dest, dataset_name="corpus"):
        export_calls["count"] += 1
        dest.mkdir(parents=True, exist_ok=True)
        out = dest / f"{dataset_name}.jsonl"
        out.write_text("[]", encoding="utf-8")
        return out

    monkeypatch.setattr(pipeline_mod, "save_corpus_cache", wrapped_save)
    monkeypatch.setattr(pipeline_mod, "export_claim_log", fake_export)

    engine = QueryOrchestrator(
        config=cfg,
        tracer=None,
        data_root=data_root,
        persist_path=persist_path,
    )

    engine._ensure_corpus()
    assert save_calls["count"] == 1
    assert export_calls["count"] == 1
    assert (persist_path / "chunks.json").exists()

    engine._cache = None
    engine._ensure_corpus()
    assert save_calls["count"] == 1
    assert export_calls["count"] == 1


def test_domain_override_applied(tmp_path):
    cfg = FRAMConfig().model_copy(
        update={
            "STORAGE_ROOT": tmp_path / "storage",
            "domain_overrides": {"legal": {"coverage_gamma": 0.85, "lambda_tok": 0.01}},
        }
    )
    engine = QueryOrchestrator(config=cfg, tracer=None, data_root=DATA_ROOT)

    result = engine.run("override check", None, 2, "legal", "qa")
    trace = result["record"]["trace"]
    assert trace["coverage"]["gamma"] == pytest.approx(0.85)
    budgets = trace["selection"]["budgets"]
    assert budgets["lambda_tok"] == pytest.approx(0.01)


def test_task_override_supersedes_domain(tmp_path):
    cfg = FRAMConfig().model_copy(
        update={
            "STORAGE_ROOT": tmp_path / "storage",
            "domain_overrides": {"legal": {"coverage_gamma": 0.9}},
            "task_overrides": {"summary": {"coverage_gamma": 0.7, "lambda_rerank": 0.02}},
        }
    )
    engine = QueryOrchestrator(config=cfg, tracer=None, data_root=DATA_ROOT)

    result = engine.run("override precedence", None, 2, "legal", "summary")
    trace = result["record"]["trace"]
    assert trace["coverage"]["gamma"] == pytest.approx(0.7)
    budgets = trace["selection"]["budgets"]
    assert budgets["lambda_rerank"] == pytest.approx(0.02)


def test_memory_chunks_seed_coverage(orchestrator):
    engine, _ = orchestrator
    memory_claim = Claim(
        key="FRAM roadmap vision",
        type=ClaimType.Entity,
        buckets=("doc:memory:session", "layout:memory:session:0"),
    )
    memory_chunk = {
        "file": "memory:session",
        "chunk_id": 0,
        "text": "FRAM roadmap vision captured in memory",
        "claims": [memory_claim],
        "hierarchy": {
            "cluster": "memory:session",
            "segment": "memory:session:item:0",
            "chunk": "chunk:0",
        },
    }

    result = engine.run(
        "What is the F-RAM roadmap vision?",
        None,
        2,
        "general",
        "qa",
        memory_chunks=[memory_chunk],
    )

    coverage_delta = result["record"]["trace"]["selection"]["coverage_delta"]
    assert coverage_delta["memory"] > 0.0
    summed = (
        coverage_delta["memory"]
        + coverage_delta["seed"]
        + coverage_delta["anchors"]
        + coverage_delta["shards"]
    )
    assert pytest.approx(summed) == pytest.approx(coverage_delta["total"])
    coverage_summary = result["record"]["trace"]["coverage"]
    assert coverage_summary["value_after_memory"] >= coverage_summary["value_start"]


def test_curvature_anchor_candidates_prefers_lower_cost(monkeypatch, orchestrator):
    engine, _ = orchestrator

    monkeypatch.setattr(
        pipeline_mod,
        "principal_residual_directions",
        lambda *args, **kwargs: (np.array([[0.0], [1.0]]), np.array([4.0])),
    )

    chunk_vecs = np.array(
        [
            [1.0, 0.0],
            [0.8, 0.6],
            [0.8, -0.6],
        ],
        dtype=float,
    )
    chunks = [
        {"file": "doc", "chunk_id": i, "text": f"chunk {i}", "tokens": None}
        for i in range(3)
    ]
    context = pipeline_mod._ClusterContext(
        centroid=np.zeros(2, dtype=float),
        basis=np.zeros((2, 0), dtype=float),
        medians={},
        mads={},
        timestamp=0.0,
        neighbor_indices=[],
        projection=np.array([1.0, 0.0], dtype=float),
    )
    cost_entries = {
        0: {"reads": 1.0, "tokens": 50.0, "pairs_scale": 1.0},
        1: {"reads": 1.0, "tokens": 10.0, "pairs_scale": 1.0},
        2: {"reads": 1.0, "tokens": 120.0, "pairs_scale": 1.0},
    }

    plan = engine._curvature_anchor_candidates(
        seed_idx=0,
        context=context,
        doc_projections={"doc": np.array([1.0, 0.0], dtype=float)},
        chunk_vecs=chunk_vecs,
        chunks=chunks,
        ann_indices=[0, 1, 2],
        cand_order=[0, 1, 2],
        doc_to_chunk_indices={"doc": [0, 1, 2]},
        cost_entries=cost_entries,
        lambda_tokens=0.05,
        lambda_rerank=0.0,
        pairs_scale=1.0,
    )

    ranked = plan.order
    assert ranked[0] == 1
    assert ranked.index(1) < ranked.index(2)
    meta = plan.residual_steps.get(ranked[0])
    assert meta is not None
    assert meta["eig_index"] == 0
    assert meta["step_sign"] in (-1, 1)


def test_anchor_trace_includes_residual_steps(monkeypatch, orchestrator):
    engine, _ = orchestrator

    def fake_curvature(
        self,
        seed_idx,
        context,
        doc_projections,
        chunk_vecs,
        chunks,
        ann_indices,
        cand_order,
        doc_to_chunk_indices,
        cost_entries,
        lambda_tokens,
        lambda_rerank,
        pairs_scale,
    ):
        idx = int(cand_order[0]) if cand_order else int(seed_idx)
        meta = {
            "eig_index": 0,
            "eig_value": 1.0,
            "base_length": 1.0,
            "step_scale": 1.0,
            "step_sign": 1,
            "target_length": 1.0,
            "clamped_length": 1.0,
            "projection_cos": 0.5,
            "radial_low": 0.0,
            "radial_high": 1.0,
            "score": 1.0,
            "composite_cost": 1.0,
        }
        return pipeline_mod._AnchorPlan([idx], {idx: meta})

    def fake_select_celf(
        items,
        claims_map,
        cost_entries,
        k,
        lambdas,
        seed,
        state,
        gamma,
        u_max,
        lazy,
        **kwargs,
    ):
        selected = [int(i) for i in items]
        stats = {"pops": len(selected), "recomps": 0, "accepted": len(selected)}
        totals = {"reads": float(len(selected)), "tokens": 0.0, "pairs": 0.0, "cost": float(len(selected))}
        details = []
        for idx in selected:
            if state is not None:
                state.apply(claims_map.get(int(idx), ()))
            details.append(
                {
                    "id": int(idx),
                    "delta": 0.5,
                    "cost": 1.0,
                    "ratio": 0.5,
                    "reads": 1.0,
                    "tokens": 0.0,
                    "pairs": 0.0,
                    "seed": False,
                    "diversity_multiplier": 1.0,
                }
            )
        return selected, stats, details, totals

    monkeypatch.setattr(pipeline_mod.QueryOrchestrator, "_curvature_anchor_candidates", fake_curvature)
    monkeypatch.setattr(pipeline_mod, "select_celf", fake_select_celf)
    monkeypatch.setattr(conf, "conformal_policy", lambda *args, **kwargs: "anchors")

    result = engine.run("anchor metadata check", None, 2, "general", "qa")
    anchors = result["record"]["trace"]["selection"].get("anchors", [])
    if anchors:
        assert "residual_step" in anchors[0]
        assert "eig_index" in anchors[0]["residual_step"]

def test_roadmap_domain_override_promotes_anchors(monkeypatch, orchestrator):
    engine, _ = orchestrator

    monkeypatch.setattr(conf, "logistic_confidence", lambda *_, **__: 0.48)

    engine._session_memory = []
    general = engine.run("domain general", None, 1, "general", "qa")
    assert general["record"]["trace"]["confidence"]["decision"] != "anchors"

    roadmap = engine.run("domain roadmap", None, 1, "roadmap", "qa")
    roadmap_trace = roadmap["record"]["trace"]
    assert roadmap_trace["confidence"]["decision"] == "anchors"

    budgets = roadmap_trace["selection"]["budgets"]
    assert budgets["reads_limit"] == pytest.approx(5.0)
    assert budgets["lambda_tok"] == pytest.approx(0.001)



def test_roadmap_query_prefers_roadmap_doc(orchestrator):
    engine, _ = orchestrator
    result = engine.run(
        "What does the roadmap say about curvature anchors?",
        None,
        2000,
        "docs",
        "qa",
    )

    citations = result["citations"]
    assert citations, "expected citations"
    roadmap_positions = [
        idx for idx, cite in enumerate(citations) if cite.startswith("docs_ingest_f_ram_roadmap.txt")
    ]
    assert roadmap_positions, "expected roadmap citation"
    sample_positions = [
        idx
        for idx, cite in enumerate(citations)
        if cite.startswith("docs_ingest_observability_trace_sample.txt")
    ]
    if sample_positions:
        assert roadmap_positions[0] <= sample_positions[0]

    answer = result["answer"]
    assert "section:" in answer
    assert "roadmap" in answer.lower()
    observability_idx = answer.find("section:observability_trace_sample")
    roadmap_idx = answer.find("section:f_ram_roadmap")
    if observability_idx != -1:
        assert roadmap_idx != -1 and roadmap_idx < observability_idx

    trace = result["record"]["trace"]
    alignment = trace["selection"].get("doc_alignment", [])
    assert alignment, "expected doc alignment diagnostics"

    cache = engine.ensure_corpus()
    roadmap_hits = [
        entry
        for entry in alignment
        if cache.chunks[int(entry["id"])]["file"] == "docs_ingest_f_ram_roadmap.txt"
    ]
    assert roadmap_hits, "expected roadmap doc alignment"
    assert "roadmap" in roadmap_hits[0].get("tokens", [])


def test_candidate_overlap_uses_content_tokens_before_truncation():
    chunks = [
        {"file": "notes.txt", "tokens": ["aria"]},
        {"file": "bird.txt", "tokens": ["aria", "spring", "niobrara"]},
        {"file": "other.txt", "tokens": ["spring"]},
    ]

    ordered = pipeline_mod._prioritize_candidates_by_query_overlap(
        [0, 2, 1],
        chunks,
        {"aria", "rest", "spring"},
    )

    assert ordered == [1, 0, 2]


def test_candidate_overlap_keeps_document_metadata_in_primary_tier():
    chunks = [
        {
            "file": "observability_trace_sample.txt",
            "tokens": ["roadmap", "curvature", "anchors"],
        },
        {
            "file": "f_ram_roadmap.txt",
            "tokens": ["roadmap", "curvature"],
        },
    ]

    ordered = pipeline_mod._prioritize_candidates_by_query_overlap(
        [0, 1],
        chunks,
        {"roadmap", "curvature", "anchors"},
    )

    assert ordered == [1, 0]


def test_domain_specific_calibration_used(monkeypatch, orchestrator):
    engine, _ = orchestrator
    cache = engine.ensure_corpus()
    cache.calibration_by_task.pop("qa", None)
    base_cal = cache.calibration
    cache.calibration_by_domain["roadmap"] = CalibrationPayload(
        logistic_coefs=dict(base_cal.logistic_coefs),
        temperature=base_cal.temperature,
        tau1=0.95,
        tau2=0.85,
    )

    engine.config.domain_overrides.setdefault("roadmap", {})
    engine.config.domain_overrides["roadmap"].pop("tau1", None)
    engine.config.domain_overrides["roadmap"].pop("tau2", None)

    monkeypatch.setattr(conf, "logistic_confidence", lambda *_, **__: 0.58)

    general = engine.run("general calibration test", None, 1, "general", "qa")
    roadmap = engine.run("roadmap calibration test", None, 1, "roadmap", "qa")

    assert general["record"]["trace"]["confidence"]["decision"] == "anchors"
    assert roadmap["record"]["trace"]["confidence"]["decision"] == "global"

    general_cal = general["record"]["trace"]["confidence"]["calibration"]
    roadmap_cal = roadmap["record"]["trace"]["confidence"]["calibration"]

    assert general_cal["tau1"] == pytest.approx(base_cal.tau1)
    assert general_cal["tau2"] == pytest.approx(base_cal.tau2)
    assert general_cal["source"] in {"global", "default"}
    assert roadmap_cal["source"] == "domain:roadmap"
    assert roadmap_cal["tau1"] == pytest.approx(0.95)
    assert roadmap_cal["tau2"] == pytest.approx(0.85)


def test_task_specific_calibration_precedence(monkeypatch, orchestrator):
    engine, _ = orchestrator
    cache = engine.ensure_corpus()
    base_cal = cache.calibration

    cache.calibration_by_domain["roadmap"] = CalibrationPayload(
        logistic_coefs=dict(base_cal.logistic_coefs),
        temperature=base_cal.temperature,
        tau1=0.7,
        tau2=0.6,
    )
    cache.calibration_by_task["qa"] = CalibrationPayload(
        logistic_coefs=dict(base_cal.logistic_coefs),
        temperature=base_cal.temperature,
        tau1=0.95,
        tau2=0.9,
    )

    engine.config.domain_overrides.setdefault("roadmap", {})
    engine.config.domain_overrides["roadmap"].pop("tau1", None)
    engine.config.domain_overrides["roadmap"].pop("tau2", None)
    engine.config.task_overrides.setdefault("qa", {})
    engine.config.task_overrides["qa"].pop("tau1", None)
    engine.config.task_overrides["qa"].pop("tau2", None)

    monkeypatch.setattr(conf, "logistic_confidence", lambda *_, **__: 0.85)

    result = engine.run("task calibration precedence", None, 1, "roadmap", "qa")
    conf_trace = result["record"]["trace"]["confidence"]

    assert conf_trace["decision"] == "global"
    calibration = conf_trace["calibration"]
    assert calibration["source"] == "task:qa"
    assert calibration["tau1"] == pytest.approx(0.95)
    assert calibration["tau2"] == pytest.approx(0.9)


def test_default_domain_applies_calibration(monkeypatch):
    tracer = _StubTracer()
    cfg = FRAMConfig(default_domain="roadmap")
    engine = QueryOrchestrator(config=cfg, tracer=tracer)
    cache = engine.ensure_corpus()
    cache.calibration_by_task.pop("qa", None)
    base_cal = cache.calibration

    cache.calibration_by_domain["roadmap"] = CalibrationPayload(
        logistic_coefs=dict(base_cal.logistic_coefs),
        temperature=base_cal.temperature,
        tau1=0.74,
        tau2=0.58,
    )
    engine.config.domain_overrides.setdefault("roadmap", {})
    engine.config.domain_overrides["roadmap"].pop("tau1", None)
    engine.config.domain_overrides["roadmap"].pop("tau2", None)

    monkeypatch.setattr(conf, "logistic_confidence", lambda *_, **__: 0.6)

    result = engine.run("default domain calibration", None, 1)
    trace = result["record"]["trace"]
    calibration = trace["confidence"]["calibration"]

    assert result["record"]["domain"] == "roadmap"
    assert trace["domain"] == "roadmap"
    assert calibration["source"] == "domain:roadmap"
    assert calibration["tau1"] == pytest.approx(0.74)
    assert calibration["tau2"] == pytest.approx(0.58)


def test_calibration_falls_back_to_default():
    config = FRAMConfig()
    engine = QueryOrchestrator(config=config, tracer=None)
    cache = engine.ensure_corpus()
    override_cache = copy.deepcopy(cache)
    override_cache.calibration = None
    override_cache.calibration_by_domain.clear()
    override_cache.calibration_by_task.clear()

    default_payload = pipeline_mod._default_calibration(config)

    result = engine.run("fallback calibration", None, 1, "general", "qa", cache_override=override_cache)
    calibration = result["record"]["trace"]["confidence"]["calibration"]

    assert calibration["source"] == "default"
    assert calibration["tau1"] == pytest.approx(default_payload.tau1)
    assert calibration["tau2"] == pytest.approx(default_payload.tau2)


def test_calibration_falls_back_to_global_payload(orchestrator):
    engine, _ = orchestrator
    cache = engine.ensure_corpus()
    cache.calibration_by_task.pop("qa", None)
    base_cal = cache.calibration
    global_payload = CalibrationPayload(
        logistic_coefs=dict(base_cal.logistic_coefs),
        temperature=base_cal.temperature,
        tau1=0.91,
        tau2=0.61,
    )
    cache.calibration = global_payload
    cache.calibration_by_domain.pop("roadmap", None)

    engine.config.domain_overrides.setdefault("roadmap", {})
    engine.config.domain_overrides["roadmap"].pop("tau1", None)
    engine.config.domain_overrides["roadmap"].pop("tau2", None)

    result = engine.run("global fallback calibration", None, 1, "roadmap", "qa")
    calibration = result["record"]["trace"]["confidence"]["calibration"]

    assert calibration["source"] == "global"
    assert calibration["tau1"] == pytest.approx(0.91)
    assert calibration["tau2"] == pytest.approx(0.61)


def test_persisted_corpus_rebuilds_when_sklearn_changes(tmp_path, monkeypatch):
    storage_root = tmp_path / "storage"
    cfg = FRAMConfig().model_copy(update={"STORAGE_ROOT": storage_root})

    base_version = "1.0.0"
    upgraded_version = "2.0.0"

    monkeypatch.setattr(pipeline_mod, "_current_sklearn_version", lambda: base_version)
    engine = QueryOrchestrator(config=cfg, tracer=None, data_root=DATA_ROOT)
    cache = engine.ensure_corpus()
    assert cache.metadata.get("sklearn_version") == base_version
    assert cache.metadata.get("ann_backend") == "sklearn"

    index_dir = storage_root / cfg.STORAGE_SUBFOLDERS.get("index", "index") / "demo_corpus"
    meta_path = index_dir / "corpus.meta.json"
    assert meta_path.exists()
    meta_payload = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta_payload.get("sklearn_version") == base_version
    assert meta_payload.get("ann_backend") == "sklearn"

    loader_calls = {"count": 0}
    original_loader = pipeline_mod.load_demo_corpus

    def tracked_loader(*args, **kwargs):
        loader_calls["count"] += 1
        return original_loader(*args, **kwargs)

    monkeypatch.setattr(pipeline_mod, "load_demo_corpus", tracked_loader)
    monkeypatch.setattr(pipeline_mod, "_current_sklearn_version", lambda: upgraded_version)

    refreshed_engine = QueryOrchestrator(config=cfg, tracer=None, data_root=DATA_ROOT)
    refreshed_cache = refreshed_engine.ensure_corpus()

    assert loader_calls["count"] == 1
    assert refreshed_cache.metadata.get("sklearn_version") == upgraded_version
    assert refreshed_cache.metadata.get("ann_backend") == "sklearn"
    updated_meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert updated_meta.get("sklearn_version") == upgraded_version
    assert updated_meta.get("ann_backend") == "sklearn"


def test_ann_metadata_records_backend(tmp_path):
    storage_root = tmp_path / "storage"
    cfg = FRAMConfig().model_copy(update={"STORAGE_ROOT": storage_root})
    engine = QueryOrchestrator(config=cfg, tracer=None, data_root=DATA_ROOT)
    engine.run("ann meta check", None, 1, "general", "qa")

    index_dir = storage_root / cfg.STORAGE_SUBFOLDERS.get("index", "index") / "demo_corpus"
    ann_meta_path = index_dir / "ann_index.meta.json"
    assert ann_meta_path.exists()
    ann_meta = json.loads(ann_meta_path.read_text(encoding="utf-8"))
    assert ann_meta.get("backend") == "sklearn"
    assert ann_meta.get("file", "").endswith(".joblib")


def test_ann_backend_faiss_fallback(monkeypatch, tmp_path):
    storage_root = tmp_path / "storage"
    cfg = FRAMConfig().model_copy(update={"STORAGE_ROOT": storage_root})
    monkeypatch.setenv("FRAM_ANN_BACKEND", "faiss")
    monkeypatch.setattr(pipeline_mod, "faiss", None, raising=False)
    engine = QueryOrchestrator(config=cfg, tracer=None, data_root=DATA_ROOT)
    engine.ensure_corpus()
    assert engine._ann_backend == "sklearn"
    assert engine._ann_index_filename.endswith(".joblib")


def test_section_penalty_domain_override(monkeypatch, orchestrator):
    engine, _ = orchestrator

    captured: list[tuple[float | None, float | None]] = []
    original = pipeline_mod.select_celf

    def wrapped_select_celf(*args, **kwargs):
        captured.append(
            (
                kwargs.get("segment_repeat_penalty"),
                kwargs.get("segment_penalty_floor"),
            )
        )
        return original(*args, **kwargs)

    monkeypatch.setattr(pipeline_mod, "select_celf", wrapped_select_celf)

    engine.run("roadmap penalty sweep", None, 2, "roadmap", "qa")

    assert captured, "expected select_celf to be invoked"
    expected_repeat = engine.config.domain_overrides["roadmap"].get("section_repeat_penalty")
    expected_floor = engine.config.domain_overrides["roadmap"].get("section_penalty_floor")
    assert expected_repeat is not None and expected_floor is not None
    for repeat, floor in captured:
        assert repeat == pytest.approx(expected_repeat)
        assert floor == pytest.approx(expected_floor)


def test_trace_log_writer_persists_records(tmp_path):
    cfg = FRAMConfig().model_copy(update={"STORAGE_ROOT": tmp_path})
    traces_dir = tmp_path / cfg.STORAGE_SUBFOLDERS.get("traces", "traces")
    tracer = observability.TraceLogWriter(traces_dir)
    engine = QueryOrchestrator(config=cfg, tracer=tracer)

    result = engine.run("trace logging", None, 1, "general", "qa")

    files = list(traces_dir.glob("trace_*.jsonl"))
    assert files, "expected trace log file"
    latest = max(files)
    contents = latest.read_text(encoding="utf-8").strip().splitlines()
    assert contents, "expected at least one trace record"
    record = json.loads(contents[-1])
    assert record["id"] == result["trace_id"]
    assert record["query"] == "trace logging"
    assert record["trace"]["trace_id"] == result["trace_id"]


def _reset_app_state(tmp_path, monkeypatch):
    cfg = FRAMConfig().model_copy(update={"STORAGE_ROOT": tmp_path})
    trace_dir = tmp_path / cfg.STORAGE_SUBFOLDERS.get("traces", "traces")
    monkeypatch.setattr(app_mod, "CFG", cfg, raising=False)
    monkeypatch.setattr(app_mod, "_TRACE_DIR", trace_dir, raising=False)
    monkeypatch.setattr(app_mod, "TRACE_LOGGER", observability.TraceLogWriter(trace_dir), raising=False)
    monkeypatch.setattr(app_mod, "_ORCHESTRATOR", None, raising=False)
    monkeypatch.setattr(app_mod, "_PROB_CACHE", OrderedDict(), raising=False)
    monkeypatch.setattr(app_mod, "REL", observability.LiveReliability(maxlen=max(1, int(cfg.metrics_window))), raising=False)
    monkeypatch.setattr(app_mod, "ALM", observability.AlarmBook(alpha1=cfg.alpha1, alpha2=cfg.alpha2), raising=False)
    memory_dir = cfg.STORAGE_ROOT / cfg.STORAGE_SUBFOLDERS.get("memory", "memory")
    monkeypatch.setattr(app_mod, "_MEMORY_STORE", app_mod.WorkingMemoryStore(memory_dir), raising=False)


def test_query_endpoint_uses_requested_domain(tmp_path, monkeypatch):
    _reset_app_state(tmp_path, monkeypatch)
    client = TestClient(app_mod.app)

    response = client.post("/query", json={"text": "domain shift", "domain": "Roadmap", "task": "Diary"})
    assert response.status_code == 200
    payload = response.json()
    trace = payload["trace"]

    assert trace["domain"] == "roadmap"
    assert trace["task"] == "diary"
    calibration = trace.get("confidence", {}).get("calibration")
    assert calibration is not None
    assert calibration.get("source") in {"global", "default", "domain:roadmap", "task:diary"}


def test_label_endpoint_updates_reliability(tmp_path, monkeypatch):
    _reset_app_state(tmp_path, monkeypatch)
    client = TestClient(app_mod.app)

    query_resp = client.post("/query", json={"text": "label me"})
    assert query_resp.status_code == 200
    query_id = query_resp.json()["id"]

    label_resp = client.post("/label", json={"query_id": query_id, "label": 1})
    assert label_resp.status_code == 200
    payload = label_resp.json()
    assert payload["query_id"] == query_id
    assert payload["label"] == 1
    assert payload["metrics"]["window_size"] >= 1

    metrics_resp = client.get("/metrics")
    metrics = metrics_resp.json()
    assert metrics["window_size"] >= 1
    reliability_summary = metrics.get("reliability", {})
    by_domain = reliability_summary.get("by_domain", {})
    by_task = reliability_summary.get("by_task", {})
    latest_metric = reliability_summary.get("latest")
    assert reliability_summary, "expected reliability summary in metrics output"
    assert latest_metric is not None, "expected latest reliability entry"

    obs_dir = app_mod.CFG.STORAGE_ROOT / app_mod.CFG.STORAGE_SUBFOLDERS.get("observability", "observability")
    confidence_log = obs_dir / "confidence.jsonl"
    assert confidence_log.exists()
    lines = [line for line in confidence_log.read_text(encoding="utf-8").strip().splitlines() if line.strip()]

    records: list[dict] = []
    for line in lines:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        records.append(record)

    label_records = [rec for rec in records if rec.get("event") == "label"]
    decision_records = [rec for rec in records if rec.get("event") == "decision"]
    assert label_records, "expected label event in confidence log"
    assert decision_records, "expected decision event in confidence log"

    last_label = label_records[-1]
    last_decision = decision_records[-1]

    def _expected(value: str | None, fallback: str) -> str:
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
        return fallback

    expected_domain = _expected(getattr(app_mod.CFG, "default_domain", None), "general")
    expected_task = _expected(getattr(app_mod.CFG, "default_task", None), "qa")

    assert by_domain.get(expected_domain, {}).get("count", 0) >= 1
    assert by_task.get(expected_task, {}).get("count", 0) >= 1
    assert latest_metric.get("domain") == expected_domain
    assert latest_metric.get("task") == expected_task

    assert last_label.get("domain") == expected_domain
    assert last_label.get("task") == expected_task
    assert last_decision.get("domain") == expected_domain
    assert last_decision.get("task") == expected_task

    assert last_label.get("tau1") is not None and last_label["tau1"] > 0
    assert last_label.get("tau2") is not None and last_label["tau2"] > 0
    assert last_decision.get("tau1") == pytest.approx(last_label["tau1"])
    assert last_decision.get("tau2") == pytest.approx(last_label["tau2"])

    rel_records = list(app_mod.REL._records)  # type: ignore[attr-defined]
    assert rel_records, "expected reliability tracker to retain entries"
    rel_latest = rel_records[-1]
    assert rel_latest["tau1"] == pytest.approx(last_label["tau1"])
    assert rel_latest["tau2"] == pytest.approx(last_label["tau2"])
    assert rel_latest.get("domain") == expected_domain
    assert rel_latest.get("task") == expected_task
    if last_label.get("calibration_source"):
        assert rel_latest.get("source") == last_label.get("calibration_source")

def test_session_memory_replay(orchestrator):
    engine, _ = orchestrator

    engine.run("prime session", None, 2, "general", "qa")
    assert engine._session_memory, "expected session memory after first run"
    primed_snapshot = [copy.deepcopy(chunk) for chunk in engine._session_memory]

    fresh_engine = QueryOrchestrator(config=FRAMConfig(), tracer=None)
    control = fresh_engine.run("budget zero baseline", None, 0, "general", "qa")
    assert control["citations"] == []

    replay_result = engine.run("budget zero with replay", None, 0, "general", "qa")
    assert replay_result["citations"], "expected memory-driven citations"
    trace = replay_result["record"]["trace"]
    first_snapshot = primed_snapshot[0]
    expected_citation = "{}:chunk{}".format(first_snapshot.get("file"), first_snapshot.get("chunk_id"))
    assert expected_citation in replay_result["citations"]
    # Memory replay now reserves read slots in the budget, even when the incoming
    # request has zero reads available (see docs/F-RAM-roadmap.md Always-On Memory).
    reads_used = trace["selection"]["budgets"]["reads_used"]
    assert reads_used == pytest.approx(len(primed_snapshot))
    assert trace["selection"]["budgets"]["reads_limit"] == pytest.approx(0.0)


def test_hierarchy_sections_reflect_headings(orchestrator):
    engine, _ = orchestrator
    cache = engine.ensure_corpus()
    segments = {chunk["hierarchy"]["segment"] for chunk in cache.chunks if chunk.get("file") == "docs_ingest_f_ram_roadmap.txt"}
    assert segments, "expected roadmap chunks in corpus"
    assert all(seg.startswith("section:") for seg in segments)
    assert any(
        seg.startswith("section:vision_next_steps_1_calibration_confidence_tuning_short_term")
        or seg.startswith("section:f_ram_roadmap_next_steps_1_calibration_confidence_tuning_short_term")
        for seg in segments
    )
