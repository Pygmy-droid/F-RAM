from __future__ import annotations

import logging
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

import numpy as np

from fram_core.claims import extract_claims
from fram_core.pipeline import QueryOrchestrator, tokenize_text
from fram_serving import observability
from fram_serving import pil
from fram_serving.archive import ArchiveWriter
from fram_serving.cognitive_embeddings import normalize_cognitive_backend
from fram_serving.config import FRAMConfig
from fram_serving.continuity import (
    ContinuityWitnessWriteError,
    ContinuityWitnessWriter,
    build_continuity_witness,
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
from fram_serving.memory import (
    CognitiveMemoryStore,
    MemoryWriteError,
    WorkingMemoryStore,
)
from fram_serving.memory_capsule import (
    CAPSULE_VERSION,
    MemoryCapsuleStore,
    build_capsule_turns,
)
from fram_serving.rep import update_rep

try:
    from fram_core.pipeline import (
        compute_phase_d_priority,
        phase_d_weight_for_cognitive,
    )
except Exception:  # pragma: no cover - optional in baseline branches

    def compute_phase_d_priority(**_: Any) -> float:  # type: ignore[override]
        return 1.0

    def phase_d_weight_for_cognitive(**_: Any) -> float:  # type: ignore[override]
        return 1.0


try:
    from fram_core.priority_graph import apply_priority_graph
except Exception:  # pragma: no cover - optional in baseline branches

    def apply_priority_graph(candidates: List[Dict[str, Any]], _: Any = None) -> List[Dict[str, Any]]:  # type: ignore[override]
        return candidates


try:
    from fram_serving.memory.retention_curve import compute_retention_score
except Exception:  # pragma: no cover - optional in baseline branches

    def compute_retention_score(*, age_seconds: float | None, config: Any) -> float:  # type: ignore[override]
        return 1.0


try:
    from fram_serving.scoring._fractal_trace_scores_phase_d import phase_d_score_batch
except Exception:  # pragma: no cover - optional in baseline branches
    phase_d_score_batch = None  # type: ignore[assignment]


DEFAULT_CFG = FRAMConfig()
FRACTAL_INFLUENCE_ALPHA = float(DEFAULT_CFG.fractal_influence_alpha)
_logger = logging.getLogger(__name__)


@dataclass(slots=True)
class QueryContext:
    cfg: Any
    orchestrator: QueryOrchestrator
    memory_store: WorkingMemoryStore
    cognitive_store: CognitiveMemoryStore
    capsule_store: MemoryCapsuleStore | None
    get_memory_vectorizer: Callable[[], Any]
    encode_cognitive_text: Callable[[str], tuple[List[float] | None, str | None]]
    apply_phase_d_memory_bridge: Callable[
        [str, List[Dict[str, Any]], bool],
        tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]],
    ]
    cooldown_active: Callable[[str, datetime], bool]
    register_cooldown: Callable[[str, datetime], None]
    cooldown_window: timedelta
    resolve_time_sensitivity: Callable[[str | None, str | None], str]
    ensure_doc_cache: Callable[[], Dict[str, Any]]
    trace_writer: observability.TraceLogWriter
    observability_dir: Path
    trace_dir: Path
    store_prob: Callable[..., None]
    log_memory_event: Callable[[str, str], None]
    archive_writer: ArchiveWriter | None
    archive_kind: str
    cognitive_write_enabled: bool = True
    continuity_witness_writer: ContinuityWitnessWriter | None = None
    lived_memory_store: LivedMemoryStore | None = None


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


def _fractal_episode_id(doc_id: str | None) -> Optional[str]:
    if not doc_id:
        return None
    text = str(doc_id)
    if not text.startswith("cmem:ep:"):
        return None
    base = text.split(":chunk", 1)[0]
    episode_id = base[len("cmem:ep:") :]
    return episode_id or None


def _constraint_patterns(record: Dict[str, Any]) -> List[str]:
    meta = record.get("metadata") or {}
    raw = meta.get("patterns")
    if isinstance(raw, (list, tuple, set)):
        patterns = [str(item).strip() for item in raw if str(item).strip()]
        if patterns:
            return patterns
    text = str(record.get("text") or "").strip()
    return [text] if text else []


def _constraint_match(query: str, pattern: str, mode: str) -> bool:
    if not pattern:
        return False
    query_text = query.strip()
    if not query_text:
        return False
    mode_value = (mode or "contains").strip().lower()
    if mode_value == "exact":
        return query_text.lower() == pattern.lower()
    if mode_value == "regex":
        try:
            return re.search(pattern, query_text, flags=re.IGNORECASE) is not None
        except re.error:
            return False
    return pattern.lower() in query_text.lower()


def _evaluate_constraints(
    query: str, constraints: List[Dict[str, Any]]
) -> Dict[str, Any]:
    applied: List[Dict[str, Any]] = []
    violations: List[Dict[str, Any]] = []
    for record in constraints:
        kind = str(record.get("kind") or "forbid").strip().lower()
        meta = record.get("metadata") or {}
        match_mode = str(meta.get("match_mode") or "contains")
        patterns = _constraint_patterns(record)
        matched = any(
            _constraint_match(query, pattern, match_mode) for pattern in patterns
        )
        entry = {
            "id": record.get("id"),
            "scope": record.get("scope") or "global",
            "kind": kind,
            "status": record.get("status") or "active",
            "matched": matched,
            "match_mode": match_mode,
            "patterns": patterns,
        }
        applied.append(entry)
        if kind == "forbid" and matched:
            violations.append(entry)
        elif kind == "require" and patterns and not matched:
            violations.append(entry)
    return {"applied": applied, "violations": violations}


def _apply_fractal_influence(
    candidates: List[Dict[str, Any]],
    score_map: Dict[str, float],
    *,
    alpha: float,
    enabled: bool,
) -> List[Dict[str, Any]]:
    if not enabled or not score_map or alpha == 0.0:
        return candidates
    for cand in candidates:
        base_score = float(cand.get("score", 0.0))
        episode_id = _fractal_episode_id(cand.get("doc_id"))
        fractal_score = float(score_map.get(episode_id, 0.0)) if episode_id else 0.0
        influence = alpha * fractal_score
        cand["base_score"] = base_score
        cand["fractal_score"] = fractal_score
        cand["fractal_influence"] = influence
        cand["score"] = base_score + influence
    return candidates


def _fractal_replay_payloads(
    cognitive_store: CognitiveMemoryStore,
    scores: List[Dict[str, Any]],
    max_nodes: int = 24,
) -> List[Dict[str, Any]]:
    store = cognitive_store.fractal_trace_store()
    if store is None:
        return []
    payloads: List[Dict[str, Any]] = []
    for item in scores:
        episode_id = item.get("episode_id")
        if not episode_id:
            continue
        bundle = store.load_trace(str(episode_id))
        if bundle is None:
            if not cognitive_store.ensure_fractal_trace(str(episode_id)):
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


def _fractal_bound_episode_ids(cognitive_store: CognitiveMemoryStore) -> set[str]:
    """Read the same episode identity domain used by cognitive search once."""
    # _load_episode_record uses this iterator too, but calling it for every
    # trace would rescan the whole episode file. I/O/schema failures propagate;
    # neither an unavailable store nor a metadata hint establishes a binding.
    return {
        str(record["id"])
        for record in cognitive_store._iter_jsonl(cognitive_store.FILE_EPISODES)
        if record.get("id") is not None and str(record["id"])
    }


def _fractal_trace_scores(
    cognitive_store: CognitiveMemoryStore,
    query_vector: Sequence[float] | None,
    limit: int,
    cfg: Any,
) -> List[Dict[str, Any]]:
    if not getattr(cfg, "fractal_enabled", False):
        return []
    if query_vector is None:
        return []
    store = cognitive_store.fractal_trace_store()
    if store is None:
        return []
    vector = np.asarray(query_vector, dtype=float).ravel()
    if vector.size == 0:
        return []
    target_dim = getattr(store.generator, "embedding_dim", vector.size)
    if vector.size != target_dim:
        return []
    bound_episode_ids = None
    if getattr(cfg, "fractal_influence_enabled", False):
        bound_episode_ids = _fractal_bound_episode_ids(cognitive_store)
        if not bound_episode_ids:
            return []
    scoring_mode = getattr(cfg, "fractal_scoring_mode", "legacy")
    if scoring_mode == "source_frame":
        from fram_serving.fractal_memory.source_frame import score_source_frames

        if getattr(cfg, "fractal_quat_influence", False):
            raise ValueError("source-frame scoring does not support quaternion influence")
        return score_source_frames(
            store, vector, limit,
            alpha=float(getattr(cfg, "fractal_blend_alpha", 0.4)),
            bound_episode_ids=bound_episode_ids,
        )
    if scoring_mode != "legacy":
        raise ValueError("unknown fractal scoring mode")
    window = max(1, min(int(limit), 16))
    try:
        alpha = float(
            getattr(cfg, "fractal_blend_alpha", DEFAULT_CFG.fractal_blend_alpha)
        )
    except Exception:
        alpha = DEFAULT_CFG.fractal_blend_alpha
    alpha = max(0.0, min(1.0, alpha))
    try:
        downsample_target = int(
            getattr(
                cfg, "fractal_downsample_target", DEFAULT_CFG.fractal_downsample_target
            )
        )
    except Exception:
        downsample_target = DEFAULT_CFG.fractal_downsample_target
    if downsample_target <= 0:
        downsample_target = DEFAULT_CFG.fractal_downsample_target
    try:
        quat_weight = float(
            getattr(cfg, "fractal_quat_weight", DEFAULT_CFG.fractal_quat_weight)
        )
    except Exception:
        quat_weight = DEFAULT_CFG.fractal_quat_weight
    quat_weight = max(0.0, min(1.0, quat_weight))
    quat_enabled = bool(
        getattr(cfg, "fractal_quat_influence", DEFAULT_CFG.fractal_quat_influence)
    )
    quat_use_lambda = bool(
        getattr(cfg, "fractal_quat_use_lambda", DEFAULT_CFG.fractal_quat_use_lambda)
    )
    projection_cache: dict[Optional[int], np.ndarray] = {}
    path_cache: dict[tuple[Optional[int], int], np.ndarray] = {}
    quat_cache: dict[tuple[Optional[int], int], np.ndarray] = {}
    entries: List[Dict[str, Any]] = []
    for trace_line, metadata in store.iter_traces():
        # Unresolved historical traces remain available for observation/replay.
        # They cannot influence ranking or consume its normalization/top-k slots.
        if (
            bound_episode_ids is not None
            and str(trace_line.seed_id) not in bound_episode_ids
        ):
            continue
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


