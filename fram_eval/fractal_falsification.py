from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np

from fram_serving.fractal_memory import (
    DEFAULT_LAMBDA,
    DEFAULT_QUATERNION,
    FractalGenerator,
    FractalSeed,
    TraceLine,
    TraceNode,
    build_query_path,
    downsample_path,
    logistic_lambda,
    min_max_normalize,
    path_quaternions,
    quaternion_alignment,
    soft_dtw_distance,
    soft_dtw_similarity,
)

AizawaComponent = float | np.ndarray


@dataclass(frozen=True)
class ScoreConfig:
    alpha: float = 0.4
    quat_weight: float = 0.2
    quat_use_lambda: bool = True
    quat_influence: bool = False
    downsample_target: int = 128
    soft_gamma: float = 0.1
    soft_band: float = 0.15


def _normalize_trajectory(traj: np.ndarray) -> np.ndarray:
    arr = np.asarray(traj, dtype=np.float64)
    if arr.ndim != 2:
        raise ValueError("trajectory must be 2-D (steps x dims)")
    if not np.isfinite(arr).all():
        arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
    max_abs = float(np.max(np.abs(arr))) if arr.size else 0.0
    if max_abs > 1e6:
        arr = arr / max_abs
    mean = arr.mean(axis=0)
    std = arr.std(axis=0)
    std[~np.isfinite(std)] = 1.0
    std[std == 0] = 1.0
    return (arr - mean) / std


def simulate_logistic_map(x0: float, steps: int, *, r: float = 3.9) -> np.ndarray:
    xs = np.empty((steps, 1), dtype=np.float64)
    x = float(x0)
    for idx in range(steps):
        x = r * x * (1.0 - x)
        xs[idx, 0] = x
    return xs


def simulate_henon(
    state: Tuple[float, float],
    steps: int,
    *,
    a: float = 1.4,
    b: float = 0.3,
) -> np.ndarray:
    xs = np.empty((steps, 2), dtype=np.float64)
    x, y = state
    for idx in range(steps):
        x_next = 1.0 - a * x * x + y
        y_next = b * x
        x, y = x_next, y_next
        xs[idx] = (x, y)
    return xs


def simulate_lorenz(
    state: Tuple[float, float, float],
    steps: int,
    *,
    dt: float = 0.01,
    sigma: float = 10.0,
    beta: float = 8.0 / 3.0,
    rho: float = 28.0,
) -> np.ndarray:
    xs = np.empty((steps, 3), dtype=np.float64)
    x, y, z = state
    for idx in range(steps):
        dx = sigma * (y - x)
        dy = x * (rho - z) - y
        dz = x * y - beta * z
        x += dx * dt
        y += dy * dt
        z += dz * dt
        xs[idx] = (x, y, z)
    return xs


def aizawa_velocity(
    state: Tuple[AizawaComponent, AizawaComponent, AizawaComponent],
    *,
    a: float = 0.95,
    b: float = 0.7,
    c: float = 0.6,
    d: float = 3.5,
    e: float = 0.25,
    f: float = 0.1,
) -> Tuple[AizawaComponent, AizawaComponent, AizawaComponent]:
    """Return the standard ambient Aizawa velocity.

    Components may be scalars or NumPy arrays. This is the single equation
    primitive shared by the legacy Euler simulator and proof-track sphere
    construction.
    """

    x, y, z = state
    dx = (z - b) * x - d * y
    dy = d * x + (z - b) * y
    dz = (
        c
        + a * z
        - (z ** 3) / 3.0
        - (x * x + y * y) * (1.0 + e * z)
        + f * z * (x ** 3)
    )
    return dx, dy, dz


def simulate_aizawa(
    state: Tuple[float, float, float],
    steps: int,
    *,
    dt: float = 0.01,
    a: float = 0.95,
    b: float = 0.7,
    c: float = 0.6,
    d: float = 3.5,
    e: float = 0.25,
    f: float = 0.1,
) -> np.ndarray:
    xs = np.empty((steps, 3), dtype=np.float64)
    x, y, z = state
    for idx in range(steps):
        dx, dy, dz = aizawa_velocity(
            (x, y, z),
            a=a,
            b=b,
            c=c,
            d=d,
            e=e,
            f=f,
        )
        x += dx * dt
        y += dy * dt
        z += dz * dt
        xs[idx] = (x, y, z)
    return xs


