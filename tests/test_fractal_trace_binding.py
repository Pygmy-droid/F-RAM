"""Only exact, current episode bindings grant trace ranking influence."""

from __future__ import annotations

import hashlib
import json

import numpy as np
import pytest

from fram_serving.config import FRAMConfig
from fram_serving.memory import CognitiveMemoryStore
from fram_serving.query_runner import _apply_fractal_influence, _fractal_trace_scores


def _fixture(tmp_path):
    config = FRAMConfig().model_copy(
        update={
            "STORAGE_ROOT": tmp_path,
            "embedding_dim": 6,
            "fractal_enabled": True,
            "fractal_influence_enabled": True,
            "fractal_quat_influence": False,
            "fractal_downsample_target": 8,
        }
    )
    store = CognitiveMemoryStore(tmp_path / "memory" / "cognitive", config=config)
    for index in range(3):
        vector = np.eye(6)[index] + 0.1
        store.append_episode(
            query=f"fixture query {index}",
            answer=f"fixture answer {index}",
            embedding=vector.tolist(),
            embedding_backend="hashing",
        )
    traces = store.fractal_trace_store()
    assert traces is not None
    for path in traces.storage_root.glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["nodes"] = payload["nodes"][:8]
        path.write_text(json.dumps(payload), encoding="utf-8")
    query = np.array([1.0, 0.6, 0.3, 0.1, 0.2, 0.7])
    baseline = _fractal_trace_scores(store, query, 3, config)
    assert len(baseline) == 3
    return config, store, traces, query, baseline


def _write_trace(traces, payload, seed_id):
    payload["seed_id"] = seed_id
    path = traces.storage_root / f"{seed_id}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _manifest(root):
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_unresolved_traces_cannot_consume_influence_slots_or_change_bound_scores(
    tmp_path,
):
    config, store, traces, query, baseline = _fixture(tmp_path)
    best_id = baseline[0]["episode_id"]
    for index in range(4):
        # Exact geometric copies of the winning trace sort first by filename.
        # Metadata still names the original source: it must not rebind the ID.
        payload = traces.load_raw(best_id)
        payload["metadata"]["episode_id"] = best_id
        _write_trace(traces, payload, f"!historical-unresolved-{index}")
    before = _manifest(tmp_path)
    observation = _fractal_trace_scores(
        store,
        query,
        3,
        config.model_copy(update={"fractal_influence_enabled": False}),
    )
    assert all(row["episode_id"].startswith("!historical") for row in observation)
    assert _fractal_trace_scores(store, query, 3, config) == baseline
    assert _manifest(tmp_path) == before


def test_unresolved_extreme_trace_does_not_shift_influence_normalization(tmp_path):
    config, store, traces, query, baseline = _fixture(tmp_path)
    payload = traces.load_raw(baseline[0]["episode_id"])
    projected = traces.generator.project(
        query, projection_seed=payload["provenance"]["projection_seed"]
    )
    for index, node in enumerate(payload["nodes"]):
        node["coord6"] = (-projected * (1000.0 + index)).tolist()
    _write_trace(traces, payload, "historical-extreme")
    before = _manifest(tmp_path)
    influenced = _fractal_trace_scores(store, query, 3, config)
    assert influenced == baseline
    observation = _fractal_trace_scores(
        store,
        query,
        20,
        config.model_copy(update={"fractal_influence_enabled": False}),
    )
    observed_by_id = {row["episode_id"]: row for row in observation}
    assert "historical-extreme" in observed_by_id
    assert any(
        not np.isclose(
            row["cosine_norm"], observed_by_id[row["episode_id"]]["cosine_norm"]
        )
        for row in baseline
    )
    assert _manifest(tmp_path) == before


