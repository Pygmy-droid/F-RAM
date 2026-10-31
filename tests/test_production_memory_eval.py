from __future__ import annotations

import json
import sqlite3
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from fram_core.claims import Claim
from fram_eval import production_memory_eval as adapter
from fram_eval.production_memory_eval import (
    ExactTraceCache,
    build_context,
    capture_selection,
    evaluate_production,
    isolated_evaluation,
    merge_production_reports,
    snapshot_memory,
    strict_production_gate,
    tree_manifest,
    validate_config,
)
from fram_serving import query_runner
from fram_serving.cognitive_embeddings import build_cognitive_vectorizer
from fram_serving.config import FRAMConfig
from fram_serving.fractal_memory.fractal_gen import FractalGenerator
from fram_serving.lived_memory import LivedMemoryStore
from fram_serving.memory import CognitiveMemoryStore


def fixture_store(tmp_path: Path, **updates):
    config = FRAMConfig().model_copy(
        update={
            "STORAGE_ROOT": tmp_path,
            "fractal_enabled": True,
            "fractal_downsample_target": 8,
            "cognitive_memory_half_life_hours": 8760.0,
            "lived_memory_enabled": False,
            **updates,
        }
    )
    vectorizer = build_cognitive_vectorizer(config)
    store = CognitiveMemoryStore(tmp_path / "memory" / "cognitive", config=config)

    def embedding(text):
        return vectorizer.transform([text]).toarray()[0].tolist()

    # Generate small, internally consistent traces specifically for this fixture.
    store._ensure_fractal_store(len(embedding("lantern")))
    store.fractal_trace_store().generator = FractalGenerator(
        len(embedding("lantern")), n_nodes=8
    )
    first = store.append_episode(
        query="lantern fox tea",
        answer="silver lantern hearth",
        embedding=embedding("lantern fox tea silver lantern hearth"),
    )
    second = store.append_episode(
        query="lantern fox garden",
        answer="blue lantern garden",
        embedding=embedding("lantern fox garden blue lantern garden"),
    )
    belief = store.append_belief(
        text="lantern fox prefers gentle tea",
        confidence=0.9,
        embedding=embedding("lantern fox prefers gentle tea"),
    )
    return config, first["id"], second["id"], belief["id"]


def test_adapter_capture_equals_direct_route_including_beliefs(tmp_path):
    config, first, _, belief = fixture_store(tmp_path / "source")
    source = tmp_path / "source" / "memory"
    snapshot_memory(source, tmp_path / "direct" / "memory")
    snapshot_memory(source, tmp_path / "adapter" / "memory")
    direct = build_context(tmp_path / "direct", config)
    req = SimpleNamespace(
        text="lantern fox tea",
        domain="general",
        task="qa",
        as_of=None,
        version_id=None,
        budget_reads=None,
        memory_session=None,
        principal=None,
    )
    actual = query_runner.run_query(req, direct)
    adapted = capture_selection(build_context(tmp_path / "adapter", config), req.text)
    assert [c["id"] for c in adapted["selected"]] == [
        c["file"] for c in direct.orchestrator.chunks
    ]
    assert [c["id"] for c in adapted["trace_prefix"]] == [
        c["id"] for c in actual["trace"]["cognitive_memory"]["selected"]
    ]
    assert f"cmem:ep:{first}" in [c["id"] for c in adapted["selected"]]
    assert f"cmem:bl:{belief}" in [c["id"] for c in adapted["selected"]]
    assert [c["score"] for c in adapted["trace_prefix"]] == pytest.approx(
        [c["score"] for c in actual["trace"]["cognitive_memory"]["selected"]], abs=1e-6
    )
    assert len(adapted["selected"]) == len(adapted["chunks"])


