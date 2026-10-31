from __future__ import annotations

import json

import numpy as np

from fram_serving.fractal_memory import (
    FractalGenerator,
    FractalSeed,
    FractalTraceStore,
    build_query_path,
    coord6_to_vec3,
    downsample_path,
    logistic_lambda,
    min_max_normalize,
    path_quaternions,
    quaternion_alignment,
    soft_dtw_distance,
)


def test_generation_determinism() -> None:
    dim = 32
    generator = FractalGenerator(embedding_dim=dim, n_nodes=64)
    embedding = np.random.RandomState(0).normal(size=(dim,))
    seed = FractalSeed(
        episode_id="ep-deterministic",
        timestamp_ms=1_700_000_000_000,
        embedding=embedding,
    )
    first = generator.generate(seed)
    second = generator.generate(seed)
    a = np.array([node.coord6 for node in first.nodes])
    b = np.array([node.coord6 for node in second.nodes])
    assert np.allclose(a, b)
    assert first.provenance == second.provenance
    q_first = [node.q for node in first.nodes]
    q_second = [node.q for node in second.nodes]
    assert q_first == q_second
    lambda_first = [node.lambda_value for node in first.nodes]
    lambda_second = [node.lambda_value for node in second.nodes]
    assert lambda_first == lambda_second


def test_projection_shape() -> None:
    dim = 48
    generator = FractalGenerator(embedding_dim=dim, n_nodes=32)
    vector = np.random.RandomState(1).normal(size=(dim,))
    projected = generator.project(vector)
    assert projected.shape == (6,)


def test_coord6_to_vec3_mapping() -> None:
    coord = [2.0, 4.0, 6.0, 0.0, 2.0, 4.0]
    vec3 = coord6_to_vec3(coord)
    assert np.allclose(vec3, np.array([1.0, 3.0, 5.0]))


def test_store_ingest_and_load(tmp_path) -> None:
    storage_root = tmp_path / "fractal"
    obs_root = tmp_path / "observability"
    store = FractalTraceStore(
        storage_root,
        observability_root=obs_root,
        embedding_dim=16,
        n_nodes=32,
    )
    embedding = np.ones(16, dtype=float)
    seed = FractalSeed(
        episode_id="episode-42",
        timestamp_ms=1_700_000_001_000,
        embedding=embedding,
        metadata={"source": "test"},
    )
    line = store.ingest_seed(seed)
    loaded = store.load_trace("episode-42")
    assert loaded is not None
    restored_line, meta = loaded
    assert restored_line.seed_id == line.seed_id
    assert len(restored_line.nodes) == len(line.nodes)
    assert meta.get("source") == "test"
    assert (storage_root / "episode-42.json").exists()
    events = list(obs_root.glob("memory_fractal.jsonl"))
    assert events, "expected observability file to be created"


def test_trace_schema_v2_persisted(tmp_path) -> None:
    storage_root = tmp_path / "fractal"
    obs_root = tmp_path / "observability"
    store = FractalTraceStore(
        storage_root,
        observability_root=obs_root,
        embedding_dim=8,
        n_nodes=4,
    )
    seed = FractalSeed(
        episode_id="episode-v2",
        timestamp_ms=1_700_000_002_000,
        embedding=np.ones(8, dtype=float),
    )
    store.ingest_seed(seed)
    raw = json.loads((storage_root / "episode-v2.json").read_text(encoding="utf-8"))
    assert raw.get("trace_version") == 2
    nodes = raw.get("nodes")
    assert nodes
    node0 = nodes[0]
    assert "q" in node0
    assert "lambda" in node0
    assert set(node0["q"].keys()) >= {"w", "x", "y", "z"}
    assert 0.0 < float(node0["lambda"]) < 1.0