def _apply_phase_d_memory_bridge(
    cfg: Any,
    orchestrator: QueryOrchestrator,
    query_text: str,
    candidates: List[Dict[str, Any]],
    debug: bool,
) -> tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    phase_d_cfg = getattr(cfg, "phase_d", None)
    if phase_d_cfg is None:
        return candidates, None
    if not getattr(phase_d_cfg, "enabled", False) or not getattr(
        phase_d_cfg, "enable_memory_bridge", False
    ):
        return candidates, None
    if phase_d_score_batch is None or not hasattr(
        orchestrator, "get_embeddings_for_shortlist"
    ):
        return candidates, None
    shortlist_payload = [{"text": c.get("text", "")} for c in candidates]
    try:
        query_embedding, episode_embeddings = orchestrator.get_embeddings_for_shortlist(
            query_text, shortlist_payload
        )
    except Exception:
        query_embedding, episode_embeddings = ([], [])
    if not query_embedding or not episode_embeddings:
        return candidates, None
    try:
        result = phase_d_score_batch(
            query_embedding=query_embedding,
            episode_embeddings=episode_embeddings,
            phase_d_enabled=True,
            phase_d_debug=bool(debug),
        )
        scores = result.get("scores") or []
        for cand, pd_score in zip(candidates, scores):
            cand["phase_d_score"] = float(pd_score)
        diag = None
        if debug:
            diag = (result.get("diagnostics") or {}).get("phase_d")
        return candidates, diag
    except Exception:
        return candidates, None


