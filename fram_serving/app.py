from __future__ import annotations

import json
import logging
import os
from collections import Counter, OrderedDict, deque
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence

import numpy as np
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import AliasChoices, BaseModel, Field

from fram_core.pipeline import QueryOrchestrator, corpus_cache_to_dict, tokenize_text
from fram_core.pipeline import _build_vocab as _pipeline_build_vocab
from fram_core.pipeline import (
    _make_hashing_vectorizer as _pipeline_make_hashing_vectorizer,
)
from fram_core.rerank import SimpleCosineReranker
from fram_serving import observability
from fram_serving.archive import ArchiveWriter
from fram_serving.cognitive_embeddings import (
    build_cognitive_vectorizer,
    normalize_cognitive_backend,
)
from fram_serving.continuity import (
    WITNESS_SCHEMA_VERSION,
    ContinuityWitnessCorruptError,
    ContinuityWitnessNotFoundError,
    ContinuityWitnessReadError,
    ContinuityWitnessTamperedError,
    ContinuityWitnessWriter,
    load_latest_continuity_witness,
)
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
from fram_serving.lived_memory import LivedMemoryStore
from fram_serving.mcp_server import mcp
from fram_serving.memory import (
    CognitiveMemoryStore,
    MemorySessionError,
    WorkingMemoryStore,
    list_conflicts,
)
from fram_serving.memory_capsule import MemoryCapsuleStore
from fram_serving.query_runner import QueryContext, run_query
from fram_serving.scoring._fractal_trace_scores_phase_d import (
    attach_phase_d_observability,
    phase_d_score_batch,
)
from fram_serving.semantic import (
    CandidateFeatures,
    EntityGraph,
    RelevanceReranker,
    build_situation,
)

from .config import FRAMConfig

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = REPO_ROOT / "examples" / "data"

CFG = FRAMConfig.from_env()
CFG_DEFAULTS = FRAMConfig()
_alpha_env_value = os.getenv("FRAM_FRACTAL_BLEND_ALPHA")
try:
    _alpha_resolved = float(CFG.fractal_blend_alpha)
except (TypeError, ValueError):
    _alpha_resolved = CFG.fractal_blend_alpha
_logger = logging.getLogger("fram.serving.app")
if _alpha_env_value is not None:
    _logger.warning(
        "Fractal blend alpha resolved to %.3f (FRAM_FRACTAL_BLEND_ALPHA=%s)",
        _alpha_resolved,
        _alpha_env_value,
    )
else:
    _logger.warning(
        "Fractal blend alpha resolved to %.3f (default/config)", _alpha_resolved
    )
REL = observability.LiveReliability(maxlen=max(1, int(CFG.metrics_window)))
ALM = observability.AlarmBook(alpha1=CFG.alpha1, alpha2=CFG.alpha2)
TC_WINDOW = deque(maxlen=max(1, int(CFG.metrics_window)))
RERANKER = SimpleCosineReranker()
SEMANTIC_RERANKER = RelevanceReranker(getattr(CFG, "semantic_reranker_model", None))
ENTITY_GRAPH = EntityGraph(getattr(CFG, "semantic_entity_graph", {}))
_ORCHESTRATOR: Optional[QueryOrchestrator] = None
_PROB_CACHE: OrderedDict[str, Dict[str, Any]] = OrderedDict()
_PROB_CACHE_MAX = 1000
_MEMORY_STORE = WorkingMemoryStore(
    CFG.STORAGE_ROOT / CFG.STORAGE_SUBFOLDERS.get("memory", "memory"),
    dedupe_window_seconds=getattr(CFG, "working_memory_dedupe_window_sec", 0),
)

# Cognitive memory lives under a subfolder to avoid mixing with working-memory files
_COG_STORE = CognitiveMemoryStore(
    CFG.STORAGE_ROOT / CFG.STORAGE_SUBFOLDERS.get("memory", "memory") / "cognitive",
    config=CFG,
)
_CAPSULE_STORE = MemoryCapsuleStore(
    CFG.STORAGE_ROOT / CFG.STORAGE_SUBFOLDERS.get("memory", "memory") / "capsules",
    config=CFG,
)


def _build_lived_store(config: FRAMConfig) -> LivedMemoryStore | None:
    if not bool(getattr(config, "lived_memory_enabled", False)):
        return None
    return LivedMemoryStore(
        config.STORAGE_ROOT
        / config.STORAGE_SUBFOLDERS.get("memory", "memory")
        / "lived",
        target_dim=int(getattr(config, "lived_memory_target_dim", 12)),
        fractal_nodes=int(getattr(config, "lived_memory_fractal_nodes", 64)),
        scan_limit=int(getattr(config, "lived_memory_scan_limit", 5000)),
        state_decay=float(getattr(config, "lived_memory_state_decay", 0.82)),
        busy_timeout_seconds=float(
            getattr(config, "lived_memory_busy_timeout_seconds", 5.0)
        ),
    )


_LIVED_STORE: LivedMemoryStore | None = _build_lived_store(CFG)


def _get_lived_store() -> LivedMemoryStore | None:
    """Return a store bound to the active configuration's storage root.

    This also keeps test/dev config swaps isolated instead of leaking recalled
    events from the process's original storage root.
    """

    global _LIVED_STORE
    if not bool(getattr(CFG, "lived_memory_enabled", False)):
        return None
    expected_root = (
        CFG.STORAGE_ROOT / CFG.STORAGE_SUBFOLDERS.get("memory", "memory") / "lived"
    )
    if (
        _LIVED_STORE is None
        or _LIVED_STORE.root != expected_root
        or _LIVED_STORE.target_dim != int(getattr(CFG, "lived_memory_target_dim", 12))
        or _LIVED_STORE.fractal_nodes
        != int(getattr(CFG, "lived_memory_fractal_nodes", 64))
    ):
        _LIVED_STORE = _build_lived_store(CFG)
    return _LIVED_STORE


_MEMORY_VECTORIZER: Any | None = None
_MEMORY_BACKEND: str | None = None
_NEGATIVE_COOLDOWNS: Dict[str, datetime] = {}
_COOLDOWNS_LOADED = False
_COOLDOWN_WINDOW = timedelta(
    minutes=max(1, int(getattr(CFG, "negative_cue_cooldown_minutes", 10)))
)


def _cooldown_key(doc_id: str) -> str:
    """Normalize doc ids used for cooldown decisions.

    Accept either a base doc_id (e.g., `cmem:ep:<id>`) or a citation
    string (e.g., `cmem:ep:<id>:chunk0`) and normalize to the base.
    """

    doc_id = str(doc_id or "").strip()
    if not doc_id:
        return doc_id
    if ":chunk" in doc_id:
        base, suffix = doc_id.rsplit(":chunk", 1)
        if suffix.isdigit():
            return base
    return doc_id


def _cooldown_log_path() -> Path:
    return _observability_root() / "memory_sessions.jsonl"


def _rehydrate_cooldowns(reference: datetime | None = None) -> None:
    global _COOLDOWNS_LOADED
    if _COOLDOWNS_LOADED:
        return
    _COOLDOWNS_LOADED = True

    ref = reference if isinstance(reference, datetime) else datetime.now(timezone.utc)
    path = _cooldown_log_path()
    if not path.exists():
        return

    latest: Dict[str, datetime] = {}
    for event in observability.iter_jsonl(path):
        if event.get("event") != "dismiss":
            continue
        doc_id = _cooldown_key(str(event.get("session_id") or ""))
        if not doc_id:
            continue
        stamp = event.get("time") or event.get("timestamp")
        ts = _parse_datetime(stamp)
        if ts is None:
            if isinstance(stamp, str) and stamp.endswith("Z"):
                ts = _parse_datetime(stamp[:-1] + "+00:00")
        if ts is None:
            continue
        current = latest.get(doc_id)
        if current is None or ts > current:
            latest[doc_id] = ts

    if not latest:
        return

    for doc_id, ts in latest.items():
        if (ref - ts) < _COOLDOWN_WINDOW:
            _NEGATIVE_COOLDOWNS[doc_id] = ts


def _get_memory_vectorizer() -> Any | None:
    global _MEMORY_VECTORIZER, _MEMORY_BACKEND
    try:
        backend = normalize_cognitive_backend(
            getattr(CFG, "cognitive_memory_embedding_backend", "hashing")
        )
    except Exception:
        backend = "hashing"
    if _MEMORY_VECTORIZER is None or backend != _MEMORY_BACKEND:
        _MEMORY_VECTORIZER = build_cognitive_vectorizer(CFG)
        _MEMORY_BACKEND = backend
    return _MEMORY_VECTORIZER


def _encode_cognitive_text(text: str) -> tuple[list[float] | None, str | None]:
    vectorizer = _get_memory_vectorizer()
    backend = normalize_cognitive_backend(
        getattr(CFG, "cognitive_memory_embedding_backend", "hashing")
    )
    if vectorizer is None:
        return None, backend
    try:
        matrix = vectorizer.transform([text])
    except Exception:
        return None, backend
    if hasattr(matrix, "toarray"):
        arr = matrix.toarray()
    else:
        arr = np.asarray(matrix)
    arr = np.asarray(arr, dtype=float)
    if arr.ndim == 2:
        arr = arr[0]
    vec = arr.astype(float, copy=False).ravel()
    return vec.tolist(), backend