def generate_trajectories(
    system: str,
    *,
    count: int,
    steps: int,
    rng: np.random.RandomState,
) -> List[np.ndarray]:
    system_key = system.strip().lower()
    trajectories: List[np.ndarray] = []
    for _ in range(count):
        if system_key == "logistic":
            x0 = rng.uniform(0.1, 0.9)
            trajectories.append(simulate_logistic_map(x0, steps))
        elif system_key == "henon":
            x0 = rng.uniform(-0.5, 0.5)
            y0 = rng.uniform(-0.5, 0.5)
            trajectories.append(simulate_henon((x0, y0), steps))
        elif system_key == "lorenz":
            state = (
                rng.uniform(-10.0, 10.0),
                rng.uniform(-10.0, 10.0),
                rng.uniform(10.0, 30.0),
            )
            trajectories.append(simulate_lorenz(state, steps))
        elif system_key == "aizawa":
            state = (
                rng.uniform(-0.5, 0.5),
                rng.uniform(-0.5, 0.5),
                rng.uniform(0.0, 1.0),
            )
            trajectories.append(simulate_aizawa(state, steps))
        else:
            raise ValueError(f"unknown system '{system}'")
    return trajectories


def trajectory_to_embedding(
    traj: np.ndarray,
    *,
    embed_dim: int | None = None,
    rng: np.random.RandomState | None = None,
) -> np.ndarray:
    flat = np.asarray(traj, dtype=np.float64).ravel()
    if embed_dim is None or embed_dim <= 0 or embed_dim == flat.size:
        vec = flat
    else:
        if rng is None:
            rng = np.random.RandomState(0)
        proj = rng.normal(scale=1.0 / np.sqrt(flat.size), size=(flat.size, embed_dim))
        vec = flat @ proj
    norm = float(np.linalg.norm(vec))
    if norm <= 0.0:
        return vec
    return vec / norm


def build_traces(
    embeddings: Sequence[np.ndarray],
    *,
    n_nodes: int,
    seed_offset: int = 1700000000000,
) -> Tuple[FractalGenerator, List[TraceLine]]:
    if not embeddings:
        raise ValueError("embeddings must be non-empty")
    dim = int(embeddings[0].size)
    generator = FractalGenerator(embedding_dim=dim, n_nodes=n_nodes)
    traces: List[TraceLine] = []
    for idx, emb in enumerate(embeddings):
        seed = FractalSeed(
            episode_id=f"traj-{idx:03d}",
            timestamp_ms=seed_offset + idx,
            embedding=emb,
        )
        traces.append(generator.generate(seed))
    return generator, traces


def pairwise_dtw_distances(
    trajectories: Sequence[np.ndarray],
    *,
    gamma: float = 0.1,
    band: float = 0.15,
) -> np.ndarray:
    count = len(trajectories)
    distances = np.zeros((count, count), dtype=np.float64)
    for i in range(count):
        for j in range(i + 1, count):
            dist = soft_dtw_distance(trajectories[i], trajectories[j], gamma=gamma, band=band)
            distances[i, j] = dist
            distances[j, i] = dist
    return distances


