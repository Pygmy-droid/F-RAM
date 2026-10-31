from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from fram_core.pipeline import tokenize_text
from fram_serving.cognitive_embeddings import build_cognitive_vectorizer, normalize_cognitive_backend
from fram_serving.config import FRAMConfig
from fram_serving.memory import CognitiveMemoryStore
try:  # pragma: no cover - optional in baseline branches
    from fram_serving.query_runner import _apply_fractal_influence
except Exception:  # pragma: no cover - optional in baseline branches
    _apply_fractal_influence = None  # type: ignore[assignment]
try:  # pragma: no cover - optional in baseline branches
    from fram_serving.fractal_memory import (
        DEFAULT_LAMBDA,
        DEFAULT_QUATERNION,
        build_query_path,
        downsample_path,
        logistic_lambda,
        min_max_normalize,
        path_quaternions,
        quaternion_alignment,
        soft_dtw_distance,
        soft_dtw_similarity,
    )
except Exception:  # pragma: no cover - optional in baseline branches
    DEFAULT_LAMBDA = None  # type: ignore[assignment]
    DEFAULT_QUATERNION = None  # type: ignore[assignment]
    build_query_path = None  # type: ignore[assignment]
    downsample_path = None  # type: ignore[assignment]
    logistic_lambda = None  # type: ignore[assignment]
    min_max_normalize = None  # type: ignore[assignment]
    path_quaternions = None  # type: ignore[assignment]
    quaternion_alignment = None  # type: ignore[assignment]
    soft_dtw_distance = None  # type: ignore[assignment]
    soft_dtw_similarity = None  # type: ignore[assignment]

DATA_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_DATASET = DATA_DIR / "conversation_memory_eval.jsonl"
DEFAULT_LIVE_DATASET = DATA_DIR / "conversation_memory_live_probes.jsonl"
DETAIL_PREVIEW_CHARS = 160

Ranker = Callable[[str, int], List[Dict[str, Any]]]


def load_eval_items(path: Path = DEFAULT_DATASET) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))
    return items


def _embed_text(text: str, *, vectorizer: Any | None) -> List[float] | None:
    if vectorizer is None:
        return None
    matrix = vectorizer.transform([text])
    if hasattr(matrix, "toarray"):
        arr = matrix.toarray()[0]
    else:
        arr = np.asarray(matrix, dtype=float).ravel()
    arr = np.asarray(arr, dtype=float)
    if arr.ndim == 2:
        arr = arr[0]
    return arr.astype(float, copy=False).ravel().tolist()


def build_query_vectorizer(config: FRAMConfig) -> Any | None:
    return build_cognitive_vectorizer(config)


def _doc_id_for_result(result: Dict[str, Any]) -> str:
    kind = str(result.get("kind") or "")
    item_id = result.get("id")
    if not item_id:
        return ""
    if kind == "episode":
        return f"cmem:ep:{item_id}"
    if kind == "belief":
        return f"cmem:bl:{item_id}"
    return ""


def _result_preview(result: Dict[str, Any], *, limit: int = DETAIL_PREVIEW_CHARS) -> str:
    kind = str(result.get("kind") or "")
    text = ""
    if kind == "episode":
        query = str(result.get("query") or "")
        answer = str(result.get("answer") or "")
        text = f"Q: {query}\nA: {answer}".strip()
    elif kind == "belief":
        text = str(result.get("text") or "")
    else:
        text = str(result.get("text") or "")
    preview = " ".join(text.split())
    if limit <= 0:
        return preview
    if len(preview) > limit:
        if limit <= 3:
            return preview[:limit]
        return preview[: limit - 3] + "..."
    return preview


def _candidate_text(result: Dict[str, Any]) -> str:
    kind = str(result.get("kind") or "")
    if kind == "episode":
        query = str(result.get("query") or "")
        answer = str(result.get("answer") or "")
        return f"{query}\n{answer}".strip()
    if kind == "belief":
        return str(result.get("text") or "").strip()
    return str(result.get("text") or "").strip()


def _candidate_gate_text(result: Dict[str, Any], *, overlap_mode: str) -> str:
    kind = str(result.get("kind") or "")
    if overlap_mode == "answer" and kind == "episode":
        answer = str(result.get("answer") or "").strip()
        if answer:
            return answer
    return _candidate_text(result)


_QUOTE_RE = re.compile(r"(?:'[^']*'|\"[^\"]*\")")


def _strip_quoted_text(text: str) -> str:
    return _QUOTE_RE.sub(" ", text)


def _gate_query_tokens(query: str) -> List[str]:
    stripped = _strip_quoted_text(query)
    tokens = tokenize_text(stripped)
    if not tokens:
        tokens = tokenize_text(query)
    return [token for token in tokens if token]


def _cosine_similarity(a: Sequence[float], b: Sequence[float]) -> Optional[float]:
    a_vec = np.asarray(a, dtype=float).ravel()
    b_vec = np.asarray(b, dtype=float).ravel()
    if a_vec.size == 0 or b_vec.size == 0:
        return None
    if a_vec.size != b_vec.size:
        return None
    denom = float(np.linalg.norm(a_vec) * np.linalg.norm(b_vec))
    if denom <= 0.0:
        return None
    return float(np.dot(a_vec, b_vec) / denom)