def _apply_phase_d_memory_bridge(
    query_text: str, candidates: List[Dict[str, Any]], debug: bool
) -> tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Optionally enrich cognitive-memory candidates with Phase D scores."""

    if not CFG.phase_d.enabled or not CFG.phase_d.enable_memory_bridge:
        return candidates, None
    shortlist = [{"text": candidate.get("text", "")} for candidate in candidates]
    try:
        query_embedding, episode_embeddings = (
            _get_orchestrator().get_embeddings_for_shortlist(query_text, shortlist)
        )
        if not query_embedding or not episode_embeddings:
            return candidates, None
        result = phase_d_score_batch(
            query_embedding=query_embedding,
            episode_embeddings=episode_embeddings,
            phase_d_enabled=True,
            phase_d_debug=bool(debug),
        )
    except Exception:
        return candidates, None
    for candidate, score in zip(candidates, result.get("scores") or []):
        candidate["phase_d_score"] = float(score)
    diagnostics = (result.get("diagnostics") or {}).get("phase_d") if debug else None
    return candidates, diagnostics


def _fractal_trace_scores(
    query_vector: Sequence[float] | None, limit: int
) -> List[Dict[str, Any]]:
    if getattr(CFG, "fractal_scoring_mode", "legacy") == "source_frame":
        from fram_serving.query_runner import _fractal_trace_scores as shared_scores

        return shared_scores(_COG_STORE, query_vector, limit, CFG)
    if not getattr(CFG, "fractal_enabled", False):
        return []
    if query_vector is None:
        return []
    store = _COG_STORE.fractal_trace_store()
    if store is None:
        return []
    vector = np.asarray(query_vector, dtype=float).ravel()
    if vector.size == 0:
        return []
    target_dim = getattr(store.generator, "embedding_dim", vector.size)
    if vector.size != target_dim:
        return []
    window = max(1, min(int(limit), 16))
    try:
        alpha = float(
            getattr(CFG, "fractal_blend_alpha", CFG_DEFAULTS.fractal_blend_alpha)
        )
    except Exception:
        alpha = CFG_DEFAULTS.fractal_blend_alpha
    alpha = max(0.0, min(1.0, alpha))
    try:
        downsample_target = int(
            getattr(
                CFG, "fractal_downsample_target", CFG_DEFAULTS.fractal_downsample_target
            )
        )
    except Exception:
        downsample_target = CFG_DEFAULTS.fractal_downsample_target
    if downsample_target <= 0:
        downsample_target = CFG_DEFAULTS.fractal_downsample_target
    try:
        quat_weight = float(
            getattr(CFG, "fractal_quat_weight", CFG_DEFAULTS.fractal_quat_weight)
        )
    except Exception:
        quat_weight = CFG_DEFAULTS.fractal_quat_weight
    quat_weight = max(0.0, min(1.0, quat_weight))
    quat_enabled = bool(
        getattr(CFG, "fractal_quat_influence", CFG_DEFAULTS.fractal_quat_influence)
    )
    quat_use_lambda = bool(
        getattr(CFG, "fractal_quat_use_lambda", CFG_DEFAULTS.fractal_quat_use_lambda)
    )
    projection_cache: dict[Optional[int], np.ndarray] = {}
    path_cache: dict[tuple[Optional[int], int], np.ndarray] = {}
    quat_cache: dict[tuple[Optional[int], int], np.ndarray] = {}
    entries: List[Dict[str, Any]] = []
    for trace_line, metadata in store.iter_traces():
        provenance = trace_line.provenance or {}
        proj_seed_raw = provenance.get("projection_seed")
        try:
            proj_seed = int(proj_seed_raw) if proj_seed_raw is not None else None
        except (TypeError, ValueError):
            proj_seed = None
        try:
            q6 = projection_cache[proj_seed]
        except KeyError:
            try:
                q6 = store.generator.project(vector, projection_seed=proj_seed)
            except Exception:
                continue
            projection_cache[proj_seed] = q6
        try:
            coords_full = store.generator.retrace(trace_line)
        except Exception:
            continue
        if coords_full.size == 0:
            continue
        coords, stride = downsample_path(coords_full, target=downsample_target)
        if coords.shape[0] == 0:
            continue
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
        norm_q = float(np.linalg.norm(q6))
        norm_comp = float(np.linalg.norm(composite))
        if norm_q <= 0.0 or norm_comp <= 0.0:
            continue
        cosine_score = float(np.dot(q6, composite) / (norm_q * norm_comp))
        path_key = (proj_seed, coords.shape[0])
        try:
            query_path = path_cache[path_key]
        except KeyError:
            try:
                query_path = build_query_path(q6, steps=coords.shape[0])
            except Exception:
                continue
            query_path, _ = downsample_path(query_path, target=coords.shape[0])
            path_cache[path_key] = query_path
        try:
            query_quats = quat_cache[path_key]
        except KeyError:
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
            soft_dist = soft_dtw_distance(query_path, coords, gamma=0.1, band=0.15)
            soft_score = soft_dtw_similarity(soft_dist)
        except Exception:
            soft_dist = float("inf")
            soft_score = 0.0
        arc_total = float(trace_line.nodes[-1].s_arc) if trace_line.nodes else 0.0
        preview: List[Dict[str, Any]] = []
        for node in trace_line.nodes[:window]:
            preview.append(
                {
                    "index": int(node.index),
                    "scale": node.scale,
                    "s_arc": float(node.s_arc),
                    "coord6": [round(float(val), 4) for val in node.coord6],
                }
            )
        entries.append(
            {
                "episode_id": trace_line.seed_id,
                "cosine_raw": cosine_score,
                "soft_raw": soft_score,
                "quat_raw": quat_raw,
                "quat_lambda_raw": quat_lambda_raw,
                "soft_distance": soft_dist,
                "original_nodes": int(coords_full.shape[0]),
                "downsampled_nodes": int(coords.shape[0]),
                "downsample_stride": int(stride),
                "nodes": len(trace_line.nodes),
                "arc_length": arc_total,
                "projection_seed": proj_seed,
                "metadata": metadata,
                "provenance": provenance,
                "path_preview": preview,
            }
        )
    if not entries:
        return []
    cos_array = np.array([entry["cosine_raw"] for entry in entries], dtype=float)
    soft_array = np.array([entry["soft_raw"] for entry in entries], dtype=float)
    quat_array = np.array([entry["quat_raw"] for entry in entries], dtype=float)
    quat_lambda_array = np.array(
        [entry["quat_lambda_raw"] for entry in entries], dtype=float
    )
    cos_norm = min_max_normalize(cos_array)
    soft_norm = min_max_normalize(soft_array)
    quat_norm = min_max_normalize(quat_array)
    quat_lambda_norm = min_max_normalize(quat_lambda_array)
    payloads: List[Dict[str, Any]] = []
    for entry, cos_n, soft_n, quat_n, quat_lambda_n in zip(
        entries, cos_norm, soft_norm, quat_norm, quat_lambda_norm
    ):
        base_norm = alpha * cos_n + (1.0 - alpha) * soft_n
        quat_norm_value = float(quat_lambda_n if quat_use_lambda else quat_n)
        score_norm = base_norm
        if quat_enabled and quat_weight > 0.0:
            score_norm = (1.0 - quat_weight) * base_norm + quat_weight * quat_norm_value
        base_raw = alpha * entry["cosine_raw"] + (1.0 - alpha) * entry["soft_raw"]
        quat_raw_value = float(
            entry["quat_lambda_raw"] if quat_use_lambda else entry["quat_raw"]
        )
        score_raw = base_raw
        if quat_enabled and quat_weight > 0.0:
            score_raw = (1.0 - quat_weight) * base_raw + quat_weight * quat_raw_value
        payload = {
            "episode_id": entry["episode_id"],
            "score": float(score_norm),
            "score_raw": float(score_raw),
            "cosine": float(entry["cosine_raw"]),
            "cosine_norm": float(cos_n),
            "soft_dtw": float(entry["soft_raw"]),
            "soft_dtw_norm": float(soft_n),
            "quat_raw": float(entry["quat_raw"]),
            "quat_norm": float(quat_n),
            "quat_lambda_raw": float(entry["quat_lambda_raw"]),
            "quat_lambda_norm": float(quat_lambda_n),
            "soft_dtw_distance": float(entry["soft_distance"]),
            "original_nodes": entry["original_nodes"],
            "downsampled_nodes": entry["downsampled_nodes"],
            "downsample_stride": entry["downsample_stride"],
            "nodes": int(entry["nodes"]),
            "arc_length": float(entry["arc_length"]),
            "projection_seed": entry["projection_seed"],
            "metadata": entry["metadata"],
            "provenance": entry["provenance"],
            "path_preview": entry["path_preview"],
            "alpha": alpha,
            "normalization": "min_max",
            "score_components": {
                "cosine_norm": float(cos_n),
                "soft_dtw_norm": float(soft_n),
                "quat_norm": float(quat_n),
                "quat_lambda_norm": float(quat_lambda_n),
                "quat_weight": float(quat_weight),
                "quat_enabled": bool(quat_enabled),
                "quat_use_lambda": bool(quat_use_lambda),
                "score_base": float(base_norm),
                "score_raw_base": float(base_raw),
                "alpha": alpha,
            },
        }
        payloads.append(payload)
    payloads.sort(key=lambda item: item["score"], reverse=True)
    return payloads[:limit]


def _fractal_chunk_candidates(meta: Dict[str, Any] | None) -> List[str]:
    if not meta:
        return []
    candidates: List[str] = []
    citations = meta.get("citations")
    if isinstance(citations, (list, tuple, set)):
        candidates.extend(str(entry) for entry in citations if entry)
    episode_meta = meta.get("episode_metadata")
    if isinstance(episode_meta, dict):
        hierarchy = episode_meta.get("hierarchy_scales")
        if isinstance(hierarchy, list):
            for item in hierarchy:
                if not isinstance(item, dict):
                    continue
                ref = item.get("id") or item.get("ref") or item.get("segment_id")
                scale = item.get("scale")
                if ref:
                    label = f"{scale}:{ref}" if scale else str(ref)
                    candidates.append(label)
    return candidates


def _fractal_choose_ref(refs: List[str], index: int) -> str | None:
    if not refs:
        return None
    return refs[index % len(refs)]


def _fractal_replay_payloads(
    scores: List[Dict[str, Any]], max_nodes: int = 24
) -> List[Dict[str, Any]]:
    if not getattr(CFG, "fractal_enabled", False):
        return []
    store = _COG_STORE.fractal_trace_store()
    if store is None:
        return []
    payloads: List[Dict[str, Any]] = []
    for item in scores:
        episode_id = item.get("episode_id")
        if not episode_id:
            continue
        bundle = store.load_trace(str(episode_id))
        if bundle is None:
            if not _COG_STORE.ensure_fractal_trace(str(episode_id)):
                continue
            bundle = store.load_trace(str(episode_id))
        if bundle is None:
            continue
        trace_line, metadata = bundle
        refs = _fractal_chunk_candidates(metadata)
        nodes_payload: List[Dict[str, Any]] = []
        for node in trace_line.nodes[:max_nodes]:
            raw_q = node.q
            if isinstance(raw_q, dict):
                q_payload = {
                    "w": float(raw_q.get("w", DEFAULT_QUATERNION[0])),
                    "x": float(raw_q.get("x", DEFAULT_QUATERNION[1])),
                    "y": float(raw_q.get("y", DEFAULT_QUATERNION[2])),
                    "z": float(raw_q.get("z", DEFAULT_QUATERNION[3])),
                }
            elif isinstance(raw_q, (list, tuple)) and len(raw_q) == 4:
                q_payload = {
                    "w": float(raw_q[0]),
                    "x": float(raw_q[1]),
                    "y": float(raw_q[2]),
                    "z": float(raw_q[3]),
                }
            else:
                q_payload = {
                    "w": DEFAULT_QUATERNION[0],
                    "x": DEFAULT_QUATERNION[1],
                    "y": DEFAULT_QUATERNION[2],
                    "z": DEFAULT_QUATERNION[3],
                }
            raw_lambda = node.lambda_value
            try:
                lambda_value = (
                    float(raw_lambda) if raw_lambda is not None else DEFAULT_LAMBDA
                )
            except (TypeError, ValueError):
                lambda_value = DEFAULT_LAMBDA
            if not (0.0 < lambda_value < 1.0):
                lambda_value = DEFAULT_LAMBDA
            entry: Dict[str, Any] = {
                "index": int(node.index),
                "scale": node.scale,
                "s_arc": float(node.s_arc),
                "coord6": [round(float(val), 4) for val in node.coord6],
                "q": q_payload,
                "lambda": lambda_value,
            }
            chunk_ref = _fractal_choose_ref(refs, node.index)
            if chunk_ref:
                entry["chunk_ref"] = chunk_ref
            nodes_payload.append(entry)
        payloads.append(
            {
                "episode_id": episode_id,
                "score": item.get("score"),
                "cosine": item.get("cosine"),
                "soft_dtw": item.get("soft_dtw"),
                "score_components": item.get("score_components"),
                "alpha": item.get("alpha"),
                "original_nodes": item.get("original_nodes"),
                "downsampled_nodes": item.get("downsampled_nodes"),
                "downsample_stride": item.get("downsample_stride"),
                "citations": metadata.get("citations"),
                "trace_id": metadata.get("trace_id"),
                "seed_hash": (trace_line.provenance or {}).get("seed_hash"),
                "provenance": trace_line.provenance,
                "nodes": nodes_payload,
            }
        )
    return payloads


def _fractal_trace_evidence() -> Optional[Dict[str, Any]]:
    store = _COG_STORE.fractal_trace_store()
    if store is None:
        return None
    try:
        storage_root = store.storage_root.resolve()
    except Exception:
        storage_root = store.storage_root
    available_ids = store.available_ids()
    evidence: Dict[str, Any] = {
        "storage_root": str(storage_root),
        "available_ids": available_ids,
    }
    try:
        candidates = list(store.storage_root.glob("*.json"))
    except Exception:
        candidates = []
    if not candidates:
        return evidence
    latest_path = max(candidates, key=lambda path: path.stat().st_mtime)
    evidence.update(
        {
            "trace_id": latest_path.stem,
            "trace_path": str(latest_path.resolve()),
        }
    )
    raw = store.load_raw(latest_path.stem)
    if isinstance(raw, dict):
        evidence["trace_version"] = raw.get("trace_version")
        nodes = raw.get("nodes") or []
        if nodes and isinstance(nodes[0], dict):
            evidence["node0_quaternion"] = nodes[0].get("q")
            evidence["node0_lambda"] = nodes[0].get("lambda")
    return evidence


def _observability_root() -> Path:
    return CFG.STORAGE_ROOT / CFG.STORAGE_SUBFOLDERS.get(
        "observability", "observability"
    )


def _continuity_witness_root() -> Path:
    return _observability_root() / "continuity"


def _count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def _storage_summary() -> Dict[str, Any]:
    root = CFG.STORAGE_ROOT
    active_path = root / "active" / "memory_active.jsonl"
    archive_path = root / "archive" / "memory_archive.jsonl"

    def _read_json(path: Path) -> Optional[Dict[str, Any]]:
        if not path.exists():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return value if isinstance(value, dict) else None

    def _file_summary(path: Path) -> Dict[str, Any]:
        size = path.stat().st_size if path.exists() else 0
        return {
            "path": str(path),
            "size_bytes": size,
            "size_mb": size / (1024 * 1024),
            "count": _count_jsonl(path),
        }

    snapshots_dir = root / "snapshots"
    return {
        "active": _file_summary(active_path),
        "archive": _file_summary(archive_path),
        "last_compaction": _read_json(
            root / "observability" / "compaction_latest.json"
        ),
        "last_archive": _read_json(root / "observability" / "archive_latest.json"),
        "snapshots": {
            "dir": str(snapshots_dir),
            "latest": _read_json(snapshots_dir / "snapshot_latest.json"),
        },
        "connectors": _read_json(root / "observability" / "connectors_latest.json"),
    }


def _trace_dir() -> Path:
    return CFG.STORAGE_ROOT / CFG.STORAGE_SUBFOLDERS.get("traces", "traces")


def _get_trace_logger() -> observability.TraceLogWriter:
    current_dir = _trace_dir()
    current_dir.mkdir(parents=True, exist_ok=True)
    return observability.TraceLogWriter(current_dir)


MEMORY_UI_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>FRAM Memory Sessions</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 2rem; }
    h1 { margin-bottom: 0.5rem; }
    section { margin-bottom: 2rem; }
    label { display: block; margin-top: 0.5rem; }
    input, textarea { width: 100%; padding: 0.4rem; }
    button { margin-top: 0.6rem; padding: 0.5rem 1rem; }
    table { border-collapse: collapse; width: 100%; margin-top: 1rem; }
    th, td { border: 1px solid #ccc; padding: 0.4rem; text-align: left; }
    .status { font-weight: bold; }
    .log { background: #f7f7f7; padding: 0.5rem; border: 1px solid #ccc; height: 10rem; overflow: auto; }
  </style>
</head>
<body>
  <h1>FRAM Working-Memory Sessions</h1>
  <p>Manage session lifecycle without invoking tools manually. Actions call the REST endpoints already exposed by the server.</p>

  <p><strong>Cognitive Seeding:</strong> <span id="cog-state">loading...</span></p>

  <section>
    <h2>Sessions</h2>
    <button onclick="loadSessions()">Refresh Sessions</button>
    <table id="sessions-table">
      <thead>
        <tr><th>Session</th><th>Status</th><th>Entries</th><th>Updated</th></tr>
      </thead>
      <tbody></tbody>
    </table>
  </section>

  <section>
    <h2>Create / Load Session</h2>
    <label>Session ID (blank = auto):<input id="create-id" placeholder="optional" /></label>
    <label>Metadata JSON:<textarea id="create-meta" rows="3" placeholder="{
  &quot;owner&quot;: &quot;ui&quot;
}"></textarea></label>
    <button onclick="createSession()">Create or Load</button>
  </section>

  <section>
    <h2>Append Entry</h2>
    <label>Session ID:<input id="append-id" /></label>
    <label>Text:<textarea id="append-text" rows="3"></textarea></label>
    <button onclick="appendEntry()">Append</button>
  </section>

  <section>
    <h2>Lifecycle Control</h2>
    <label>Session ID:<input id="control-id" /></label>
    <label>Action:
      <select id="control-action">
        <option value="resume">Resume</option>
        <option value="pause">Pause</option>
        <option value="end">End</option>
      </select>
    </label>
    <button onclick="controlSession()">Apply</button>
  </section>

  <section>
    <h2>Clear Session</h2>
    <label>Session ID:<input id="clear-id" /></label>
    <button onclick="clearSession()">Clear</button>
  </section>

  <section>
    <h2>Session Detail</h2>
    <label>Session ID:<input id="detail-id" /></label>
    <button onclick="showDetail()">Fetch Detail</button>
    <pre id="detail-output" class="log"></pre>
  </section>

  <section>
    <h2>Log</h2>
    <pre id="log" class="log"></pre>
  </section>

  <section>
    <h2>Summary</h2>
    <button onclick="loadSummary()">Refresh Summary</button>
    <pre id="summary-output" class="log"></pre>
  </section>

  <section>
    <h2>Cognitive Seeds</h2>
    <label>Show top N:
      <input id="cog-topn" type="number" min="1" max="10" value="3" style="width:4rem" />
    </label>
    <button onclick="loadLatestTrace()">Load Latest Trace</button>
    <pre id="cog-output" class="log"></pre>
  </section>

  <script>
    async function loadSessions() {
      try {
        const resp = await fetch('/memory');
        if (!resp.ok) throw new Error(await resp.text());
        const data = await resp.json();
        const tbody = document.querySelector('#sessions-table tbody');
        tbody.innerHTML = '';
        for (const session of data.sessions || []) {
          const row = document.createElement('tr');
          row.innerHTML = `<td>${session.id}</td><td class="status">${session.status}</td><td>${session.entry_count ?? '-'}</td><td>${session.updated ?? '-'}</td>`;
          tbody.appendChild(row);
        }
        log('Loaded sessions.');
      } catch (err) {
        log('Error loading sessions: ' + err);
      }
    }

    async function createSession() {
      const sessionId = document.getElementById('create-id').value.trim() || null;
      const metaRaw = document.getElementById('create-meta').value.trim();
      let metadata = undefined;
      if (metaRaw) {
        try { metadata = JSON.parse(metaRaw); }
        catch (err) { return log('Invalid metadata JSON: ' + err); }
      }
      try {
        const resp = await fetch('/memory', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: sessionId, metadata })
        });
        if (!resp.ok) throw new Error(await resp.text());
        const data = await resp.json();
        log('Session ready: ' + JSON.stringify(data.session));
        loadSessions();
      } catch (err) {
        log('Create failed: ' + err);
      }
    }

    async function appendEntry() {
      const sessionId = document.getElementById('append-id').value.trim();
      const text = document.getElementById('append-text').value.trim();
      if (!sessionId || !text) return log('Session and text required.');
      try {
        const resp = await fetch(`/memory/${encodeURIComponent(sessionId)}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text })
        });
        if (!resp.ok) throw new Error(await resp.text());
        log('Entry appended.');
        loadSessions();
      } catch (err) {
        log('Append failed: ' + err);
      }
    }

    async function controlSession() {
      const sessionId = document.getElementById('control-id').value.trim();
      const action = document.getElementById('control-action').value;
      if (!sessionId) return log('Session required.');
      try {
        const resp = await fetch(`/memory/${encodeURIComponent(sessionId)}/control`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action })
        });
        if (!resp.ok) throw new Error(await resp.text());
        log(`Control applied (${action}).`);
        loadSessions();
      } catch (err) {
        log('Control failed: ' + err);
      }
    }

    async function clearSession() {
      const sessionId = document.getElementById('clear-id').value.trim();
      if (!sessionId) return log('Session required.');
      try {
        const resp = await fetch(`/memory/${encodeURIComponent(sessionId)}`, { method: 'DELETE' });
        if (!resp.ok) throw new Error(await resp.text());
        log('Session cleared.');
        loadSessions();
      } catch (err) {
        log('Clear failed: ' + err);
      }
    }

    async function showDetail() {
      const sessionId = document.getElementById('detail-id').value.trim();
      if (!sessionId) return log('Session required.');
      try {
        const resp = await fetch(`/memory/${encodeURIComponent(sessionId)}`);
        if (!resp.ok) throw new Error(await resp.text());
        const data = await resp.json();
        document.getElementById('detail-output').textContent = JSON.stringify(data, null, 2);
        log('Fetched session detail.');
      } catch (err) {
        log('Detail failed: ' + err);
      }
    }

    function log(message) {
      const node = document.getElementById('log');
      const timestamp = new Date().toISOString();
      node.textContent = `[${timestamp}] ${message}
` + node.textContent;
    }

    async function loadSummary() {
      try {
        const resp = await fetch('/observability/memory/summary?window=10');
        if (!resp.ok) throw new Error(await resp.text());
        const data = await resp.json();
        document.getElementById('summary-output').textContent = JSON.stringify(data, null, 2);
        log('Loaded memory summary.');
      } catch (err) {
        log('Error loading summary: ' + err);
      }
    }

    async function loadLatestTrace() {
      try {
        const resp = await fetch('/observability/traces?limit=1');
        if (!resp.ok) throw new Error(await resp.text());
        const data = await resp.json();
        const traces = data.traces || [];
        if (!traces.length) {
          document.getElementById('cog-output').textContent = 'No traces available.';
          return log('No traces.');
        }
        const trace = traces[0] || {};
        const cog = (trace.trace || {}).cognitive_memory || {};
        const selected = cog.selected || [];
        const budgetRaw = cog.token_budget;
        const budget = (cog.token_budget_unlimited || budgetRaw == null || budgetRaw <= 0)
          ? 'unlimited'
          : budgetRaw;
        const nRaw = document.getElementById('cog-topn').value;
        let n = parseInt(nRaw || '3', 10);
        if (!Number.isFinite(n) || n < 1) n = 3;
        const preview = selected.slice(0, n);
        const out = { available: (cog.available ?? selected.length), selected: preview, token_budget: budget };
        document.getElementById('cog-output').textContent = JSON.stringify(out, null, 2);
        log('Loaded latest trace cognitive seeds.');
      } catch (err) {
        log('Error loading latest trace: ' + err);
      }
    }

    async function loadConfig() {
      try {
        const resp = await fetch('/config');
        if (!resp.ok) throw new Error(await resp.text());
        const cfg = await resp.json();
        const k = cfg.cognitive_memory_k ?? 0;
        const budgetRaw = cfg.cognitive_memory_token_budget;
        const budget = (budgetRaw == null || budgetRaw <= 0) ? 'unlimited' : budgetRaw;
        const traceK = cfg.cognitive_memory_trace_k ?? '-';
        const state = (k > 0) ? `enabled (k=${k}, budget=${budget}, trace_k=${traceK})` : 'disabled';
        document.getElementById('cog-state').textContent = state;
      } catch (err) {
        document.getElementById('cog-state').textContent = 'error';
        log('Error loading /config: ' + err);
      }
    }

    loadSessions();
    loadConfig();
  </script>
</body>
</html>"""


