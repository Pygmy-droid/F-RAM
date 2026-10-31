from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from fram_eval.conversation_memory_eval import (
    DEFAULT_DATASET,
    DEFAULT_LIVE_DATASET,
    build_eval_store,
    build_fractal_ranker,
    build_query_vectorizer,
    load_eval_items,
    resolve_live_id_map,
)
from fram_serving.config import FRAMConfig
from fram_serving.memory import CognitiveMemoryStore

DEFAULT_OUT = Path("storage/observability/memory_shadow_eval.json")
DEFAULT_LIVE_OUT = Path("storage/observability/memory_shadow_eval_live.json")


def _normalize(vec: np.ndarray) -> np.ndarray | None:
    if vec.size == 0:
        return None
    norm = float(np.linalg.norm(vec))
    if norm <= 0.0:
        return None
    return vec / norm


def _embed_text(text: str, *, vectorizer: Any | None) -> np.ndarray | None:
    if vectorizer is None:
        return None
    try:
        matrix = vectorizer.transform([text])
    except Exception:
        return None
    if hasattr(matrix, "toarray"):
        arr = matrix.toarray()
    else:
        arr = np.asarray(matrix, dtype=float)
    arr = np.asarray(arr, dtype=float)
    if arr.ndim == 2:
        arr = arr[0]
    vec = arr.astype(float, copy=False).ravel()
    return _normalize(vec)


def _load_episode_vectors(store: CognitiveMemoryStore) -> Dict[str, np.ndarray]:
    path = store.vector_path(kind="episode")
    if not path.exists():
        return {}
    vectors: Dict[str, np.ndarray] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            item_id = payload.get("id")
            raw_vec = payload.get("vector")
            if not item_id or raw_vec is None:
                continue
            arr = np.asarray(raw_vec, dtype=float).ravel()
            normed = _normalize(arr)
            if normed is None:
                continue
            vectors[str(item_id)] = normed
    return vectors


def _result_text(result: Dict[str, Any]) -> str:
    kind = str(result.get("kind") or "")
    if kind == "episode":
        q = str(result.get("query") or "")
        a = str(result.get("answer") or "")
        text = f"Q: {q}\nA: {a}".strip()
        return text
    if kind == "belief":
        return str(result.get("text") or "").strip()
    return ""


def _build_snippet(results: Sequence[Dict[str, Any]], *, memory_k: int, max_chars: int) -> Tuple[str, List[str]]:
    snippet_parts: List[str] = []
    used_ids: List[str] = []
    for result in results[: max(0, int(memory_k))]:
        text = _result_text(result)
        if not text:
            continue
        snippet_parts.append(text)
        item_id = result.get("id")
        if item_id:
            used_ids.append(str(item_id))
        if sum(len(part) for part in snippet_parts) >= max_chars:
            break
    snippet = "\n\n".join(snippet_parts)
    if len(snippet) > max_chars:
        snippet = snippet[:max_chars]
    return snippet, used_ids


def _cosine(a: np.ndarray | None, b: np.ndarray | None) -> Optional[float]:
    if a is None or b is None:
        return None
    if a.size == 0 or b.size == 0:
        return None
    return float(np.dot(a, b))