def test_real_ann_only_candidate_and_global_trace_population(tmp_path):
    config, _, _, _ = fixture_store(
        tmp_path / "source",
        cognitive_memory_k=1,
        cognitive_ann_top_k=8,
        fractal_influence_enabled=True,
    )
    snapshot_memory(tmp_path / "source" / "memory", tmp_path / "run" / "memory")
    ctx = build_context(tmp_path / "run", config)
    base = ctx.cognitive_store.search(
        "lantern fox tea", k=1, vectorizer=ctx.get_memory_vectorizer()
    )
    base_ids = {
        f"cmem:{'ep' if row['kind'] == 'episode' else 'bl'}:{row['id']}" for row in base
    }
    captured = capture_selection(ctx, "lantern fox tea")
    selected_ids = {row["id"] for row in captured["selected"]}
    assert captured["ann_bridge"]["applied"]
    assert selected_ids - base_ids  # Real persisted ANN contributes outside base k=1.
    vector, _ = ctx.encode_cognitive_text("lantern fox tea")
    scored = query_runner._fractal_trace_scores(ctx.cognitive_store, vector, 3, ctx.cfg)
    assert any(f"cmem:ep:{row['episode_id']}" not in base_ids for row in scored)
    assert any(row["fractal_influence"] > 0 for row in captured["selected"])


def test_flag_off_is_invariant_to_alpha_and_cache_matches_uncached(tmp_path):
    config, _, _, _ = fixture_store(
        tmp_path / "source", fractal_influence_enabled=False
    )
    snapshot_memory(tmp_path / "source" / "memory", tmp_path / "a" / "memory")
    snapshot_memory(tmp_path / "source" / "memory", tmp_path / "b" / "memory")
    a = capture_selection(build_context(tmp_path / "a", config), "lantern fox tea")
    high_alpha = config.model_copy(update={"fractal_influence_alpha": 1000.0})
    b = capture_selection(build_context(tmp_path / "b", high_alpha), "lantern fox tea")
    assert [c["id"] for c in a["selected"]] == [c["id"] for c in b["selected"]]
    assert [c["score"] for c in a["selected"]] == pytest.approx(
        [c["score"] for c in b["selected"]], abs=1e-6
    )
    assert all(c["fractal_influence"] == 0.0 for c in b["selected"])
    ctx = build_context(tmp_path / "b", config)
    vector, _ = ctx.encode_cognitive_text("lantern fox tea")
    expected = query_runner._fractal_trace_scores(
        ctx.cognitive_store, vector, 3, ctx.cfg
    )
    cache = ExactTraceCache()
    assert cache(ctx.cognitive_store, vector, 3, ctx.cfg) == expected
    assert cache(ctx.cognitive_store, vector, 3, ctx.cfg) == expected
    assert (cache.hits, cache.misses) == (1, 1)
    cached = cache(ctx.cognitive_store, vector, 3, ctx.cfg)
    cached.clear()
    assert cache(ctx.cognitive_store, vector, 3, ctx.cfg) == expected
    ctx.cfg = ctx.cfg.model_copy(update={"fractal_blend_alpha": 0.3})
    cache(ctx.cognitive_store, vector, 3, ctx.cfg)
    assert cache.misses == 2


def test_single_capture_serves_both_metrics_and_preserves_source(tmp_path):
    config, first, _, _ = fixture_store(tmp_path / "source")
    source = tmp_path / "source" / "memory"
    before = tree_manifest(source)
    report = evaluate_production(
        [
            {
                "id": "tea",
                "match_episode_id": first,
                "probe": "lantern fox tea",
                "probe_low_lex": "gentle hearth lantern",
            }
        ],
        source_memory_root=source,
        scratch_root=tmp_path / "eval",
        config=config,
        max_items=1,
    )
    assert report["source_unchanged"] and before == tree_manifest(source)
    assert report["matching"]["matched"] == 1
    assert (
        len(report["captures"]) == 6
    )  # 3 modes x 2 fields, not two separate evaluations.
    assert report["trace_cache"]["hits"] >= 2
    for mode in ("semantic", "lexical", "fractal"):
        for field in ("probe", "probe_low_lex"):
            assert report["conversation"]["results"][mode][field]["count"] == 1
            assert report["shadow"]["results"][mode][field]["count"] == 1
    serialized = json.dumps(report)
    assert "silver lantern hearth" not in serialized
    assert "lantern fox tea" not in serialized
    assert "api_key" not in report["profile"]
    assert report["profile"]["cognitive_memory_half_life_hours"] == 8760.0