OBSERVABILITY_UI_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>FRAM Observability</title>
  <style>
    :root {
      --bg: #f6f2ea;
      --card: #ffffff;
      --ink: #1b1b1b;
      --muted: #5b5b5b;
      --accent: #1f6feb;
      --accent-soft: #e4efff;
      --border: #d9d4c8;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Space Grotesk", "Trebuchet MS", sans-serif;
      color: var(--ink);
      background: linear-gradient(120deg, #f7f1e3 0%, #e9f1ff 100%);
      min-height: 100vh;
      padding: 2rem;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      margin-bottom: 1.5rem;
    }
    h1 {
      margin: 0;
      font-size: 1.8rem;
      letter-spacing: 0.02em;
    }
    .controls {
      display: flex;
      gap: 0.75rem;
      align-items: center;
      flex-wrap: wrap;
    }
    button {
      border: 1px solid var(--accent);
      background: var(--accent);
      color: #fff;
      padding: 0.5rem 1rem;
      border-radius: 999px;
      font-weight: 600;
      cursor: pointer;
    }
    button.secondary {
      background: var(--accent-soft);
      color: var(--accent);
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 1rem;
    }
    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 1rem;
      box-shadow: 0 6px 20px rgba(31, 111, 235, 0.08);
    }
    .card h2 {
      margin: 0 0 0.5rem 0;
      font-size: 1rem;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }
    pre {
      background: #f2f1ec;
      border-radius: 10px;
      padding: 0.75rem;
      margin: 0;
      max-height: 240px;
      overflow: auto;
      font-family: "IBM Plex Mono", "Consolas", monospace;
      font-size: 0.85rem;
    }
    .status-line {
      font-weight: 600;
      margin-bottom: 0.5rem;
    }
    .muted { color: var(--muted); }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>FRAM Observability</h1>
      <div class="muted">Quick view for traces, memory, and metrics.</div>
    </div>
    <div class="controls">
      <button onclick="refreshAll()">Refresh All</button>
      <button class="secondary" onclick="toggleAuto()">Auto Refresh</button>
      <span id="auto-state" class="muted">Auto: off</span>
    </div>
  </header>

  <section class="grid">
    <div class="card">
      <h2>Health</h2>
      <div class="status-line" id="health-line">loading...</div>
      <pre id="health-json"></pre>
    </div>
    <div class="card">
      <h2>Metrics</h2>
      <pre id="metrics-json"></pre>
    </div>
    <div class="card">
      <h2>Observability Summary</h2>
      <pre id="summary-json"></pre>
    </div>
    <div class="card">
      <h2>Memory Summary</h2>
      <pre id="memory-json"></pre>
    </div>
    <div class="card">
      <h2>Recall Report</h2>
      <pre id="recall-json"></pre>
    </div>
    <div class="card">
      <h2>Experiments</h2>
      <pre id="experiments-digest"></pre>
      <pre id="experiments-json"></pre>
    </div>
    <div class="card">
      <h2>Experiment Digest</h2>
      <div class="status-line" id="digest-path">no digest yet</div>
      <pre id="digest-json"></pre>
    </div>
    <div class="card">
      <h2>Latest Traces</h2>
      <pre id="traces-json"></pre>
    </div>
  </section>

  <script>
    let autoTimer = null;

    async function fetchJson(url) {
      const resp = await fetch(url);
      if (!resp.ok) {
        throw new Error(await resp.text());
      }
      return await resp.json();
    }

    async function loadHealth() {
      const data = await fetchJson('/health');
      document.getElementById('health-line').textContent = `${data.status} (${data.service || 'fram'})`;
      document.getElementById('health-json').textContent = JSON.stringify(data, null, 2);
    }

    async function loadMetrics() {
      const data = await fetchJson('/metrics');
      document.getElementById('metrics-json').textContent = JSON.stringify(data, null, 2);
    }

    async function loadSummary() {
      const data = await fetchJson('/observability/summary?limit=10');
      document.getElementById('summary-json').textContent = JSON.stringify(data, null, 2);
    }

    async function loadMemorySummary() {
      const data = await fetchJson('/observability/memory/summary?window=10');
      document.getElementById('memory-json').textContent = JSON.stringify(data, null, 2);
    }

    async function loadRecall() {
      const data = await fetchJson('/observability/recall_report');
      document.getElementById('recall-json').textContent = JSON.stringify(data, null, 2);
    }

    async function loadExperiments() {
      const data = await fetchJson('/observability/experiments?limit=10');
      const items = data.experiments || [];
      const digest = items.length
        ? items.slice(0, 5).map((item) => {
            const stamp = item.time || '';
            const title = item.title || 'untitled';
            const decision = item.decision || 'n/a';
            return `${stamp} | ${title} | decision: ${decision}`;
          }).join('\n')
        : 'No experiments logged yet.';
      document.getElementById('experiments-digest').textContent = digest;
      document.getElementById('experiments-json').textContent = JSON.stringify(data, null, 2);
    }

    async function loadDigest() {
      const data = await fetchJson('/observability/experiment_digest?max_lines=120');
      if (!data.available) {
        document.getElementById('digest-path').textContent = 'no digest yet';
        document.getElementById('digest-json').textContent = '';
        return;
      }
      document.getElementById('digest-path').textContent = `${data.updated} • ${data.path}`;
      document.getElementById('digest-json').textContent = data.content || '';
    }

    async function loadTraces() {
      const data = await fetchJson('/observability/traces?limit=5');
      document.getElementById('traces-json').textContent = JSON.stringify(data, null, 2);
    }

    async function refreshAll() {
      try {
        await Promise.all([
          loadHealth(),
          loadMetrics(),
          loadSummary(),
          loadMemorySummary(),
          loadRecall(),
          loadExperiments(),
          loadDigest(),
          loadTraces(),
        ]);
      } catch (err) {
        document.getElementById('health-line').textContent = 'error';
        document.getElementById('health-json').textContent = String(err);
      }
    }

    function toggleAuto() {
      if (autoTimer) {
        clearInterval(autoTimer);
        autoTimer = null;
        document.getElementById('auto-state').textContent = 'Auto: off';
        return;
      }
      autoTimer = setInterval(refreshAll, 8000);
      document.getElementById('auto-state').textContent = 'Auto: on (8s)';
      refreshAll();
    }

    refreshAll();
  </script>