def _score_trace(
    query_vec: np.ndarray,
    trace_line: TraceLine,
    generator: FractalGenerator,
    *,
    config: ScoreConfig,
) -> Dict[str, float]:
    projection_seed = trace_line.provenance.get("projection_seed")
    try:
        seed_value = int(projection_seed) if projection_seed is not None else None
    except (TypeError, ValueError):
        seed_value = None
    q6 = generator.project(query_vec, projection_seed=seed_value)
    coords_full = generator.retrace(trace_line)
    coords, stride = downsample_path(coords_full, target=config.downsample_target)
    if coords.shape[0] == 0:
        return {"cosine_raw": 0.0, "soft_raw": 0.0, "quat_raw": 0.0, "quat_lambda_raw": 0.0}
    indices = list(range(0, coords_full.shape[0], stride))
    if len(indices) > coords.shape[0]:
        indices = indices[: coords.shape[0]]
    centroid = coords.mean(axis=0)
    composite = (centroid + coords[0] + coords[-1]) / 3.0
    norm_q = float(np.linalg.norm(q6))
    norm_comp = float(np.linalg.norm(composite))
    cosine_score = 0.0
    if norm_q > 0.0 and norm_comp > 0.0:
        cosine_score = float(np.dot(q6, composite) / (norm_q * norm_comp))
    try:
        query_path = build_query_path(q6, steps=coords.shape[0])
    except Exception:
        query_path = np.zeros_like(coords)
    query_path, _ = downsample_path(query_path, target=coords.shape[0])
    try:
        soft_dist = soft_dtw_distance(query_path, coords, gamma=config.soft_gamma, band=config.soft_band)
        soft_score = soft_dtw_similarity(soft_dist)
    except Exception:
        soft_score = 0.0
    query_quats = path_quaternions(query_path)
    trace_quats = path_quaternions(coords)
    if trace_line.nodes and trace_quats.shape[0] > 0:
        for pos, node_idx in enumerate(indices[: trace_quats.shape[0]]):
            if node_idx >= len(trace_line.nodes):
                continue
            raw_q = trace_line.nodes[node_idx].q
            if raw_q is None:
                continue
            if isinstance(raw_q, dict):
                q_vals = [
                    raw_q.get("w", DEFAULT_QUATERNION[0]),
                    raw_q.get("x", DEFAULT_QUATERNION[1]),
                    raw_q.get("y", DEFAULT_QUATERNION[2]),
                    raw_q.get("z", DEFAULT_QUATERNION[3]),
                ]
                q_arr = np.asarray(q_vals, dtype=float)
            else:
                q_arr = np.asarray(raw_q, dtype=float).ravel()
            if q_arr.size != 4:
                continue
            q_norm = float(np.linalg.norm(q_arr))
            if q_norm <= 1e-12:
                continue
            trace_quats[pos] = q_arr / q_norm
    alignment = quaternion_alignment(query_quats, trace_quats, absolute=True)
    quat_raw = float(np.mean(alignment)) if alignment.size > 0 else 0.0
    quat_lambda_raw = quat_raw
    if alignment.size > 0 and indices:
        weights: List[float] = []
        for node_idx in indices[: alignment.size]:
            lambda_val = None
            if node_idx < len(trace_line.nodes):
                raw_lambda = trace_line.nodes[node_idx].lambda_value
                if raw_lambda is not None:
                    try:
                        lambda_val = float(raw_lambda)
                    except (TypeError, ValueError):
                        lambda_val = None
            if lambda_val is None or not (0.0 < lambda_val < 1.0):
                try:
                    lambda_val = logistic_lambda(trace_line.seed_id, node_idx)
                except Exception:
                    lambda_val = DEFAULT_LAMBDA
            if not (0.0 < lambda_val < 1.0):
                lambda_val = DEFAULT_LAMBDA
            weights.append(lambda_val)
        if weights:
            weight_arr = np.asarray(weights, dtype=np.float64)
            weight_sum = float(weight_arr.sum())
            if weight_sum > 0.0:
                quat_lambda_raw = float(np.average(alignment[: len(weight_arr)], weights=weight_arr))
    return {
        "cosine_raw": cosine_score,
        "soft_raw": soft_score,
        "quat_raw": quat_raw,
        "quat_lambda_raw": quat_lambda_raw,
    }


def _blend_scores(entries: List[Dict[str, float]], config: ScoreConfig) -> List[Dict[str, float]]:
    cos_array = np.array([entry["cosine_raw"] for entry in entries], dtype=np.float64)
    soft_array = np.array([entry["soft_raw"] for entry in entries], dtype=np.float64)
    quat_array = np.array([entry["quat_raw"] for entry in entries], dtype=np.float64)
    quat_lambda_array = np.array([entry["quat_lambda_raw"] for entry in entries], dtype=np.float64)
    cos_norm = min_max_normalize(cos_array)
    soft_norm = min_max_normalize(soft_array)
    quat_norm = min_max_normalize(quat_array)
    quat_lambda_norm = min_max_normalize(quat_lambda_array)
    blended: List[Dict[str, float]] = []
    for entry, cos_n, soft_n, quat_n, quat_lambda_n in zip(
        entries, cos_norm, soft_norm, quat_norm, quat_lambda_norm
    ):
        base_norm = config.alpha * cos_n + (1.0 - config.alpha) * soft_n
        quat_norm_value = float(quat_lambda_n if config.quat_use_lambda else quat_n)
        score_norm = base_norm
        if config.quat_influence and config.quat_weight > 0.0:
            score_norm = (1.0 - config.quat_weight) * base_norm + config.quat_weight * quat_norm_value
        base_raw = config.alpha * entry["cosine_raw"] + (1.0 - config.alpha) * entry["soft_raw"]
        quat_raw_value = float(
            entry["quat_lambda_raw"] if config.quat_use_lambda else entry["quat_raw"]
        )
        score_raw = base_raw
        if config.quat_influence and config.quat_weight > 0.0:
            score_raw = (1.0 - config.quat_weight) * base_raw + config.quat_weight * quat_raw_value
        blended.append(
            {
                "score": float(score_norm),
                "score_raw": float(score_raw),
                "score_base": float(base_norm),
                "score_raw_base": float(base_raw),
            }
        )
    return blended