def test_unsupported_profile_and_roots_fail_closed(tmp_path):
    config, _, _, _ = fixture_store(tmp_path / "source")
    source = tmp_path / "source" / "memory"
    with pytest.raises(ValueError, match="disjoint"):
        snapshot_memory(source, source / "scratch")
    with pytest.raises(ValueError, match="disjoint"):
        snapshot_memory(source, source)
    with pytest.raises(ValueError, match="Phase-D"):
        validate_config(
            config.model_copy(
                update={"phase_d": config.phase_d.model_copy(update={"enabled": True})}
            )
        )
    with pytest.raises(ValueError, match="capsule"):
        validate_config(
            config.model_copy(update={"memory_capsule_retrieval_enabled": True})
        )
    with pytest.raises(ValueError, match="remain in scratch"):
        validate_config(
            config.model_copy(
                update={"STORAGE_SUBFOLDERS": {"observability": "../escape"}}
            )
        )
    with pytest.raises(TypeError):
        evaluate_production(
            [],
            source_memory_root=source,
            scratch_root=tmp_path / "bad",
            config=config,
            pool_multiplier=3,
        )
    with pytest.raises(ValueError, match="explicit fractal"):
        evaluate_production(
            [],
            source_memory_root=source,
            scratch_root=tmp_path / "bad",
            config=config.model_copy(update={"fractal_enabled": False}),
        )


def test_active_lived_wal_rejected_without_touching_source(tmp_path):
    config, _, _, _ = fixture_store(tmp_path / "source")
    source = tmp_path / "source" / "memory"
    (source / "lived").mkdir()
    (source / "lived" / "lived_memory.sqlite3-wal").write_bytes(
        b"not a consistent snapshot"
    )
    before = tree_manifest(source)
    with pytest.raises(ValueError, match="offline SQLite backup"):
        snapshot_memory(source, tmp_path / "copy")
    assert tree_manifest(source) == before


def test_supplied_lived_snapshot_participates_without_writes(tmp_path):
    config, first, _, _ = fixture_store(tmp_path / "source", lived_memory_enabled=True)
    vectorizer = build_cognitive_vectorizer(config)
    lived = LivedMemoryStore(tmp_path / "fixture-live")
    lived.append_experience(
        query="lantern fox tea",
        answer="a distinct lived memory",
        embedding=vectorizer.transform(["lantern fox tea"]).toarray()[0],
        session_id="synthetic-living-fixture",
        episode_id=first,
    )
    source = tmp_path / "source" / "memory"
    (source / "lived").mkdir()
    with sqlite3.connect(lived.path) as origin:
        with sqlite3.connect(source / "lived" / "lived_memory.sqlite3") as backup:
            origin.backup(backup)
            backup.execute("PRAGMA journal_mode=DELETE")
    origin.close()
    backup.close()
    before = tree_manifest(source)
    snapshot_memory(source, tmp_path / "run" / "memory")
    captured = capture_selection(
        build_context(tmp_path / "run", config), "lantern fox tea"
    )
    assert captured["lived_store_present"]
    assert any(entry["id"].startswith("lmem:event:") for entry in captured["selected"])
    assert tree_manifest(source) == before
    assert (
        LivedMemoryStore(tmp_path / "run" / "memory" / "lived").status()["event_count"]
        == 1
    )


def test_cache_key_includes_flag_and_binding_corpus(tmp_path):
    config, _, _, _ = fixture_store(tmp_path / "source")
    snapshot_memory(tmp_path / "source" / "memory", tmp_path / "run" / "memory")
    ctx = build_context(tmp_path / "run", config)
    vector, _ = ctx.encode_cognitive_text("lantern fox tea")
    cache = ExactTraceCache()
    cache(ctx.cognitive_store, vector, 3, ctx.cfg)
    cache(
        ctx.cognitive_store,
        vector,
        3,
        ctx.cfg.model_copy(update={"fractal_influence_enabled": True}),
    )
    assert cache.misses == 2
    ctx.cognitive_store.append_episode(query="new binding corpus row", answer="fixture")
    cache(ctx.cognitive_store, vector, 3, ctx.cfg)
    assert cache.misses == 3