</body>
</html>"""


def _log_memory_event(session_id: str, event: str, **fields: Any) -> None:
    payload = {"session_id": session_id, "event": event}
    for key, value in fields.items():
        if value is not None:
            payload[key] = value
    observability.log_memory_event(_observability_root(), payload)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure storage directories exist at startup
    root = CFG.STORAGE_ROOT
    try:
        root.mkdir(parents=True, exist_ok=True)
        for sub in CFG.STORAGE_SUBFOLDERS.values():
            (root / sub).mkdir(parents=True, exist_ok=True)
        _ensure_doc_cache()
    except Exception as e:
        raise RuntimeError(f"Failed to prepare storage directories: {e}")
    try:
        async with mcp.session_manager.run():
            yield
    except RuntimeError as exc:
        if "run() can only be called once" not in str(exc):
            raise
        # TestClient can reuse the global MCP session manager in-process;
        # skip MCP startup on subsequent lifespans.
        yield


app = FastAPI(title="FRAM v2.2 MCP Server", lifespan=lifespan)
api_router = APIRouter()

_allowed_origins_raw = os.getenv("ALLOWED_ORIGINS", "https://chat.openai.com")
_ALLOWED_ORIGINS = [
    origin.strip() for origin in _allowed_origins_raw.split(",") if origin.strip()
]
if not _ALLOWED_ORIGINS:
    _ALLOWED_ORIGINS = ["https://chat.openai.com"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Mcp-Session-Id"],
)

_mcp_sse_app = mcp.sse_app()
_mcp_streamable_http_app = mcp.streamable_http_app()


async def _mcp_compat_app(scope, receive, send):
    if scope.get("type") != "http":
        await _mcp_streamable_http_app(scope, receive, send)
        return

    root_path = scope.get("root_path") or ""
    path = scope.get("path") or ""
    route_path = (
        path[len(root_path) :] if root_path and path.startswith(root_path) else path
    )
    if route_path.startswith("/sse") or route_path.startswith("/messages"):
        await _mcp_sse_app(scope, receive, send)
        return

    await _mcp_streamable_http_app(scope, receive, send)


app.mount("/mcp", _mcp_compat_app)

# --- Minimal in-memory corpus cache for /query ---
_DOC_CACHE: Optional[Dict] = None  # built on first /query


def _tokenize(text: str) -> List[str]:
    return tokenize_text(text)


def _build_vocab(chunks: Sequence[Sequence[str]]) -> Dict[str, int]:
    return _pipeline_build_vocab(chunks)


def _load_and_index_corpus() -> Dict[str, Any]:
    cache = _get_orchestrator().ensure_corpus()
    return corpus_cache_to_dict(cache)


def _ensure_doc_cache() -> Dict[str, Any]:
    global _DOC_CACHE
    if _DOC_CACHE is None:
        cache = _load_and_index_corpus()
        chunk_vecs = cache.get("chunk_vecs")
        if chunk_vecs is not None and not isinstance(chunk_vecs, np.ndarray):
            chunk_vecs = np.asarray(chunk_vecs)
            cache["chunk_vecs"] = chunk_vecs
        vocab = cache.get("vocab", {})
        vec_dim = (
            int(chunk_vecs.shape[1])
            if isinstance(chunk_vecs, np.ndarray) and chunk_vecs.ndim == 2
            else 0
        )
        vocab_size = len(vocab) if hasattr(vocab, "__len__") else 0
        if vec_dim and vocab_size and vec_dim != vocab_size:
            cache.setdefault("embedding_backend", "hashing")
            cache.setdefault("embedder", _pipeline_make_hashing_vectorizer(CFG))
        _DOC_CACHE = cache
    return _DOC_CACHE


def _store_prob(
    query_id: str,
    prob_value: Optional[float] = None,
    *,
    prob: Optional[float] = None,
    tau1: Optional[float] = None,
    tau2: Optional[float] = None,
    domain: Optional[str] = None,
    task: Optional[str] = None,
    source: Optional[str] = None,
    temperature: Optional[float] = None,
) -> None:
    prob_final = prob if prob is not None else prob_value
    if prob_final is None:
        raise ValueError("prob is required")
    tau1_final = float(tau1) if tau1 is not None else float(CFG.tau1)
    tau2_final = float(tau2) if tau2 is not None else float(CFG.tau2)
    if tau2_final >= tau1_final:
        tau2_final = max(1e-6, tau1_final - 1e-6)
    if query_id in _PROB_CACHE:
        del _PROB_CACHE[query_id]
    payload: Dict[str, Any] = {
        "prob": float(prob_final),
        "tau1": tau1_final,
        "tau2": tau2_final,
    }
    if domain:
        payload["domain"] = str(domain)
    if task:
        payload["task"] = str(task)
    if source:
        payload["source"] = str(source)
    if temperature is not None:
        payload["temperature"] = float(temperature)
    _PROB_CACHE[query_id] = payload
    while len(_PROB_CACHE) > _PROB_CACHE_MAX:
        _PROB_CACHE.popitem(last=False)


def _pop_prob(query_id: str) -> Optional[Dict[str, Any]]:
    return _PROB_CACHE.pop(query_id, None)


class QueryRequest(BaseModel):
    text: str
    as_of: Optional[str] = None
    version_id: Optional[str] = None
    budget_reads: Optional[int] = Field(
        default=None, validation_alias=AliasChoices("budget_reads", "budget")
    )
    memory_session: Optional[str] = None
    domain: Optional[str] = None
    task: Optional[str] = None


class ExpandSearchRequest(BaseModel):
    query: str
    situation: Optional[Dict[str, Any]] = None
    max_expansions: int = 10


class ExpandSearchResponse(BaseModel):
    expanded_query: str
    terms: List[str]
    entities: List[str]
    aliases: List[str]
    notes: List[str]
    threshold: float


class RankCandidate(BaseModel):
    id: str
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RankRelevanceRequest(BaseModel):
    query: str
    situation: Optional[Dict[str, Any]] = None
    candidates: List[RankCandidate]


class RankRelevanceScore(BaseModel):
    id: str
    score: float
    breakdown: Dict[str, float]
    details: Dict[str, Any] = Field(default_factory=dict)


class RankRelevanceResponse(BaseModel):
    scores: List[RankRelevanceScore]
    phase_d_scores: Optional[List[float]] = None
    phase_d_diagnostics: Optional[Dict[str, Any]] = None


class BeliefConflict(BaseModel):
    belief_id: str
    claim: str
    evidence_for: List[str]
    evidence_against: List[str]
    status: Literal["pending", "resolved"]


class ConflictsResponse(BaseModel):
    conflicts: List[BeliefConflict]


class FractalEventEntry(BaseModel):
    query_id: Optional[str] = None
    timestamp: Optional[str] = None
    requested: int = 0
    returned: int = 0
    backend: Optional[str] = None
    alpha: Optional[float] = None
    top: List[Dict[str, Any]] = Field(default_factory=list)


class FractalTopEpisode(BaseModel):
    episode_id: str
    count: int


class FractalRecallSummary(BaseModel):
    events: int
    hits: int
    hit_rate: float
    recent: List[FractalEventEntry]
    top_episodes: List[FractalTopEpisode]
    logistic_state_color: Optional[str] = None
    logistic_alpha_preview: Optional[float] = None
    quaternion_similarity_avg: Optional[float] = None


class PhaseDRecallBlock(BaseModel):
    enabled: bool
    debug: bool = False
    alpha_t: Optional[float] = None
    alpha_color: Optional[str] = None
    quat_avg: Optional[float] = None


class PhaseDMemorySummary(BaseModel):
    enabled: bool
    debug: bool = False
    scored: int = 0
    alpha_t: Optional[float] = None
    alpha_color: Optional[str] = None
    quat_avg: Optional[float] = None
    events: int = 0
    latest: Optional[Dict[str, Any]] = None
    stats: Optional[Dict[str, Any]] = None
    retention_snapshot: Optional[List[Dict[str, Any]]] = None
    decay_snapshot: Optional[List[Dict[str, Any]]] = None


class CognitiveRecallSummary(BaseModel):
    invocations: int = 0
    selected: int = 0
    phase_d_memory: Optional[PhaseDMemorySummary] = None


class RecallReport(BaseModel):
    since: Optional[str] = None
    invocations: int
    seeds: List[Dict[str, Any]]
    misses: List[Dict[str, Any]]
    conflicts: List[Dict[str, Any]]
    hit_rate: float
    time_sensitivity: Dict[str, int]
    fractal: Optional[FractalRecallSummary] = None
    phase_d: Optional[PhaseDRecallBlock] = None
    phase_d_memory: Optional[PhaseDMemorySummary] = None
    cognitive: Optional[CognitiveRecallSummary] = None


class PhaseDScoreRequest(BaseModel):
    query_embedding: List[float]
    episode_embeddings: List[List[float]]
    enabled: Optional[bool] = None
    debug: Optional[bool] = None


class PhaseDScoreResponse(BaseModel):
    scores: List[float]
    diagnostics: Dict[str, Any]


class MemoryDismissRequest(BaseModel):
    doc_id: str
    reason: Optional[str] = None


class MemoryEntryRequest(BaseModel):
    text: str
    metadata: Optional[Dict[str, Any]] = None
    idempotency_key: Optional[str] = None


class MemorySessionCreateRequest(BaseModel):
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class MemorySessionControlRequest(BaseModel):
    action: Literal["resume", "continue", "pause", "end"]

    def normalized_action(self) -> str:
        value = self.action.lower()
        return "resume" if value == "continue" else value


class LabelRequest(BaseModel):
    query_id: str
    label: int

    def normalized_label(self) -> int:
        value = int(self.label)
        if value not in (0, 1):
            raise ValueError("label must be 0 or 1")
        return value


MemoryEntryRequest.model_rebuild()


class CognitiveBeliefRequest(BaseModel):
    text: str
    source_episode: Optional[str] = None
    confidence: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class CognitiveLinkRequest(BaseModel):
    src_id: str
    dst_id: str
    link_type: str
    metadata: Optional[Dict[str, Any]] = None


class CognitiveConstraintRequest(BaseModel):
    text: str
    scope: Literal["global", "personal", "session"] = "global"
    kind: Literal["forbid", "require", "caveat"] = "forbid"
    status: Literal["active", "disabled", "retracted"] = "active"
    session_id: Optional[str] = None
    principal: Optional[str] = None
    supersedes_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    source_episode: Optional[str] = None


# (startup handled via lifespan)


def _get_orchestrator() -> QueryOrchestrator:
    global _ORCHESTRATOR
    if _ORCHESTRATOR is None:
        _ORCHESTRATOR = QueryOrchestrator(
            config=CFG,
            tracer=_get_trace_logger(),
            data_root=DATA_ROOT,
            reranker=RERANKER,
        )
    return _ORCHESTRATOR


def _truncate_answer(text: str, limit: int = 1200) -> str:
    if len(text) <= limit:
        return text
    truncated = text[:limit]
    cut = -1
    for ch in ".?!":
        idx = truncated.rfind(ch)
        if idx != -1:
            cut = max(cut, idx + 1)
    if cut <= 0:
        newline_idx = truncated.rfind("\n")
        if newline_idx != -1:
            cut = newline_idx
    if cut <= 0:
        space_idx = truncated.rfind(" ")
        if space_idx != -1:
            cut = space_idx
    if cut <= 0:
        cut = limit
    trimmed = text[:cut].rstrip()
    if not trimmed:
        trimmed = text[:limit].rstrip()
    return trimmed + "..."


def _assemble_answer(chunks: Sequence[Dict], limit: int = 1200) -> str:
    texts = [chunk.get("text", "") for chunk in chunks if chunk.get("text")]
    if not texts:
        return ""
    combined = "\n\n".join(texts)
    return _truncate_answer(combined, limit)


def _tokenize_for_semantics(text: str) -> List[str]:
    if not text:
        return []
    return [token.lower() for token in tokenize_text(text) if token]


def _unique_preserve(items: Sequence[str]) -> List[str]:
    seen: set[str] = set()
    ordered: List[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def _resolve_time_sensitivity(task: str | None, domain: str | None) -> str:
    if task:
        sens = CFG.time_sensitivity_task.get(task)
        if sens:
            return sens.lower()
    if domain:
        sens = CFG.time_sensitivity_domain.get(domain)
        if sens:
            return sens.lower()
    return "low"


def _time_boost(age_hours: float, sensitivity: str) -> float:
    if age_hours <= 0:
        return 0.5 if sensitivity in {"medium", "low"} else 1.0
    half_life = {
        "high": 12.0,
        "medium": 48.0,
        "low": 168.0,
    }.get(sensitivity, 168.0)
    bonus = max(0.0, 1.0 - age_hours / half_life)
    if sensitivity == "medium":
        bonus *= 0.5
    if sensitivity == "low":
        bonus *= 0.25
    return bonus


def _parse_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            return None
    return None


def _experiment_decision_from_text(text: str) -> str:
    if not text:
        return ""
    for line in str(text).splitlines():
        if line.lower().startswith("decision:"):
            return line.split(":", 1)[1].strip()
    return ""


def _extract_experiment_record(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    meta = record.get("metadata") or {}
    kind = str(meta.get("kind") or "").lower()
    tags: List[str] = []
    raw_tags = meta.get("tags")
    if isinstance(raw_tags, (list, tuple, set)):
        tags = [str(tag).lower() for tag in raw_tags if tag]
    if kind != "experiment" and "experiment" not in tags:
        return None
    decision = str(meta.get("decision") or "")
    if not decision:
        decision = _experiment_decision_from_text(record.get("text") or "")
    return {
        "id": record.get("id"),
        "run_id": meta.get("run_id"),
        "title": str(meta.get("title") or ""),
        "decision": decision,
        "tags": tags,
        "time": record.get("time") or record.get("created_at"),
    }


def _collect_experiments(
    *, session_id: Optional[str] = None, tag: Optional[str] = None
) -> List[Dict[str, Any]]:
    tag_value = tag.lower() if tag else None
    entries: List[Dict[str, Any]] = []
    for record in _COG_STORE._iter_belief_records():
        if session_id and str(record.get("session_id") or "") != session_id:
            continue
        experiment = _extract_experiment_record(record)
        if not experiment:
            continue
        if tag_value and tag_value not in experiment.get("tags", []):
            continue
        entries.append(experiment)
    entries.sort(
        key=lambda item: _parse_datetime(item.get("time"))
        or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return entries


def _summarise_experiments(
    entries: List[Dict[str, Any]], *, limit: int
) -> Dict[str, Any]:
    tag_counts: Counter[str] = Counter()
    decision_count = 0
    latest_time: Optional[datetime] = None
    for entry in entries:
        for tag in entry.get("tags", []) or []:
            tag_counts[str(tag)] += 1
        if entry.get("decision"):
            decision_count += 1
        stamp = _parse_datetime(entry.get("time"))
        if stamp and (latest_time is None or stamp > latest_time):
            latest_time = stamp
    return {
        "total": len(entries),
        "decisions": decision_count,
        "latest": latest_time.isoformat() if latest_time else None,
        "tags": dict(tag_counts),
        "experiments": entries[:limit],
    }


def _cooldown_remaining(doc_id: str, reference: datetime) -> Optional[float]:
    _rehydrate_cooldowns(reference)
    key = _cooldown_key(doc_id)
    ts = _NEGATIVE_COOLDOWNS.get(key)
    if not ts:
        return None
    remaining = (_COOLDOWN_WINDOW - (reference - ts)).total_seconds()
    if remaining > 0:
        return remaining
    return None


def _cooldown_active(doc_id: str, reference: datetime) -> bool:
    return _cooldown_remaining(doc_id, reference) is not None


def _register_cooldown(doc_id: str, timestamp: datetime) -> None:
    _NEGATIVE_COOLDOWNS[_cooldown_key(doc_id)] = timestamp


def _experiment_digest_dir() -> Path:
    override = os.getenv("FRAM_EXPERIMENT_DIGEST_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return REPO_ROOT / "artifacts" / "observability"


def _latest_experiment_digest() -> Optional[Path]:
    root = _experiment_digest_dir()
    if not root.exists():
        return None
    latest_path = root / "experiment_digest_latest.md"
    if latest_path.exists():
        return latest_path
    candidates = list(root.glob("experiment_digest_*.md"))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.stat().st_mtime)


def _read_digest(path: Path, *, max_lines: int) -> str:
    lines = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for idx, line in enumerate(handle):
                if idx >= max_lines:
                    break
                lines.append(line.rstrip("\n"))
    except FileNotFoundError:
        return ""
    return "\n".join(lines)


@app.get("/ui/memory", response_class=HTMLResponse)
def memory_ui() -> HTMLResponse:
    return HTMLResponse(content=MEMORY_UI_HTML)


@app.get("/ui/observability", response_class=HTMLResponse)
def observability_ui() -> HTMLResponse:
    return HTMLResponse(content=OBSERVABILITY_UI_HTML)


@app.get("/health")
def health():
    return {"status": "ok", "service": "fram-v22", "version": "0.0.1"}


@app.get("/config")
def get_config():
    # `/config` is an observability surface, not a credential export. Keep
    # secret-bearing fields out even when the service is bound to loopback.
    return CFG.model_dump(exclude={"api_key"})


@app.get("/time")
def get_time():
    now_local = datetime.now()
    now_utc = datetime.now(timezone.utc)
    return {
        "local_iso": now_local.isoformat(),
        "utc_iso": now_utc.isoformat(),
        "epoch_seconds": int(now_utc.timestamp()),
    }


@app.get("/calibration")
def get_calibration():
    orchestrator = _get_orchestrator()
    cache = orchestrator.ensure_corpus()

    def summarize(payload):
        if payload is None:
            return None
        summary = {
            "tau1": float(payload.tau1),
            "tau2": float(payload.tau2),
            "temperature": float(payload.temperature),
        }
        coefs = getattr(payload, "logistic_coefs", None)
        if isinstance(coefs, dict) and coefs:
            summary["logistic_coefs"] = {
                key: float(value) for key, value in coefs.items()
            }
        return summary

    domain_payloads = getattr(cache, "calibration_by_domain", {}) or {}
    task_payloads = getattr(cache, "calibration_by_task", {}) or {}

    return {
        "default_domain": CFG.default_domain,
        "default_task": CFG.default_task,
        "precedence": ["task", "domain", "global", "default"],
        "global": summarize(getattr(cache, "calibration", None)),
        "domains": {
            name: summarize(payload) for name, payload in domain_payloads.items()
        },
        "tasks": {name: summarize(payload) for name, payload in task_payloads.items()},
    }


# --- Where: show storage locations (Task A) ---
@app.get("/where")
def where():
    root = CFG.STORAGE_ROOT.resolve()
    out: Dict[str, str] = {}
    for k, sub in CFG.STORAGE_SUBFOLDERS.items():
        out[k] = str((root / sub).resolve())
    return out


@app.get("/observability/summary")
def observability_summary(limit: int = 100):
    traces = observability.load_recent_traces(
        CFG.STORAGE_ROOT,
        limit=limit,
    )
    summary = observability.summarize_traces(traces)
    ece, bins = REL.ece()
    summary["fractal_trace_evidence"] = _fractal_trace_evidence()
    summary.update(
        {
            "ece": ece,
            "bins": bins,
            "alarms": ALM.to_dict(),
        }
    )
    return summary


@app.get("/observability/calibration")
def calibration_observability(html: bool = False):
    meta_path = _observability_root() / "calibration_latest.json"
    try:
        summary = (
            json.loads(meta_path.read_text(encoding="utf-8"))
            if meta_path.exists()
            else {}
        )
    except (OSError, ValueError):
        summary = {}
    if html:
        return HTMLResponse(
            "<html><body><h3>Calibration Run Summary</h3>"
            f"<pre>{json.dumps(summary, ensure_ascii=False, indent=2)}</pre>"
            "</body></html>"
        )
    return summary


@app.get("/observability/as_of")
def observability_as_of(limit: int = 50, html: bool = False):
    summary = observability.as_of_delta_summary(_observability_root(), limit=limit)
    if html:
        return HTMLResponse(
            "<html><body><h3>As-of Filter + Delta Snippets</h3>"
            f"<pre>{json.dumps(summary, ensure_ascii=False, indent=2)}</pre>"
            "</body></html>"
        )
    return summary


@app.get("/observability/memory_search.json")
def memory_search_observability(limit: int = 50):
    if not CFG.phase_d.debug_observability:
        return {}
    traces = observability.load_recent_traces(_observability_root(), limit=limit)
    if not traces:
        traces = observability.load_recent_traces(_trace_dir(), limit=limit)
    items: List[Dict[str, Any]] = []
    for trace in traces:
        selection = (
            trace.get("selection") or (trace.get("trace") or {}).get("selection") or {}
        )
        layers = selection.get("memory_layers") or {}
        if not layers:
            continue
        items.append(
            {
                "id": trace.get("id") or trace.get("trace_id"),
                "time": trace.get("time"),
                "merge_enabled": layers.get("merge_enabled"),
                "ann": layers.get("ann"),
                "cognitive": layers.get("cognitive"),
                "merged": layers.get("merged"),
                "premerge": selection.get("cognitive_ann_premerge"),
                "merge": selection.get("cognitive_ann_merge"),
            }
        )
    return {"items": items, "total": len(items)}


@app.get("/observability/dashboard")
def observability_dashboard():
    template_path = (
        Path(__file__).resolve().parent / "templates" / "observability_dashboard.html"
    )
    try:
        content = template_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        content = "<html><body><p>dashboard template missing</p></body></html>"
    return HTMLResponse(content=content)


@app.get("/observability/experiments")
def observability_experiments(
    limit: int = 20, session_id: Optional[str] = None, tag: Optional[str] = None
):
    try:
        limit_value = max(1, min(int(limit), 200))
    except Exception:
        limit_value = 20
    entries = _collect_experiments(session_id=session_id, tag=tag)
    return _summarise_experiments(entries, limit=limit_value)


@app.get("/observability/experiment_digest")
def observability_experiment_digest(max_lines: int = 120):
    try:
        max_lines_value = max(10, min(int(max_lines), 400))
    except Exception:
        max_lines_value = 120
    latest = _latest_experiment_digest()
    if latest is None:
        return {"available": False, "path": None, "updated": None, "content": ""}
    updated = datetime.fromtimestamp(
        latest.stat().st_mtime, tz=timezone.utc
    ).isoformat()
    content = _read_digest(latest, max_lines=max_lines_value)
    return {
        "available": True,
        "path": str(latest),
        "updated": updated,
        "content": content,
    }


@app.get("/ui/experiments", response_class=HTMLResponse)
def experiments_ui() -> HTMLResponse:
    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>FRAM Experiments</title>
  <style>
    :root {
      --bg: #f6f2ea;
      --card: #ffffff;
      --ink: #1b1b1b;
      --muted: #5b5b5b;
      --accent: #1f6feb;
      --accent-soft: #e4efff;
      --border: #d9d4c8;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Space Grotesk", "Trebuchet MS", sans-serif;
      color: var(--ink);
      background: linear-gradient(120deg, #f7f1e3 0%, #e9f1ff 100%);
      min-height: 100vh;
      padding: 2rem;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      margin-bottom: 1.5rem;
    }
    h1 { margin: 0; font-size: 1.8rem; letter-spacing: 0.02em; }
    .controls {
      display: flex;
      gap: 0.75rem;
      align-items: center;
      flex-wrap: wrap;
    }
    input, button {
      border-radius: 999px;
      border: 1px solid var(--border);
      padding: 0.4rem 0.8rem;
      font-family: inherit;
    }
    button {
      background: var(--accent);
      color: #fff;
      border-color: var(--accent);
      font-weight: 600;
      cursor: pointer;
    }
    button.secondary {
      background: var(--accent-soft);
      color: var(--accent);
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 1rem;
    }
    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 1rem;
      box-shadow: 0 6px 20px rgba(31, 111, 235, 0.08);
    }
    .card h2 {
      margin: 0 0 0.5rem 0;
      font-size: 1rem;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }
    pre {
      background: #f2f1ec;
      border-radius: 10px;
      padding: 0.75rem;
      margin: 0;
      max-height: 320px;
      overflow: auto;
      font-family: "IBM Plex Mono", "Consolas", monospace;
      font-size: 0.85rem;
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Experiment Review</h1>
      <div class="muted">Filter and scan experiment decisions fast.</div>
    </div>
    <div class="controls">
      <input id="session" placeholder="session id (optional)" />
      <input id="tag" placeholder="tag (optional)" />
      <button onclick="refresh()">Refresh</button>
      <button class="secondary" onclick="refreshDigest()">Digest</button>
    </div>
  </header>

  <section class="grid">
    <div class="card">
      <h2>Experiments</h2>
      <pre id="experiments"></pre>
    </div>
    <div class="card">
      <h2>Digest</h2>
      <pre id="digest"></pre>
    </div>
  </section>

  <script>
    async function fetchJson(url) {
      const resp = await fetch(url);
      if (!resp.ok) {
        throw new Error(await resp.text());
      }
      return await resp.json();
    }

    async function refresh() {
      const session = document.getElementById('session').value.trim();
      const tag = document.getElementById('tag').value.trim();
      const params = new URLSearchParams();
      params.set('limit', '25');
      if (session) params.set('session_id', session);
      if (tag) params.set('tag', tag);
      const data = await fetchJson(`/observability/experiments?${params.toString()}`);
      document.getElementById('experiments').textContent = JSON.stringify(data, null, 2);
    }

    async function refreshDigest() {
      const data = await fetchJson('/observability/experiment_digest?max_lines=160');
      if (!data.available) {
        document.getElementById('digest').textContent = 'no digest yet';
        return;
      }
      document.getElementById('digest').textContent = data.content || '';
    }

    refresh();
    refreshDigest();
  </script>
</body>
</html>
"""
    return HTMLResponse(content=html)