def score_matrices(
    embeddings: Sequence[np.ndarray],
    traces: Sequence[TraceLine],
    generator: FractalGenerator,
    *,
    config: ScoreConfig,
) -> Tuple[np.ndarray, np.ndarray]:
    count = len(embeddings)
    score_raw = np.zeros((count, count), dtype=np.float64)
    score_norm = np.zeros((count, count), dtype=np.float64)
    for i in range(count):
        entries = [
            _score_trace(embeddings[i], trace_line, generator, config=config)
            for trace_line in traces
        ]
        blended = _blend_scores(entries, config)
        for j, entry in enumerate(blended):
            score_raw[i, j] = entry["score_raw"]
            score_norm[i, j] = entry["score"]
    return score_raw, score_norm


def rankdata(values: Sequence[float]) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float64)
    if arr.size == 0:
        return np.array([], dtype=np.float64)
    order = np.argsort(arr, kind="mergesort")
    ranks = np.empty(arr.size, dtype=np.float64)
    i = 0
    while i < arr.size:
        j = i
        while j + 1 < arr.size and arr[order[j + 1]] == arr[order[i]]:
            j += 1
        rank = 0.5 * (i + j) + 1.0
        ranks[order[i : j + 1]] = rank
        i = j + 1
    return ranks


def spearman_rho(x: Sequence[float], y: Sequence[float]) -> float:
    rx = rankdata(x)
    ry = rankdata(y)
    if rx.size == 0 or ry.size == 0:
        return 0.0
    if rx.size != ry.size:
        raise ValueError("x and y must have the same length")
    x_mean = float(np.mean(rx))
    y_mean = float(np.mean(ry))
    x_dev = rx - x_mean
    y_dev = ry - y_mean
    denom = float(np.linalg.norm(x_dev) * np.linalg.norm(y_dev))
    if denom == 0.0:
        return 0.0
    return float(np.dot(x_dev, y_dev) / denom)


def topk_accuracy(true_dists: np.ndarray, scores: np.ndarray, *, k: int = 1) -> float:
    count = true_dists.shape[0]
    hits = 0
    for i in range(count):
        order_true = np.argsort(true_dists[i])
        true_neighbors = [idx for idx in order_true if idx != i][:k]
        order_pred = np.argsort(-scores[i])
        pred_neighbors = [idx for idx in order_pred if idx != i][:k]
        if set(true_neighbors) & set(pred_neighbors):
            hits += 1
    return hits / count if count else 0.0


def _pairwise_score_summary(
    true_dists: np.ndarray,
    score_raw: np.ndarray,
    score_norm: np.ndarray,
) -> Dict[str, float]:
    pairs_true: List[float] = []
    pairs_pred: List[float] = []
    count = true_dists.shape[0]
    for i in range(count):
        for j in range(i + 1, count):
            pairs_true.append(float(true_dists[i, j]))
            avg_score = 0.5 * (score_raw[i, j] + score_raw[j, i])
            pairs_pred.append(float(-avg_score))
    rho = spearman_rho(pairs_true, pairs_pred)
    return {
        "pairs": float(len(pairs_true)),
        "spearman_rho": float(rho),
        "top1": float(topk_accuracy(true_dists, score_norm, k=1)),
        "top3": float(topk_accuracy(true_dists, score_norm, k=3)),
    }


def _random_unit_quaternion(rng: np.random.RandomState) -> Tuple[float, float, float, float]:
    vec = rng.normal(size=4)
    norm = float(np.linalg.norm(vec))
    if norm <= 1e-12:
        return DEFAULT_QUATERNION
    vec = vec / norm
    return (float(vec[0]), float(vec[1]), float(vec[2]), float(vec[3]))


def apply_ablation(
    traces: Sequence[TraceLine],
    *,
    mode: str,
    rng: np.random.RandomState,
) -> List[TraceLine]:
    ablated: List[TraceLine] = []
    for trace in traces:
        nodes = list(trace.nodes)
        if mode == "shuffle_nodes":
            order = rng.permutation(len(nodes)) if nodes else []
            nodes = [nodes[idx] for idx in order]
        elif mode == "reverse_nodes":
            nodes = list(reversed(nodes))

        coords_override = None
        if mode == "random_coords" and nodes:
            coords = np.array([node.coord6 for node in nodes], dtype=np.float64)
            mean = coords.mean(axis=0)
            std = coords.std(axis=0)
            std[std == 0] = 1.0
            coords_override = rng.normal(loc=mean, scale=std, size=coords.shape)

        new_nodes: List[TraceNode] = []
        for idx, node in enumerate(nodes):
            coord6 = tuple(coords_override[idx]) if coords_override is not None else node.coord6
            q_value = node.q
            lambda_value = node.lambda_value
            if mode == "random_quat":
                q_value = _random_unit_quaternion(rng)
            elif mode == "flat_quat":
                q_value = DEFAULT_QUATERNION
            if mode == "flat_lambda":
                lambda_value = DEFAULT_LAMBDA
            new_nodes.append(
                TraceNode(
                    scale=node.scale,
                    coord6=coord6,
                    s_arc=node.s_arc,
                    index=node.index,
                    q=q_value,
                    lambda_value=lambda_value,
                )
            )
        ablated.append(TraceLine(seed_id=trace.seed_id, nodes=new_nodes, provenance=dict(trace.provenance)))
    return ablated