def _percentile_normalize(values: Sequence[float]) -> np.ndarray:
    arr = np.asarray(values, dtype=float).ravel()
    if arr.size == 0:
        return arr
    mask = np.isfinite(arr)
    if not np.any(mask):
        return np.zeros_like(arr, dtype=float)
    valid = arr[mask]
    order = np.argsort(valid)
    sorted_vals = valid[order]
    n = sorted_vals.size
    if n == 1:
        result = np.zeros_like(arr, dtype=float)
        result[mask] = 0.5
        return result
    ranks = np.empty_like(sorted_vals, dtype=float)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and sorted_vals[j + 1] == sorted_vals[i]:
            j += 1
        rank = 0.5 * (i + j)
        ranks[i : j + 1] = rank
        i = j + 1
    mapped = np.empty_like(ranks)
    mapped[order] = ranks
    result = np.zeros_like(arr, dtype=float)
    result[mask] = mapped / float(n - 1)
    return result


def _turn_angle_hist(path: np.ndarray, *, bins: int = 8) -> Optional[np.ndarray]:
    coords = np.asarray(path, dtype=float)
    if coords.ndim != 2 or coords.shape[0] < 3:
        return None
    deltas = np.diff(coords, axis=0)
    norms = np.linalg.norm(deltas, axis=1)
    valid = norms > 1e-12
    if not np.any(valid):
        return None
    deltas = deltas[valid]
    norms = norms[valid]
    if deltas.shape[0] < 2:
        return None
    deltas = deltas / norms[:, None]
    cos_vals = np.sum(deltas[:-1] * deltas[1:], axis=1)
    cos_vals = np.clip(cos_vals, -1.0, 1.0)
    hist, _ = np.histogram(cos_vals, bins=bins, range=(-1.0, 1.0))
    total = float(hist.sum())
    if total <= 0.0:
        return None
    return hist.astype(float) / total


def _radius_hist(path: np.ndarray, *, bins: int = 8) -> Optional[np.ndarray]:
    coords = np.asarray(path, dtype=float)
    if coords.ndim != 2 or coords.shape[0] < 2:
        return None
    centroid = coords.mean(axis=0)
    distances = np.linalg.norm(coords - centroid, axis=1)
    max_dist = float(np.max(distances))
    if not np.isfinite(max_dist) or max_dist <= 0.0:
        return None
    scaled = distances / max_dist
    hist, _ = np.histogram(scaled, bins=bins, range=(0.0, 1.0))
    total = float(hist.sum())
    if total <= 0.0:
        return None
    return hist.astype(float) / total


def _curvature_hist(path: np.ndarray, *, bins: int = 8) -> Optional[np.ndarray]:
    coords = np.asarray(path, dtype=float)
    if coords.ndim != 2 or coords.shape[0] < 3:
        return None
    deltas = np.diff(coords, axis=0)
    if deltas.shape[0] < 2:
        return None
    accel = np.diff(deltas, axis=0)
    if accel.size == 0:
        return None
    values = np.linalg.norm(accel, axis=1)
    max_val = float(np.max(values))
    if not np.isfinite(max_val) or max_val <= 0.0:
        return None
    scaled = values / max_val
    hist, _ = np.histogram(scaled, bins=bins, range=(0.0, 1.0))
    total = float(hist.sum())
    if total <= 0.0:
        return None
    return hist.astype(float) / total


def _lag_distance_signature(
    path: np.ndarray,
    *,
    lags: Sequence[int] = (1, 2, 4, 8),
) -> Optional[np.ndarray]:
    coords = np.asarray(path, dtype=float)
    if coords.ndim != 2:
        return None
    count = coords.shape[0]
    if count < 2:
        return None
    values = []
    for lag in lags:
        if lag <= 0 or lag >= count:
            return None
        diffs = coords[lag:] - coords[:-lag]
        if diffs.size == 0:
            return None
        distances = np.linalg.norm(diffs, axis=1)
        if distances.size == 0:
            return None
        values.append(float(distances.mean()))
    signature = np.asarray(values, dtype=float)
    total = float(signature.sum())
    if total <= 0.0:
        return None
    return signature / total


def _ifs_query_path(
    generator: Any,
    query_point: np.ndarray,
    *,
    steps: int,
    ifs_seed: int | None,
    order_seed: int | None,
) -> Optional[np.ndarray]:
    if ifs_seed is None or order_seed is None or steps <= 0:
        return None
    try:
        rng = generator._rng(int(ifs_seed))
        transforms, offsets = generator._ifs_params(rng)
        order = generator._ifs_order(generator._rng(int(order_seed)), len(transforms))
    except Exception:
        return None
    if not transforms or not offsets:
        return None
    state = np.asarray(query_point, dtype=float)
    coords: List[np.ndarray] = []
    for idx in range(steps):
        transform = transforms[order[idx % len(order)]]
        offset = offsets[order[idx % len(order)]]
        state = transform @ state + offset
        coords.append(state.copy())
    if not coords:
        return None
    return np.vstack(coords)


def _max_similarity(
    query_vector: Sequence[float],
    results: Sequence[Dict[str, Any]],
    *,
    vectorizer: Any,
) -> Optional[float]:
    max_sim: Optional[float] = None
    for result in results:
        text = _candidate_text(result)
        if not text:
            continue
        cand_vec = _embed_text(text, vectorizer=vectorizer)
        if not cand_vec:
            continue
        sim = _cosine_similarity(query_vector, cand_vec)
        if sim is None:
            continue
        if max_sim is None or sim > max_sim:
            max_sim = sim
    return max_sim


def _token_overlap_ratio(query_tokens: Sequence[str], text: str) -> float:
    q_tokens = [token for token in query_tokens if token]
    if not q_tokens:
        return 0.0
    t_tokens = set(tokenize_text(text))
    if not t_tokens:
        return 0.0
    q_set = set(q_tokens)
    if not q_set:
        return 0.0
    return len(q_set & t_tokens) / float(len(q_set))


