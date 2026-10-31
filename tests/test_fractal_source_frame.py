"""Source-frame recognition contracts chosen independently of recall labels."""

from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest
from pydantic import ValidationError

from fram_serving.config import FRAMConfig
from fram_serving.fractal_memory import FractalGenerator, FractalSeed
from fram_serving.fractal_memory.source_frame import (
    score_source_frames,
    source_frame_components,
)
from fram_serving.query_runner import _fractal_trace_scores


def generated(vector, identifier="source", timestamp=1_700_000_000_000, nodes=64):
    generator = FractalGenerator(len(vector), n_nodes=nodes)
    trace = generator.generate(FractalSeed(identifier, timestamp, np.array(vector)))
    return generator, trace


def store_for(generator, traces):
    trace_store = SimpleNamespace(
        generator=generator, iter_traces=lambda: iter((trace, {}) for trace in traces)
    )
    cognitive = SimpleNamespace(
        fractal_trace_store=lambda: trace_store,
        FILE_EPISODES="synthetic",
        _iter_jsonl=lambda _: iter({"id": trace.seed_id} for trace in traces),
    )
    return trace_store, cognitive


@pytest.mark.parametrize("dimension", [6, 16, 64, 1024])
@pytest.mark.parametrize("nodes", [8, 64, 256])
def test_replay_distance_equals_declared_projected_residual(dimension, nodes):
    rng = np.random.RandomState(402)
    source, query = rng.normal(size=(2, dimension))
    generator, trace = generated(source, nodes=nodes)
    result = source_frame_components(generator, trace, query)
    projection_seed = trace.provenance["projection_seed"]
    x, q = [generator.project(v, projection_seed) for v in (source, query)]
    expected = np.sum((q - x) ** 2) / (q @ q + x @ x)
    assert result["source_frame_distance"] == pytest.approx(expected, abs=1e-12)
    assert result["cosine"] == pytest.approx(
        q @ x / np.linalg.norm(q) / np.linalg.norm(x)
    )
    assert result["recurrence_max_abs_error"] < 1e-12


@pytest.mark.parametrize("prefix", ["original", "renamed"])
@pytest.mark.parametrize("timestamp", [1_700_000_000_000, 1_900_000_000_000])
def test_exact_and_near_source_top_one_across_id_and_time_changes(prefix, timestamp):
    vectors = np.eye(64)[:12]
    generated_rows = [
        generated(v, f"{prefix}-{i}", timestamp) for i, v in enumerate(vectors)
    ]
    generator, _ = generated_rows[0]
    traces = [trace for _, trace in generated_rows]
    _, cognitive = store_for(generator, traces)
    cfg = FRAMConfig(
        fractal_enabled=True,
        fractal_influence_enabled=True,
        fractal_scoring_mode="source_frame",
    )
    original = deepcopy(traces)
    for i, vector in enumerate(vectors):
        for query in (
            vector,
            vector + np.random.RandomState(55 + i).normal(0, 0.01, 64),
        ):
            scores = _fractal_trace_scores(cognitive, query, 12, cfg)
            assert scores[0]["episode_id"] == traces[i].seed_id
            assert scores[0]["scoring_mode"] == "source_frame"
            assert "soft_dtw_distance" not in scores[0]
    assert traces == original


@pytest.mark.parametrize(
    "change", ["version", "seed", "indices", "coordinate", "order"]
)
def test_incomplete_or_inconsistent_trace_cannot_supply_influence(change):
    generator, valid = generated(np.eye(64)[0])
    invalid = deepcopy(valid)
    invalid.seed_id = "invalid"
    if change == "version":
        invalid.provenance["version"] = "unknown-future-recipe"
    elif change == "seed":
        del invalid.provenance["ifs_seed"]
    elif change == "indices":
        invalid.nodes[4] = replace(invalid.nodes[4], index=999)
    elif change == "coordinate":
        invalid.nodes[4] = replace(invalid.nodes[4], coord6=(9.0,) * 6)
    else:
        a, b = invalid.nodes[4], invalid.nodes[5]
        invalid.nodes[4], invalid.nodes[5] = replace(b, index=4), replace(a, index=5)
    traces, _ = store_for(generator, [invalid, valid])
    scores = score_source_frames(
        traces, np.eye(64)[0], 3, alpha=0.4, bound_episode_ids={"source", "invalid"}
    )
    assert [row["episode_id"] for row in scores] == ["source"]
    assert scores[0]["trace_coverage"]["valid"] == 1
    assert sum(scores[0]["trace_coverage"]["rejected"].values()) == 1