def test_actual_claim_bearing_chunks_preserve_typed_private_capture(tmp_path):
    config, _, _, _ = fixture_store(tmp_path / "source")
    vectorizer = build_cognitive_vectorizer(config)
    store = CognitiveMemoryStore(
        tmp_path / "source" / "memory" / "cognitive", config=config
    )
    text = "On 2026-09-08 Eterna recorded 12 cups of tea in FRAM-22."
    episode = store.append_episode(
        query="Eterna tea record",
        answer=text,
        embedding=vectorizer.transform([text]).toarray()[0],
    )
    snapshot_memory(tmp_path / "source" / "memory", tmp_path / "direct" / "memory")
    capture = capture_selection(
        build_context(tmp_path / "direct", config), "Eterna tea record"
    )
    claims = [claim for chunk in capture["chunks"] for claim in chunk["claims"]]
    assert claims and all(isinstance(claim, Claim) for claim in claims)
    report = evaluate_production(
        [
            {
                "id": "typed-claim",
                "match_episode_id": episode["id"],
                "probe": "Eterna tea record",
            }
        ],
        source_memory_root=tmp_path / "source" / "memory",
        scratch_root=tmp_path / "eval",
        config=config,
        modes=("semantic",),
        fields=("probe",),
        max_items=1,
    )
    private = json.loads((tmp_path / "eval" / "private-captures.jsonl").read_text())
    encoded_claims = [claim for chunk in private["chunks"] for claim in chunk["claims"]]
    assert encoded_claims
    assert all(
        claim["record_type"] == "fram_core.claims.Claim" for claim in encoded_claims
    )
    assert any(claim["fields"]["type"] == "date" for claim in encoded_claims)
    assert any(claim["fields"]["key"] == "2026-09-08" for claim in encoded_claims)
    assert all(isinstance(claim["fields"]["buckets"], list) for claim in encoded_claims)
    assert text not in json.dumps(report)
    progress = json.loads((tmp_path / "eval" / "production-progress.json").read_text())
    assert progress["status"] == "completed"
    assert (
        progress["queries_attempted"]
        == progress["queries_selected"]
        == progress["queries_persisted"]
        == 1
    )
    assert progress["source_preservation"]["status"] == "unchanged"


def test_failure_receipt_counts_expensive_selection_without_exposing_bodies(
    tmp_path, monkeypatch
):
    config, first, _, _ = fixture_store(tmp_path / "source")
    source = tmp_path / "source" / "memory"
    before = tree_manifest(source)
    private_text = "private source body must not leak through errors"

    def fail_serialization(_value):
        raise TypeError(private_text)

    monkeypatch.setattr(adapter, "_private_json", fail_serialization)
    with pytest.raises(TypeError, match=private_text):
        evaluate_production(
            [
                {
                    "id": "serialization-failure",
                    "match_episode_id": first,
                    "probe": "lantern fox tea",
                }
            ],
            source_memory_root=source,
            scratch_root=tmp_path / "eval",
            config=config,
            modes=("semantic",),
            fields=("probe",),
            max_items=1,
        )
    serialized = (tmp_path / "eval" / "production-progress.json").read_text()
    progress = json.loads(serialized)
    assert progress["status"] == "failed"
    assert progress["error_type"] == "TypeError"
    assert progress["phase"] == "metrics_and_private_capture"
    assert progress["queries_selected"] == progress["queries_attempted"] == 1
    assert progress["queries_persisted"] == 0
    assert progress["selection_seconds"] > 0
    assert progress["elapsed_seconds"] >= progress["selection_seconds"]
    assert progress["source_preservation"]["status"] == "unchanged"
    assert private_text not in serialized and "lantern fox tea" not in serialized
    assert tree_manifest(source) == before