def run_query(req: Any, ctx: QueryContext) -> Dict[str, Any]:
    """Shared /query helper used by FastAPI and MCP surfaces."""
    CFG = ctx.cfg
    phase_d_cfg = getattr(CFG, "phase_d", None)
    _COG_STORE = ctx.cognitive_store
    _MEMORY_STORE = ctx.memory_store
    _get_memory_vectorizer = ctx.get_memory_vectorizer
    _encode_cognitive_text = ctx.encode_cognitive_text
    _capsule_store = ctx.capsule_store
    _apply_pd_bridge = lambda text, cands, debug: ctx.apply_phase_d_memory_bridge(
        text, cands, debug
    )
    _cooldown_active = ctx.cooldown_active
    _register_cooldown = ctx.register_cooldown
    _COOLDOWN_WINDOW = ctx.cooldown_window
    _resolve_time_sensitivity = ctx.resolve_time_sensitivity
    _ensure_doc_cache = ctx.ensure_doc_cache
    _log_memory_event = ctx.log_memory_event
    _store_prob = ctx.store_prob

    obs_dir = ctx.observability_dir
    t_start = time.perf_counter()
    clock_local = datetime.now()
    clock_utc = datetime.now(timezone.utc)
    clock_payload = {
        "local_iso": clock_local.isoformat(),
        "utc_iso": clock_utc.isoformat(),
        "epoch_seconds": int(clock_utc.timestamp()),
    }

    # full query logic is appended below; this stub will be expanded in-place.
    as_of_dt: Optional[datetime] = None
    if getattr(req, "as_of", None):
        try:
            as_of_dt = datetime.fromisoformat(req.as_of)
        except ValueError as exc:
            raise ValueError("invalid as_of") from exc
        if as_of_dt.tzinfo is None:
            as_of_dt = as_of_dt.replace(tzinfo=timezone.utc)
        else:
            as_of_dt = as_of_dt.astimezone(timezone.utc)

    orchestrator = ctx.orchestrator
    session_memory_chunks = None
    memory_trace = None
    memory_entries: List[dict] | None = None

    if getattr(req, "memory_session", None):
        memory_info = _MEMORY_STORE.session_info(req.memory_session)
        status = str(memory_info.get("status", WorkingMemoryStore.STATUS_ACTIVE))
        entries = _MEMORY_STORE.list(req.memory_session)
        available = len(entries)
        memory_entries = entries
        if status == WorkingMemoryStore.STATUS_ACTIVE and entries:
            session_memory_chunks = _MEMORY_STORE.session_chunks(
                req.memory_session, entries
            )
            used = len(session_memory_chunks)
        elif status == WorkingMemoryStore.STATUS_ACTIVE:
            session_memory_chunks = []
            used = 0
        else:
            used = 0
        memory_trace = {
            "session": req.memory_session,
            "status": status,
            "available": available,
            "used": used,
            "clock": clock_payload,
        }

    doc_cache = _ensure_doc_cache()
    budget_raw = getattr(req, "budget_reads", None)
    if budget_raw is None:
        budget_raw = getattr(req, "budget", None)
    if budget_raw is None:
        default_reads = int(
            getattr(CFG, "default_query_reads", DEFAULT_CFG.default_query_reads)
        )
    else:
        try:
            default_reads = int(budget_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid budget_reads") from exc
    if default_reads <= 0:
        default_reads = 1
    slot_budget_raw = getattr(CFG, "cognitive_memory_slot_budget", None)
    slot_budget: Optional[int] = None
    if slot_budget_raw is not None:
        try:
            slot_budget = int(slot_budget_raw)
        except Exception:
            slot_budget = None
    if slot_budget is None:
        memory_slot_budget = max(0, default_reads - 1)
        unlimited_slots = False
    elif slot_budget <= 0:
        memory_slot_budget = 0
        unlimited_slots = True
    else:
        memory_slot_budget = slot_budget
        unlimited_slots = False
    slot_budget_report = None if unlimited_slots else memory_slot_budget
    if session_memory_chunks is not None:
        if unlimited_slots:
            session_memory_chunks = list(session_memory_chunks)
        elif memory_slot_budget > 0:
            session_memory_chunks = list(session_memory_chunks[:memory_slot_budget])
        else:
            session_memory_chunks = []
        if not unlimited_slots:
            memory_slot_budget = max(0, memory_slot_budget - len(session_memory_chunks))

    domain_candidate = (
        getattr(req, "domain", None)
        if getattr(req, "domain", None) is not None
        else getattr(CFG, "default_domain", None)
    )
    domain_value = (
        domain_candidate.strip().lower()
        if isinstance(domain_candidate, str) and domain_candidate.strip()
        else "general"
    )
    task_candidate = (
        getattr(req, "task", None)
        if getattr(req, "task", None) is not None
        else getattr(CFG, "default_task", None)
    )
    task_value = (
        task_candidate.strip().lower()
        if isinstance(task_candidate, str) and task_candidate.strip()
        else "qa"
    )
    time_sensitivity = _resolve_time_sensitivity(task_value, domain_value)

    fractal_query_vector, fractal_backend = _encode_cognitive_text(req.text)
    fractal_influence_enabled = bool(
        getattr(CFG, "fractal_influence_enabled", False)
        and getattr(CFG, "fractal_enabled", False)
    )
    fractal_influence_alpha = float(
        getattr(CFG, "fractal_influence_alpha", DEFAULT_CFG.fractal_influence_alpha)
    )
    fractal_influence_scores: Dict[str, float] = {}
    fractal_scores: List[Dict[str, Any]] = []
    fractal_requested = 0
    fractal_replay: List[Dict[str, Any]] = []
    if getattr(CFG, "fractal_enabled", False):
        try:
            fractal_requested = max(
                0,
                int(
                    getattr(
                        CFG,
                        "cognitive_memory_trace_k",
                        DEFAULT_CFG.cognitive_memory_trace_k,
                    )
                ),
            )
        except Exception:
            fractal_requested = int(DEFAULT_CFG.cognitive_memory_trace_k)
        if (
            fractal_influence_enabled
            and fractal_requested > 0
            and fractal_query_vector is not None
        ):
            fractal_scores = _fractal_trace_scores(
                _COG_STORE, fractal_query_vector, fractal_requested, CFG
            )
            for item in fractal_scores:
                episode_id = item.get("episode_id")
                if not episode_id:
                    continue
                try:
                    fractal_influence_scores[str(episode_id)] = float(
                        item.get("score", 0.0)
                    )
                except (TypeError, ValueError):
                    fractal_influence_scores[str(episode_id)] = 0.0

    memory_backend = str(
        getattr(
            CFG,
            "cognitive_memory_embedding_backend",
            DEFAULT_CFG.cognitive_memory_embedding_backend,
        )
    ).lower()
    cognitive_event: Dict[str, Any] | None = None
    cog_trace_selected: List[Dict[str, Any]] = []
    results_count = 0
    situation_context = None
    try:
        k_cog = int(getattr(CFG, "cognitive_memory_k", DEFAULT_CFG.cognitive_memory_k))
    except Exception:
        k_cog = int(DEFAULT_CFG.cognitive_memory_k)
    cog_chunks: List[Dict[str, Any]] = []
    if k_cog > 0:
        try:
            recent_turn_texts = [
                str(entry.get("text", ""))
                for entry in (memory_entries or [])
                if entry.get("text")
            ]
            from fram_serving.semantic import build_situation

            situation_context = build_situation(
                req.text,
                task=task_value,
                domain=domain_value,
                recent_turns=recent_turn_texts[-5:],
                clock=clock_payload,
            )
            search_text = situation_context.text if situation_context else req.text
            search_diag: Dict[str, Any] = {}
            results = _COG_STORE.search(
                search_text,
                k=k_cog,
                vectorizer=_get_memory_vectorizer(),
                diagnostics=search_diag,
            )
            lived_recall: List[Dict[str, Any]] = []
            if (
                bool(getattr(CFG, "lived_memory_enabled", False))
                and ctx.lived_memory_store is not None
                and fractal_query_vector is not None
            ):
                try:
                    lived_recall = ctx.lived_memory_store.search(
                        fractal_query_vector,
                        k=max(1, int(getattr(CFG, "lived_memory_recall_k", 4))),
                        scan_limit=max(
                            1, int(getattr(CFG, "lived_memory_scan_limit", 5000))
                        ),
                    )
                except Exception as exc:
                    search_diag["lived_memory_error"] = str(exc)
            if lived_recall:
                results = list(results) + lived_recall
                search_diag["lived_memory_count"] = len(lived_recall)
            results_count = len(results)
            try:
                token_budget = int(
                    getattr(
                        CFG,
                        "cognitive_memory_token_budget",
                        DEFAULT_CFG.cognitive_memory_token_budget,
                    )
                )
            except Exception:
                token_budget = int(DEFAULT_CFG.cognitive_memory_token_budget)
            unlimited_budget = token_budget <= 0
            candidates: List[Dict[str, Any]] = []
            skipped_due_to_cooldown: List[str] = []
            for item in results:
                kind = str(item.get("kind", ""))
                score = float(item.get("_score", 0.0))
                score_raw = float(item.get("_score_raw", score))
                if kind == "lived":
                    # Search/API scores shift cosine to [0, 1]. Mixed ranking
                    # uses its unshifted blend, without a lived-only +0.5 prior.
                    score = score_raw
                recency_weight = float(item.get("_recency_weight", 1.0))
                last_seen = item.get("last_seen")
                if kind == "episode":
                    ep_id = str(item.get("id"))
                    doc_id = f"cmem:ep:{ep_id}"
                    q = str(item.get("query") or "")
                    a = str(item.get("answer") or "")
                    text = (f"Q: {q}\nA: {a}").strip()
                elif kind == "belief":
                    bl_id = str(item.get("id"))
                    doc_id = f"cmem:bl:{bl_id}"
                    text = str(item.get("text") or "")
                elif kind == "lived":
                    event_id = str(item.get("event_id") or item.get("id"))
                    doc_id = f"lmem:event:{event_id}"
                    q = str(item.get("query") or "")
                    a = str(item.get("answer") or "")
                    text = (f"Lived Q: {q}\nLived A: {a}").strip()
                else:
                    continue
                lineage = item.get("lineage") if isinstance(item, dict) else None
                if _cooldown_active(doc_id, clock_utc):
                    skipped_due_to_cooldown.append(doc_id)
                    continue
                tokens = tokenize_text(text)
                tcount = len(tokens)
                ratio = score / max(1.0, float(tcount))
                candidates.append(
                    {
                        "kind": kind,
                        "doc_id": doc_id,
                        "text": text,
                        "tokens": tokens,
                        "tcount": tcount,
                        "score": score,
                        "score_raw": score_raw,
                        "recency_weight": recency_weight,
                        "last_seen": last_seen,
                        "affect_score": (
                            float(item.get("affect_score", 0.5))
                            if isinstance(item, dict)
                            else 0.5
                        ),
                        "quality_score": (
                            float(item.get("quality_score", 0.5))
                            if isinstance(item, dict)
                            else 0.5
                        ),
                        "coherence_score": (
                            float(item.get("coherence_score", 0.5))
                            if isinstance(item, dict)
                            else 0.5
                        ),
                        "ratio": ratio,
                        "lineage": lineage,
                    }
                )
            total_tokens = 0
            selected_all: List[Dict[str, Any]] = []
            debug_phase_d = bool(getattr(phase_d_cfg, "debug_observability", False))
            candidates, phase_d_diag = _apply_pd_bridge(
                search_text, candidates, debug_phase_d
            )
            ann_bridge_obs: Optional[Dict[str, Any]] = None
            try:
                ann_enabled = bool(getattr(CFG, "enable_cognitive_ann_bridge", False))
            except Exception:
                ann_enabled = False
            if ann_enabled:
                try:
                    top_k_ann = max(0, int(getattr(CFG, "cognitive_ann_top_k", 0)))
                except Exception:
                    top_k_ann = 0
                try:
                    ann_weight = float(getattr(CFG, "cognitive_ann_weight", 1.0))
                except Exception:
                    ann_weight = 1.0
                ann_weight = max(0.0, min(5.0, ann_weight))
                try:
                    floor_boost = float(getattr(CFG, "cognitive_ann_floor_boost", 0.01))
                except Exception:
                    floor_boost = 0.01
                ann_cap = (
                    max(0, memory_slot_budget) if memory_slot_budget > 0 else top_k_ann
                )
                ann_candidates, ann_bridge_obs = _COG_STORE.cognitive_ann_candidates(
                    search_text,
                    vectorizer=_get_memory_vectorizer(),
                    top_k=top_k_ann,
                    weight=ann_weight,
                    floor_boost=floor_boost,
                    budget_cap=ann_cap if ann_cap >= 0 else None,
                )
                if memory_slot_budget > 0:
                    ann_cap = max(0, memory_slot_budget - len(candidates))
                else:
                    ann_cap = top_k_ann
                if ann_bridge_obs is not None:
                    ann_bridge_obs["budget_exhausted"] = ann_cap < len(ann_candidates)
                    ann_candidates = ann_candidates[:ann_cap] if ann_cap >= 0 else []
                if ann_candidates:
                    filtered_ann: List[Dict[str, Any]] = []
                    for ann in ann_candidates:
                        doc_id = str(ann.get("doc_id") or "")
                        if not doc_id:
                            continue
                        if _cooldown_active(doc_id, clock_utc):
                            if doc_id not in skipped_due_to_cooldown:
                                skipped_due_to_cooldown.append(doc_id)
                            continue
                        filtered_ann.append(ann)
                    ann_candidates = filtered_ann
                if ann_candidates:
                    existing = {c["doc_id"]: c for c in candidates}
                    for ann in ann_candidates:
                        doc_id = ann.get("doc_id")
                        combined = float(ann.get("combined_score", 0.0))
                        if doc_id in existing:
                            prev_score = float(existing[doc_id].get("score", 0.0))
                            if combined > prev_score:
                                existing[doc_id]["score"] = combined
                                existing[doc_id]["ann_similarity"] = ann.get(
                                    "ann_similarity"
                                )
                                existing[doc_id]["source"] = ann.get("source")
                                existing[doc_id]["origin"] = ann.get("origin")
                                existing[doc_id]["candidate_id"] = ann.get(
                                    "candidate_id", doc_id
                                )
                                if not existing[doc_id].get("version_id"):
                                    existing[doc_id]["version_id"] = (
                                        ann.get("version_id") or doc_id
                                    )
                        else:
                            candidate_id = ann.get("candidate_id") or doc_id
                            candidates.append(
                                {
                                    "kind": "episode",
                                    "doc_id": doc_id,
                                    "candidate_id": candidate_id,
                                    "version_id": ann.get("version_id") or doc_id,
                                    "text": "",
                                    "tokens": [],
                                    "tcount": 0,
                                    "score": combined,
                                    "score_raw": combined,
                                    "recency_weight": 1.0,
                                    "ratio": combined,
                                    "ann_similarity": ann.get("ann_similarity"),
                                    "source": ann.get("source"),
                                    "origin": ann.get("origin"),
                                }
                            )
                    if ann_bridge_obs is not None:
                        ann_bridge_obs["applied"] = True
                else:
                    ann_bridge_obs = {
                        "enabled": False,
                        "bridge_disabled_reason": "bridge_disabled",
                    }

            candidates = _apply_fractal_influence(
                candidates,
                fractal_influence_scores,
                alpha=fractal_influence_alpha,
                enabled=fractal_influence_enabled,
            )

            def _compute_age_seconds(c: Dict[str, Any]) -> Optional[float]:
                age_seconds = c.get("age_seconds")
                if age_seconds is None:
                    last_seen = c.get("last_seen")
                    if isinstance(last_seen, str):
                        try:
                            dt = datetime.fromisoformat(last_seen)
                            dt = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
                            age_seconds = max(0.0, (clock_utc - dt).total_seconds())
                        except Exception:
                            age_seconds = None
                return age_seconds

            def _color_adjustment(color_value: Any) -> float:
                if color_value is None:
                    return 0.0
                color = str(color_value).lower()
                if color == "saturated":
                    return 0.05
                if color == "bright":
                    return 0.03
                if color == "soft":
                    return 0.0
                if color == "dull":
                    return -0.03
                return 0.0

            if getattr(phase_d_cfg, "enabled", False) and getattr(
                phase_d_cfg, "enable_memory_bridge", False
            ):
                for cand in candidates:
                    age_seconds = _compute_age_seconds(cand)
                    cand["age_seconds"] = age_seconds
                    color_value = cand.get("alpha_color")
                    if color_value is None and phase_d_diag:
                        color_value = phase_d_diag.get("alpha_color")
                    rarity_score = None
                    if cand.get("seen_count") is not None:
                        try:
                            rarity_score = float(
                                1.0 / (1.0 + float(cand.get("seen_count")))
                            )
                        except Exception:
                            rarity_score = None
                    recency_factor = None
                    if age_seconds is not None:
                        try:
                            recency_factor = float(
                                np.clip(1.0 - 0.001 * float(age_seconds), 0.7, 1.0)
                            )
                        except Exception:
                            recency_factor = None
                    cand["phase_d_priority"] = compute_phase_d_priority(
                        affect_score=cand.get("affect_score", 0.5),
                        enable_affect=getattr(
                            phase_d_cfg, "enable_affect_weighting", True
                        ),
                        coherence_score=cand.get("coherence_score", 0.5),
                        enable_coherence=getattr(
                            phase_d_cfg, "enable_coherence_weighting", True
                        ),
                        quality_score=cand.get("quality_score", 0.5),
                        enable_quality=getattr(
                            phase_d_cfg, "enable_quality_weighting", True
                        ),
                        rarity_score=rarity_score,
                        enable_rarity=getattr(
                            phase_d_cfg, "enable_rarity_weighting", True
                        ),
                        recency_factor=recency_factor,
                        enable_recency=getattr(
                            phase_d_cfg, "enable_recency_weighting", True
                        ),
                        alpha_color_adjustment=_color_adjustment(color_value),
                        enable_alpha_color=getattr(
                            phase_d_cfg, "enable_alpha_color_weighting", True
                        ),
                        priority_clip_min=getattr(
                            phase_d_cfg, "priority_clip_min", 0.0
                        ),
                        priority_clip_max=getattr(
                            phase_d_cfg, "priority_clip_max", 2.0
                        ),
                        priority_normalize=getattr(
                            phase_d_cfg, "priority_normalize", False
                        ),
                    )
                candidates = apply_priority_graph(candidates, phase_d_cfg)
                for cand in candidates:
                    base_priority = float(cand.get("phase_d_priority", 1.0))
                    graph_priority = float(cand.get("graph_priority", base_priority))
                    blend_w = float(
                        getattr(phase_d_cfg, "memory_bridge_priority_weight", 0.5)
                    )
                    if not getattr(phase_d_cfg, "enable_memory_bridge_priority", True):
                        blend_w = 0.0
                    final_priority = (
                        1.0 - blend_w
                    ) * base_priority + blend_w * graph_priority
                    hysteresis_boost = 0.0
                    if getattr(phase_d_cfg, "enable_hysteresis", False):
                        prev_priority = float(cand.get("previous_priority", 0.0) or 0.0)
                        prev_selected = bool(
                            cand.get("previous_session_selected", False)
                        )
                        hysteresis_w = float(
                            getattr(phase_d_cfg, "hysteresis_weight", 0.0)
                        )
                        if prev_selected and hysteresis_w > 0.0:
                            hysteresis_boost = hysteresis_w * prev_priority
                            final_priority += hysteresis_boost
                        cand["previous_priority"] = prev_priority
                        cand["previous_session_selected"] = prev_selected
                    if getattr(phase_d_cfg, "enable_temporal_priority", False):
                        try:
                            from fram_serving.memory.forgetting import (
                                temporal_recency_score,
                            )
                        except Exception:
                            recency = 1.0
                        else:
                            recency = temporal_recency_score(
                                cand.get("age_seconds"),
                                float(
                                    getattr(
                                        phase_d_cfg, "temporal_decay_half_life", 3.0
                                    )
                                ),
                                float(getattr(phase_d_cfg, "temporal_min_floor", 0.2)),
                            )
                        temporal_w = float(
                            getattr(phase_d_cfg, "temporal_recency_weight", 0.0)
                        )
                        temporal_factor = (1.0 - temporal_w) + temporal_w * recency
                        final_priority *= temporal_factor
                        cand["recency_score"] = recency
                        cand["temporal_priority_factor"] = temporal_factor
                    final_priority = float(
                        np.clip(
                            final_priority,
                            getattr(phase_d_cfg, "priority_clip_min", 0.0),
                            getattr(phase_d_cfg, "priority_clip_max", 2.0),
                        )
                    )
                    cand["graph_priority"] = graph_priority
                    cand["final_priority_for_bridge"] = final_priority
                    cand["hysteresis_boost"] = hysteresis_boost

            def _cog_sort_key(c: Dict[str, Any]) -> tuple[float, float, float]:
                base = float(c["score"])
                weight = 1.0
                preserve_full_experience = bool(
                    getattr(CFG, "preserve_full_experience", True)
                )
                retention_enabled = (
                    bool(getattr(CFG, "enable_retention_curve", False))
                    and not preserve_full_experience
                )
                decay_enabled = (
                    bool(getattr(CFG, "enable_decay", False))
                    and not preserve_full_experience
                )
                forgetting_enabled = (
                    bool(getattr(CFG, "enable_hard_forgetting", False))
                    and not preserve_full_experience
                )
                age_seconds = (
                    _compute_age_seconds(c)
                    if (retention_enabled or decay_enabled)
                    else None
                )
                if retention_enabled and age_seconds is not None:
                    c["age_seconds"] = age_seconds
                    retention = compute_retention_score(
                        age_seconds=age_seconds, config=CFG
                    )
                    c["retention_score"] = retention
                    base *= retention
                if decay_enabled and age_seconds is not None:
                    try:
                        from fram_serving.memory.forgetting import compute_decay_factor
                    except Exception:
                        decay_factor = 1.0
                    else:
                        decay_factor = compute_decay_factor(
                            age_seconds=age_seconds, config=CFG
                        )
                    c["decay_factor"] = decay_factor
                    base *= decay_factor
                if forgetting_enabled and "age_seconds" not in c:
                    c["age_seconds"] = age_seconds
                if forgetting_enabled:
                    forget_score = base
                    c["forget_score"] = forget_score
                pd_score = c.get("phase_d_score")
                if (
                    pd_score is not None
                    and getattr(phase_d_cfg, "enabled", False)
                    and getattr(phase_d_cfg, "enable_memory_bridge", False)
                    and getattr(phase_d_cfg, "enable_memory_weighting", True)
                ):
                    age_seconds = _compute_age_seconds(c)
                    color_value = c.get("alpha_color")
                    if color_value is None and phase_d_diag:
                        color_value = phase_d_diag.get("alpha_color")
                    affect_value = c.get("affect_score", 0.5)
                    weight = phase_d_weight_for_cognitive(
                        phase_d_score=pd_score,
                        alpha_t=phase_d_diag.get("alpha_t") if phase_d_diag else None,
                        quat_avg=phase_d_diag.get("quat_avg") if phase_d_diag else None,
                        alpha_color=color_value,
                        seen_count=c.get("seen_count"),
                        age_seconds=age_seconds,
                        enable_alpha_color=getattr(
                            phase_d_cfg, "enable_alpha_color_weighting", True
                        ),
                        enable_rarity=getattr(
                            phase_d_cfg, "enable_rarity_weighting", True
                        ),
                        enable_recency=getattr(
                            phase_d_cfg, "enable_recency_weighting", True
                        ),
                        affect_score=affect_value,
                        enable_affect=getattr(
                            phase_d_cfg, "enable_affect_weighting", True
                        ),
                        coherence_score=c.get("coherence_score", 0.5),
                        enable_coherence=getattr(
                            phase_d_cfg, "enable_coherence_weighting", True
                        ),
                        quality_score=c.get("quality_score", 0.5),
                        enable_quality=getattr(
                            phase_d_cfg, "enable_quality_weighting", True
                        ),
                        priority_clip_min=getattr(
                            phase_d_cfg, "priority_clip_min", 0.0
                        ),
                        priority_clip_max=getattr(
                            phase_d_cfg, "priority_clip_max", 2.0
                        ),
                        priority_normalize=getattr(
                            phase_d_cfg, "priority_normalize", False
                        ),
                    )
                    if getattr(phase_d_cfg, "enable_memory_bridge_priority", True):
                        weight *= float(c.get("final_priority_for_bridge", 1.0))
                adjusted = base * weight
                return (-adjusted, -c["recency_weight"], -c["ratio"])

            for cand in sorted(candidates, key=_cog_sort_key):
                if (
                    not unlimited_budget
                    and total_tokens + cand["tcount"] > token_budget
                ):
                    continue
                if getattr(CFG, "enable_hard_forgetting", False):
                    try:
                        from fram_serving.memory.forgetting import (
                            ForgetDecision,
                            decide_forgetting,
                        )
                    except Exception:
                        pass
                    else:
                        decision = decide_forgetting(
                            cand,
                            {
                                "forget_score": cand.get("forget_score"),
                                "retention_score": cand.get("retention_score", 1.0),
                                "decay_factor": cand.get("decay_factor", 1.0),
                            },
                            CFG,
                            active_count=len(candidates),
                        )
                        cand["forgetting_decision"] = decision.value
                        cand["forgetting_threshold"] = float(
                            getattr(CFG, "forgetting_threshold", 0.05)
                        )
                        cand["hard_forgetting_mode"] = str(
                            getattr(CFG, "hard_forgetting_mode", "dry_run")
                        )
                        cand["min_active_items"] = int(
                            getattr(CFG, "min_active_items", 0)
                        )
                        cand["active_count"] = len(candidates)
                        if decision == ForgetDecision.FORGET_ENFORCE:
                            continue
                selected_all.append(cand)
                total_tokens += cand["tcount"]

            phase_d_memory_block: Optional[Dict[str, Any]] = None
            if getattr(phase_d_cfg, "enabled", False) and getattr(
                phase_d_cfg, "enable_memory_bridge", False
            ):
                scored = [c for c in selected_all if c.get("phase_d_score") is not None]
                if scored:
                    phase_d_memory_block = {
                        "enabled": True,
                        "debug": debug_phase_d,
                        "scored": len(scored),
                        "scores": [
                            {"id": c.get("doc_id"), "score": c.get("phase_d_score")}
                            for c in scored[: memory_slot_budget or len(scored)]
                        ],
                        "priority": [
                            {
                                "id": c.get("doc_id"),
                                "phase_d_priority": c.get("phase_d_priority"),
                                "graph_priority": c.get("graph_priority"),
                                "final_priority": c.get("final_priority_for_bridge"),
                                "temporal_factor": c.get("temporal_priority_factor"),
                                "hysteresis_boost": c.get("hysteresis_boost"),
                                "previous_priority": c.get("previous_priority"),
                                "previous_session_selected": c.get(
                                    "previous_session_selected"
                                ),
                            }
                            for c in scored[: memory_slot_budget or len(scored)]
                        ],
                    }
                    if getattr(CFG, "enable_retention_curve", False):
                        half_life_days = float(
                            getattr(CFG, "retention_half_life_days", 30.0)
                        )
                        retention_entries = []
                        for c in scored:
                            if "retention_score" not in c:
                                continue
                            retention_entries.append(
                                {
                                    "id": c.get("doc_id"),
                                    "retention_score": c.get("retention_score"),
                                    "age_seconds": c.get("age_seconds"),
                                    "half_life_days": half_life_days,
                                }
                            )
                        if retention_entries:
                            phase_d_memory_block["retention"] = retention_entries
                            phase_d_memory_block["retention_half_life_days"] = (
                                half_life_days
                            )
                    if getattr(CFG, "enable_decay", False):
                        forgetting_half_life = float(
                            getattr(CFG, "forgetting_half_life_days", 30.0)
                        )
                        decay_entries = []
                        for c in scored:
                            if "decay_factor" not in c:
                                continue
                            decay_entries.append(
                                {
                                    "id": c.get("doc_id"),
                                    "decay_factor": c.get("decay_factor"),
                                    "age_seconds": c.get("age_seconds"),
                                    "half_life_days": forgetting_half_life,
                                    "retention_score": c.get("retention_score"),
                                }
                            )
                        if decay_entries:
                            phase_d_memory_block["decay"] = decay_entries
                            phase_d_memory_block["forgetting_half_life_days"] = (
                                forgetting_half_life
                            )
                    if getattr(CFG, "enable_hard_forgetting", False):
                        forget_entries = []
                        for c in scored:
                            decision = c.get("forgetting_decision")
                            if not decision:
                                continue
                            forget_entries.append(
                                {
                                    "id": c.get("doc_id"),
                                    "decision": decision,
                                    "forget_score": c.get("forget_score"),
                                    "retention_score": c.get("retention_score"),
                                    "decay_factor": c.get("decay_factor"),
                                    "threshold": getattr(
                                        CFG, "forgetting_threshold", 0.05
                                    ),
                                    "mode": getattr(
                                        CFG, "hard_forgetting_mode", "dry_run"
                                    ),
                                    "active_count": len(scored),
                                    "min_active_items": getattr(
                                        CFG, "min_active_items", 0
                                    ),
                                }
                            )
                        if forget_entries:
                            phase_d_memory_block["forgetting_snapshot"] = forget_entries
                    if phase_d_diag:
                        phase_d_memory_block.update(
                            {
                                "alpha_t": phase_d_diag.get("alpha_t"),
                                "alpha_color": phase_d_diag.get("alpha_color"),
                                "quat_avg": phase_d_diag.get("quat_avg"),
                            }
                        )
            selected: List[Dict[str, Any]]
            selected = []
            dropped = 0
            if unlimited_slots:
                selected = selected_all
                dropped = 0
            elif memory_slot_budget > 0:
                selected = selected_all[:memory_slot_budget]
                dropped = max(0, len(selected_all) - len(selected))
                memory_slot_budget = max(0, memory_slot_budget - len(selected))
            else:
                dropped = len(selected_all)
            cognitive_event = {
                "backend": memory_backend,
                "k_requested": k_cog,
                "results": results_count,
                "token_budget": None if unlimited_budget else token_budget,
                "token_budget_unlimited": unlimited_budget,
                "slot_budget": slot_budget_report,
                "slot_budget_unlimited": unlimited_slots,
                "domain": domain_value,
                "task": task_value,
                "time_sensitivity": time_sensitivity,
                "query_preview": search_text[:200],
                "situation": situation_context.as_dict() if situation_context else None,
                "cooldowns_skipped": skipped_due_to_cooldown,
                "selected_total": len(selected_all),
                "selected_used": len(selected),
                "selected_dropped": dropped,
                "fractal_influence": {
                    "enabled": fractal_influence_enabled,
                    "alpha": fractal_influence_alpha,
                },
                "selected": [
                    {
                        "id": c["doc_id"],
                        "kind": c["kind"],
                        "score": c["score"],
                        "score_raw": c["score_raw"],
                        "base_score": float(c.get("base_score", c["score"])),
                        "fractal_score": float(c.get("fractal_score", 0.0)),
                        "fractal_influence": float(c.get("fractal_influence", 0.0)),
                        "combined_score": float(c["score"]),
                        "recency_weight": c["recency_weight"],
                        "phase_d_score": c.get("phase_d_score"),
                        "lineage": c.get("lineage"),
                        "tokens": c["tcount"],
                        "time_sensitivity": time_sensitivity,
                    }
                    for c in selected
                ],
            }
            if ann_bridge_obs is not None:
                cognitive_event["ann_bridge"] = ann_bridge_obs
                if ann_bridge_obs.get("candidates"):
                    cognitive_event["ann_bridge"]["sorted_shortlist_preview"] = [
                        {
                            "id": c.get("doc_id"),
                            "combined_score": c.get("combined_score"),
                            "ann_similarity": c.get("ann_similarity"),
                        }
                        for c in ann_bridge_obs.get("candidates", [])[:5]
                    ]
            try:
                observability.update_memory_search_window(
                    ctx.observability_dir,
                    {
                        "query_preview": search_text[:200],
                        "backend": memory_backend,
                        "results": results_count,
                        "selected_total": len(selected_all),
                        "selected_used": len(selected),
                        "selected_dropped": dropped,
                        "token_budget": None if unlimited_budget else token_budget,
                        "slot_budget": slot_budget_report,
                        "ann_enabled": search_diag.get("ann_enabled"),
                        "ann_returned": search_diag.get("ann_returned"),
                        "ann_backend": search_diag.get("ann_backend"),
                        "ann_requested": search_diag.get("ann_requested"),
                        "ann_index_size": search_diag.get("ann_index_size"),
                        "ann_reason": search_diag.get("ann_reason"),
                    },
                )
            except Exception:
                pass
            if phase_d_memory_block:
                cognitive_event["phase_d_memory"] = phase_d_memory_block

            for idx, cand in enumerate(selected):
                claims = extract_claims(
                    cand["text"], doc_id=cand["doc_id"], chunk_id=idx
                )
                cog_chunks.append(
                    {
                        "file": cand["doc_id"],
                        "chunk_id": idx,
                        "text": cand["text"],
                        "tokens": cand["tokens"],
                        "kind": cand["kind"],
                        "version_id": cand.get("version_id") or cand["doc_id"],
                        "source": "cognitive_memory",
                        "last_seen": cand.get("last_seen"),
                        "time_sensitivity": time_sensitivity,
                        "score": cand["score"],
                        "recency_weight": cand["recency_weight"],
                        "phase_d_score": cand.get("phase_d_score"),
                        "claims": claims,
                        "hierarchy": {
                            "cluster": cand["doc_id"],
                            "segment": f"{cand['doc_id']}:item:{idx}",
                            "chunk": f"chunk:{idx}",
                        },
                    }
                )
            try:
                trace_k = int(getattr(CFG, "cognitive_memory_trace_k", 3))
            except Exception:
                trace_k = 3
            cog_trace_selected = [
                {
                    "id": c["doc_id"],
                    "kind": c["kind"],
                    "tokens": c["tcount"],
                    "score": c["score"],
                    "score_raw": c["score_raw"],
                    "base_score": float(c.get("base_score", c["score"])),
                    "fractal_score": float(c.get("fractal_score", 0.0)),
                    "fractal_influence": float(c.get("fractal_influence", 0.0)),
                    "combined_score": float(c["score"]),
                    "recency_weight": c["recency_weight"],
                }
                for c in selected[: max(0, trace_k)]
            ]
        except Exception:
            pass

    capsule_chunks: List[Dict[str, Any]] = []
    capsule_trace_selected: List[Dict[str, Any]] = []
    capsule_event: Dict[str, Any] | None = None
    if getattr(CFG, "memory_capsule_retrieval_enabled", False):
        if _capsule_store is None:
            capsule_event = {
                "enabled": False,
                "skipped": True,
                "reason": "capsule_store_unavailable",
            }
        else:
            try:
                capsule_k = int(
                    getattr(
                        CFG,
                        "memory_capsule_retrieval_k",
                        DEFAULT_CFG.memory_capsule_retrieval_k,
                    )
                )
            except Exception:
                capsule_k = int(DEFAULT_CFG.memory_capsule_retrieval_k)
            try:
                turns_per_capsule = int(
                    getattr(
                        CFG,
                        "memory_capsule_retrieval_turns_per_capsule",
                        DEFAULT_CFG.memory_capsule_retrieval_turns_per_capsule,
                    )
                )
            except Exception:
                turns_per_capsule = int(
                    DEFAULT_CFG.memory_capsule_retrieval_turns_per_capsule
                )
            if capsule_k <= 0:
                capsule_event = {
                    "enabled": False,
                    "skipped": True,
                    "reason": "capsule_k_disabled",
                }
            else:
                capsule_diag: Dict[str, Any] = {}
                capsule_results = _capsule_store.search(
                    req.text,
                    k=capsule_k,
                    vectorizer=_get_memory_vectorizer(),
                    vectorizer_backend=memory_backend,
                    turns_per_capsule=turns_per_capsule,
                    diagnostics=capsule_diag,
                )
                capsule_candidates: List[Dict[str, Any]] = []
                capsule_cooldowns: List[str] = []
                for item in capsule_results:
                    capsule_id = str(item.get("capsule_id") or "")
                    try:
                        turn_index = int(item.get("turn_index"))
                    except (TypeError, ValueError):
                        continue
                    doc_id = f"capsule:{capsule_id}:turn:{turn_index}"
                    if _cooldown_active(doc_id, clock_utc):
                        capsule_cooldowns.append(doc_id)
                        continue
                    text = str(item.get("text") or "")
                    if not text:
                        continue
                    tokens = tokenize_text(text)
                    tcount = len(tokens)
                    capsule_candidates.append(
                        {
                            "doc_id": doc_id,
                            "capsule_id": capsule_id,
                            "turn_index": turn_index,
                            "role": item.get("role"),
                            "text": text,
                            "tokens": tokens,
                            "tcount": tcount,
                            "score": float(item.get("score", 0.0)),
                            "score_raw": float(
                                item.get("score_raw", item.get("score", 0.0))
                            ),
                            "recency_weight": float(item.get("recency_weight", 1.0)),
                            "timestamp": item.get("time"),
                            "match_type": item.get("match_type"),
                            "capsule_path": item.get("capsule_path"),
                            "capsule_created_at": item.get("capsule_created_at"),
                            "embedding_backend": item.get("embedding_backend"),
                            "session_id": item.get("session_id"),
                        }
                    )
                selected_capsules: List[Dict[str, Any]] = []
                dropped_capsules = 0
                if unlimited_slots:
                    selected_capsules = capsule_candidates
                elif memory_slot_budget > 0:
                    selected_capsules = capsule_candidates[:memory_slot_budget]
                    dropped_capsules = max(
                        0, len(capsule_candidates) - len(selected_capsules)
                    )
                    memory_slot_budget = max(
                        0, memory_slot_budget - len(selected_capsules)
                    )
                else:
                    dropped_capsules = len(capsule_candidates)
                capsule_event = {
                    "enabled": True,
                    "k_requested": capsule_k,
                    "results": len(capsule_results),
                    "slot_budget": slot_budget_report,
                    "slot_budget_unlimited": unlimited_slots,
                    "selected_total": len(capsule_candidates),
                    "selected_used": len(selected_capsules),
                    "selected_dropped": dropped_capsules,
                    "cooldowns_skipped": capsule_cooldowns,
                    "diagnostics": capsule_diag,
                }
                for cand in selected_capsules:
                    claims = extract_claims(
                        cand["text"], doc_id=cand["doc_id"], chunk_id=cand["turn_index"]
                    )
                    capsule_chunks.append(
                        {
                            "file": f"capsule:{cand['capsule_id']}",
                            "chunk_id": cand["turn_index"],
                            "text": cand["text"],
                            "tokens": cand["tokens"],
                            "kind": "capsule_turn",
                            "version_id": cand["doc_id"],
                            "source": "memory_capsule",
                            "timestamp": cand.get("timestamp"),
                            "score": cand["score"],
                            "score_raw": cand["score_raw"],
                            "recency_weight": cand["recency_weight"],
                            "match_type": cand.get("match_type"),
                            "role": cand.get("role"),
                            "capsule_id": cand.get("capsule_id"),
                            "hierarchy": {
                                "cluster": f"capsule:{cand['capsule_id']}",
                                "segment": f"capsule:{cand['capsule_id']}:turn:{cand['turn_index']}",
                                "chunk": f"chunk:{cand['turn_index']}",
                            },
                            "claims": claims,
                        }
                    )
                capsule_trace_selected = [
                    {
                        "id": c["doc_id"],
                        "role": c.get("role"),
                        "tokens": c["tcount"],
                        "score": c["score"],
                        "score_raw": c["score_raw"],
                        "recency_weight": c["recency_weight"],
                        "match_type": c.get("match_type"),
                    }
                    for c in selected_capsules
                ]

    memory_chunks_for_orchestrator = None
    if session_memory_chunks is not None:
        memory_chunks_for_orchestrator = list(session_memory_chunks)
    if cog_chunks:
        memory_chunks_for_orchestrator = (
            memory_chunks_for_orchestrator or []
        ) + cog_chunks
    if capsule_chunks:
        memory_chunks_for_orchestrator = (
            memory_chunks_for_orchestrator or []
        ) + capsule_chunks

    constraint_records: List[Dict[str, Any]] = []
    try:
        constraint_records = ctx.cognitive_store.constraints_for_request(
            session_id=getattr(req, "memory_session", None),
            principal=getattr(req, "principal", None),
        )
    except Exception:
        constraint_records = []
    constraint_eval = _evaluate_constraints(req.text, constraint_records)
    if constraint_eval.get("violations"):
        refusal = "Request refused by constraint memory."
        record_id = uuid.uuid4().hex
        trace_payload: Dict[str, Any] = {
            "query_id": record_id,
            "trace_id": record_id,
            "constraint_memory": constraint_eval,
            "coverage": {},
            "confidence": {"decision": "constraint_refusal"},
            "refusal": {"kind": "constraint_violation", "message": refusal},
        }
        record = {
            "id": record_id,
            "time": datetime.now(timezone.utc).isoformat(),
            "query": req.text,
            "citations": [],
            "domain": domain_value,
            "task": task_value,
            "trace": trace_payload,
        }
        result = {
            "trace_id": record_id,
            "answer": refusal,
            "citations": [],
            "coverage": {},
            "record": record,
        }
    else:
        result = orchestrator.run(
            req.text,
            as_of_dt,
            budget_reads=default_reads,
            domain=domain_value,
            task=task_value,
            cache_override=doc_cache,
            memory_chunks=memory_chunks_for_orchestrator,
            version_id=getattr(req, "version_id", None),
        )
    if memory_trace is not None:
        if session_memory_chunks is not None:
            memory_trace["used"] = len(session_memory_chunks)
        result["record"]["trace"]["memory"] = memory_trace
        _log_memory_event(
            memory_trace.get("session", getattr(req, "memory_session", None)),
            "query",
            status=memory_trace.get("status"),
            available=memory_trace.get("available"),
            used=memory_trace.get("used"),
            clock=clock_payload,
        )
    record = result["record"]
    trace = record["trace"]
    if constraint_eval.get("applied") is not None:
        trace.setdefault("constraint_memory", constraint_eval)
    trace.setdefault(
        "memory_policy",
        {
            "preserve_full_experience": bool(
                getattr(CFG, "preserve_full_experience", True)
            )
        },
    )
    trace["clock"] = clock_payload
    latency = trace.setdefault("latency_ms", {})
    latency["total_ms"] = (time.perf_counter() - t_start) * 1000.0

    if getattr(CFG, "fractal_enabled", False):
        if fractal_requested <= 0:
            try:
                fractal_requested = max(
                    0,
                    int(
                        getattr(
                            CFG,
                            "cognitive_memory_trace_k",
                            DEFAULT_CFG.cognitive_memory_trace_k,
                        )
                    ),
                )
            except Exception:
                fractal_requested = int(DEFAULT_CFG.cognitive_memory_trace_k)
        if (
            fractal_requested > 0
            and fractal_query_vector is not None
            and not fractal_scores
        ):
            fractal_scores = _fractal_trace_scores(
                _COG_STORE, fractal_query_vector, fractal_requested, CFG
            )
        if fractal_scores and not fractal_replay:
            fractal_replay = _fractal_replay_payloads(_COG_STORE, fractal_scores)
    try:
        alpha_value = float(
            getattr(CFG, "fractal_blend_alpha", DEFAULT_CFG.fractal_blend_alpha)
        )
    except Exception:
        alpha_value = DEFAULT_CFG.fractal_blend_alpha
    alpha_value = max(0.0, min(1.0, alpha_value))
    try:
        downsample_target = int(
            getattr(
                CFG, "fractal_downsample_target", DEFAULT_CFG.fractal_downsample_target
            )
        )
    except Exception:
        downsample_target = int(DEFAULT_CFG.fractal_downsample_target)
    if downsample_target <= 0:
        downsample_target = int(DEFAULT_CFG.fractal_downsample_target)
    if fractal_scores:
        trace["fractal_memory"] = {
            "scores": fractal_scores,
            "k": len(fractal_scores),
            "requested": fractal_requested,
            "backend": fractal_backend,
            "replay": fractal_replay,
            "alpha": alpha_value,
            "normalization": "min_max",
            "downsample_target": downsample_target,
        }
        observability.log_fractal_memory_event(
            obs_dir,
            {
                "kind": "score",
                "query_id": record["id"],
                "k": len(fractal_scores),
                "requested": fractal_requested,
                "backend": fractal_backend,
                "top": fractal_scores,
                "alpha": alpha_value,
                "normalization": "min_max",
                "downsample_target": downsample_target,
                "replay_preview": [
                    {
                        "episode_id": item.get("episode_id"),
                        "nodes": len(item.get("nodes", [])),
                    }
                    for item in fractal_replay[: min(3, len(fractal_replay))]
                ],
                "clock": clock_payload,
            },
        )
    elif getattr(CFG, "fractal_enabled", False) and fractal_requested > 0:
        observability.log_fractal_memory_event(
            obs_dir,
            {
                "kind": "score",
                "query_id": record["id"],
                "k": 0,
                "requested": fractal_requested,
                "backend": fractal_backend,
                "alpha": alpha_value,
                "normalization": "min_max",
                "downsample_target": downsample_target,
                "clock": clock_payload,
            },
        )

    p_temp = trace.get("p_temp")
    if p_temp is not None:
        confidence_raw = trace.get("confidence")
        confidence_info = confidence_raw if isinstance(confidence_raw, dict) else {}
        calibration_raw = confidence_info.get("calibration")
        calibration_info = calibration_raw if isinstance(calibration_raw, dict) else {}
        tau1_used = float(calibration_info.get("tau1", CFG.tau1))
        tau2_used = float(calibration_info.get("tau2", CFG.tau2))
        source = calibration_info.get("source")
        temperature_value = None
        if calibration_info.get("temperature") is not None:
            try:
                temperature_value = float(calibration_info.get("temperature"))
            except (TypeError, ValueError):
                temperature_value = None
        domain_log = record.get("domain")
        task_log = record.get("task")

        _store_prob(
            record["id"],
            prob=float(p_temp),
            tau1=tau1_used,
            tau2=tau2_used,
            domain=domain_log,
            task=task_log,
            source=source,
            temperature=temperature_value,
        )

        payload = {
            "event": "decision",
            "query_id": record["id"],
            "decision": confidence_info.get("decision"),
            "prob": float(p_temp),
            "tau1": tau1_used,
            "tau2": tau2_used,
            "domain": domain_log,
            "task": task_log,
        }
        if source:
            payload["calibration_source"] = source
        if temperature_value is not None:
            payload["calibration_temperature"] = temperature_value
        observability.log_confidence_event(
            obs_dir,
            payload,
        )

    try:
        if "cog_trace_selected" in locals() and (cog_trace_selected or cognitive_event):
            trace["cognitive_memory"] = {
                "selected": cog_trace_selected,
                "token_budget": None if unlimited_budget else token_budget,
                "token_budget_unlimited": unlimited_budget,
                "slot_budget": slot_budget_report,
                "slot_budget_unlimited": unlimited_slots,
                "backend": memory_backend,
                "k_requested": k_cog,
                "results": results_count,
                "total_selected": (
                    len(cognitive_event.get("selected", []))
                    if cognitive_event
                    else len(cog_trace_selected)
                ),
                "clock": clock_payload,
                "fractal_influence": {
                    "enabled": fractal_influence_enabled,
                    "alpha": fractal_influence_alpha,
                },
            }
            if getattr(phase_d_cfg, "enabled", False) and getattr(
                phase_d_cfg, "enable_memory_bridge", False
            ):
                phase_d_block: Dict[str, Any] = {
                    "enabled": True,
                    "debug": bool(getattr(phase_d_cfg, "debug_observability", False)),
                }
                pd_scores = [
                    {"id": c.get("doc_id"), "score": c.get("phase_d_score")}
                    for c in selected_all
                    if c.get("phase_d_score") is not None
                ]
                if pd_scores:
                    phase_d_block["scores"] = pd_scores
                if "phase_d_diag" in locals() and phase_d_diag:
                    phase_d_block.update(
                        {
                            "alpha_t": phase_d_diag.get("alpha_t"),
                            "alpha_color": phase_d_diag.get("alpha_color"),
                            "quat_avg": phase_d_diag.get("quat_avg"),
                        }
                    )
                trace["cognitive_memory"]["phase_d_memory"] = phase_d_block
    except Exception:
        pass

    try:
        if capsule_trace_selected or capsule_event:
            capsule_trace: Dict[str, Any] = {
                "selected": capsule_trace_selected,
                "slot_budget": slot_budget_report,
                "slot_budget_unlimited": unlimited_slots,
                "backend": memory_backend,
                "clock": clock_payload,
            }
            if capsule_event:
                capsule_trace.update(
                    {
                        "enabled": capsule_event.get("enabled", False),
                        "k_requested": capsule_event.get("k_requested"),
                        "results": capsule_event.get("results"),
                        "selected_total": capsule_event.get("selected_total"),
                        "selected_used": capsule_event.get("selected_used"),
                        "selected_dropped": capsule_event.get("selected_dropped"),
                        "cooldowns_skipped": capsule_event.get("cooldowns_skipped"),
                        "diagnostics": capsule_event.get("diagnostics"),
                    }
                )
                if capsule_event.get("skipped"):
                    capsule_trace["skipped"] = True
                    capsule_trace["reason"] = capsule_event.get("reason")
            trace["memory_capsule"] = capsule_trace
    except Exception:
        pass

    if cognitive_event:
        event_payload = dict(cognitive_event)
        event_payload["query_id"] = record["id"]
        event_payload.setdefault(
            "selected_count", len(cognitive_event.get("selected", []))
        )
        event_payload["clock"] = clock_payload
        observability.log_cognitive_memory_event(obs_dir, event_payload)

    observability.log_latency_event(
        obs_dir,
        {"query_id": record["id"], "latency_ms": latency},
    )

    try:
        maxlen = max(1, int(getattr(CFG, "metrics_window", 500)))
        tc_payload = trace.get("transitional_complexity")
        if isinstance(tc_payload, dict):
            tc_entry = dict(tc_payload)
            tc_entry["query_id"] = record.get("id")
            tc_entry["time"] = clock_payload.get("utc_iso")
            observability.update_transitional_complexity_window(
                obs_dir, tc_entry, maxlen=maxlen
            )
        routing_payload = trace.get("tc_routing")
        if isinstance(routing_payload, dict):
            routing_entry = dict(routing_payload)
            routing_entry["query_id"] = record.get("id")
            routing_entry["time"] = clock_payload.get("utc_iso")
            observability.update_tc_routing_window(
                obs_dir, routing_entry, maxlen=maxlen
            )
    except Exception:
        pass

    tracer_obj = getattr(orchestrator, "tracer", None)
    mirror_needed = True
    if isinstance(tracer_obj, observability.TraceLogWriter):
        try:
            mirror_needed = tracer_obj._base_dir.resolve() != ctx.trace_dir.resolve()
        except Exception:
            mirror_needed = True
    if mirror_needed:
        try:
            observability.TraceLogWriter(ctx.trace_dir).write(record)
        except Exception:
            pass

    episode_id: Optional[str] = None
    archive_write: Dict[str, Any] | None = None
    embedding_values: List[float] | None = None
    embedding_backend: str | None = None
    cognitive_write_enabled = bool(getattr(ctx, "cognitive_write_enabled", True))
    if not cognitive_write_enabled:
        cognitive_write = {
            "ok": False,
            "skipped": True,
            "reason": "cognitive_write_disabled",
        }
    else:
        try:
            calib_info = {}
            conf_raw = trace.get("confidence")
            if isinstance(conf_raw, dict):
                c = conf_raw.get("calibration")
                if isinstance(c, dict):
                    calib_info = {
                        k: c[k]
                        for k in ("source", "tau1", "tau2", "temperature")
                        if k in c
                    }
            hierarchy_scales = (
                trace.get("hierarchy_scales") if isinstance(trace, dict) else None
            )
            extra_meta = (
                {"hierarchy_scales": hierarchy_scales} if hierarchy_scales else {}
            )
            if calib_info:
                extra_meta.update({"calibration": calib_info})
            combined_text = f"{req.text}\n{result.get('answer', '') or ''}".strip()
            embedding_values, embedding_backend = _encode_cognitive_text(
                combined_text or req.text
            )
            episode_record = _COG_STORE.append_episode(
                query=req.text,
                domain=record.get("domain"),
                task=record.get("task"),
                answer=result.get("answer", ""),
                citations=list(result.get("citations", []) or []),
                trace_id=record.get("id"),
                calibration=calib_info or None,
                metadata=extra_meta or None,
                embedding=embedding_values,
                embedding_backend=(
                    embedding_backend if embedding_values is not None else None
                ),
            )
            if isinstance(episode_record, dict):
                episode_id = (
                    str(episode_record.get("id"))
                    if episode_record.get("id") is not None
                    else None
                )
            cognitive_write = {"ok": True, "episode_id": episode_id}
        except Exception as exc:
            cognitive_write = {"ok": False, "error": str(exc)}
            if not isinstance(exc, MemoryWriteError) or not getattr(
                exc, "logged", False
            ):
                try:
                    observability.log_cognitive_memory_event(
                        obs_dir,
                        {
                            "kind": "episode_write_failed",
                            "query_id": record.get("id"),
                            "error": str(exc),
                            "clock": clock_payload,
                        },
                    )
                except Exception:
                    pass

    lived_memory_write: Dict[str, Any]
    if not bool(getattr(CFG, "lived_memory_enabled", False)):
        lived_memory_write = {"ok": False, "skipped": True, "reason": "disabled"}
    elif ctx.lived_memory_store is None:
        lived_memory_write = {
            "ok": False,
            "skipped": True,
            "reason": "store_unavailable",
        }
    elif not cognitive_write_enabled:
        lived_memory_write = {
            "ok": False,
            "skipped": True,
            "reason": "persistence_not_authorized",
        }
    else:
        try:
            if embedding_values is None:
                combined_text = f"{req.text}\n{result.get('answer', '') or ''}".strip()
                embedding_values, embedding_backend = _encode_cognitive_text(
                    combined_text or req.text
                )
            if embedding_values is None:
                lived_memory_write = {
                    "ok": False,
                    "skipped": True,
                    "reason": "embedding_unavailable",
                }
            else:
                lived_record = ctx.lived_memory_store.append_experience(
                    query=req.text,
                    answer=result.get("answer", "") or "",
                    embedding=embedding_values,
                    embedding_backend=embedding_backend,
                    session_id=getattr(req, "memory_session", None),
                    episode_id=episode_id,
                    trace_id=record.get("id"),
                    domain=record.get("domain"),
                    task=record.get("task"),
                    citations=list(result.get("citations", []) or []),
                    metadata={
                        "clock": clock_payload,
                        "cognitive_write": cognitive_write,
                    },
                    created_at=clock_payload.get("utc_iso"),
                )
                lived_memory_write = {
                    "ok": True,
                    "event_id": lived_record.get("event_id"),
                    "session_id": lived_record.get("session_id"),
                    "session_seq": lived_record.get("session_seq"),
                    "projection_dim": lived_record.get("projection_dim"),
                    "state_digest": lived_record.get("state_digest"),
                }
        except Exception as exc:
            lived_memory_write = {"ok": False, "error": str(exc)}
            _logger.exception("lived-memory append failed")

    if ctx.archive_writer is not None and cognitive_write.get("ok") and episode_id:
        try:
            request_payload = {
                "text": req.text,
                "as_of": getattr(req, "as_of", None),
                "budget_reads": default_reads,
                "domain": record.get("domain"),
                "task": record.get("task"),
                "memory_session": getattr(req, "memory_session", None),
            }
            response_payload = {
                "answer": result.get("answer", ""),
                "citations": list(result.get("citations", []) or []),
            }
            meta_payload = {
                "query_id": record.get("id"),
                "domain": record.get("domain"),
                "task": record.get("task"),
            }
            manifest_entry = ctx.archive_writer.append_event(
                kind=ctx.archive_kind or "query",
                request=request_payload,
                response=response_payload,
                trace_id=episode_id,
                meta=meta_payload,
            )
            archive_write = {
                "ok": True,
                "event_id": manifest_entry.get("event_id"),
                "trace_id": episode_id,
                "chain_hash": manifest_entry.get("chain_hash"),
            }
        except Exception as exc:
            archive_write = {"ok": False, "error": str(exc)}
    else:
        archive_write = {
            "ok": False,
            "skipped": True,
            "reason": "missing_trace_id_or_writer",
        }

    capsule_write: Dict[str, Any] | None = None
    if getattr(CFG, "memory_capsule_enabled", False):
        if _capsule_store is None:
            capsule_write = {
                "ok": False,
                "skipped": True,
                "reason": "capsule_store_unavailable",
            }
        elif not cognitive_write.get("ok"):
            capsule_write = {
                "ok": False,
                "skipped": True,
                "reason": "cognitive_write_failed",
            }
        else:
            try:
                backend = normalize_cognitive_backend(
                    getattr(CFG, "cognitive_memory_embedding_backend", "hashing")
                )
            except Exception:
                backend = "hashing"
            turns = build_capsule_turns(
                memory_entries=memory_entries,
                user_text=req.text,
                assistant_text=result.get("answer", "") or "",
                timestamp=clock_payload.get("utc_iso"),
                trace_id=record.get("id"),
            )
            source = {
                "kind": ctx.archive_kind or "query",
                "tool": "fram_serving",
                "version": CAPSULE_VERSION,
                "trace_id": record.get("id"),
                "episode_id": episode_id,
                "domain": record.get("domain"),
                "task": record.get("task"),
            }
            capsule_result = _capsule_store.write_capsule(
                turns=turns,
                session_id=getattr(req, "memory_session", None),
                source=source,
                vectorizer=_get_memory_vectorizer(),
                vectorizer_backend=backend,
                created_at=clock_payload.get("utc_iso"),
            )
            capsule_payload = capsule_result.get("capsule", {})
            capsule_write = {
                "ok": True,
                "capsule_id": capsule_payload.get("capsule_id"),
                "path": capsule_result.get("path"),
            }
    else:
        capsule_write = {"ok": False, "skipped": True, "reason": "disabled"}

    if archive_write and archive_write.get("ok"):
        try:
            update_rep(storage_root=Path(ctx.cfg.STORAGE_ROOT))
        except Exception:
            pass

    if isinstance(trace, dict):
        trace["cognitive_episode_write"] = cognitive_write
        trace["lived_memory_write"] = lived_memory_write
        if capsule_write is not None:
            trace["memory_capsule_write"] = capsule_write
        if archive_write is not None:
            trace["archive_write"] = archive_write
        # PIL first slice (WB-0008): observational only, behind FRAM_PIL_ENABLED.
        # Runs after selection, ranking, and every write; returns None when off.
        pil.attach_teach_to_trace(trace, CFG)

    # The witness is a finalized, sanitized observability sidecar. It is
    # deliberately emitted after every memory/archive outcome is known and is
    # never read by retrieval or ranking.
    if ctx.continuity_witness_writer is not None:
        active_gates = {
            "archive_write": ctx.archive_writer is not None,
            "cognitive_ann_bridge": bool(
                getattr(ctx.cfg, "enable_cognitive_ann_bridge", False)
            ),
            "cognitive_memory_write": bool(ctx.cognitive_write_enabled),
            "continuity_witness": True,
            "coverage_selection": True,
            "fractal_ranking": bool(
                getattr(ctx.cfg, "fractal_influence_enabled", False)
            ),
            "lived_memory": bool(
                getattr(ctx.cfg, "lived_memory_enabled", False)
                and ctx.lived_memory_store is not None
            ),
            "memory_capsule": bool(getattr(ctx.cfg, "memory_capsule_enabled", False)),
            "session_memory": bool(getattr(req, "memory_session", None)),
        }
        witness_source = {
            "trace_id": record["id"],
            "citations": list(result.get("citations", []) or []),
            "record": record,
        }
        try:
            witness = build_continuity_witness(
                witness_source,
                feature_enabled=True,
                expected_trace_id=str(record["id"]),
                source_state="available",
                active_gates=active_gates,
            )
            ctx.continuity_witness_writer.append(witness)
        except ContinuityWitnessWriteError as exc:
            # Observability is best-effort and must never change query behavior,
            # but a skipped sidecar remains visible to operators.
            _logger.warning("continuity witness append skipped: %s", exc)
        except Exception:
            _logger.exception("continuity witness projection failed")

    return {
        "id": record["id"],
        "answer": result["answer"],
        "citations": result["citations"],
        "trace": trace,
        "cognitive_episode_write_ok": bool(cognitive_write.get("ok")),
        "lived_memory_write_ok": bool(lived_memory_write.get("ok")),
    }