def run_falsification(
    system: str,
    *,
    count: int = 12,
    steps: int = 64,
    seed: int = 7,
    n_nodes: int = 128,
    config_classic: ScoreConfig,
    config_quat: ScoreConfig,
    ablations: Iterable[str],
) -> Dict[str, Dict[str, Dict[str, float]]]:
    rng = np.random.RandomState(seed)
    raw_trajs = generate_trajectories(system, count=count, steps=steps, rng=rng)
    trajectories = [_normalize_trajectory(traj) for traj in raw_trajs]
    embeddings = [
        trajectory_to_embedding(traj, rng=rng)
        for traj in trajectories
    ]
    generator, traces = build_traces(embeddings, n_nodes=n_nodes)
    true_dists = pairwise_dtw_distances(
        trajectories,
        gamma=config_classic.soft_gamma,
        band=config_classic.soft_band,
    )

    results: Dict[str, Dict[str, Dict[str, float]]] = {}
    for label, cfg in (
        ("classic", config_classic),
        ("quat_influence", config_quat),
    ):
        score_raw, score_norm = score_matrices(embeddings, traces, generator, config=cfg)
        summary = _pairwise_score_summary(true_dists, score_raw, score_norm)
        ablation_results: Dict[str, Dict[str, float]] = {}
        for mode in ablations:
            ablated = apply_ablation(traces, mode=mode, rng=rng)
            score_raw_a, score_norm_a = score_matrices(embeddings, ablated, generator, config=cfg)
            ablation_results[mode] = _pairwise_score_summary(true_dists, score_raw_a, score_norm_a)
        results[label] = {"baseline": summary, "ablations": ablation_results}
    return results


def _aggregate_stats(samples: Sequence[Dict[str, float]]) -> Dict[str, float]:
    if not samples:
        return {}
    keys = sorted({key for sample in samples for key in sample.keys()})
    aggregated: Dict[str, float] = {}
    for key in keys:
        values = [float(sample[key]) for sample in samples if key in sample]
        if not values:
            continue
        arr = np.asarray(values, dtype=np.float64)
        aggregated[key] = float(np.mean(arr))
        aggregated[f"{key}_stdev"] = float(np.std(arr))
    return aggregated


def aggregate_seed_results(
    results_by_seed: Sequence[Dict[str, Dict[str, Dict[str, Dict[str, float]]]]],
) -> Dict[str, Dict[str, Dict[str, Dict[str, float]]]]:
    if not results_by_seed:
        return {}
    systems: Dict[str, Dict[str, Dict[str, Dict[str, float]]]] = {}
    for seed_result in results_by_seed:
        for system, modes in seed_result.items():
            system_bucket = systems.setdefault(system, {})
            for mode, data in modes.items():
                mode_bucket = system_bucket.setdefault(mode, {"baseline": {}, "ablations": {}})
                baseline_samples = mode_bucket.setdefault("baseline_samples", [])
                baseline_samples.append(data.get("baseline", {}))
                ablation_samples = mode_bucket.setdefault("ablation_samples", {})
                for ablation_name, ablation_stats in data.get("ablations", {}).items():
                    ablation_samples.setdefault(ablation_name, []).append(ablation_stats)

    aggregated: Dict[str, Dict[str, Dict[str, Dict[str, float]]]] = {}
    for system, modes in systems.items():
        aggregated[system] = {}
        for mode, buckets in modes.items():
            baseline_samples = buckets.get("baseline_samples", [])
            ablation_samples = buckets.get("ablation_samples", {})
            ablations_summary: Dict[str, Dict[str, float]] = {}
            for ablation_name, samples in ablation_samples.items():
                ablations_summary[ablation_name] = _aggregate_stats(samples)
            aggregated[system][mode] = {
                "baseline": _aggregate_stats(baseline_samples),
                "ablations": ablations_summary,
            }
    return aggregated