def _passing_scope_fixture(count=6):
    """Synthetic evidence for gate validation, not retrieval-performance evidence."""
    import hashlib

    items = [
        {
            "id": f"item-{index}",
            "match_episode_id": f"target-{index}",
            "probe": f"query {index}",
            "probe_low_lex": f"other query {index}",
        }
        for index in range(count)
    ]
    captures = []
    for mode in adapter.MODES:
        for field in ("probe", "probe_low_lex"):
            for item in items:
                target = "cmem:ep:" + item["match_episode_id"]
                ids = (
                    [target, "cmem:ep:other"]
                    if mode == "fractal"
                    else ["cmem:ep:other", target]
                )
                captures.append(
                    {
                        "mode": mode,
                        "field": field,
                        "item_id": item["id"],
                        "query_sha256": hashlib.sha256(
                            item[field].encode()
                        ).hexdigest(),
                        "expected_id": target,
                        "rank": 0 if mode == "fractal" else 1,
                        "source_corpus_sha256": "synthetic-corpus",
                        "clock": {"utc_iso": "2026-09-08T17:00:00+00:00"},
                        "elapsed_seconds": 1.0,
                        "delta": 0.2 if mode == "fractal" else 0.1,
                        "selected": [
                            {
                                "id": ident,
                                **{
                                    key: 1.0
                                    for key in (
                                        "score",
                                        "score_raw",
                                        "base_score",
                                        "fractal_score",
                                        "combined_score",
                                        "recency_weight",
                                    )
                                },
                            }
                            for ident in ids
                        ],
                    }
                )
    conversation, shadow = adapter._capture_metrics(captures)
    report = {
        "schema": "production-cognitive-selection-v1",
        "dataset_sha256": adapter._digest(items),
        "source_unchanged": True,
        "full_dataset_evaluated": True,
        "trace_cache": {"boundary_violations": 0},
        "matching": {
            "total": count,
            "matched": count,
            "matched_by_id": count,
            "missing": 0,
            "ambiguous": 0,
        },
        "resolved_targets": {item["id"]: item["match_episode_id"] for item in items},
        "provenance": {"corpus_sha256": "synthetic-corpus"},
        "evaluation_time": "2026-09-08T17:00:00+00:00",
        "captures": captures,
        "conversation": conversation,
        "shadow": shadow,
    }
    return items, report


def test_six_matched_of_full_36_cannot_pass_strict_gate():
    items, report = _passing_scope_fixture(36)
    assert strict_production_gate(report, items)["recommend_enable"]
    kept = {item["id"] for item in items[:6]}
    report["captures"] = [row for row in report["captures"] if row["item_id"] in kept]
    report["resolved_targets"] = {
        key: value for key, value in report["resolved_targets"].items() if key in kept
    }
    report["matching"].update(matched=6, matched_by_id=6, missing=30)
    report["conversation"], report["shadow"] = adapter._capture_metrics(
        report["captures"]
    )
    # Reproduce the unsafe old rule: full attempted list and six counted examples.
    assert adapter.recommend_fractal_influence(
        report["conversation"],
        report["shadow"],
        fields=("probe", "probe_low_lex"),
        low_lex_fields=("probe_low_lex",),
    )["recommend_enable"]
    gate = strict_production_gate(report, items)
    assert not gate["recommend_enable"] and not gate["production_scope_complete"]
    assert "incomplete or ambiguous target coverage" in gate["scope_errors"]
    assert "paired item/query/expected-ID row coverage mismatch" in gate["scope_errors"]