def test_unbound_copy_cannot_consume_normalization_or_influence_slots():
    generator, valid = generated(np.eye(64)[0])
    unbound = deepcopy(valid)
    unbound.seed_id = "!unbound"
    traces, _ = store_for(generator, [unbound, valid])
    scores = score_source_frames(
        traces, np.eye(64)[0], 1, alpha=0.4, bound_episode_ids={"source"}
    )
    assert scores[0]["episode_id"] == "source"
    assert scores[0]["trace_coverage"]["rejected"] == {"unbound_episode": 1}


def test_projection_collision_is_not_full_embedding_identity():
    source = np.eye(64)[0]
    generator, trace = generated(source)
    projection = generator._stable_projection(
        generator._rng(trace.provenance["projection_seed"]), 64, 6
    )
    null_direction = np.linalg.svd(projection.T, full_matrices=True)[2][6]
    different_source = source + null_direction
    assert np.linalg.norm(source - different_source) > 0.9
    result = source_frame_components(generator, trace, different_source)
    assert result["source_frame_distance"] < 1e-25
    assert result["cosine"] == pytest.approx(1)


@pytest.mark.parametrize("query", [np.zeros(64), np.full(64, np.nan), np.ones(7)])
def test_invalid_or_empty_signal_abstains(query):
    generator, trace = generated(np.eye(64)[0])
    traces, _ = store_for(generator, [trace])
    assert (
        score_source_frames(traces, query, 1, alpha=0.4, bound_episode_ids={"source"})
        == []
    )


def test_candidate_is_explicit_and_rejects_unsupported_quaternion_blend():
    assert FRAMConfig().fractal_scoring_mode == "legacy"
    assert not FRAMConfig().fractal_influence_enabled
    with pytest.raises(ValidationError):
        FRAMConfig(fractal_scoring_mode="unknown")
    generator, trace = generated(np.eye(64)[0])
    _, cognitive = store_for(generator, [trace])
    cfg = FRAMConfig(
        fractal_enabled=True,
        fractal_scoring_mode="source_frame",
        fractal_quat_influence=True,
    )
    with pytest.raises(ValueError, match="quaternion"):
        _fractal_trace_scores(cognitive, np.eye(64)[0], 1, cfg)


def test_candidate_env_is_explicit_without_enabling_influence(monkeypatch):
    monkeypatch.setenv("FRAM_FRACTAL_SCORING_MODE", "source_frame")
    monkeypatch.setenv("FRAM_FRACTAL_INFLUENCE", "0")
    cfg = FRAMConfig.from_env()
    assert cfg.fractal_scoring_mode == "source_frame"
    assert not cfg.fractal_influence_enabled
    monkeypatch.setenv("FRAM_FRACTAL_SCORING_MODE", "unknown")
    assert FRAMConfig.from_env().fractal_scoring_mode == "legacy"


def test_app_and_runner_use_the_same_source_frame_scores(monkeypatch):
    from fram_serving import app

    generator, trace = generated(np.eye(64)[0])
    _, cognitive = store_for(generator, [trace])
    cfg = FRAMConfig(
        fractal_enabled=True,
        fractal_influence_enabled=True,
        fractal_scoring_mode="source_frame",
    )
    monkeypatch.setattr(app, "CFG", cfg)
    monkeypatch.setattr(app, "_COG_STORE", cognitive)
    query = np.eye(64)[0]
    assert app._fractal_trace_scores(query, 1) == _fractal_trace_scores(
        cognitive, query, 1, cfg
    )