def evaluate_shadow(
    items: Sequence[Dict[str, str]],
    *,
    store: CognitiveMemoryStore,
    id_map: Dict[str, str],
    vectorizer: Any,
    modes: Sequence[str],
    fields: Sequence[str],
    kinds: Sequence[str] | None = None,
    memory_k: int = 3,
    k_values: Iterable[int] = (1, 3),
    pool_multiplier: int = 1,
    fractal_alpha: float | None = None,
    fractal_trace_k: int | None = None,
    fractal_quat: bool | None = None,
    fractal_quat_weight: float | None = None,
    fractal_quat_use_lambda: bool | None = None,
    fractal_alpha_low_lex: float | None = None,
    fractal_low_lex_threshold: float | None = None,
    fractal_low_lex_similarity_threshold: float | None = None,
    fractal_low_lex_overlap_mode: str | None = None,
    fractal_soft_dtw_gamma: float | None = None,
    fractal_soft_dtw_band: float | None = None,
    fractal_soft_dtw_score_mode: str | None = None,
    fractal_cosine_mode: str | None = None,
    fractal_trace_norm_mode: str | None = None,
    fractal_query_path_mode: str | None = None,
    fractal_low_lex_query_path_mode: str | None = None,
    include_details: bool = False,
    max_chars: int = 2000,
) -> Tuple[Dict[str, Any], Dict[str, Any] | None, Dict[str, Any] | None]:
    config = store._config if store._config is not None else FRAMConfig.from_env()
    vectors = _load_episode_vectors(store)
    k_list = sorted({max(1, int(k)) for k in k_values})
    k_max = max(k_list)
    modes_norm = [str(m).strip().lower() for m in modes]
    fields_norm = [str(f).strip() for f in fields if str(f).strip()]
    details: Dict[str, Any] | None = {} if include_details else None
    kind_filters = [str(k).strip().lower() for k in (kinds or []) if str(k).strip()]
    filters = {"kinds": kind_filters} if kind_filters else None

    rankers: Dict[str, Any] = {}
    for mode in modes_norm:
        if mode == "semantic":
            rankers[mode] = lambda query, k: store.search(
                query, k=k, filters=filters, vectorizer=vectorizer
            )
        elif mode == "lexical":
            rankers[mode] = lambda query, k: store.search(
                query, k=k, filters=filters, vectorizer=None
            )
        elif mode == "fractal":
            rankers[mode] = build_fractal_ranker(
                store,
                vectorizer=vectorizer,
                config=config,
                pool_multiplier=pool_multiplier,
                trace_limit=fractal_trace_k,
                influence_alpha=fractal_alpha,
                quat_enabled=fractal_quat,
                quat_weight=fractal_quat_weight,
                quat_use_lambda=fractal_quat_use_lambda,
                low_lex_alpha=fractal_alpha_low_lex,
                low_lex_threshold=fractal_low_lex_threshold,
                low_lex_similarity_threshold=fractal_low_lex_similarity_threshold,
                low_lex_overlap_mode=fractal_low_lex_overlap_mode,
                soft_dtw_gamma=fractal_soft_dtw_gamma,
                soft_dtw_band=fractal_soft_dtw_band,
                soft_dtw_score_mode=fractal_soft_dtw_score_mode,
                cosine_mode=fractal_cosine_mode,
                trace_norm_mode=fractal_trace_norm_mode,
                query_path_mode=fractal_query_path_mode,
                low_lex_query_path_mode=fractal_low_lex_query_path_mode,
                kinds=kinds,
            )

    results: Dict[str, Any] = {}
    for mode in modes_norm:
        if mode not in rankers:
            continue
        results[mode] = {}
        if include_details:
            details[mode] = {}
        ranker = rankers[mode]
        for field in fields_norm:
            hits = {k: 0 for k in k_list}
            base_scores: List[float] = []
            aug_scores: List[float] = []
            deltas: List[float] = []
            pos_delta = 0
            total = 0
            missing_expected = 0
            missing_query = 0
            per_item: List[Dict[str, Any]] = []
            for item in items:
                query = str(item.get(field) or item.get("probe") or "")
                if not query:
                    missing_query += 1
                    continue
                expected = id_map.get(str(item.get("id")))
                if not expected:
                    missing_expected += 1
                    continue
                expected_vec = vectors.get(str(expected))
                if expected_vec is None:
                    missing_expected += 1
                    continue
                query_vec = _embed_text(query, vectorizer=vectorizer)
                base_sim = _cosine(query_vec, expected_vec)
                if base_sim is None:
                    missing_expected += 1
                    continue
                results_list = ranker(query, k_max)
                rank = None
                for idx, result in enumerate(results_list):
                    if str(result.get("id")) == str(expected):
                        rank = idx
                        break
                snippet, used_ids = _build_snippet(results_list, memory_k=memory_k, max_chars=max_chars)
                if snippet:
                    augmented_text = f"{query}\n\n{snippet}"
                else:
                    augmented_text = query
                aug_vec = _embed_text(augmented_text, vectorizer=vectorizer)
                aug_sim = _cosine(aug_vec, expected_vec)
                if aug_sim is None:
                    missing_expected += 1
                    continue
                delta = aug_sim - base_sim
                total += 1
                base_scores.append(base_sim)
                aug_scores.append(aug_sim)
                deltas.append(delta)
                if delta > 0:
                    pos_delta += 1
                if rank is not None:
                    for k in k_list:
                        if rank < k:
                            hits[k] += 1
                if include_details:
                    per_item.append(
                        {
                            "id": str(item.get("id")),
                            "expected_id": str(expected),
                            "rank": rank,
                            "base_similarity": base_sim,
                            "augmented_similarity": aug_sim,
                            "delta": delta,
                            "top_ids": [str(r.get("id")) for r in results_list],
                            "snippet_ids": used_ids,
                            "snippet_preview": snippet[:160] if snippet else "",
                        }
                    )
            denom = max(1, total)
            summary = {
                "count": float(total),
                "avg_base": float(np.mean(base_scores)) if base_scores else 0.0,
                "avg_augmented": float(np.mean(aug_scores)) if aug_scores else 0.0,
                "avg_delta": float(np.mean(deltas)) if deltas else 0.0,
                "median_delta": float(np.median(deltas)) if deltas else 0.0,
                "pos_delta_frac": float(pos_delta) / float(denom),
                "missing_expected": float(missing_expected),
                "missing_query": float(missing_query),
            }
            for k in k_list:
                summary[f"top{k}"] = hits[k] / denom
            results[mode][field] = summary
            if include_details:
                details[mode][field] = per_item

    fractal_stats = None
    fractal_ranker = rankers.get("fractal")
    if fractal_ranker is not None:
        fractal_stats = getattr(fractal_ranker, "stats", None)
    return results, details, fractal_stats