def _max_overlap_ratio(
    query_tokens: Sequence[str],
    results: Sequence[Dict[str, Any]],
    *,
    overlap_mode: str = "full",
) -> Optional[float]:
    if not query_tokens:
        return None
    max_overlap: Optional[float] = None
    for result in results:
        text = _candidate_gate_text(result, overlap_mode=overlap_mode)
        if not text:
            continue
        overlap = _token_overlap_ratio(query_tokens, text)
        if max_overlap is None or overlap > max_overlap:
            max_overlap = overlap
    return max_overlap


def _compute_trace_entries(
    store: CognitiveMemoryStore,
    *,
    candidate_ids: Sequence[str],
    query_vector: Sequence[float],
    config: FRAMConfig,
    soft_dtw_gamma: float | None = None,
    soft_dtw_band: float | None = None,
    soft_dtw_score_mode: str | None = None,
    cosine_mode: str | None = None,
    query_path_mode: str | None = None,
) -> List[Dict[str, Any]]:
    if any(
        func is None
        for func in (
            DEFAULT_LAMBDA,
            DEFAULT_QUATERNION,
            build_query_path,
            downsample_path,
            logistic_lambda,
            path_quaternions,
            quaternion_alignment,
            soft_dtw_distance,
        )
    ):
        return []
    if not candidate_ids:
        return []
    trace_store = store.fractal_trace_store()
    if trace_store is None:
        return []
    vector = np.asarray(query_vector, dtype=float).ravel()
    if vector.size == 0:
        return []
    target_dim = getattr(trace_store.generator, "embedding_dim", vector.size)
    if vector.size != target_dim:
        return []
    try:
        downsample_target = int(getattr(config, "fractal_downsample_target", 256))
    except Exception:
        downsample_target = 256
    if downsample_target <= 0:
        downsample_target = 256
    cosine_mode_value = str(cosine_mode or "composite").strip().lower()
    if cosine_mode_value not in {
        "composite",
        "centroid",
        "delta",
        "turn_hist",
        "lag_dist",
        "radius_hist",
        "curvature_hist",
    }:
        cosine_mode_value = "composite"
    query_path_mode_value = str(query_path_mode or "synthetic").strip().lower()
    if query_path_mode_value not in {"synthetic", "ifs"}:
        query_path_mode_value = "synthetic"
    soft_dtw_score_mode_value = str(soft_dtw_score_mode or "inverse").strip().lower()
    if soft_dtw_score_mode_value not in {"inverse", "exp"}:
        soft_dtw_score_mode_value = "inverse"
    try:
        gamma_value = float(soft_dtw_gamma) if soft_dtw_gamma is not None else 0.1
    except (TypeError, ValueError):
        gamma_value = 0.1
    try:
        band_value = float(soft_dtw_band) if soft_dtw_band is not None else 0.15
    except (TypeError, ValueError):
        band_value = 0.15
    projection_cache: Dict[Optional[int], np.ndarray] = {}
    path_cache: Dict[Tuple[object, ...], np.ndarray] = {}
    quat_cache: Dict[Tuple[object, ...], np.ndarray] = {}
    hist_cache: Dict[Tuple[object, ...], Optional[np.ndarray]] = {}
    lag_cache: Dict[Tuple[object, ...], Optional[np.ndarray]] = {}
    radius_cache: Dict[Tuple[object, ...], Optional[np.ndarray]] = {}
    curvature_cache: Dict[Tuple[object, ...], Optional[np.ndarray]] = {}
    entries: List[Dict[str, Any]] = []
    for episode_id in candidate_ids:
        bundle = trace_store.load_trace(str(episode_id))
        if bundle is None:
            if not store.ensure_fractal_trace(str(episode_id)):
                continue
            bundle = trace_store.load_trace(str(episode_id))
        if bundle is None:
            continue
        trace_line, metadata = bundle
        provenance = trace_line.provenance or {}
        proj_seed_raw = provenance.get("projection_seed")
        ifs_seed_raw = provenance.get("ifs_seed")
        order_seed_raw = provenance.get("order_seed")
        try:
            proj_seed = int(proj_seed_raw) if proj_seed_raw is not None else None
        except (TypeError, ValueError):
            proj_seed = None
        try:
            ifs_seed = int(ifs_seed_raw) if ifs_seed_raw is not None else None
        except (TypeError, ValueError):
            ifs_seed = None
        try:
            order_seed = int(order_seed_raw) if order_seed_raw is not None else None
        except (TypeError, ValueError):
            order_seed = None
        if proj_seed in projection_cache:
            q6 = projection_cache[proj_seed]
        else:
            try:
                q6 = trace_store.generator.project(vector, projection_seed=proj_seed)
            except Exception:
                continue
            projection_cache[proj_seed] = q6
        try:
            coords_full = trace_store.generator.retrace(trace_line)
        except Exception:
            continue
        if coords_full.size == 0:
            continue
        coords, stride = downsample_path(coords_full, target=downsample_target)
        if coords.size == 0:
            continue
        coords = np.asarray(coords, dtype=float)
        indices = list(range(0, coords_full.shape[0], stride))
        if len(indices) > coords.shape[0]:
            indices = indices[: coords.shape[0]]
        centroid = coords.mean(axis=0)
        start = coords[0]
        end = coords[-1]
        composite = (centroid + start + end) / 3.0
        cosine_target = centroid if cosine_mode_value == "centroid" else composite
        norm_q = float(np.linalg.norm(q6))
        norm_target = float(np.linalg.norm(cosine_target))
        if norm_q <= 0.0 or norm_target <= 0.0:
            continue
        cosine_score = float(np.dot(q6, cosine_target) / (norm_q * norm_target))
        synthetic_key = (proj_seed, coords.shape[0], "synthetic")
        query_path = None
        path_key = synthetic_key
        if query_path_mode_value == "ifs" and ifs_seed is not None and order_seed is not None:
            ifs_key = (proj_seed, coords.shape[0], ifs_seed, order_seed, "ifs")
            if ifs_key in path_cache:
                query_path = path_cache[ifs_key]
                path_key = ifs_key
            else:
                query_path = _ifs_query_path(
                    trace_store.generator,
                    q6,
                    steps=coords.shape[0],
                    ifs_seed=ifs_seed,
                    order_seed=order_seed,
                )
                if query_path is not None:
                    query_path, _ = downsample_path(query_path, target=coords.shape[0])
                    path_cache[ifs_key] = query_path
                    path_key = ifs_key
        if query_path is None:
            if synthetic_key in path_cache:
                query_path = path_cache[synthetic_key]
            else:
                try:
                    query_path = build_query_path(q6, steps=coords.shape[0])
                except Exception:
                    continue
                query_path, _ = downsample_path(query_path, target=coords.shape[0])
                path_cache[synthetic_key] = query_path
            path_key = synthetic_key
        turn_hist_raw: Optional[float] = None
        lag_dist_raw: Optional[float] = None
        radius_hist_raw: Optional[float] = None
        curvature_hist_raw: Optional[float] = None
        if cosine_mode_value == "turn_hist":
            if path_key in hist_cache:
                query_hist = hist_cache[path_key]
            else:
                query_hist = _turn_angle_hist(query_path)
                hist_cache[path_key] = query_hist
            trace_hist = _turn_angle_hist(coords)
            if query_hist is not None and trace_hist is not None:
                hist_score = _cosine_similarity(query_hist, trace_hist)
                if hist_score is not None:
                    turn_hist_raw = float(hist_score)
                    cosine_score = turn_hist_raw
        if cosine_mode_value == "lag_dist":
            if path_key in lag_cache:
                query_sig = lag_cache[path_key]
            else:
                query_sig = _lag_distance_signature(query_path)
                lag_cache[path_key] = query_sig
            trace_sig = _lag_distance_signature(coords)
            if query_sig is not None and trace_sig is not None:
                sig_score = _cosine_similarity(query_sig, trace_sig)
                if sig_score is not None:
                    lag_dist_raw = float(sig_score)
                    cosine_score = lag_dist_raw
        if cosine_mode_value == "radius_hist":
            if path_key in radius_cache:
                query_hist = radius_cache[path_key]
            else:
                query_hist = _radius_hist(query_path)
                radius_cache[path_key] = query_hist
            trace_hist = _radius_hist(coords)
            if query_hist is not None and trace_hist is not None:
                hist_score = _cosine_similarity(query_hist, trace_hist)
                if hist_score is not None:
                    radius_hist_raw = float(hist_score)
                    cosine_score = radius_hist_raw
        if cosine_mode_value == "curvature_hist":
            if path_key in curvature_cache:
                query_hist = curvature_cache[path_key]
            else:
                query_hist = _curvature_hist(query_path)
                curvature_cache[path_key] = query_hist
            trace_hist = _curvature_hist(coords)
            if query_hist is not None and trace_hist is not None:
                hist_score = _cosine_similarity(query_hist, trace_hist)
                if hist_score is not None:
                    curvature_hist_raw = float(hist_score)
                    cosine_score = curvature_hist_raw
        if cosine_mode_value == "delta":
            query_delta = np.diff(query_path, axis=0)
            trace_delta = np.diff(coords, axis=0)
            if query_delta.size == 0 or trace_delta.size == 0:
                continue
            q_mean = query_delta.mean(axis=0)
            t_mean = trace_delta.mean(axis=0)
            q_norm = float(np.linalg.norm(q_mean))
            t_norm = float(np.linalg.norm(t_mean))
            if q_norm <= 0.0 or t_norm <= 0.0:
                continue
            cosine_score = float(np.dot(q_mean, t_mean) / (q_norm * t_norm))
        if path_key in quat_cache:
            query_quats = quat_cache[path_key]
        else:
            try:
                query_quats = path_quaternions(query_path)
            except Exception:
                query_quats = np.zeros((0, 4), dtype=np.float64)
            quat_cache[path_key] = query_quats
        try:
            trace_quats = path_quaternions(coords)
        except Exception:
            trace_quats = np.zeros((0, 4), dtype=np.float64)
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
        try:
            alignment = quaternion_alignment(query_quats, trace_quats, absolute=True)
        except Exception:
            alignment = np.zeros((0,), dtype=np.float64)
        quat_raw = 0.0
        quat_lambda_raw = 0.0
        if alignment.size > 0:
            quat_raw = float(np.mean(alignment))
            weights: List[float] = []
            if indices:
                for node_idx in indices[: alignment.size]:
                    lambda_val: Optional[float] = None
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
                    quat_lambda_raw = float(
                        np.average(alignment[: len(weight_arr)], weights=weight_arr)
                    )
                else:
                    quat_lambda_raw = quat_raw
            else:
                quat_lambda_raw = quat_raw
        try:
            soft_dist = float(soft_dtw_distance(query_path, coords, gamma=gamma_value, band=band_value))
        except Exception:
            soft_dist = float("nan")
        entries.append(
            {
                "episode_id": trace_line.seed_id,
                "projection_seed": proj_seed,
                "cosine_raw": cosine_score,
                "turn_hist_raw": turn_hist_raw,
                "lag_dist_raw": lag_dist_raw,
                "radius_hist_raw": radius_hist_raw,
                "curvature_hist_raw": curvature_hist_raw,
                "soft_dist": soft_dist,
                "quat_raw": quat_raw,
                "quat_lambda_raw": quat_lambda_raw,
                "nodes": int(coords.shape[0]),
            }
        )
    if not entries:
        return []
    soft_dists = np.array([entry["soft_dist"] for entry in entries], dtype=float)
    if soft_dtw_score_mode_value == "exp":
        valid = soft_dists[np.isfinite(soft_dists)]
        scale = float(np.median(valid)) if valid.size else 1.0
        if scale <= 0.0:
            scale = 1.0
        soft_scores = np.exp(-soft_dists / scale)
    else:
        soft_scores = soft_dtw_similarity(soft_dists)
    soft_scores = np.where(np.isfinite(soft_scores), soft_scores, 0.0)
    for entry, soft_score in zip(entries, soft_scores):
        entry["soft_raw"] = float(soft_score)
    return entries