@pytest.mark.parametrize(
    "defect",
    [
        "nan_delta",
        "nan_aggregate",
        "query_mismatch",
        "duplicate_row",
        "wrong_expected",
        "missing_vector",
        "ambiguous",
    ],
)
def test_invalid_paired_evidence_cannot_authorize(defect):
    items, report = _passing_scope_fixture()
    if defect == "nan_delta":
        report["captures"][0]["delta"] = float("nan")
    elif defect == "nan_aggregate":
        report["shadow"]["results"]["fractal"]["probe"]["avg_delta"] = float("nan")
    elif defect == "query_mismatch":
        report["captures"][0]["query_sha256"] = "different query"
    elif defect == "duplicate_row":
        report["captures"].append(deepcopy(report["captures"][0]))
    elif defect == "wrong_expected":
        report["captures"][0]["expected_id"] = "cmem:ep:wrong"
    elif defect == "missing_vector":
        report["shadow"]["results"]["semantic"]["probe"]["missing_vectors"] = 1
    else:
        report["matching"]["ambiguous"] = 1
    gate = strict_production_gate(report, items)
    assert not gate["recommend_enable"]
    assert gate["scope_errors"]


def test_off_observation_skip_respects_delivery_and_fixed_clock(tmp_path):
    config, _, _, _ = fixture_store(tmp_path / "source", fractal_influence_alpha=0.0)
    clock = datetime(2027, 1, 1, tzinfo=timezone.utc)
    captures = []
    for name, skip, influence in (
        ("direct", False, False),
        ("off_skip", True, False),
        ("on", True, True),
    ):
        snapshot_memory(tmp_path / "source" / "memory", tmp_path / name / "memory")
        ctx = build_context(
            tmp_path / name,
            config.model_copy(update={"fractal_influence_enabled": influence}),
        )
        cache = ExactTraceCache(skip_off_observation=skip)
        cache.active_orchestrator = ctx.orchestrator
        with isolated_evaluation(tmp_path / name, cache, clock):
            captures.append(capture_selection(ctx, "lantern fox tea"))
        assert captures[-1]["clock"]["utc_iso"] == clock.isoformat()
        if name == "off_skip":
            assert cache.off_observations_skipped == 1 and cache.misses == 0
        if name == "on":
            assert cache.off_observations_skipped == 0 and cache.misses > 0
    for capture in captures[1:]:
        assert [row["id"] for row in capture["selected"]] == [
            row["id"] for row in captures[0]["selected"]
        ]
        assert [row["score"] for row in capture["selected"]] == [
            row["score"] for row in captures[0]["selected"]
        ]
    guard = ExactTraceCache(skip_off_observation=True)
    guard.active_orchestrator = adapter.CaptureOrchestrator()
    vector, _ = ctx.encode_cognitive_text("lantern fox tea")
    with pytest.raises(RuntimeError, match="before actual chunk delivery"):
        guard(ctx.cognitive_store, vector, 3, config)
    assert guard.boundary_violations == 1


def test_serial_and_sharded_actual_selections_aggregate_equally(tmp_path):
    config, first, second, _ = fixture_store(tmp_path / "source")
    items = [
        {
            "id": "first",
            "match_episode_id": first,
            "probe": "lantern fox tea",
            "probe_low_lex": "gentle hearth lantern",
        },
        {
            "id": "second",
            "match_episode_id": second,
            "probe": "lantern fox garden",
            "probe_low_lex": "blue garden lantern",
        },
    ]
    common = {
        "source_memory_root": tmp_path / "source" / "memory",
        "config": config,
        "evaluation_time": "2027-01-01T00:00:00+00:00",
        "skip_off_observation": True,
    }
    serial = evaluate_production(
        items, scratch_root=tmp_path / "serial", max_items=2, **common
    )
    shards = [
        evaluate_production(
            items,
            scratch_root=tmp_path / f"shard-{index}",
            item_offset=index,
            max_items=1,
            **common,
        )
        for index in range(2)
    ]
    merged = merge_production_reports(shards, items=items, expected_shards=2)
    assert merged["conversation"] == serial["conversation"]
    assert merged["shadow"] == serial["shadow"]
    assert strict_production_gate(merged, items)["production_scope_complete"]
    with pytest.raises(ValueError, match="missing shard"):
        merge_production_reports(shards[:1], items=items, expected_shards=2)
    with pytest.raises(ValueError, match="overlapping"):
        merge_production_reports([shards[0], shards[0]], items=items, expected_shards=2)
    damaged = deepcopy(shards)
    damaged[1]["captures"].pop()
    with pytest.raises(ValueError, match="incomplete shard"):
        merge_production_reports(damaged, items=items, expected_shards=2)
    damaged = deepcopy(shards)
    damaged[1]["evaluation_time"] = "2027-01-02T00:00:00+00:00"
    with pytest.raises(ValueError, match="clock policy mismatch"):
        merge_production_reports(damaged, items=items, expected_shards=2)