def run_shadow_eval(
    *,
    dataset_path: Path,
    modes: Sequence[str],
    fields: Sequence[str],
    kinds: Sequence[str] | None,
    k_values: Iterable[int],
    memory_k: int,
    pool_multiplier: int,
    fractal_alpha: float | None,
    fractal_trace_k: int | None,
    fractal_quat: bool | None,
    fractal_quat_weight: float | None,
    fractal_quat_use_lambda: bool | None,
    fractal_alpha_low_lex: float | None,
    fractal_low_lex_threshold: float | None,
    fractal_low_lex_similarity_threshold: float | None,
    fractal_low_lex_overlap_mode: str | None,
    fractal_soft_dtw_gamma: float | None,
    fractal_soft_dtw_band: float | None,
    fractal_soft_dtw_score_mode: str | None,
    fractal_cosine_mode: str | None,
    fractal_trace_norm_mode: str | None,
    fractal_query_path_mode: str | None,
    fractal_low_lex_query_path_mode: str | None,
    include_details: bool,
    live: bool,
    live_store_root: Optional[Path],
) -> Dict[str, Any]:
    items = load_eval_items(dataset_path)
    cfg = FRAMConfig.from_env()
    vectorizer = build_query_vectorizer(cfg)
    if live:
        store_root = live_store_root or (cfg.STORAGE_ROOT / cfg.STORAGE_SUBFOLDERS.get("memory", "memory") / "cognitive")
        store = CognitiveMemoryStore(store_root, config=cfg)
        id_map, live_stats = resolve_live_id_map(items, store=store)
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        base_root = DEFAULT_OUT.parent / f"memory_shadow_eval_{stamp}"
        store_root = base_root / "cognitive"
        store, id_map, _ = build_eval_store(items, store_root=store_root, config=cfg)
        live_stats = None
    results, details, fractal_stats = evaluate_shadow(
        items,
        store=store,
        id_map=id_map,
        vectorizer=vectorizer,
        modes=modes,
        fields=fields,
        kinds=kinds,
        memory_k=memory_k,
        k_values=k_values,
        pool_multiplier=pool_multiplier,
        fractal_alpha=fractal_alpha,
        fractal_trace_k=fractal_trace_k,
        fractal_quat=fractal_quat,
        fractal_quat_weight=fractal_quat_weight,
        fractal_quat_use_lambda=fractal_quat_use_lambda,
        fractal_alpha_low_lex=fractal_alpha_low_lex,
        fractal_low_lex_threshold=fractal_low_lex_threshold,
        fractal_low_lex_similarity_threshold=fractal_low_lex_similarity_threshold,
        fractal_low_lex_overlap_mode=fractal_low_lex_overlap_mode,
        fractal_soft_dtw_gamma=fractal_soft_dtw_gamma,
        fractal_soft_dtw_band=fractal_soft_dtw_band,
        fractal_soft_dtw_score_mode=fractal_soft_dtw_score_mode,
        fractal_cosine_mode=fractal_cosine_mode,
        fractal_trace_norm_mode=fractal_trace_norm_mode,
        fractal_query_path_mode=fractal_query_path_mode,
        fractal_low_lex_query_path_mode=fractal_low_lex_query_path_mode,
        include_details=include_details,
    )
    payload: Dict[str, Any] = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "run_mode": "live" if live else "synthetic",
        "config": {
            "dataset": str(dataset_path),
            "fields": list(fields),
            "modes": list(modes),
            "k_values": list(k_values),
            "kinds": list(kinds or []),
            "memory_k": int(memory_k),
            "pool_multiplier": int(pool_multiplier),
            "store_root": str(store_root),
            "defaults": {
                "default_query_reads": cfg.default_query_reads,
                "cognitive_memory_k": cfg.cognitive_memory_k,
                "cognitive_memory_token_budget": cfg.cognitive_memory_token_budget,
            },
            "count": len(items),
        },
        "results": results,
    }
    if live and live_stats is not None:
        payload["config"]["live"] = {
            "store_root": str(store_root),
            "matched": live_stats.get("matched", 0),
            "matched_by_id": live_stats.get("matched_by_id", 0),
            "missing": live_stats.get("missing", 0),
            "ambiguous": live_stats.get("ambiguous", 0),
        }
    if "fractal" in [mode.lower() for mode in modes]:
        payload["config"]["fractal"] = {
            "alpha": fractal_alpha if fractal_alpha is not None else cfg.fractal_influence_alpha,
            "trace_k": fractal_trace_k,
            "trace_k_default": cfg.cognitive_memory_trace_k,
            "quat_enabled": bool(fractal_quat) if fractal_quat is not None else cfg.fractal_quat_influence,
            "quat_weight": fractal_quat_weight if fractal_quat_weight is not None else cfg.fractal_quat_weight,
            "quat_use_lambda": (
                bool(fractal_quat_use_lambda)
                if fractal_quat_use_lambda is not None
                else cfg.fractal_quat_use_lambda
            ),
            "low_lex_alpha": fractal_alpha_low_lex,
            "low_lex_threshold": fractal_low_lex_threshold,
            "low_lex_similarity_threshold": fractal_low_lex_similarity_threshold,
            "low_lex_overlap_mode": fractal_low_lex_overlap_mode,
            "soft_dtw_gamma": fractal_soft_dtw_gamma,
            "soft_dtw_band": fractal_soft_dtw_band,
            "soft_dtw_score_mode": fractal_soft_dtw_score_mode,
            "cosine_mode": fractal_cosine_mode,
            "trace_norm_mode": fractal_trace_norm_mode,
            "query_path_mode": fractal_query_path_mode,
            "low_lex_query_path_mode": fractal_low_lex_query_path_mode,
        }
        if fractal_stats:
            payload["config"]["fractal"]["low_lex_gate"] = {
                key: value for key, value in fractal_stats.items() if not str(key).startswith("_")
            }
    if include_details and details is not None:
        payload["details"] = details
    return payload