def _score_trace_entries(
    entries: Sequence[Dict[str, Any]],
    *,
    alpha: float,
    quat_enabled: bool,
    quat_weight: float,
    quat_use: bool,
    trace_norm_mode: str = "minmax",
) -> Dict[str, float]:
    if not entries:
        return {}
    norm_mode = str(trace_norm_mode or "minmax").strip().lower()
    if norm_mode not in {"minmax", "percentile"}:
        norm_mode = "minmax"
    if norm_mode == "minmax" and min_max_normalize is None:
        return {}
    cos_array = np.array([entry["cosine_raw"] for entry in entries], dtype=float)
    soft_array = np.array([entry["soft_raw"] for entry in entries], dtype=float)
    quat_array = np.array([entry["quat_raw"] for entry in entries], dtype=float)
    quat_lambda_array = np.array([entry["quat_lambda_raw"] for entry in entries], dtype=float)
    if norm_mode == "percentile":
        cos_norm = _percentile_normalize(cos_array)
        soft_norm = _percentile_normalize(soft_array)
        quat_norm = _percentile_normalize(quat_array)
        quat_lambda_norm = _percentile_normalize(quat_lambda_array)
    else:
        cos_norm = min_max_normalize(cos_array)
        soft_norm = min_max_normalize(soft_array)
        quat_norm = min_max_normalize(quat_array)
        quat_lambda_norm = min_max_normalize(quat_lambda_array)
    score_map: Dict[str, float] = {}
    for entry, cos_n, soft_n, quat_n, quat_lambda_n in zip(
        entries, cos_norm, soft_norm, quat_norm, quat_lambda_norm
    ):
        base_norm = alpha * cos_n + (1.0 - alpha) * soft_n
        quat_norm_value = float(quat_lambda_n if quat_use else quat_n)
        score_norm = base_norm
        if quat_enabled and quat_weight > 0.0:
            score_norm = (1.0 - quat_weight) * base_norm + quat_weight * quat_norm_value
        score_map[str(entry["episode_id"])] = float(score_norm)
    return score_map