@app.get("/memory")
def list_memory_sessions():
    return {"sessions": list(_MEMORY_STORE.session_summaries())}


@app.post("/memory")
def create_memory_session(req: MemorySessionCreateRequest) -> dict:
    info = _MEMORY_STORE.create(req.session_id, metadata=req.metadata)
    created = bool(info.pop("created", False))
    session_id = info.get("id")
    if session_id:
        _log_memory_event(
            session_id,
            "create",
            status=info.get("status"),
            entry_count=info.get("entry_count"),
            created=created,
        )
    return {"session": info, "created": created}


# Place static memory routes before dynamic /memory/{session_id} to avoid shadowing
@app.get("/memory/fractal_trace")
def memory_fractal_trace(episode_id: Optional[str] = None, limit: int = 10):
    if not getattr(CFG, "fractal_enabled", False):
        raise HTTPException(status_code=404, detail="fractal memory disabled")
    store = _COG_STORE.fractal_trace_store()
    if store is None:
        return {"items": [], "count": 0, "available_ids": [], "storage_root": None}
    if episode_id:
        payload = store.load_raw(episode_id)
        if payload is None:
            raise HTTPException(
                status_code=404, detail=f"no fractal trace for {episode_id}"
            )
        return payload
    try:
        storage_root = str(store.storage_root.resolve())
    except Exception:
        storage_root = str(store.storage_root)
    try:
        limit_value = max(1, min(int(limit), 50))
    except Exception:
        limit_value = 10
    items: List[Dict[str, Any]] = []
    available_ids = store.available_ids()
    for eid in available_ids[:limit_value]:
        raw = store.load_raw(eid)
        if raw is None:
            continue
        items.append(raw)
    return {
        "items": items,
        "count": len(items),
        "available_ids": available_ids,
        "storage_root": storage_root,
    }