def test_bound_old_schema_trace_is_retained_without_requiring_a_vector(tmp_path):
    config, store, traces, query, baseline = _fixture(tmp_path)
    episode_id = baseline[0]["episode_id"]
    payload = traces.load_raw(episode_id)
    payload.pop("trace_version", None)
    for node in payload["nodes"]:
        node.pop("q", None)
        node.pop("lambda", None)
    _write_trace(traces, payload, episode_id)
    # A valid persisted episode/trace binding does not depend on vector custody.
    store.vector_path(kind="episode").write_text("", encoding="utf-8")
    before = _manifest(tmp_path)
    scored = _fractal_trace_scores(store, query, 3, config)
    assert [row["episode_id"] for row in scored] == [
        row["episode_id"] for row in baseline
    ]
    np.testing.assert_allclose(
        [row["score"] for row in scored],
        [row["score"] for row in baseline],
        rtol=1e-13,
        atol=1e-13,
    )
    assert _manifest(tmp_path) == before


@pytest.mark.parametrize("episode_file", [None, "{malformed json}\n", "{}\n"])
def test_missing_or_unresolvable_episode_store_grants_no_influence(
    tmp_path,
    episode_file,
):
    config, store, _, query, baseline = _fixture(tmp_path)
    path = store._path(store.FILE_EPISODES)
    if episode_file is None:
        path.unlink()
    else:
        path.write_text(episode_file, encoding="utf-8")
    before = _manifest(tmp_path)
    assert _fractal_trace_scores(store, query, 3, config) == []
    observation = _fractal_trace_scores(
        store,
        query,
        3,
        config.model_copy(update={"fractal_influence_enabled": False}),
    )
    assert observation == baseline
    assert _manifest(tmp_path) == before


def test_malformed_line_does_not_hide_other_resolvable_episode_ids(tmp_path):
    config, store, _, query, baseline = _fixture(tmp_path)
    with store._path(store.FILE_EPISODES).open("a", encoding="utf-8") as handle:
        handle.write("{malformed json}\n")
    before = _manifest(tmp_path)
    # Match cognitive search's existing iterator semantics for malformed lines.
    assert _fractal_trace_scores(store, query, 3, config) == baseline
    assert _manifest(tmp_path) == before


def test_invalid_episode_record_schema_fails_influence_conservatively(tmp_path):
    config, store, _, query, baseline = _fixture(tmp_path)
    store._path(store.FILE_EPISODES).write_text(
        '["not an episode"]\n', encoding="utf-8"
    )
    with pytest.raises(AttributeError):
        _fractal_trace_scores(store, query, 3, config)
    observation = _fractal_trace_scores(
        store,
        query,
        3,
        config.model_copy(update={"fractal_influence_enabled": False}),
    )
    assert observation == baseline


def test_unreadable_store_fails_influence_without_disabling_observation(
    tmp_path,
    monkeypatch,
):
    config, store, _, query, baseline = _fixture(tmp_path)

    def unavailable(_name):
        raise PermissionError("episode store unavailable")

    monkeypatch.setattr(store, "_iter_jsonl", unavailable)
    with pytest.raises(PermissionError, match="episode store unavailable"):
        _fractal_trace_scores(store, query, 3, config)
    observation = _fractal_trace_scores(
        store,
        query,
        3,
        config.model_copy(update={"fractal_influence_enabled": False}),
    )
    assert observation == baseline


def test_episode_lookup_scanned_once_and_flag_off_selection_is_unchanged(
    tmp_path,
    monkeypatch,
):
    config, store, _, query, baseline = _fixture(tmp_path)
    original = store._iter_jsonl
    reads = []

    def tracked(name):
        reads.append(name)
        return original(name)

    monkeypatch.setattr(store, "_iter_jsonl", tracked)
    assert _fractal_trace_scores(store, query, 3, config) == baseline
    assert reads == [store.FILE_EPISODES]
    reads.clear()
    observation = _fractal_trace_scores(
        store,
        query,
        3,
        config.model_copy(update={"fractal_influence_enabled": False}),
    )
    assert reads == []
    candidates = [
        {"doc_id": f"cmem:ep:{row['episode_id']}", "score": 0.3 - 0.01 * index}
        for index, row in enumerate(baseline)
    ]
    before = [dict(candidate) for candidate in candidates]
    score_map = {row["episode_id"]: row["score"] for row in observation}
    _apply_fractal_influence(candidates, score_map, alpha=1000.0, enabled=False)
    assert candidates == before