def build_fractal_ranker(
    store: CognitiveMemoryStore,
    *,
    vectorizer: Any,
    config: FRAMConfig,
    pool_multiplier: int = 1,
    trace_limit: int | None = None,
    influence_alpha: float | None = None,
    quat_enabled: bool | None = None,
    quat_weight: float | None = None,
    quat_use_lambda: bool | None = None,
    low_lex_alpha: float | None = None,
    low_lex_threshold: float | None = None,
    low_lex_similarity_threshold: float | None = None,
    low_lex_overlap_mode: str | None = None,
    soft_dtw_gamma: float | None = None,
    soft_dtw_band: float | None = None,
    soft_dtw_score_mode: str | None = None,
    cosine_mode: str | None = None,
    trace_norm_mode: str | None = None,
    query_path_mode: str | None = None,
    low_lex_query_path_mode: str | None = None,
    kinds: Sequence[str] | None = None,
) -> Ranker:
    pool_multiplier = max(1, int(pool_multiplier))
    kind_filters = [str(k).strip().lower() for k in (kinds or []) if str(k).strip()]
    filters = {"kinds": kind_filters} if kind_filters else None
    try:
        low_lex_alpha_value = float(low_lex_alpha) if low_lex_alpha is not None else None
    except (TypeError, ValueError):
        low_lex_alpha_value = None
    try:
        low_lex_threshold_value = (
            float(low_lex_threshold) if low_lex_threshold is not None else None
        )
    except (TypeError, ValueError):
        low_lex_threshold_value = None
    if low_lex_threshold_value is not None:
        low_lex_threshold_value = max(0.0, min(1.0, low_lex_threshold_value))
    try:
        low_lex_similarity_value = (
            float(low_lex_similarity_threshold)
            if low_lex_similarity_threshold is not None
            else None
        )
    except (TypeError, ValueError):
        low_lex_similarity_value = None
    if low_lex_similarity_value is not None:
        low_lex_similarity_value = max(-1.0, min(1.0, low_lex_similarity_value))
    gate_mode = None
    if low_lex_similarity_value is not None:
        gate_mode = "similarity"
    elif low_lex_threshold_value is not None:
        gate_mode = "overlap"
    overlap_mode_value = str(low_lex_overlap_mode or "full").strip().lower()
    if overlap_mode_value not in {"full", "answer"}:
        overlap_mode_value = "full"
    cosine_mode_value = str(cosine_mode or "composite").strip().lower()
    if cosine_mode_value not in {
        "composite",
        "centroid",
        "delta",
        "turn_hist",
        "lag_dist",
        "radius_hist",
        "curvature_hist",
    }:
        cosine_mode_value = "composite"
    soft_dtw_score_mode_value = str(soft_dtw_score_mode or "inverse").strip().lower()
    if soft_dtw_score_mode_value not in {"inverse", "exp"}:
        soft_dtw_score_mode_value = "inverse"
    trace_norm_mode_value = str(trace_norm_mode or "minmax").strip().lower()
    if trace_norm_mode_value not in {"minmax", "percentile"}:
        trace_norm_mode_value = "minmax"
    query_path_mode_value = str(query_path_mode or "synthetic").strip().lower()
    if query_path_mode_value not in {"synthetic", "ifs"}:
        query_path_mode_value = "synthetic"
    low_lex_query_path_mode_value = None
    if low_lex_query_path_mode is not None:
        candidate = str(low_lex_query_path_mode).strip().lower()
        if candidate in {"synthetic", "ifs"}:
            low_lex_query_path_mode_value = candidate
    try:
        soft_dtw_gamma_value = float(soft_dtw_gamma) if soft_dtw_gamma is not None else None
    except (TypeError, ValueError):
        soft_dtw_gamma_value = None
    try:
        soft_dtw_band_value = float(soft_dtw_band) if soft_dtw_band is not None else None
    except (TypeError, ValueError):
        soft_dtw_band_value = None
    stats: Dict[str, Any] = {
        "queries": 0,
        "low_lex_hits": 0,
        "low_lex_overlap_min": None,
        "low_lex_overlap_max": None,
        "low_lex_overlap_mean": None,
        "low_lex_threshold": low_lex_threshold_value,
        "low_lex_alpha": low_lex_alpha_value,
        "low_lex_overlap_mode": overlap_mode_value,
        "low_lex_similarity_min": None,
        "low_lex_similarity_max": None,
        "low_lex_similarity_mean": None,
        "low_lex_similarity_threshold": low_lex_similarity_value,
        "low_lex_gate_mode": gate_mode,
        "soft_dtw_gamma": soft_dtw_gamma_value,
        "soft_dtw_band": soft_dtw_band_value,
        "soft_dtw_score_mode": soft_dtw_score_mode_value,
        "cosine_mode": cosine_mode_value,
        "trace_norm_mode": trace_norm_mode_value,
        "query_path_mode": query_path_mode_value,
        "low_lex_query_path_mode": low_lex_query_path_mode_value,
        "_low_lex_overlap_sum": 0.0,
        "_low_lex_overlap_count": 0,
        "_low_lex_similarity_sum": 0.0,
        "_low_lex_similarity_count": 0,
    }

    def _fractal_score_map(
        candidate_ids: List[str],
        query_vector: Sequence[float],
        cfg: FRAMConfig,
        path_mode: str | None = None,
    ) -> Dict[str, float]:
        try:
            alpha = float(getattr(cfg, "fractal_blend_alpha", 0.4))
        except Exception:
            alpha = 0.4
        alpha = max(0.0, min(1.0, alpha))
        try:
            quat_weight = float(getattr(cfg, "fractal_quat_weight", 0.0))
        except Exception:
            quat_weight = 0.0
        quat_weight = max(0.0, min(1.0, quat_weight))
        quat_enabled = bool(getattr(cfg, "fractal_quat_influence", False))
        quat_use = bool(getattr(cfg, "fractal_quat_use_lambda", True))
        entries = _compute_trace_entries(
            store,
            candidate_ids=candidate_ids,
            query_vector=query_vector,
            config=cfg,
            soft_dtw_gamma=soft_dtw_gamma_value,
            soft_dtw_band=soft_dtw_band_value,
            soft_dtw_score_mode=soft_dtw_score_mode_value,
            cosine_mode=cosine_mode_value,
            query_path_mode=path_mode or query_path_mode_value,
        )
        if not entries:
            return {}
        return _score_trace_entries(
            entries,
            alpha=alpha,
            quat_enabled=quat_enabled,
            quat_weight=quat_weight,
            quat_use=quat_use,
            trace_norm_mode=trace_norm_mode_value,
        )

    def _ranker(query: str, k_max: int) -> List[Dict[str, Any]]:
        pool_size = max(1, int(k_max) * pool_multiplier)
        base_results = store.search(query, k=pool_size, filters=filters, vectorizer=vectorizer)
        if _apply_fractal_influence is None:
            return base_results[:k_max]
        if vectorizer is None:
            return base_results[:k_max]
        query_vector = _embed_text(query, vectorizer=vectorizer)
        if not query_vector:
            return base_results[:k_max]
        alpha = influence_alpha
        if alpha is None:
            alpha = float(getattr(config, "fractal_influence_alpha", 0.05))
        alpha = max(0.0, min(1.0, float(alpha)))
        stats["queries"] += 1
        low_lex_overlap: Optional[float] = None
        low_lex_similarity: Optional[float] = None
        low_lex_triggered = False
        if low_lex_alpha_value is not None:
            if low_lex_similarity_value is not None:
                low_lex_similarity = _max_similarity(query_vector, base_results, vectorizer=vectorizer)
                if low_lex_similarity is not None:
                    stats["_low_lex_similarity_sum"] += low_lex_similarity
                    stats["_low_lex_similarity_count"] += 1
                    stats["low_lex_similarity_min"] = (
                        low_lex_similarity
                        if stats["low_lex_similarity_min"] is None
                        else min(stats["low_lex_similarity_min"], low_lex_similarity)
                    )
                    stats["low_lex_similarity_max"] = (
                        low_lex_similarity
                        if stats["low_lex_similarity_max"] is None
                        else max(stats["low_lex_similarity_max"], low_lex_similarity)
                    )
                    if stats["_low_lex_similarity_count"]:
                        stats["low_lex_similarity_mean"] = (
                            stats["_low_lex_similarity_sum"]
                            / stats["_low_lex_similarity_count"]
                        )
                if (
                    low_lex_similarity is not None
                    and low_lex_similarity <= low_lex_similarity_value
                ):
                    alpha = low_lex_alpha_value
                    stats["low_lex_hits"] += 1
                    low_lex_triggered = True
            elif low_lex_threshold_value is not None:
                q_tokens = _gate_query_tokens(query)
                low_lex_overlap = _max_overlap_ratio(
                    q_tokens, base_results, overlap_mode=overlap_mode_value
                )
                if low_lex_overlap is not None:
                    stats["_low_lex_overlap_sum"] += low_lex_overlap
                    stats["_low_lex_overlap_count"] += 1
                    stats["low_lex_overlap_min"] = (
                        low_lex_overlap
                        if stats["low_lex_overlap_min"] is None
                        else min(stats["low_lex_overlap_min"], low_lex_overlap)
                    )
                    stats["low_lex_overlap_max"] = (
                        low_lex_overlap
                        if stats["low_lex_overlap_max"] is None
                        else max(stats["low_lex_overlap_max"], low_lex_overlap)
                    )
                    if stats["_low_lex_overlap_count"]:
                        stats["low_lex_overlap_mean"] = (
                            stats["_low_lex_overlap_sum"] / stats["_low_lex_overlap_count"]
                        )
                if low_lex_overlap is not None and low_lex_overlap <= low_lex_threshold_value:
                    alpha = low_lex_alpha_value
                    stats["low_lex_hits"] += 1
                    low_lex_triggered = True
        if alpha == 0.0:
            return base_results[:k_max]
        cfg_update: Dict[str, Any] = {"fractal_enabled": True}
        if quat_enabled is not None:
            cfg_update["fractal_quat_influence"] = bool(quat_enabled)
        if quat_weight is not None:
            cfg_update["fractal_quat_weight"] = float(quat_weight)
        if quat_use_lambda is not None:
            cfg_update["fractal_quat_use_lambda"] = bool(quat_use_lambda)
        cfg_for_fractal = config.model_copy(update=cfg_update)
        score_ids: List[str] = []
        for result in base_results:
            if str(result.get("kind") or "") != "episode":
                continue
            episode_id = result.get("id")
            if episode_id:
                score_ids.append(str(episode_id))
        if trace_limit is not None:
            try:
                limit = max(1, int(trace_limit))
            except (TypeError, ValueError):
                limit = None
            if limit is not None:
                score_ids = score_ids[:limit]
        if not score_ids:
            return base_results[:k_max]
        path_mode = query_path_mode_value
        if low_lex_triggered and low_lex_query_path_mode_value:
            path_mode = low_lex_query_path_mode_value
        score_map = _fractal_score_map(
            score_ids,
            query_vector,
            cfg_for_fractal,
            path_mode=path_mode,
        )
        if not score_map:
            return base_results[:k_max]
        candidates: List[Dict[str, Any]] = []
        for idx, result in enumerate(base_results):
            doc_id = _doc_id_for_result(result)
            base_score = float(result.get("_score", result.get("score", 0.0)))
            candidates.append(
                {
                    "doc_id": doc_id,
                    "score": base_score,
                    "result": result,
                    "index": idx,
                }
            )
        if not candidates:
            return base_results[:k_max]
        _apply_fractal_influence(candidates, score_map, alpha=float(alpha), enabled=True)
        candidates.sort(
            key=lambda item: (float(item.get("score", 0.0)), -int(item.get("index", 0))),
            reverse=True,
        )
        return [item["result"] for item in candidates[:k_max]]

    setattr(_ranker, "stats", stats)
    return _ranker