@app.get("/memory/lived/status")
def lived_memory_status():
    store = _get_lived_store()
    if store is None:
        return {"enabled": False, "reason": "feature_disabled"}
    return {"enabled": True, **store.status()}


@app.get("/memory/lived/verify")
def lived_memory_verify():
    store = _get_lived_store()
    if store is None:
        raise HTTPException(status_code=404, detail="lived memory disabled")
    result = store.verify()
    if not result.get("valid"):
        raise HTTPException(status_code=409, detail=result)
    return result


@app.get("/memory/lived/search")
def lived_memory_search(
    query: str,
    k: int = 4,
    session_id: str | None = None,
    include_seeds: bool = True,
    collapse: bool = True,
):
    """Search the lived store. ``include_seeds=false`` leaves ``seed:*`` sessions
    out of this read (nothing is deleted); ``collapse=false`` lists identical
    events separately instead of one row with a ``duplicates`` count (WB-0031)."""
    store = _get_lived_store()
    if store is None:
        raise HTTPException(status_code=404, detail="lived memory disabled")
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="'query' must be non-empty")
    embedding, backend = _encode_cognitive_text(query.strip())
    if embedding is None:
        raise HTTPException(status_code=503, detail="memory embedding unavailable")
    results = store.search(
        embedding,
        k=max(1, min(int(k), 50)),
        session_id=session_id,
        collapse_duplicates=bool(collapse),
        exclude_session_prefixes=None if include_seeds else ("seed:",),
    )
    return {
        "query": query,
        "embedding_backend": backend,
        "count": len(results),
        "include_seeds": bool(include_seeds),
        "collapsed": bool(collapse),
        "items": results,
    }


@app.get("/memory/lived/session/{session_id}")
def lived_memory_session(session_id: str):
    store = _get_lived_store()
    if store is None:
        raise HTTPException(status_code=404, detail="lived memory disabled")
    result = store.session_state(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="lived-memory session not found")
    return result


@app.get("/memory/search")
def memory_search(
    query: str, k: int = 5, domain: str | None = None, task: str | None = None
):
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="'query' must be non-empty")
    k = max(1, int(k))
    filters: Dict[str, Any] = {}
    if domain:
        filters["domain"] = domain.strip()
    if task:
        filters["task"] = task.strip()
    vectorizer = _get_memory_vectorizer()
    results = _COG_STORE.search(
        query.strip(), k=k, filters=filters or None, vectorizer=vectorizer
    )
    return {"results": results}


@app.post("/memory/dismiss")
def dismiss_memory(req: MemoryDismissRequest):
    now_ts = datetime.now(timezone.utc)
    requested = req.doc_id
    doc_id = _cooldown_key(requested)
    _register_cooldown(doc_id, now_ts)
    cooldown_until = now_ts + _COOLDOWN_WINDOW
    _log_memory_event(
        doc_id,
        "dismiss",
        requested=requested,
        cooldown_until=cooldown_until.isoformat(),
        cooldown_minutes=int(_COOLDOWN_WINDOW.total_seconds() / 60),
        reason=req.reason,
    )
    return {
        "doc_id": doc_id,
        "requested": requested,
        "cooldown_until": cooldown_until.isoformat(),
    }