def test_v1_trace_load_compatibility(tmp_path) -> None:
    storage_root = tmp_path / "fractal"
    obs_root = tmp_path / "observability"
    store = FractalTraceStore(
        storage_root,
        observability_root=obs_root,
        embedding_dim=8,
        n_nodes=4,
    )
    payload = {
        "seed_id": "episode-v1",
        "nodes": [
            {
                "scale": "macro",
                "coord6": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
                "s_arc": 0.0,
                "index": 0,
            }
        ],
        "provenance": {"version": "fractal-trace-v0"},
        "metadata": {"source": "legacy"},
    }
    (storage_root / "episode-v1.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )
    loaded = store.load_trace("episode-v1")
    assert loaded is not None
    line, meta = loaded
    assert line.seed_id == "episode-v1"
    assert len(line.nodes) == 1
    assert meta.get("source") == "legacy"


def test_quaternion_normalized() -> None:
    dim = 24
    generator = FractalGenerator(embedding_dim=dim, n_nodes=32)
    embedding = np.random.RandomState(3).normal(size=(dim,))
    seed = FractalSeed(
        episode_id="ep-quat",
        timestamp_ms=1_700_000_004_000,
        embedding=embedding,
    )
    line = generator.generate(seed)
    for node in line.nodes:
        q = np.asarray(node.q, dtype=float)
        norm = float(np.linalg.norm(q))
        assert abs(norm - 1.0) < 1e-6


def test_path_quaternions_unit() -> None:
    path = np.array(
        [
            [1.0, 0.0, 0.0, 1.0, 0.0, 0.0],
            [2.0, 0.0, 0.0, 2.0, 0.0, 0.0],
        ],
        dtype=float,
    )
    quats = path_quaternions(path)
    assert quats.shape == (2, 4)
    norms = np.linalg.norm(quats, axis=1)
    assert np.allclose(norms, 1.0)


def test_quaternion_alignment_absolute() -> None:
    q_a = np.array([[1.0, 0.0, 0.0, 0.0]], dtype=float)
    q_b = np.array([[-1.0, 0.0, 0.0, 0.0]], dtype=float)
    aligned = quaternion_alignment(q_a, q_b, absolute=True)
    assert np.allclose(aligned, np.array([1.0]))
    aligned_signed = quaternion_alignment(q_a, q_b, absolute=False)
    assert np.allclose(aligned_signed, np.array([-1.0]))


def test_lambda_bounds() -> None:
    dim = 16
    generator = FractalGenerator(embedding_dim=dim, n_nodes=16)
    embedding = np.random.RandomState(7).normal(size=(dim,))
    seed = FractalSeed(
        episode_id="ep-lambda",
        timestamp_ms=1_700_000_005_000,
        embedding=embedding,
    )
    line = generator.generate(seed)
    for node in line.nodes:
        assert node.lambda_value is not None
        assert 0.0 < float(node.lambda_value) < 1.0


def test_logistic_lambda_deterministic() -> None:
    value_a = logistic_lambda("seed", 3)
    value_b = logistic_lambda("seed", 3)
    assert value_a == value_b
    assert 0.0 < value_a < 1.0


def test_downsample_path_reduces_steps() -> None:
    path = np.arange(600, dtype=float).reshape(100, 6)
    reduced, stride = downsample_path(path, target=16)
    assert reduced.shape[0] <= 16
    assert reduced.shape[1] == 6
    assert stride >= 1


def test_build_query_path_deterministic() -> None:
    point = np.ones(6, dtype=float)
    path_a = build_query_path(point, steps=32)
    path_b = build_query_path(point, steps=32)
    assert path_a.shape == (32, 6)
    assert np.allclose(path_a, path_b)


def test_soft_dtw_distance_monotonic() -> None:
    base = np.zeros((32, 6), dtype=float)
    identical = soft_dtw_distance(base, base, gamma=0.1)
    perturbed = base + 0.2
    noisy = soft_dtw_distance(base, perturbed, gamma=0.1)
    assert identical <= noisy


def test_min_max_normalize_bounds() -> None:
    values = np.array([-2.0, 0.0, 4.0], dtype=float)
    norm = min_max_normalize(values)
    assert norm.min() >= -1.0 and norm.max() <= 1.0
    assert np.isclose(norm[0], -1.0)
    assert np.isclose(norm[-1], 1.0)
    zeros = min_max_normalize(np.ones(4))
    assert np.allclose(zeros, 0.0)