def build_eval_store(
    items: Sequence[Dict[str, str]],
    *,
    store_root: Path,
    config: FRAMConfig,
) -> Tuple[CognitiveMemoryStore, Dict[str, str], Any]:
    store_root.mkdir(parents=True, exist_ok=True)
    store = CognitiveMemoryStore(store_root, config=config)
    vectorizer = build_query_vectorizer(config)
    backend = normalize_cognitive_backend(
        getattr(config, "cognitive_memory_embedding_backend", "hashing")
    )
    id_map: Dict[str, str] = {}
    for item in items:
        query = str(item.get("query") or "")
        answer = str(item.get("answer") or "")
        combined = f"{query}\n{answer}".strip()
        embedding = _embed_text(combined or query, vectorizer=vectorizer)
        record = store.append_episode(
            query=query,
            answer=answer,
            metadata={"eval_id": str(item.get("id"))},
            embedding=embedding,
            embedding_backend=backend if embedding is not None else None,
        )
        id_map[str(item.get("id"))] = str(record.get("id"))
    return store, id_map, vectorizer


def evaluate_items(
    items: Sequence[Dict[str, str]],
    *,
    store: CognitiveMemoryStore,
    id_map: Dict[str, str],
    query_field: str,
    vectorizer: Any | None,
    k_values: Iterable[int] = (1, 3),
    ranker: Ranker | None = None,
    skip_missing_expected: bool = False,
    details: List[Dict[str, Any]] | None = None,
    details_topk: int = 5,
    kinds: Sequence[str] | None = None,
) -> Dict[str, float]:
    k_list = sorted({max(1, int(k)) for k in k_values})
    k_max = max(k_list)
    hits = {k: 0 for k in k_list}
    mrr = 0.0
    total = 0
    missing_expected = 0
    missing_query = 0
    kind_filters = [str(k).strip().lower() for k in (kinds or []) if str(k).strip()]
    filters = {"kinds": kind_filters} if kind_filters else None
    for item in items:
        query = str(item.get(query_field) or item.get("probe") or "")
        if not query:
            missing_query += 1
            if details is not None:
                details.append(
                    {
                        "id": str(item.get("id") or ""),
                        "query": "",
                        "expected_id": None,
                        "rank": None,
                        "status": "missing_query",
                        "top_results": [],
                    }
                )
            continue
        expected = id_map.get(str(item.get("id")))
        if expected is None and skip_missing_expected and details is None:
            missing_expected += 1
            continue
        if ranker is None:
            results = store.search(query, k=k_max, filters=filters, vectorizer=vectorizer)
        else:
            results = ranker(query, k_max)
        if expected is None and skip_missing_expected:
            missing_expected += 1
            if details is not None:
                top_results: List[Dict[str, Any]] = []
                for idx, result in enumerate(results[: max(0, details_topk)]):
                    top_results.append(
                        {
                            "rank": idx,
                            "id": result.get("id"),
                            "kind": result.get("kind"),
                            "doc_id": _doc_id_for_result(result),
                            "score": float(result.get("_score", result.get("score", 0.0))),
                            "preview": _result_preview(result),
                        }
                    )
                details.append(
                    {
                        "id": str(item.get("id") or ""),
                        "query": query,
                        "expected_id": None,
                        "rank": None,
                        "status": "missing_expected",
                        "top_results": top_results,
                    }
                )
            continue
        total += 1
        rank = None
        for idx, result in enumerate(results):
            if str(result.get("id")) == expected:
                rank = idx
                break
        if rank is not None:
            mrr += 1.0 / float(rank + 1)
            for k in k_list:
                if rank < k:
                    hits[k] += 1
        if details is not None:
            top_results = []
            for idx, result in enumerate(results[: max(0, details_topk)]):
                top_results.append(
                    {
                        "rank": idx,
                        "id": result.get("id"),
                        "kind": result.get("kind"),
                        "doc_id": _doc_id_for_result(result),
                        "score": float(result.get("_score", result.get("score", 0.0))),
                        "preview": _result_preview(result),
                    }
                )
            status = "hit" if rank is not None else "miss"
            details.append(
                {
                    "id": str(item.get("id") or ""),
                    "query": query,
                    "expected_id": expected,
                    "rank": rank,
                    "status": status,
                    "top_results": top_results,
                }
            )
    denom = max(1, total)
    metrics = {"count": float(total), "mrr": mrr / denom}
    for k in k_list:
        metrics[f"top{k}"] = hits[k] / denom
    if skip_missing_expected:
        metrics["missing_expected"] = float(missing_expected)
        metrics["missing_query"] = float(missing_query)
    return metrics