@app.post("/memory/belief")
def append_belief(req: CognitiveBeliefRequest):
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="'text' must be non-empty")
    cleaned_text = req.text.strip()
    embedding_values, embedding_backend = _encode_cognitive_text(cleaned_text)
    try:
        entry = _COG_STORE.append_belief(
            text=cleaned_text,
            source_episode=req.source_episode,
            confidence=req.confidence,
            metadata=req.metadata,
            embedding=embedding_values,
            embedding_backend=(
                embedding_backend if embedding_values is not None else None
            ),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return entry


@app.post("/memory/link")
def append_link(req: CognitiveLinkRequest):
    if not req.src_id or not str(req.src_id).strip():
        raise HTTPException(status_code=400, detail="'src_id' must be non-empty")
    if not req.dst_id or not str(req.dst_id).strip():
        raise HTTPException(status_code=400, detail="'dst_id' must be non-empty")
    src_id = str(req.src_id).strip()
    dst_id = str(req.dst_id).strip()
    if src_id == dst_id:
        raise HTTPException(status_code=400, detail="'src_id' and 'dst_id' must differ")
    if not req.link_type or not str(req.link_type).strip():
        raise HTTPException(status_code=400, detail="'link_type' must be non-empty")
    link_type = str(req.link_type).strip().lower()
    allowed = {"supports", "contradicts", "refines"}
    if link_type not in allowed:
        raise HTTPException(
            status_code=400,
            detail="link_type must be one of: supports, contradicts, refines",
        )
    try:
        entry = _COG_STORE.append_link(
            src_id=src_id,
            dst_id=dst_id,
            link_type=link_type,
            metadata=req.metadata,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return entry


@app.post("/memory/constraint")
def append_constraint(req: CognitiveConstraintRequest):
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="'text' must be non-empty")
    cleaned_text = req.text.strip()
    try:
        entry = _COG_STORE.append_constraint(
            text=cleaned_text,
            scope=req.scope,
            kind=req.kind,
            status=req.status,
            session_id=req.session_id,
            principal=req.principal,
            supersedes_id=req.supersedes_id,
            metadata=req.metadata,
            source_episode=req.source_episode,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return entry


@app.get("/memory/constraints")
def list_constraints(
    scope: Optional[str] = None,
    session_id: Optional[str] = None,
    principal: Optional[str] = None,
):
    records = _COG_STORE.list_constraints()
    if scope:
        scope_value = scope.strip().lower()
        records = [
            rec for rec in records if str(rec.get("scope") or "").lower() == scope_value
        ]
    if session_id:
        records = [rec for rec in records if rec.get("session_id") == session_id]
    if principal:
        records = [rec for rec in records if rec.get("principal") == principal]
    return {"constraints": records}


@app.get("/memory/{session_id}")
def get_memory(session_id: str):
    info = _MEMORY_STORE.session_info(session_id)
    entries = _MEMORY_STORE.list(session_id)
    info["entry_count"] = len(entries)
    return {"session": info, "entries": entries}


@app.post("/memory/{session_id}/control")
def control_memory_session(session_id: str, req: MemorySessionControlRequest):
    action = req.normalized_action()
    if action == "resume":
        info = _MEMORY_STORE.set_status(session_id, WorkingMemoryStore.STATUS_ACTIVE)
    elif action == "pause":
        info = _MEMORY_STORE.set_status(session_id, WorkingMemoryStore.STATUS_PAUSED)
    elif action == "end":
        info = _MEMORY_STORE.set_status(session_id, WorkingMemoryStore.STATUS_ENDED)
    else:
        raise HTTPException(status_code=400, detail="invalid action")
    _log_memory_event(
        session_id,
        "control",
        action=action,
        status=info.get("status"),
        entry_count=info.get("entry_count"),
    )
    return {"session": info, "action": action}


@app.post("/memory/{session_id}")
def append_memory(session_id: str, req: MemoryEntryRequest):
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="'text' must be non-empty")
    text = req.text.strip()
    metadata = dict(req.metadata or {})
    if req.idempotency_key:
        metadata.setdefault("idempotency_key", req.idempotency_key)
    try:
        entry = _MEMORY_STORE.append(session_id, text, metadata)
    except MemorySessionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    info = _MEMORY_STORE.session_info(session_id)
    _log_memory_event(
        session_id,
        "append",
        status=info.get("status"),
        entry_count=info.get("entry_count"),
        entry_id=entry.get("id"),
        deduped=entry.get("deduped"),
    )
    return entry


@app.delete("/memory/{session_id}")
def clear_memory(session_id: str):
    _MEMORY_STORE.ensure_session(session_id)
    _MEMORY_STORE.clear(session_id)
    info = _MEMORY_STORE.session_info(session_id)
    _log_memory_event(
        session_id,
        "clear",
        status=info.get("status"),
        entry_count=info.get("entry_count"),
    )
    return {"session": info, "cleared": True}


@app.get("/observability/memory/summary")
def memory_summary(window: int = 50):
    try:
        w = max(1, int(window))
    except Exception:
        w = 50
    summary = _COG_STORE.summarize(window=w)
    return summary


@app.get("/observability/memory/fractal/ping")
def fractal_ping(limit: int = 100):
    try:
        limit_value = max(1, min(int(limit), 500))
    except Exception:
        limit_value = 100
    events_path = _observability_root() / "memory_fractal.jsonl"
    events: List[Dict[str, Any]] = list(observability.iter_jsonl(events_path))
    if len(events) > limit_value:
        events = events[-limit_value:]
    return {"events": events, "count": len(events)}


@app.get("/observability/traces")
def observability_traces(limit: int = 10):
    traces = observability.load_recent_traces(
        CFG.STORAGE_ROOT,
        limit=max(1, int(limit)),
    )
    return {"traces": traces}


@app.get("/observability/trace/{trace_id}")
def observability_trace(trace_id: str):
    traces = observability.load_recent_traces(
        CFG.STORAGE_ROOT,
        limit=int(CFG.metrics_window),
    )
    for item in traces:
        if str(item.get("id")) == str(trace_id):
            return item
    raise HTTPException(status_code=404, detail="trace not found")


@app.get("/observability/continuity/witness")
def observability_continuity_witness():
    envelope: Dict[str, Any] = {
        "schema": "fram.continuity-witness.latest",
        "version": 1,
        "witness_schema": WITNESS_SCHEMA_VERSION,
        "available": False,
        "state": "unknown",
        "reason": None,
        "witness": None,
    }
    if not bool(getattr(CFG, "continuity_witness_enabled", False)):
        envelope["reason"] = "feature_disabled"
        return envelope

    try:
        witness = load_latest_continuity_witness(_continuity_witness_root())
    except ContinuityWitnessNotFoundError:
        envelope["reason"] = "not_found"
        return envelope
    except ContinuityWitnessCorruptError:
        envelope.update({"state": "corrupt", "reason": "corrupt_log"})
        return envelope
    except ContinuityWitnessTamperedError:
        envelope.update({"state": "tampered", "reason": "digest_mismatch"})
        return envelope
    except ContinuityWitnessReadError:
        envelope["reason"] = "unreadable"
        return envelope

    state = str(witness.get("state", "unknown"))
    observed_at = witness.get("observed_at_utc")
    max_age = max(
        0.0,
        float(getattr(CFG, "continuity_witness_max_age_seconds", 3600.0)),
    )
    if state == "available" and max_age > 0.0:
        try:
            observed = datetime.fromisoformat(str(observed_at).replace("Z", "+00:00"))
            if observed.tzinfo is None:
                observed = observed.replace(tzinfo=timezone.utc)
            age_seconds = max(
                0.0,
                (
                    datetime.now(timezone.utc) - observed.astimezone(timezone.utc)
                ).total_seconds(),
            )
        except (TypeError, ValueError):
            state = "corrupt"
            envelope["reason"] = "invalid_observed_at"
        else:
            if age_seconds > max_age:
                state = "stale"
                envelope["reason"] = "max_age_exceeded"

    envelope.update(
        {
            "available": state == "available",
            "state": state,
            "witness": witness,
        }
    )
    return envelope


@app.post("/query")
def query(req: QueryRequest):
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="'text' must be non-empty")

    try:
        orchestrator = _get_orchestrator()
        ctx = QueryContext(
            cfg=CFG,
            orchestrator=orchestrator,
            memory_store=_MEMORY_STORE,
            cognitive_store=_COG_STORE,
            capsule_store=_CAPSULE_STORE,
            get_memory_vectorizer=_get_memory_vectorizer,
            encode_cognitive_text=_encode_cognitive_text,
            apply_phase_d_memory_bridge=_apply_phase_d_memory_bridge,
            cooldown_active=_cooldown_active,
            register_cooldown=_register_cooldown,
            cooldown_window=_COOLDOWN_WINDOW,
            resolve_time_sensitivity=_resolve_time_sensitivity,
            ensure_doc_cache=_ensure_doc_cache,
            trace_writer=_get_trace_logger(),
            observability_dir=_observability_root(),
            trace_dir=_trace_dir(),
            store_prob=_store_prob,
            log_memory_event=_log_memory_event,
            archive_writer=ArchiveWriter(CFG.STORAGE_ROOT / "archive"),
            archive_kind="query",
            lived_memory_store=_get_lived_store(),
            continuity_witness_writer=(
                ContinuityWitnessWriter(
                    _continuity_witness_root(),
                    lock_timeout_seconds=float(
                        getattr(CFG, "continuity_witness_lock_timeout_seconds", 0.1)
                    ),
                )
                if bool(getattr(CFG, "continuity_witness_enabled", False))
                else None
            ),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    try:
        result = run_query(req, ctx)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        trace = result.get("trace")
        if isinstance(trace, dict):
            tc_payload = trace.get("transitional_complexity")
            if isinstance(tc_payload, dict):
                tc_value = tc_payload.get("tc")
                if isinstance(tc_value, (int, float)) and np.isfinite(tc_value):
                    TC_WINDOW.append(float(tc_value))
    except Exception:
        pass

    return result


@app.get("/metrics")
def get_metrics():
    ALM.evaluate(REL, CFG.tau1, CFG.tau2)
    metrics = ALM.last_metrics
    ece_value, bins = REL.ece()
    last_update = REL.last_update.isoformat() if REL.last_update is not None else None
    domain_summary = REL.group_summary("domain")
    task_summary = REL.group_summary("task")
    latest_record = REL.latest()
    tc_latest = float(TC_WINDOW[-1]) if TC_WINDOW else None
    tc_avg = float(sum(TC_WINDOW) / len(TC_WINDOW)) if TC_WINDOW else None
    return {
        "ece": float(ece_value),
        "tau1": float(CFG.tau1),
        "tau2": float(CFG.tau2),
        "alpha1": float(CFG.alpha1),
        "alpha2": float(CFG.alpha2),
        "fn_rate_at_tau1": metrics.get("fn_tau1", 0.0),
        "fn_rate_at_tau2": metrics.get("fn_tau2", 0.0),
        "window_size": len(REL),
        "window_max": REL.capacity,
        "window": int(CFG.metrics_window),
        "last_update": last_update,
        "bins": bins,
        "reliability": {
            "by_domain": domain_summary,
            "by_task": task_summary,
            "latest": latest_record,
        },
        "transitional_complexity": {
            "window_size": len(TC_WINDOW),
            "window_max": TC_WINDOW.maxlen,
            "latest": tc_latest,
            "avg": tc_avg,
        },
        "config": {
            "lambda_tok": float(CFG.lambda_tok),
            "lambda_rerank": float(CFG.lambda_rerank),
            "pairs_scale": float(CFG.pairs_scale),
            "coverage_gamma": float(CFG.coverage_gamma),
            "coverage_u_max": int(CFG.coverage_u_max),
        },
        "alarms": ALM.to_dict(),
    }


@app.post("/label")
def label_decision(req: LabelRequest):
    label = req.normalized_label()
    prob_record = _pop_prob(req.query_id)
    if prob_record is None:
        raise HTTPException(
            status_code=404, detail="probability for query_id not found"
        )

    try:
        prob = float(prob_record.get("prob"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=500, detail="stored probability invalid")

    def _coerce_tau(field: str, fallback: float) -> float:
        value = prob_record.get(field)
        if value is None:
            return float(fallback)
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(fallback)

    tau1_used = _coerce_tau("tau1", CFG.tau1)
    tau2_used = _coerce_tau("tau2", CFG.tau2)
    domain_log = prob_record.get("domain")
    task_log = prob_record.get("task")
    source = prob_record.get("source")
    temperature_value = None
    if prob_record.get("temperature") is not None:
        try:
            temperature_value = float(prob_record.get("temperature"))
        except (TypeError, ValueError):
            temperature_value = None

    REL.update(
        req.query_id,
        prob,
        label,
        tau1=tau1_used,
        tau2=tau2_used,
        domain=domain_log,
        task=task_log,
        source=source,
        temperature=temperature_value,
    )
    ALM.evaluate(REL, CFG.tau1, CFG.tau2)

    obs_dir = CFG.STORAGE_ROOT / CFG.STORAGE_SUBFOLDERS.get(
        "observability", "observability"
    )
    log_payload = {
        "event": "label",
        "query_id": req.query_id,
        "label": int(label),
        "prob": float(prob),
        "tau1": float(tau1_used),
        "tau2": float(tau2_used),
        "domain": domain_log,
        "task": task_log,
    }
    if source:
        log_payload["calibration_source"] = source
    if temperature_value is not None:
        log_payload["calibration_temperature"] = temperature_value
    observability.log_confidence_event(
        obs_dir,
        log_payload,
    )

    return {
        "query_id": req.query_id,
        "prob": float(prob),
        "label": int(label),
        "metrics": {
            "ece": REL.ece()[0],
            "window_size": len(REL),
            "fn_tau1": ALM.last_metrics.get("fn_tau1", 0.0),
            "fn_tau2": ALM.last_metrics.get("fn_tau2", 0.0),
        },
    }


@api_router.post("/search/expand", response_model=ExpandSearchResponse)
def expand_search(req: ExpandSearchRequest) -> ExpandSearchResponse:
    situation_payload = req.situation or {}
    tau = float(situation_payload.get("tau_expand", 0.72))
    max_terms = req.max_expansions if req.max_expansions > 0 else 32
    context = build_situation(
        req.query,
        task=situation_payload.get("task"),
        domain=situation_payload.get("domain"),
        recent_turns=situation_payload.get("recent_turns"),
        goals=situation_payload.get("goals"),
        clock=situation_payload.get("clock"),
        tau_expand=tau,
        max_terms=max_terms,
    )
    expansions = _unique_preserve(context.expansions)
    if req.max_expansions > 0:
        expansions = expansions[: req.max_expansions]
    if not expansions:
        tokens = context.tokens
        expansions = tokens[: req.max_expansions] if req.max_expansions > 0 else tokens

    entities = context.entities or _unique_preserve(
        [str(e) for e in situation_payload.get("entities", []) if e]
    )
    aliases = context.aliases or _unique_preserve(
        [str(a) for a in situation_payload.get("aliases", []) if a]
    )

    return ExpandSearchResponse(
        expanded_query=context.text,
        terms=expansions,
        entities=entities,
        aliases=aliases,
        notes=context.audit,
        threshold=tau,
    )


@api_router.post("/rank/relevance", response_model=RankRelevanceResponse)
def rank_relevance(req: RankRelevanceRequest) -> RankRelevanceResponse:
    situation_payload = req.situation or {}
    tau = float(situation_payload.get("tau_expand", 0.72))
    task_value = str(situation_payload.get("task") or "").strip().lower()
    domain_value = str(situation_payload.get("domain") or "").strip().lower()
    sensitivity = _resolve_time_sensitivity(task_value, domain_value)
    context = build_situation(
        req.query,
        task=task_value,
        domain=domain_value,
        recent_turns=situation_payload.get("recent_turns"),
        goals=situation_payload.get("goals"),
        clock=situation_payload.get("clock"),
        tau_expand=tau,
        max_terms=situation_payload.get("max_terms", 32),
    )
    query_tokens = set(context.tokens)
    context_entities = {entity.lower() for entity in context.entities}
    candidate_features: List[CandidateFeatures] = []
    candidate_wrappers: List[Dict[str, Any]] = []

    now_ref = None
    if context.clock:
        utc_iso = context.clock.get("utc_iso")
        parsed = _parse_datetime(utc_iso)
        if parsed:
            now_ref = parsed
    reference = now_ref or datetime.now(timezone.utc)
    cooldown_overrides = situation_payload.get("cooldowns") or {}

    for candidate in req.candidates:
        candidate_tokens = set(_tokenize_for_semantics(candidate.text))
        meta_entities = candidate.metadata.get("entities") or []
        candidate_entities = {str(e).lower() for e in meta_entities if e}
        candidate_features.append(
            CandidateFeatures(
                id=candidate.id,
                text=candidate.text,
                tokens=candidate_tokens,
                metadata=candidate.metadata,
                entities=candidate_entities,
            )
        )
        candidate_wrappers.append(
            {
                "candidate": candidate,
                "tokens": candidate_tokens,
                "entities": candidate_entities,
            }
        )

    rerank_results = {
        result.id: result
        for result in SEMANTIC_RERANKER.rank(context.text, candidate_features)
    }

    scored: List[RankRelevanceScore] = []
    for data in candidate_wrappers:
        candidate = data["candidate"]
        candidate_tokens = data["tokens"]
        candidate_entities = data["entities"]

        coarse = 0.0
        if query_tokens and candidate_tokens:
            coarse = len(query_tokens & candidate_tokens) / max(len(query_tokens), 1)
        graph_bonus = ENTITY_GRAPH.bridge_score(context_entities, candidate_entities)
        novelty = 0.0
        if candidate_tokens:
            novelty = len(candidate_tokens - query_tokens) / len(candidate_tokens)
        time_bonus = 0.0
        last_seen = candidate.metadata.get("last_seen")
        seen_ts = _parse_datetime(last_seen)
        if seen_ts:
            age_hours = max((reference - seen_ts).total_seconds(), 0.0) / 3600.0
            time_bonus = _time_boost(age_hours, sensitivity)
        remaining_seconds = None
        override_value = cooldown_overrides.get(candidate.id)
        if override_value:
            override_ts = _parse_datetime(override_value)
            if override_ts:
                remaining = (
                    _COOLDOWN_WINDOW - (reference - override_ts)
                ).total_seconds()
                if remaining > 0:
                    remaining_seconds = remaining
        global_remaining = _cooldown_remaining(candidate.id, reference)
        if global_remaining is not None:
            remaining_seconds = max(remaining_seconds or 0.0, global_remaining)
        if remaining_seconds is not None:
            cooldown_scale = min(
                1.0, remaining_seconds / _COOLDOWN_WINDOW.total_seconds()
            )
            coarse *= 0.3
            novelty *= 0.3
            time_bonus -= cooldown_scale
            time_bonus = max(time_bonus, -1.0)

        rerank = rerank_results.get(candidate.id)
        cross_score = rerank.score if rerank else 0.0
        breakdown = {
            "coarse": round(coarse, 4),
            "cross": round(cross_score, 4),
            "graph": round(graph_bonus, 4),
            "help": round(novelty, 4),
            "time": round(time_bonus, 4),
        }
        total = sum(breakdown.values())
        details = {
            "cross_model": rerank.model if rerank else "heuristic",
            "cross_raw": rerank.raw_score if rerank else cross_score,
            "cooldown_remaining": remaining_seconds,
        }
        scored.append(
            RankRelevanceScore(
                id=candidate.id,
                score=total,
                breakdown=breakdown,
                details=details,
            )
        )

    scored.sort(key=lambda item: item.score, reverse=True)
    phase_d_scores: Optional[List[float]] = None
    phase_d_diagnostics: Optional[Dict[str, Any]] = None
    if CFG.phase_d.enabled:
        shortlist = [{"text": candidate.text} for candidate in req.candidates]
        try:
            query_embedding, episode_embeddings = (
                _get_orchestrator().get_embeddings_for_shortlist(req.query, shortlist)
            )
            if query_embedding and episode_embeddings:
                phase_d_result = phase_d_score_batch(
                    query_embedding=query_embedding,
                    episode_embeddings=episode_embeddings,
                    phase_d_enabled=True,
                    phase_d_debug=CFG.phase_d.debug_observability,
                )
                phase_d_scores = phase_d_result.get("scores")
                if CFG.phase_d.debug_observability:
                    phase_d_diagnostics = phase_d_result.get("diagnostics")
        except Exception:
            phase_d_scores = None
            phase_d_diagnostics = None
    return RankRelevanceResponse(
        scores=scored,
        phase_d_scores=phase_d_scores,
        phase_d_diagnostics=phase_d_diagnostics,
    )


@api_router.post("/phase_d/score", response_model=PhaseDScoreResponse)
def phase_d_score(req: PhaseDScoreRequest) -> PhaseDScoreResponse:
    enabled = CFG.phase_d.enabled if req.enabled is None else req.enabled
    debug = CFG.phase_d.debug_observability if req.debug is None else req.debug
    result = phase_d_score_batch(
        query_embedding=req.query_embedding,
        episode_embeddings=req.episode_embeddings,
        phase_d_enabled=bool(enabled),
        phase_d_debug=bool(debug),
    )
    return PhaseDScoreResponse(**result)


@api_router.get("/beliefs/conflicts", response_model=ConflictsResponse)
def list_belief_conflicts() -> ConflictsResponse:
    return ConflictsResponse(conflicts=list_conflicts())


def _fractal_recall_summary(
    since_dt: Optional[datetime],
) -> Optional[FractalRecallSummary]:
    path = _observability_root() / "memory_fractal.jsonl"
    if not path.exists():
        return None
    events_total = 0
    hits = 0
    recent_events: List[FractalEventEntry] = []
    episode_counts: Counter[str] = Counter()
    for event in observability.iter_jsonl(path):
        if event.get("kind") != "score":
            continue
        event_time = _parse_datetime(event.get("time"))
        if since_dt and event_time and event_time < since_dt:
            continue
        events_total += 1
        try:
            returned = int(event.get("k") or 0)
        except (TypeError, ValueError):
            returned = 0
        try:
            requested = int(event.get("requested") or 0)
        except (TypeError, ValueError):
            requested = 0
        top_items = event.get("top")
        top_list = (
            [item for item in top_items if isinstance(item, dict)]
            if isinstance(top_items, list)
            else []
        )
        if returned > 0 and top_list:
            hits += 1
            for item in top_list:
                episode_id = item.get("episode_id")
                if episode_id:
                    episode_counts[str(episode_id)] += 1
        alpha_value: Optional[float] = None
        alpha_raw = event.get("alpha")
        if alpha_raw is not None:
            try:
                alpha_value = float(alpha_raw)
            except (TypeError, ValueError):
                alpha_value = None
        recent_events.append(
            FractalEventEntry(
                query_id=event.get("query_id"),
                timestamp=event_time.isoformat() if event_time else event.get("time"),
                requested=requested,
                returned=returned,
                backend=event.get("backend"),
                alpha=alpha_value,
                top=top_list[:5],
            )
        )
    if events_total == 0:
        return None
    recent_events = recent_events[-20:]
    top_episodes = [
        FractalTopEpisode(episode_id=eid, count=count)
        for eid, count in episode_counts.most_common(10)
    ]
    hit_rate = hits / events_total if events_total else 0.0
    return FractalRecallSummary(
        events=events_total,
        hits=hits,
        hit_rate=hit_rate,
        recent=recent_events,
        top_episodes=top_episodes,
    )


def _aggregate_phase_d_stats(entries: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    scored: List[int] = []
    alpha_values: List[float] = []
    quat_values: List[float] = []
    colors: Counter[str] = Counter()
    for entry in entries:
        try:
            scored.append(int(entry.get("scored", 0)))
        except (TypeError, ValueError):
            pass
        for key, target in (("alpha_t", alpha_values), ("quat_avg", quat_values)):
            try:
                value = float(entry.get(key))
            except (TypeError, ValueError):
                continue
            if np.isfinite(value):
                target.append(value)
        if entry.get("alpha_color"):
            colors[str(entry["alpha_color"])] += 1
    alpha_missing = max(0, len(entries) - len(alpha_values))
    total = int(sum(scored))
    return {
        "events": len(entries),
        "scored_total": total,
        "scored_avg": float(total / len(scored)) if scored else 0.0,
        "alpha_t_avg": float(np.mean(alpha_values)) if alpha_values else None,
        "quat_avg": float(np.mean(quat_values)) if quat_values else None,
        "alpha_color_counts": dict(colors),
        "alpha_missing": alpha_missing,
        "missing_alpha": alpha_missing > 0,
    }


def _lifecycle_summary_from_pd_entries(
    entries: List[Dict[str, Any]],
    *,
    retention_half_life: float,
    forgetting_half_life: float,
    forgetting_threshold: float,
    min_active_items: int,
    retention_enabled: bool,
    decay_enabled: bool,
    hard_forget_enabled: bool,
) -> Optional[Dict[str, Any]]:
    if not entries or not (retention_enabled or decay_enabled or hard_forget_enabled):
        return None
    candidates: Dict[str, Dict[str, Any]] = {}
    anonymous = 0
    for entry in entries:
        for key in ("retention", "decay", "forgetting_snapshot"):
            for snapshot in entry.get(key) or []:
                identifier = snapshot.get("id")
                if identifier is None:
                    anonymous += 1
                    identifier = f"anonymous-{anonymous}"
                item = candidates.setdefault(str(identifier), {})
                if snapshot.get("age_seconds") is not None:
                    item["age_seconds"] = float(snapshot["age_seconds"])
                if key == "forgetting_snapshot":
                    item["decision"] = snapshot.get("decision")
    if not candidates:
        return None

    decision_counts = {
        "decision_keep": 0,
        "decision_forget_dry": 0,
        "decision_forget_enforce": 0,
    }
    buckets: Dict[str, Dict[str, int]] = {}
    for item in candidates.values():
        decision = str(item.get("decision") or "keep")
        decision_counts[f"decision_{decision}"] = (
            decision_counts.get(f"decision_{decision}", 0) + 1
        )
        age_days = max(0.0, float(item.get("age_seconds", 0.0))) / 86400.0
        if retention_half_life <= 0:
            label = "<unknown>"
        elif age_days < retention_half_life:
            label = "<1_half_life"
        elif age_days < 2 * retention_half_life:
            label = "1-2_half_life"
        elif age_days < 5 * retention_half_life:
            label = "2-5_half_life"
        else:
            label = ">5_half_life"
        bucket = buckets.setdefault(label, {"count": 0, "forgotten_enforce": 0})
        bucket["count"] += 1
        if decision == "forget_enforce":
            bucket["forgotten_enforce"] += 1
    return {
        "config": {
            "retention_half_life_days": retention_half_life,
            "forgetting_half_life_days": forgetting_half_life,
            "forgetting_threshold": forgetting_threshold,
            "min_active_items": min_active_items,
            "enable_retention_curve": retention_enabled,
            "enable_decay": decay_enabled,
            "enable_hard_forgetting": hard_forget_enabled,
        },
        "counts": {"total_candidates": len(candidates), **decision_counts},
        "age_buckets": [
            {"label": label, **values} for label, values in buckets.items()
        ],
    }


def _phase_d_memory_events(limit: int = 50) -> Dict[str, Any]:
    phase_d_enabled = bool(CFG.phase_d.enabled)
    bridge_enabled = bool(CFG.phase_d.enable_memory_bridge)
    base = {
        "enabled": phase_d_enabled and bridge_enabled,
        "bridge_enabled": bridge_enabled,
        "events": [],
        "config": {
            "phase_d_enabled": phase_d_enabled,
            "bridge_enabled": bridge_enabled,
        },
    }
    if not base["enabled"]:
        return base
    try:
        source_events = list(
            observability.iter_jsonl(_observability_root() / "memory_cognitive.jsonl")
        )
    except FileNotFoundError:
        source_events = []
    phase_entries: List[Dict[str, Any]] = []
    events: List[Dict[str, Any]] = []
    for event in source_events:
        phase_memory = event.get("phase_d_memory")
        if isinstance(phase_memory, dict) and phase_memory.get("enabled"):
            phase_entries.append(phase_memory)
            events.append(
                {
                    "time": event.get("time"),
                    "query_id": event.get("query_id"),
                    "phase_d_memory": phase_memory,
                }
            )
    events = events[-max(1, int(limit)) :]
    phase_entries = phase_entries[-max(1, int(limit)) :]
    latest = phase_entries[-1] if phase_entries else {}
    payload = {
        **base,
        "events": events,
        "stats": _aggregate_phase_d_stats(phase_entries),
        "priority_snapshot": list(latest.get("priority_snapshot") or []),
    }
    payload["config"].update(
        {
            "alpha_t": latest.get("alpha_t"),
            "alpha_color": latest.get("alpha_color"),
        }
    )
    retention_enabled = bool(CFG.enable_retention_curve)
    decay_enabled = bool(CFG.enable_decay)
    hard_forget_enabled = bool(CFG.enable_hard_forgetting)
    if retention_enabled:
        payload["retention_snapshot"] = list(latest.get("retention") or [])
    if decay_enabled:
        payload["decay_snapshot"] = list(latest.get("decay") or [])
    if hard_forget_enabled:
        payload["forgetting_snapshot"] = list(latest.get("forgetting_snapshot") or [])
    lifecycle = _lifecycle_summary_from_pd_entries(
        phase_entries,
        retention_half_life=float(CFG.retention_half_life_days),
        forgetting_half_life=float(CFG.forgetting_half_life_days),
        forgetting_threshold=float(CFG.forgetting_threshold),
        min_active_items=int(CFG.min_active_items),
        retention_enabled=retention_enabled,
        decay_enabled=decay_enabled,
        hard_forget_enabled=hard_forget_enabled,
    )
    if lifecycle is not None:
        payload["lifecycle_summary"] = lifecycle
    return payload


def cognitive_summary_data(limit: int = 100) -> Dict[str, Any]:
    try:
        events = list(
            observability.iter_jsonl(_observability_root() / "memory_cognitive.jsonl")
        )
    except FileNotFoundError:
        events = []
    events = events[-max(1, int(limit)) :]
    bridge_enabled = bool(CFG.phase_d.enabled and CFG.phase_d.enable_memory_bridge)
    recent: List[Dict[str, Any]] = []
    phase_entries: List[Dict[str, Any]] = []
    selected_total = 0
    for event in events:
        selected_items = list(event.get("selected") or [])
        try:
            selected_count = int(event.get("selected_count") or len(selected_items))
        except (TypeError, ValueError):
            selected_count = len(selected_items)
        selected_total += max(0, selected_count)
        entry: Dict[str, Any] = {
            "query_id": event.get("query_id"),
            "timestamp": event.get("time"),
            "selected_count": selected_count,
            "selected": [
                {
                    "id": item.get("id"),
                    "kind": item.get("kind"),
                    "score": item.get("score"),
                }
                for item in selected_items[:3]
            ],
        }
        phase_memory = event.get("phase_d_memory")
        if bridge_enabled and isinstance(phase_memory, dict):
            entry["phase_d_memory"] = phase_memory
            phase_entries.append(phase_memory)
        recent.append(entry)
    summary: Dict[str, Any] = {
        "invocations": len(events),
        "selected_total": selected_total,
        "recent": recent,
        "config": {
            "cognitive_memory_k": int(CFG.cognitive_memory_k),
            "token_budget": int(CFG.cognitive_memory_token_budget),
            "bridge_enabled": bridge_enabled,
        },
    }
    if bridge_enabled and phase_entries:
        latest = phase_entries[-1]
        summary["phase_d_memory"] = {
            "events": len(phase_entries),
            "latest": latest,
            "stats": _aggregate_phase_d_stats(phase_entries),
        }
        summary["config"]["phase_d_alpha_t"] = latest.get("alpha_t")
        summary["config"]["phase_d_alpha_color"] = latest.get("alpha_color")
        summary["bridge_activity"] = {
            "phase_d_events": len(phase_entries),
            "phase_c_events": max(0, len(events) - len(phase_entries)),
            "window": limit,
        }
    return summary


@api_router.get("/observability/phase_d_memory")
def phase_d_memory_dashboard(html: bool = False, limit: int = 50):
    payload = _phase_d_memory_events(limit)
    if not html:
        return payload
    sections = [
        ("Priority Snapshot", payload.get("priority_snapshot") or []),
        ("Retention Snapshot", payload.get("retention_snapshot") or []),
        ("Decay Snapshot", payload.get("decay_snapshot") or []),
        ("Forgetting Snapshot", payload.get("forgetting_snapshot") or []),
        ("Recent Events", payload.get("events") or []),
    ]
    rendered = "".join(
        f"<h3>{title}</h3><pre>{json.dumps(data, ensure_ascii=False, indent=2)}</pre>"
        for title, data in sections
    )
    return HTMLResponse(
        "<html><body><h2>Phase D Priority Inspector</h2>" f"{rendered}</body></html>"
    )


@app.get("/observability/storage")
def storage_observability(html: bool = False):
    summary = _storage_summary()
    if not html:
        return summary
    return HTMLResponse(
        "<html><body><h2>Storage Summary</h2>"
        f"<pre>{json.dumps(summary, ensure_ascii=False, indent=2)}</pre>"
        "</body></html>"
    )


@api_router.get("/observability/cognitive_summary")
def cognitive_summary_dashboard(html: bool = False, limit: int = 50):
    summary = cognitive_summary_data(limit)
    if not html:
        return summary
    rows = "".join(
        f"<tr><td>{item.get('timestamp')}</td><td>{item.get('query_id')}</td>"
        f"<td>{item.get('selected_count')}</td></tr>"
        for item in summary["recent"]
    )
    return HTMLResponse(
        "<html><head><style>table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:4px}</style>"
        "</head><body><table><tr><th>time</th><th>query</th><th>selected</th></tr>"
        f"{rows}</table></body></html>"
    )


@api_router.get("/observability/recall_report", response_model=RecallReport)
def recall_report(since: Optional[str] = None) -> RecallReport:
    since_dt = _parse_datetime(since) if since else None
    path = _observability_root() / "memory_cognitive.jsonl"
    seeds: List[Dict[str, Any]] = []
    misses: List[Dict[str, Any]] = []
    invocations = 0
    try:
        for event in observability.iter_jsonl(path):
            event_time = _parse_datetime(event.get("time"))
            if since_dt and event_time and event_time < since_dt:
                continue
            invocations += 1
            entry = {
                "query_id": event.get("query_id"),
                "timestamp": (
                    event_time.isoformat() if event_time else event.get("time")
                ),
                "selected_count": event.get("selected_count"),
                "selected": event.get("selected", []),
                "cooldowns_skipped": event.get("cooldowns_skipped", []),
                "phase_d_memory": event.get("phase_d_memory"),
            }
            seeds.append(entry)
            if not entry["selected"]:
                misses.append(entry)
    except FileNotFoundError:
        invocations = 0
    # return only the latest 50 entries to keep payload reasonable
    seeds = seeds[-50:]
    misses = misses[-50:]
    conflicts = list_conflicts()[:50]
    hit_count = sum(1 for entry in seeds if entry.get("selected"))
    hit_rate = hit_count / invocations if invocations else 0.0
    sensitivity_counts: Dict[str, int] = {}
    for entry in seeds:
        for item in entry.get("selected", []):
            sens = str(item.get("time_sensitivity") or "unknown").lower()
            sensitivity_counts[sens] = sensitivity_counts.get(sens, 0) + 1
    fractal_summary = _fractal_recall_summary(since_dt)
    phase_d_block: Optional[PhaseDRecallBlock] = None
    if CFG.phase_d.enabled and CFG.phase_d.debug_observability:
        diagnostics = (
            attach_phase_d_observability(
                alpha_t=(
                    fractal_summary.logistic_alpha_preview
                    if fractal_summary is not None
                    else None
                ),
                quat_similarity_values=[],
                phase_d_enabled=True,
            )
            or {}
        )
        phase_d_block = PhaseDRecallBlock(
            enabled=True,
            debug=True,
            **diagnostics,
        )
        if fractal_summary is not None:
            fractal_summary.logistic_alpha_preview = phase_d_block.alpha_t
            fractal_summary.logistic_state_color = phase_d_block.alpha_color
            fractal_summary.quaternion_similarity_avg = phase_d_block.quat_avg

    phase_entries = [
        entry["phase_d_memory"]
        for entry in seeds
        if isinstance(entry.get("phase_d_memory"), dict)
        and entry["phase_d_memory"].get("enabled")
    ]
    phase_memory_summary: Optional[PhaseDMemorySummary] = None
    if CFG.phase_d.enable_memory_bridge and phase_entries:
        latest = phase_entries[-1]
        phase_memory_summary = PhaseDMemorySummary(
            enabled=True,
            debug=bool(latest.get("debug", False)),
            scored=int(latest.get("scored", 0) or 0),
            alpha_t=latest.get("alpha_t"),
            alpha_color=latest.get("alpha_color"),
            quat_avg=latest.get("quat_avg"),
            events=len(phase_entries),
            latest=latest,
            stats=_aggregate_phase_d_stats(phase_entries),
            retention_snapshot=latest.get("retention"),
            decay_snapshot=latest.get("decay"),
        )
    cognitive_summary = CognitiveRecallSummary(
        invocations=invocations,
        selected=sum(int(entry.get("selected_count") or 0) for entry in seeds),
        phase_d_memory=phase_memory_summary,
    )
    return RecallReport(
        since=since,
        invocations=invocations,
        seeds=seeds,
        misses=misses,
        conflicts=conflicts,
        hit_rate=hit_rate,
        time_sensitivity=sensitivity_counts,
        fractal=fractal_summary,
        phase_d=phase_d_block,
        phase_d_memory=phase_memory_summary,
        cognitive=cognitive_summary,
    )


app.include_router(api_router)