def test_swallowed_pre_delivery_skip_error_still_invalidates_run(tmp_path, monkeypatch):
    config, first, _, _ = fixture_store(tmp_path / "source")
    real_run_query = query_runner.run_query

    def premature_observation(req, ctx):
        vector, _ = ctx.encode_cognitive_text(req.text)
        try:
            query_runner._fractal_trace_scores(ctx.cognitive_store, vector, 3, ctx.cfg)
        except RuntimeError:
            pass  # Simulate the serving route swallowing an optional-stage failure.
        return real_run_query(req, ctx)

    monkeypatch.setattr(query_runner, "run_query", premature_observation)
    with pytest.raises(RuntimeError, match="crossed the selection boundary"):
        evaluate_production(
            [{"id": "boundary", "match_episode_id": first, "probe": "lantern fox tea"}],
            source_memory_root=tmp_path / "source" / "memory",
            scratch_root=tmp_path / "eval",
            config=config,
            modes=("semantic",),
            fields=("probe",),
            skip_off_observation=True,
        )
    receipt = json.loads((tmp_path / "eval" / "production-progress.json").read_text())
    assert receipt["status"] == "failed"
    assert receipt["source_preservation"]["status"] == "unchanged"


def test_package_manifest_includes_dependencies_and_excludes_runtime_dirs(tmp_path):
    included = (
        "fram_serving/lived_memory.py",
        "fram_serving/semantic.py",
        "fram_serving/fractal_memory/fractal_gen.py",
        "fram_index/index.py",
        "fram_core/claims.py",
        "fram_eval/evaluator.py",
        "scripts/production_memory_eval.py",
    )
    excluded = (
        ".venv/runtime.py",
        "storage/private.py",
        "fram_serving/storage/runtime.py",
        "fram_core/.venv/helper.py",
    )
    for name in included + excluded:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# fixture\n", encoding="utf-8")
    manifest = adapter._code_manifest(tmp_path)
    assert set(manifest) == set(included)
    assert list(manifest) == sorted(manifest)
    assert manifest == adapter._code_manifest(tmp_path)


@pytest.mark.parametrize("change", ["changed", "added", "deleted"])
def test_dependency_change_invalidates_otherwise_completed_report(
    tmp_path, monkeypatch, change
):
    config, first, _, _ = fixture_store(tmp_path / "source")
    real_manifest = adapter._code_manifest
    calls = 0

    def changed_dependency(root):
        nonlocal calls
        calls += 1
        manifest = real_manifest(root)
        assert "fram_serving/lived_memory.py" in manifest
        if calls > 1:
            if change == "changed":
                manifest["fram_serving/lived_memory.py"] = "0" * 64
            elif change == "added":
                manifest["fram_serving/new_dependency.py"] = "0" * 64
            else:
                del manifest["fram_serving/lived_memory.py"]
        return manifest

    monkeypatch.setattr(adapter, "_code_manifest", changed_dependency)
    with pytest.raises(RuntimeError, match="evaluation code changed"):
        evaluate_production(
            [
                {
                    "id": "dependency",
                    "match_episode_id": first,
                    "probe": "lantern fox tea",
                }
            ],
            source_memory_root=tmp_path / "source" / "memory",
            scratch_root=tmp_path / "eval",
            config=config,
            modes=("semantic",),
            fields=("probe",),
            skip_off_observation=True,
        )
    assert calls == 2
    receipt = json.loads((tmp_path / "eval" / "production-progress.json").read_text())
    assert receipt["status"] == "failed"
    assert receipt["phase"] == "verify_source_and_code"
    assert receipt["queries_selected"] == receipt["queries_persisted"] == 1
    assert receipt["source_preservation"]["status"] == "unchanged"