def _parse_iso(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    try:
        stamp = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp


def _iter_live_episodes(store: CognitiveMemoryStore) -> List[Dict[str, Any]]:
    path = store.root / store.FILE_EPISODES
    if not path.exists():
        return []
    episodes: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for idx, line in enumerate(handle):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("type") != "episode":
                continue
            record["_index"] = idx
            episodes.append(record)
    return episodes


def resolve_live_id_map(
    items: Sequence[Dict[str, str]],
    *,
    store: CognitiveMemoryStore,
    match_query_field: str = "match_query",
    match_answer_field: str = "match_answer",
    match_domain_field: str = "match_domain",
    match_task_field: str = "match_task",
) -> Tuple[Dict[str, str], Dict[str, int]]:
    episodes = _iter_live_episodes(store)
    stats = {"total": len(items), "matched": 0, "matched_by_id": 0, "missing": 0, "ambiguous": 0}
    id_map: Dict[str, str] = {}
    if not episodes:
        stats["missing"] = len(items)
        return id_map, stats
    episodes_by_id = {str(record.get("id")): record for record in episodes if record.get("id")}

    def _norm(value: Any) -> str:
        return str(value or "").strip().lower()

    def _sort_key(record: Dict[str, Any]) -> Tuple[datetime, int]:
        stamp = _parse_iso(record.get("time"))
        if stamp is None:
            stamp = datetime.min.replace(tzinfo=timezone.utc)
        index = int(record.get("_index", -1))
        return (stamp, index)

    for item in items:
        item_id = str(item.get("id") or "").strip()
        if not item_id:
            stats["missing"] += 1
            continue
        match_episode_id = str(item.get("match_episode_id") or "").strip()
        if match_episode_id:
            if match_episode_id in episodes_by_id:
                id_map[item_id] = match_episode_id
                stats["matched"] += 1
                stats["matched_by_id"] += 1
                continue
            stats["missing"] += 1
            continue
        match_query = _norm(item.get(match_query_field) or item.get("query"))
        if not match_query:
            stats["missing"] += 1
            continue
        match_answer = _norm(item.get(match_answer_field))
        match_domain = str(item.get(match_domain_field) or "").strip()
        match_task = str(item.get(match_task_field) or "").strip()
        candidates = [
            record
            for record in episodes
            if match_query in _norm(record.get("query"))
        ]
        if match_answer:
            candidates = [
                record
                for record in candidates
                if match_answer in _norm(record.get("answer"))
            ]
        if match_domain:
            candidates = [record for record in candidates if record.get("domain") == match_domain]
        if match_task:
            candidates = [record for record in candidates if record.get("task") == match_task]
        if not candidates:
            stats["missing"] += 1
            continue
        if len(candidates) > 1:
            stats["ambiguous"] += 1
        best = max(candidates, key=_sort_key)
        id_map[item_id] = str(best.get("id"))
        stats["matched"] += 1
    return id_map, stats
