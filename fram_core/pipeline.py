from __future__ import annotations

"""Query orchestration for the demo FastAPI + MCP flow.

This module mirrors the bag-of-words retrieval path currently wired up in
`fram_serving.app`. The goal is to centralise that behaviour so both the HTTP
server and MCP tools can rely on a shared implementation while we work towards
the full FRAM v2.2 pipeline (docs/FRAMv2.2-SPEC.md, Sections 3-5 and 11).

The implementation intentionally keeps the heuristics from the serving layer:
- bag-of-words shortlist over `examples/data`
- confidence features derived from median/MAD normalised signals (Section 5.1)
- CELF-based coverage selection with independence buckets (Section 11.3-11.7)

As the roadmap shifts towards persistent ingestion and a real ANN-backed
prototype bank, this module will become the primary entry point for those
components. For now it gives the MCP server a real (non-stub) orchestrator and
keeps future refactors localised.
"""

import copy
import hashlib
import json
import time
import uuid
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Collection, Dict, Iterable, List, Mapping, Optional, Protocol, Sequence, Tuple, Set

import contextlib
import os

import numpy as np

try:  # Optional ANN dependency (scikit-learn)
    from sklearn.neighbors import NearestNeighbors
except Exception:  # pragma: no cover - optional dependency not guaranteed
    NearestNeighbors = None  # type: ignore[assignment]
from sklearn.feature_extraction.text import HashingVectorizer, TfidfVectorizer
from joblib import dump as joblib_dump, load as joblib_load

try:  # Optional FAISS ANN dependency
    import faiss  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - optional dependency not guaranteed
    faiss = None  # type: ignore[assignment]

try:  # sklearn version checks for persisted caches
    import sklearn  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - optional dependency may be absent
    sklearn = None  # type: ignore[assignment]


def _current_sklearn_version() -> str | None:
    """Return the active sklearn version if available."""

    version = getattr(sklearn, "__version__", None)
    if isinstance(version, str):
        return version
    return None


def _faiss_version() -> str | None:
    if faiss is None:
        return None
    version = getattr(faiss, "__version__", None)
    if isinstance(version, str):
        return version
    return None


def _origin_counts(
    candidates: Iterable[Mapping[str, Any]],
    *,
    fallback: str,
) -> dict[str, int]:
    """Return JSON-safe provenance counts for a candidate sequence."""

    labels = []
    for candidate in candidates:
        value = candidate.get("origin") or candidate.get("source") or fallback
        labels.append(str(value))
    return dict(Counter(labels))


def _ann_backend_from_env() -> Optional[str]:
    env_value = os.getenv("FRAM_ANN_BACKEND")
    if not env_value:
        return None
    candidate = env_value.strip().lower()
    if candidate in {"faiss", "sklearn"}:
        return candidate
    return None


def _resolve_ann_backend() -> str:
    """Choose ANN backend (faiss preferred when available)."""

    preferred = _ann_backend_from_env()
    if preferred == "faiss" and faiss is not None:
        return "faiss"
    if preferred == "sklearn":
        return "sklearn"
    if faiss is not None:
        return "faiss"
    return "sklearn"


def _ann_backend_version(backend: str) -> Optional[str]:
    if backend == "faiss":
        return _faiss_version()
    if backend == "sklearn":
        return _current_sklearn_version()
    return None


def phase_d_weight_for_cognitive(
    phase_d_score: Optional[float] = None,
    alpha_t: Optional[float] = None,
    quat_avg: Optional[float] = None,
    alpha_color: Optional[str] = None,
    seen_count: Optional[float] = None,
    age_seconds: Optional[float] = None,
    enable_alpha_color: bool = True,
    enable_rarity: bool = True,
    enable_recency: bool = True,
    affect_score: Optional[float] = None,
    enable_affect: bool = True,
    coherence_score: Optional[float] = None,
    enable_coherence: bool = True,
    quality_score: Optional[float] = None,
    enable_quality: bool = True,
    priority_clip_min: float = 0.0,
    priority_clip_max: float = 2.0,
    priority_normalize: bool = False,
) -> float:
    """
    Lightweight booster for cognitive memory shards based on Phase D signals.

    - Centered at 1.0 (no change).
    - Mild linear boosts for higher phase_d_score / alpha_t / quat_avg.
    - Optional color, rarity, and recency terms when enabled.
    - Affect, coherence, and quality treat 0.5 as neutral when enabled.
    - Clamped to keep the multiplier non-negative and avoid runaway gains.
    """

    weight = 1.0

    if phase_d_score is not None:
        # Treat 0.5 as neutral; reward confidently positive scores.
        weight += 0.3 * (float(phase_d_score) - 0.5)

    if alpha_t is not None:
        # Alpha_t near 1 nudges weight up; near 0 nudges down slightly.
        weight += 0.15 * (float(alpha_t) - 0.5)

    if quat_avg is not None:
        # Quaternion similarity offers a small extra bias.
        weight += 0.1 * (float(quat_avg) - 0.5)

    color_adjust = 0.0
    if enable_alpha_color and alpha_color:
        color = str(alpha_color).lower()
        if color == "saturated":
            color_adjust = 0.05
        elif color == "bright":
            color_adjust = 0.03
        elif color == "soft":
            color_adjust = 0.0
        elif color == "dull":
            color_adjust = -0.03

    rarity_score = None
    if enable_rarity:
        rarity = 0.5
        if seen_count is not None:
            try:
                rarity = float(1.0 / (1.0 + float(seen_count)))
            except (TypeError, ValueError, ZeroDivisionError):
                rarity = 0.5
        rarity_score = rarity

    recency_factor = 1.0
    if enable_recency and age_seconds is not None:
        try:
            recency_factor = float(np.clip(1.0 - 0.001 * float(age_seconds), 0.7, 1.0))
        except (TypeError, ValueError):
            recency_factor = 1.0

    priority = compute_phase_d_priority(
        affect_score=affect_score,
        enable_affect=enable_affect,
        coherence_score=coherence_score,
        enable_coherence=enable_coherence,
        quality_score=quality_score,
        enable_quality=enable_quality,
        rarity_score=rarity_score,
        enable_rarity=enable_rarity,
        recency_factor=recency_factor,
        enable_recency=enable_recency,
        alpha_color_adjustment=color_adjust,
        enable_alpha_color=enable_alpha_color,
        priority_clip_min=priority_clip_min,
        priority_clip_max=priority_clip_max,
        priority_normalize=priority_normalize,
    )

    multiplier = weight * priority

    # Keep within a reasonable band: floor at 0, gentle cap using the configured clip.
    return float(np.clip(multiplier, priority_clip_min, priority_clip_max))


def _delta_from_score(score: Optional[float], enabled: bool = True) -> float:
    """Return centered delta for a 0..1 score (neutral at 0.5)."""
    if not enabled:
        return 0.0
    value = 0.5
    if score is not None:
        try:
            value = float(score)
        except (TypeError, ValueError):
            value = 0.5
    return 0.25 * (value - 0.5)


def compute_phase_d_priority(
    affect_score: Optional[float] = None,
    enable_affect: bool = True,
    coherence_score: Optional[float] = None,
    enable_coherence: bool = True,
    quality_score: Optional[float] = None,
    enable_quality: bool = True,
    rarity_score: Optional[float] = None,
    enable_rarity: bool = True,
    recency_factor: Optional[float] = None,
    enable_recency: bool = True,
    alpha_color_adjustment: float = 0.0,
    enable_alpha_color: bool = True,
    priority_clip_min: float = 0.0,
    priority_clip_max: float = 2.0,
    priority_normalize: bool = False,
) -> float:
    """Blend Phase D “quality” signals into a single stable scalar (neutral around 1.0)."""

    base = 1.0
    base += _delta_from_score(affect_score, enable_affect)
    base += _delta_from_score(coherence_score, enable_coherence)
    base += _delta_from_score(quality_score, enable_quality)
    base += _delta_from_score(rarity_score, enable_rarity)

    if enable_alpha_color:
        base += float(alpha_color_adjustment)

    recency = 1.0
    if enable_recency and recency_factor is not None:
        try:
            recency = float(recency_factor)
        except (TypeError, ValueError):
            recency = 1.0

    priority = base * recency
    priority = float(np.clip(priority, priority_clip_min, priority_clip_max))

    if priority_normalize and priority_clip_max > priority_clip_min:
        priority = (priority - priority_clip_min) / (priority_clip_max - priority_clip_min)
        priority = float(np.clip(priority, 0.0, 1.0))

    return priority


def temporal_recency_score(
    age_seconds: Optional[float],
    half_life: float,
    min_floor: float,
) -> float:
    """Compute a half-life based recency score clamped to [min_floor, 1.0]."""

    if age_seconds is None or age_seconds < 0:
        return 1.0
    if half_life <= 0:
        return 1.0
    # Half-life semantics: score halves every half_life.
    recency = float(0.5 ** (float(age_seconds) / float(half_life)))
    return float(np.clip(recency, min_floor, 1.0))

import fram_core.confidence as conf
from fram_core.claims import Claim, ClaimType, extract_claims, extract_table_claims, _default_buckets
from fram_core.coverage import ClaimEvidence, CoverageState, select_celf
from fram_core.anchors import principal_residual_directions
from fram_core.rerank import Reranker, SimpleCosineReranker
from fram_core.transitional_complexity import TransitionalComplexityProbe
from fram_index.prototypes import Prototype, PrototypeBank
from fram_index.sparse_keys import SparseKeyIndex
from fram_core.priority_graph import apply_priority_graph
from fram_core.memory_merge import merge_with_gates
from fram_index.version_lattice import VersionLattice, VersionNode, write_version_manifest
from fram_layout.table_chunker import read_csv_to_table, window_for_cell
from fram_serving.config import FRAMConfig
from fram_core.math_utils import (
    projection_help_delta,
    centroid_distance,
    pairwise_mean_knn_dist,
    subspace_projection,
    whiten_embeddings,
)

_TOKEN_PATTERN = re.compile(r"\b\w+\b")
_HEADING_MARKER_RE = re.compile(r"^\[h(\d+)\]\s+(.*)$", re.MULTILINE)
_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")
_DOC_META_TOKEN_RE = re.compile(r"[a-z0-9]+")
_DOC_META_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "about",
    "at",
    "by",
    "does",
    "do",
    "doc",
    "docs",
    "for",
    "from",
    "how",
    "in",
    "ingest",
    "is",
    "of",
    "on",
    "or",
    "section",
    "say",
    "says",
    "the",
    "this",
    "to",
    "txt",
    "what",
    "when",
    "where",
    "which",
    "who",
    "with",
}


class TraceWriter(Protocol):
    """Minimal protocol for trace writers used by the orchestrator."""

    def write(self, payload: Mapping[str, Any]) -> str:  # pragma: no cover - interface
        ...


@dataclass(slots=True)
class PrototypeRecord:
    doc_id: str
    centroid: np.ndarray
    basis: np.ndarray
    timestamp: float
    feature_medians: Dict[str, float]
    feature_mads: Dict[str, float]


@dataclass(slots=True)
class CalibrationPayload:
    logistic_coefs: Dict[str, float]
    temperature: float
    tau1: float
    tau2: float


@dataclass(slots=True)
class _ClusterContext:
    centroid: np.ndarray
    basis: np.ndarray
    medians: Dict[str, float]
    mads: Dict[str, float]
    timestamp: float
    neighbor_indices: List[int]
    projection: Optional[np.ndarray]


@dataclass(slots=True)
class _AnchorPlan:
    order: List[int]
    residual_steps: Dict[int, Dict[str, float]]


@dataclass(slots=True)
class _CorpusCache:
    chunks: List[Dict[str, Any]]
    vocab: Dict[str, int]
    chunk_vecs: np.ndarray
    lattice: VersionLattice
    sparse_index: SparseKeyIndex
    prototypes: List[PrototypeRecord]
    whiten_mean: np.ndarray
    whiten_matrix: np.ndarray
    calibration: CalibrationPayload
    embedding_backend: str
    embedder: Any | None
    calibration_by_domain: Dict[str, CalibrationPayload] = field(default_factory=dict)
    calibration_by_task: Dict[str, CalibrationPayload] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Optional multi-scale prototypes (segment-level)
    prototypes_by_segment: List[PrototypeRecord] = field(default_factory=list)


def _tokenize(text: str) -> List[str]:
    return [match.group(0).lower() for match in _TOKEN_PATTERN.finditer(text)]


def tokenize_text(text: str) -> List[str]:
    """Public helper for consistent tokenization (serving + pipeline)."""

    return _tokenize(text)


def _chunk_timestamp(chunk: Mapping[str, Any]) -> float:
    ts_raw = chunk.get("timestamp")
    if not ts_raw:
        return 0.0
    try:
        return datetime.fromisoformat(str(ts_raw)).timestamp()
    except ValueError:
        return 0.0


def _chunk_tokens(tokens: Sequence[str], chunk_size: int = 250) -> List[List[str]]:
    return [list(tokens[i : i + chunk_size]) for i in range(0, len(tokens), chunk_size)]


def _focus_query_tokens(tokens: Sequence[str]) -> set[str]:
    focus: set[str] = set()
    for token in tokens:
        if not token:
            continue
        token_lower = token.lower()
        if len(token_lower) <= 1 or token_lower in _DOC_META_STOPWORDS:
            continue
        focus.add(token_lower)
    return focus


def _doc_meta_tokens_from_value(value: Any) -> set[str]:
    if value is None:
        return set()
    if not isinstance(value, str):
        value = str(value)
    tokens: set[str] = set()
    for match in _DOC_META_TOKEN_RE.findall(value.lower()):
        if len(match) <= 1 or match in _DOC_META_STOPWORDS:
            continue
        tokens.add(match)
    return tokens


def _chunk_doc_tokens(chunk: Mapping[str, Any]) -> set[str]:
    tokens: set[str] = set()
    doc_id = chunk.get("file")
    tokens |= _doc_meta_tokens_from_value(doc_id)
    if isinstance(doc_id, str):
        tokens |= _doc_meta_tokens_from_value(Path(doc_id).stem)
    layout_id = chunk.get("layout_id")
    tokens |= _doc_meta_tokens_from_value(layout_id)
    hierarchy = chunk.get("hierarchy")
    if isinstance(hierarchy, Mapping):
        for value in hierarchy.values():
            tokens |= _doc_meta_tokens_from_value(value)
    tags = chunk.get("tags")
    if isinstance(tags, str):
        tokens |= _doc_meta_tokens_from_value(tags)
    elif isinstance(tags, Sequence):
        for tag in tags:
            tokens |= _doc_meta_tokens_from_value(tag)
    return tokens


def _chunk_content_tokens(chunk: Mapping[str, Any]) -> set[str]:
    raw_tokens = chunk.get("tokens")
    if isinstance(raw_tokens, str):
        return _focus_query_tokens(_tokenize(raw_tokens))
    if isinstance(raw_tokens, Sequence):
        return _focus_query_tokens([str(token) for token in raw_tokens])
    text = chunk.get("text")
    if isinstance(text, str):
        return _focus_query_tokens(_tokenize(text))
    return set()


def _prioritize_candidates_by_query_overlap(
    cand_order: Sequence[int],
    chunks: Sequence[Mapping[str, Any]],
    query_tokens: Collection[str],
) -> list[int]:
    """Stably move stronger exact lexical matches ahead of candidate truncation."""

    if not query_tokens:
        return [int(idx) for idx in cand_order]
    scored: list[tuple[int, int, int, int]] = []
    for position, idx in enumerate(cand_order):
        metadata_overlap = len(_chunk_doc_tokens(chunks[idx]).intersection(query_tokens))
        content_overlap = len(_chunk_content_tokens(chunks[idx]).intersection(query_tokens))
        scored.append((int(idx), metadata_overlap, content_overlap, position))
    if not any(metadata or content for _, metadata, content, _ in scored):
        return [idx for idx, _, _, _ in scored]
    # A document/hierarchy match is an explicit routing cue and remains the
    # primary tier. Content overlap rescues exact passages and orders within
    # each tier without letting a sample that merely mentions a document outrank
    # that document itself.
    scored.sort(key=lambda row: (-int(row[1] > 0), -row[1], -row[2], row[3]))
    return [idx for idx, _, _, _ in scored]


def _doc_alignment_claims(
    chunk: Mapping[str, Any],
    query_tokens: Collection[str],
) -> tuple[list[ClaimEvidence], set[str]]:
    if not query_tokens:
        return [], set()
    doc_tokens = _chunk_doc_tokens(chunk)
    matched = {token for token in doc_tokens if token in query_tokens}
    if not matched:
        return [], set()
    doc_id = str(chunk.get("file", "doc"))
    chunk_id = int(chunk.get("chunk_id", 0))
    layout_id = chunk.get("layout_id")
    buckets = list(_default_buckets(doc_id, chunk_id, layout_id))
    hierarchy = chunk.get("hierarchy")
    if isinstance(hierarchy, Mapping):
        for key in ("cluster", "segment", "chunk"):
            value = hierarchy.get(key)
            if isinstance(value, str) and value:
                bucket = f"{key}:{value}"
                if bucket not in buckets:
                    buckets.append(bucket)
    evidence = [
        ClaimEvidence(key=f"doc_alignment::{token}", buckets=tuple(buckets))
        for token in sorted(matched)
    ]
    return evidence, matched


def _build_vocab(chunks: Sequence[Sequence[str]]) -> Dict[str, int]:
    vocab: Dict[str, int] = {}
    for chunk in chunks:
        for token in chunk:
            if token not in vocab:
                vocab[token] = len(vocab)
    return vocab


def _vectorize(tokens: Sequence[str], vocab: Mapping[str, int]) -> np.ndarray:
    vec = np.zeros(len(vocab), dtype=float)
    for token in tokens:
        idx = vocab.get(token)
        if idx is not None:
            vec[idx] += 1.0
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm
    return vec


def _embedding_backend(config: FRAMConfig) -> str:
    backend = getattr(config, "embedding_backend", "vocab")
    return str(backend).lower()


def _make_hashing_vectorizer(config: FRAMConfig) -> HashingVectorizer:
    return HashingVectorizer(
        lowercase=True,
        token_pattern=r"\b\w+\b",
        n_features=config.embedding_dim,
        alternate_sign=False,
        norm=None,
    )


def _build_chunk_vectors(
    chunks: Sequence[Mapping[str, Any]],
    vocab: Mapping[str, int],
    config: FRAMConfig,
) -> tuple[np.ndarray, Any | None]:
    backend = _embedding_backend(config)
    texts = [str(chunk.get("text", "")) for chunk in chunks]
    if backend == "hashing":
        vectorizer = _make_hashing_vectorizer(config)
        sparse = vectorizer.transform(texts)
        matrix = sparse.toarray().astype(float, copy=False)
        return matrix, None
    if backend == "tfidf":
        vectorizer = TfidfVectorizer(lowercase=True, token_pattern=r"\b\w+\b")
        sparse = vectorizer.fit_transform(texts)
        matrix = sparse.toarray().astype(float, copy=False)
        return matrix, vectorizer
    matrix = np.vstack([
        _vectorize(chunk.get("tokens", ()), vocab)
        for chunk in chunks
    ]).astype(float, copy=False)
    return matrix, None


def _normalize_vector(vec: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    norm = float(np.linalg.norm(vec))
    if norm <= eps:
        return np.zeros_like(vec)
    return vec / norm


def _embedding_fingerprint(vecs: np.ndarray) -> str:
    if vecs.size == 0:
        return "empty"
    return hashlib.md5(vecs.tobytes()).hexdigest()


def _robust_stats(values: Sequence[float], fallback: float = 1.0) -> tuple[float, float]:
    if not values:
        return 0.0, fallback
    arr = np.asarray(values, dtype=float)
    median = float(np.median(arr))
    mad = float(np.median(np.abs(arr - median)))
    if mad <= 1e-9:
        mad = fallback
    return median, mad


def _quantile(values: Sequence[float], q: float, default: float) -> float:
    if not values:
        return default
    arr = np.sort(np.asarray(values, dtype=float))
    q = float(np.clip(q, 0.0, 1.0))
    rank = int(np.clip(np.ceil((arr.size) * q) - 1, 0, arr.size - 1))
    return float(arr[rank])


def _default_calibration(config: FRAMConfig) -> CalibrationPayload:
    tau1 = float(config.tau1)
    tau2 = float(config.tau2 if config.tau2 < config.tau1 else max(1e-6, config.tau1 - 1e-6))
    return CalibrationPayload(
        logistic_coefs={"a": 1.0, "b": 0.8, "c": 0.6, "g": 0.9, "h": 0.3, "d": 0.0},
        temperature=1.0,
        tau1=tau1,
        tau2=tau2,
    )


def _sigmoid(z: np.ndarray) -> np.ndarray:
    z = np.clip(z, -50.0, 50.0)
    return 1.0 / (1.0 + np.exp(-z))


def _fit_logistic_regression(
    X: np.ndarray,
    y: np.ndarray,
    *,
    lr: float = 0.05,
    epochs: int = 300,
    l2: float = 0.1,
) -> tuple[np.ndarray, float] | None:
    n_samples, n_features = X.shape
    if n_samples == 0 or np.allclose(y, y[0]):
        return None

    X = np.asarray(X, dtype=float)
    if n_features >= 5:
        X[:, 0] = np.clip(X[:, 0], -10.0, 10.0)  # Delta_d_z
        X[:, 1] = np.clip(X[:, 1], -10.0, 10.0)  # rho_pos
        X[:, 2] = np.clip(X[:, 2], 0.0, 1.0)      # mhd
        X[:, 3] = np.clip(X[:, 3], -10.0, 10.0)  # d_c_z
        X[:, 4] = np.clip(X[:, 4], 0.0, 1.0)      # fresh

    weights = np.zeros(n_features, dtype=float)
    bias = 0.0
    for _ in range(epochs):
        logits = np.clip(X @ weights + bias, -50.0, 50.0)
        preds = _sigmoid(logits)
        error = preds - y
        grad_w = (X.T @ error) / n_samples + l2 * weights
        grad_b = float(np.mean(error))
        weights -= lr * grad_w
        bias -= lr * grad_b
        weights = np.clip(weights, -5.0, 5.0)
        bias = float(np.clip(bias, -5.0, 5.0))
        if np.linalg.norm(grad_w) < 1e-6 and abs(grad_b) < 1e-6:
            break

    if not np.all(np.isfinite(weights)) or not np.isfinite(bias):
        return None
    return weights, float(bias)


def _constrain_calibration_weights(weights: np.ndarray) -> np.ndarray:
    """Project fitted weights onto the confidence sign contract from spec section 5."""

    constrained = np.asarray(weights, dtype=float).copy()
    if constrained.size >= 4:
        # Runtime uses ``-g * d_c_z``. The equivalent raw logistic weight for
        # centroid distance must therefore be non-positive.
        constrained[3] = min(float(constrained[3]), 0.0)
    return constrained


def _collect_calibration_samples(
    prototypes: Sequence[PrototypeRecord],
    chunk_vecs: np.ndarray,
    doc_to_indices: Mapping[str, Sequence[int]],
    config: FRAMConfig,
) -> tuple[np.ndarray, np.ndarray]:
    samples: List[np.ndarray] = []
    labels: List[float] = []

    for proto in prototypes:
        idxs = list(doc_to_indices.get(proto.doc_id, ()))
        if len(idxs) < 2:
            continue
        sims = [(idx, float(np.dot(chunk_vecs[idx], proto.centroid))) for idx in idxs]
        sims.sort(key=lambda item: item[1], reverse=True)
        pos_cut = max(1, int(np.ceil(len(sims) * 0.2)))
        positives = {idx for idx, _ in sims[:pos_cut]}
        neighbors = chunk_vecs[idxs]
        for idx in idxs:
            feats = conf.compute_features(
                e=chunk_vecs[idx],
                p_k=proto.centroid,
                U_k=proto.basis,
                kNN_neighbors=neighbors,
                medians=proto.feature_medians,
                mads=proto.feature_mads,
                T_q=proto.timestamp,
                T_k_median=proto.timestamp,
                tau_domain=config.tau_domain_days,
            )
            samples.append(
                np.array(
                    [
                        feats.Delta_d_z,
                        feats.rho_pos,
                        feats.mhd,
                        feats.d_c_z,
                        feats.fresh,
                    ],
                    dtype=float,
                )
            )
            labels.append(1.0 if idx in positives else 0.0)

    if not samples:
        return np.empty((0, 5), dtype=float), np.empty((0,), dtype=float)
    return np.vstack(samples), np.asarray(labels, dtype=float)


def _conformal_tau(calibrated: np.ndarray, alpha: float, fallback: float) -> float:
    if calibrated.size == 0:
        return fallback
    scores = np.clip(1.0 - calibrated, 0.0, 1.0)
    level = float(np.clip(1.0 - alpha, 0.0, 1.0))
    rank = int(np.ceil((scores.size + 1) * level)) - 1
    rank = int(np.clip(rank, 0, scores.size - 1))
    threshold = float(np.sort(scores)[rank])
    tau = float(np.clip(1.0 - threshold, 1e-6, 1.0 - 1e-6))
    return tau


def _calibrate_confidence_payload(
    prototypes: Sequence[PrototypeRecord],
    chunk_vecs: np.ndarray,
    doc_to_indices: Mapping[str, Sequence[int]],
    config: FRAMConfig,
) -> CalibrationPayload:
    X, y = _collect_calibration_samples(prototypes, chunk_vecs, doc_to_indices, config)
    if X.size == 0 or np.allclose(y, y[0]):
        return _default_calibration(config)

    fit = _fit_logistic_regression(X, y)
    if fit is None:
        return _default_calibration(config)
    weights, bias = fit
    weights = _constrain_calibration_weights(weights)

    logits = np.clip(X @ weights + bias, -50.0, 50.0)
    probs = _sigmoid(logits)
    scaler = conf.TemperatureScaler().fit(probs, y)
    calibrated = scaler.transform(probs)

    tau1 = _conformal_tau(calibrated, config.alpha1, config.tau1)
    tau2 = _conformal_tau(calibrated, config.alpha2, config.tau2)
    if tau2 >= tau1:
        tau2 = max(1e-6, tau1 - 1e-6)
    min_tau1 = max(1e-6, float(config.tau2) + 1e-6)
    if tau1 <= min_tau1 or (tau1 - tau2) <= 1e-6:
        tau1 = float(max(config.tau1, min_tau1))
        fallback_tau2 = float(config.tau2)
        if fallback_tau2 >= tau1:
            fallback_tau2 = max(1e-6, tau1 - 1e-6)
        tau2 = fallback_tau2

    logistic_coefs = {
        "a": float(weights[0]),
        "b": float(weights[1]),
        "c": float(weights[2]),
        "g": float(-weights[3]),
        "h": float(weights[4]),
        "d": float(bias),
    }

    temperature = float(scaler.T if hasattr(scaler, "T") and np.isfinite(scaler.T) else 1.0)

    return CalibrationPayload(
        logistic_coefs=logistic_coefs,
        temperature=temperature,
        tau1=float(tau1),
        tau2=float(tau2),
    )


def _build_doc_prototypes(
    chunks: Sequence[Mapping[str, Any]],
    chunk_vecs: np.ndarray,
    config: FRAMConfig,
    doc_to_indices: Dict[str, List[int]] | None = None,
) -> List[PrototypeRecord]:
    if doc_to_indices is None:
        doc_to_indices = defaultdict(list)
        for idx, chunk in enumerate(chunks):
            doc_id = str(chunk.get("file", f"doc_{idx}"))
            doc_to_indices[doc_id].append(idx)

    if chunk_vecs.size == 0:
        return []

    dim = int(chunk_vecs.shape[1])
    target_cap = max(1, min(config.rank_max, dim))
    min_rank = max(1, min(config.rank_min, target_cap))

    prototypes: List[PrototypeRecord] = []
    for doc_id, indices in doc_to_indices.items():
        doc_vecs = chunk_vecs[indices]
        centroid = _normalize_vector(doc_vecs.mean(axis=0))
        centered = doc_vecs - centroid
        try:
            _, _, vh = np.linalg.svd(centered, full_matrices=False)
        except np.linalg.LinAlgError:
            vh = np.eye(dim, dtype=float)

        available_rank = vh.shape[0] if vh.ndim == 2 else 0
        desired_rank = min(target_cap, max(min_rank, available_rank))

        basis_cols: List[np.ndarray] = []
        if vh.ndim == 2 and vh.size:
            base = vh[: min(available_rank, desired_rank)].T
            for col_idx in range(base.shape[1]):
                column = base[:, col_idx]
                norm = float(np.linalg.norm(column))
                if norm > 0:
                    basis_cols.append(column / norm)

        axis = 0
        while len(basis_cols) < desired_rank:
            unit = np.zeros(dim, dtype=float)
            unit[(axis + len(basis_cols)) % dim] = 1.0
            basis_cols.append(unit)
            axis += 1

        basis = np.stack(basis_cols[:desired_rank], axis=1) if basis_cols else np.zeros((dim, 0), dtype=float)

        delta_vals: List[float] = []
        dc_vals: List[float] = []
        for vec in doc_vecs:
            if basis.size:
                delta_vals.append(float(projection_help_delta(vec, centroid, basis)))
            else:
                delta_vals.append(0.0)
            dc_vals.append(float(centroid_distance(vec, centroid)))

        density_samples: List[float] = []
        if len(doc_vecs) > 1:
            density_samples.append(float(pairwise_mean_knn_dist(centroid, doc_vecs)))
        else:
            density_samples.append(0.0)

        medians: Dict[str, float] = {}
        mads: Dict[str, float] = {}
        medians["Delta_d"], mads["Delta_d"] = _robust_stats(delta_vals)
        medians["dc"], mads["dc"] = _robust_stats(dc_vals)
        medians["mean_kNN"], mads["mean_kNN"] = _robust_stats(density_samples)

        ts_values: List[float] = []
        for idx in indices:
            ts_raw = chunks[idx].get("timestamp")
            if not ts_raw:
                continue
            try:
                ts_values.append(datetime.fromisoformat(str(ts_raw)).timestamp())
            except ValueError:
                continue
        timestamp = float(np.median(ts_values)) if ts_values else 0.0

        prototypes.append(
            PrototypeRecord(
                doc_id=doc_id,
                centroid=centroid.astype(float, copy=False),
                basis=basis.astype(float, copy=False),
                timestamp=timestamp,
                feature_medians=medians,
                feature_mads=mads,
            )
        )

    return prototypes


def _build_segment_prototypes(
    chunks: Sequence[Mapping[str, Any]],
    chunk_vecs: np.ndarray,
    config: FRAMConfig,
) -> List[PrototypeRecord]:
    """Build prototypes for the mid-scale 'segment' hierarchy (e.g., sections/layout blocks)."""
    if chunk_vecs.size == 0:
        return []
    # group by hierarchy['segment'] when available; fallback to cluster bucket
    segment_to_indices: Dict[str, List[int]] = defaultdict(list)
    for idx, chunk in enumerate(chunks):
        seg = None
        h = chunk.get("hierarchy") or {}
        if isinstance(h, Mapping):
            seg = h.get("segment")
        if not isinstance(seg, str) or not seg:
            seg = f"seg:{str(chunk.get('file',''))}:{int(chunk.get('chunk_id',0))//4}"
        segment_to_indices[str(seg)].append(idx)

    dim = int(chunk_vecs.shape[1])
    target_cap = max(1, min(config.rank_max, dim))
    min_rank = max(1, min(config.rank_min, target_cap))

    prototypes: List[PrototypeRecord] = []
    for seg_id, indices in segment_to_indices.items():
        seg_vecs = chunk_vecs[indices]
        centroid = _normalize_vector(seg_vecs.mean(axis=0)) if seg_vecs.size else np.zeros((dim,), dtype=float)
        centered = seg_vecs - centroid if seg_vecs.size else np.zeros((0, dim), dtype=float)
        try:
            _, _, vh = np.linalg.svd(centered, full_matrices=False)
        except np.linalg.LinAlgError:
            vh = np.eye(dim, dtype=float)
        available_rank = vh.shape[0] if vh.ndim == 2 else 0
        desired_rank = min(target_cap, max(min_rank, available_rank))
        basis_cols: List[np.ndarray] = []
        if vh.ndim == 2 and vh.size:
            base = vh[: min(available_rank, desired_rank)].T
            for col_idx in range(base.shape[1]):
                col = base[:, col_idx]
                n = float(np.linalg.norm(col))
                if n > 0:
                    basis_cols.append(col / n)
        axis = 0
        while len(basis_cols) < desired_rank:
            unit = np.zeros(dim, dtype=float)
            unit[(axis + len(basis_cols)) % dim] = 1.0
            basis_cols.append(unit)
            axis += 1
        basis = np.stack(basis_cols[:desired_rank], axis=1) if basis_cols else np.zeros((dim, 0), dtype=float)

        # robust stats for features (reuse doc stats formulation)
        delta_vals: List[float] = []
        dc_vals: List[float] = []
        for vec in seg_vecs:
            if basis.size:
                delta_vals.append(float(projection_help_delta(vec, centroid, basis)))
            else:
                delta_vals.append(0.0)
            dc_vals.append(float(centroid_distance(vec, centroid)))
        density_samples: List[float] = []
        if seg_vecs.shape[0] > 1:
            density_samples.append(float(pairwise_mean_knn_dist(centroid, seg_vecs)))
        else:
            density_samples.append(0.0)
        medians: Dict[str, float] = {}
        mads: Dict[str, float] = {}
        medians["Delta_d"], mads["Delta_d"] = _robust_stats(delta_vals)
        medians["dc"], mads["dc"] = _robust_stats(dc_vals)
        medians["mean_kNN"], mads["mean_kNN"] = _robust_stats(density_samples)

        prototypes.append(
            PrototypeRecord(
                doc_id=str(seg_id),
                centroid=centroid.astype(float, copy=False),
                basis=basis.astype(float, copy=False),
                timestamp=0.0,
                feature_medians=medians,
                feature_mads=mads,
            )
        )
    return prototypes
def _prototype_bank_from_records(records: Sequence[PrototypeRecord]) -> tuple[PrototypeBank | None, List[str]]:
    if not records:
        return None, []

    prototypes: List[Prototype] = []
    doc_order: List[str] = []
    for record in records:
        centroid = _normalize_vector(record.centroid)
        basis = record.basis
        if basis.size:
            # ensure orthonormal columns before handing to PrototypeBank
            try:
                q, _ = np.linalg.qr(basis, mode="reduced")
                basis = q
            except np.linalg.LinAlgError:
                pass
        prototypes.append(Prototype(p_k=centroid.astype(float, copy=False), U_k=basis.astype(float, copy=False)))
        doc_order.append(record.doc_id)

    if not prototypes:
        return None, []
    return PrototypeBank(prototypes), doc_order


def _assemble_answer(chunks: Sequence[Mapping[str, Any]], limit: int = 1200) -> str:
    segments: Dict[str, List[str]] = {}
    order: List[str] = []
    total = 0
    for chunk in chunks:
        text = str(chunk.get("text", "")).strip()
        if not text:
            continue
        hierarchy = chunk.get("hierarchy") or {}
        segment = str(hierarchy.get("segment") or hierarchy.get("cluster") or "segment:0")
        remaining = max(limit - total, 0)
        if remaining <= 0:
            break
        snippet = text if len(text) <= remaining else text[: max(0, remaining - 1)] + ("\u2026" if remaining > 0 else "")
        total += len(snippet)
        if segment not in segments:
            segments[segment] = []
            order.append(segment)
        segments[segment].append(snippet)
    pieces: List[str] = []
    for segment in order:
        pieces.append(f"[{segment}]")
        pieces.extend(segments[segment])
    return "\n\n".join(pieces)


def _chunk_claims(chunk: Mapping[str, Any]) -> List[Claim]:
    if "claims" in chunk:
        return list(chunk["claims"])
    text = chunk.get("text", "")
    file_id = str(chunk.get("file", "doc"))
    chunk_id = int(chunk.get("chunk_id", 0))
    layout = chunk.get("layout_id")
    return extract_claims(text, doc_id=file_id, chunk_id=chunk_id, layout_id=layout)



def _claim_evidence(chunk: Mapping[str, Any]) -> List[ClaimEvidence]:
    doc_id = str(chunk.get("file", "doc"))
    chunk_id = int(chunk.get("chunk_id", 0))
    layout_id = chunk.get("layout_id")
    hierarchy = chunk.get("hierarchy")
    base_buckets: List[str] = list(_default_buckets(doc_id, chunk_id, layout_id))
    if isinstance(hierarchy, Mapping):
        for key in ("cluster", "segment", "chunk"):
            value = hierarchy.get(key)
            if value:
                bucket = f"{key}:{value}"
                if bucket not in base_buckets:
                    base_buckets.append(bucket)
    evidence: List[ClaimEvidence] = []
    for claim in _chunk_claims(chunk):
        if isinstance(claim, Claim):
            claim_buckets = list(claim.buckets)
            key = claim.key
        else:
            claim_buckets = []
            key = str(claim)
        combined: List[str] = []
        for bucket in base_buckets + claim_buckets:
            bucket_str = str(bucket)
            if bucket_str not in combined:
                combined.append(bucket_str)
        evidence.append(ClaimEvidence(key=str(key), buckets=tuple(combined)))
    return evidence


def _candidate_cost_entry(chunk: Mapping[str, Any], pairs_scale: float) -> Dict[str, float]:
    tokens = chunk.get("tokens")
    token_count = len(tokens) if isinstance(tokens, Sequence) else 0
    if token_count == 0 and chunk.get("text"):
        token_count = len(tokenize_text(str(chunk.get("text"))))
    return {
        "reads": 1.0,
        "tokens": float(token_count),
        "pairs_scale": float(pairs_scale),
        "pairs_exponent": 2.0,
    }


def _composite_cost(tokens: Sequence[str], reads: float = 1.0, pairs: float = 1.0, *,
                    lambda_tokens: float, lambda_rerank: float, pairs_scale: float) -> float:
    token_cost = lambda_tokens * float(len(tokens))
    rerank_cost = lambda_rerank * float(pairs_scale) * float(pairs)
    return float(reads + token_cost + rerank_cost)


def load_demo_corpus(
    data_root: Path,
    config: FRAMConfig | None = None,
    *,
    include_legacy: bool = False,
) -> _CorpusCache:
    """Build the in-memory demo corpus under `examples/data` with prototypes.

    Parameters
    ----------
    include_legacy:
        When true, also ingest legacy fixture text files (`doc1/doc2`). The fixtures
        live under `examples/data/fixtures/` and are skipped by default so the demo
        corpus focuses on project docs.
    """
    cfg = config or FRAMConfig()
    if not data_root.exists():
        raise FileNotFoundError(f"Data directory not found: {data_root}")

    chunk_records: List[Dict[str, Any]] = []
    all_tokens: List[List[str]] = []
    lattice = VersionLattice()
    sparse_index = SparseKeyIndex()

    legacy_names = {"doc1.txt", "doc2.txt"}
    seen_texts: set[Path] = set()

    def _iter_text_files() -> Iterable[Path]:
        primary = sorted(data_root.glob("*.txt"))
        for txt in primary:
            if txt.name in legacy_names and not include_legacy:
                continue
            yield txt
        if include_legacy:
            fixtures_dir = data_root / "fixtures"
            if fixtures_dir.exists():
                for txt in sorted(fixtures_dir.glob("*.txt")):
                    yield txt

    for path in _iter_text_files():
        if path in seen_texts:
            continue
        seen_texts.add(path)
        text = path.read_text(encoding="utf-8", errors="ignore")
        sparse_index.add(path.name, text)
        heading_sections = _heading_sections(text)
        matches = list(_TOKEN_PATTERN.finditer(text))
        if not matches:
            continue
        tokens = [m.group(0).lower() for m in matches]
        token_chunks = _chunk_tokens(tokens, chunk_size=250)
        if not token_chunks:
            continue
        timestamp = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        lattice.add_node(VersionNode(node_id=path.name, timestamp=timestamp))
        offset = 0
        for chunk_id, ctoks in enumerate(token_chunks):
            start_idx = offset
            end_idx = start_idx + len(ctoks)
            start_char = matches[start_idx].start()
            end_char = matches[end_idx - 1].end()
            while end_char < len(text) and not text[end_char].isspace():
                end_char += 1
            snippet = text[start_char:end_char].strip()
            if not snippet:
                snippet = " ".join(matches[i].group(0) for i in range(start_idx, end_idx))
            section_slug = _section_slug_for_offset(heading_sections, start_char)
            record = {
                "file": path.name,
                "chunk_id": chunk_id,
                "text": snippet,
                "tokens": ctoks,
                "timestamp": timestamp.isoformat(),
                "version_id": path.name,
                "hierarchy": _hierarchy_address(path.name, chunk_id, section=section_slug),
            }
            if section_slug:
                record["section"] = section_slug
            chunk_records.append(record)
            all_tokens.append(ctoks)
            offset = end_idx

        # Ensure each heading slug is represented by at least one segment entry
        try:
            present_segs = {
                (rec.get("hierarchy") or {}).get("segment")
                for rec in chunk_records
                if rec.get("file") == path.name
            }
            missing_slugs = []
            seen = set()
            for _pos, slug in heading_sections:
                if slug in seen:
                    continue
                seen.add(slug)
                seg_id = f"section:{slug}"
                if seg_id not in present_segs:
                    missing_slugs.append(slug)
            for i, slug in enumerate(missing_slugs):
                # Create a minimal marker record so the section appears in hierarchy
                marker_text = f"heading {slug.replace('_', ' ')}"
                marker_tokens = _DOC_META_TOKEN_RE.findall(marker_text.lower())
                marker_id = 10_000_000 + i
                record = {
                    "file": path.name,
                    "chunk_id": marker_id,
                    "text": marker_text,
                    "tokens": marker_tokens,
                    "timestamp": timestamp.isoformat(),
                    "version_id": path.name,
                    "hierarchy": _hierarchy_address(path.name, marker_id, section=slug),
                    "section": slug,
                }
                chunk_records.append(record)
                # Note: we intentionally do not add marker tokens to all_tokens so vocab derives from real content
        except Exception:
            # Defensive: never fail ingestion on marker construction
            pass

    for path in sorted(data_root.glob("*.csv")):
        table = read_csv_to_table(path)
        headers = table.get("headers", [])
        rows = table.get("rows", [])
        if not rows:
            continue
        csv_text = "\n".join([",".join(headers)] + [",".join(row) for row in rows])
        sparse_index.add(path.name, csv_text)
        timestamp = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        lattice.add_node(VersionNode(node_id=path.name, timestamp=timestamp))
        raw_claims = extract_table_claims(rows, headers)
        claims_by_row: Dict[int, List[Claim]] = {}
        for claim in raw_claims:
            row_idx = (claim.ctx or {}).get("row")
            if row_idx is None:
                continue
            claims_by_row.setdefault(int(row_idx), []).append(claim)
        for row_idx, row in enumerate(rows):
            snippets: List[str] = []
            seen: set[str] = set()
            for col_idx, _ in enumerate(headers):
                if col_idx >= len(row):
                    continue
                try:
                    window = window_for_cell(table, row_idx, col_idx)
                except IndexError:
                    continue
                if window not in seen:
                    seen.add(window)
                    snippets.append(window)
            text = "\n\n".join(snippets) if snippets else " ".join(row)
            tokens = _tokenize(text)
            layout_id = f"{path.name}:row{row_idx}"
            buckets = _default_buckets(path.name, row_idx, layout_id)
            row_claims = [
                Claim(key=c.key, type=c.type, buckets=buckets, ctx=c.ctx)
                for c in claims_by_row.get(row_idx, [])
            ]
            record = {
                "file": path.name,
                "chunk_id": row_idx,
                "text": text,
                "tokens": tokens,
                "timestamp": timestamp.isoformat(),
                "version_id": path.name,
                "claims": row_claims,
                "layout_id": layout_id,
                "hierarchy": _hierarchy_address(path.name, row_idx, layout_id=layout_id),
            }
            chunk_records.append(record)
            all_tokens.append(tokens)

    if not chunk_records:
        raise RuntimeError("No chunks built from data directory")

    vocab = _build_vocab(all_tokens)
    vecs, embedder = _build_chunk_vectors(chunk_records, vocab, cfg)
    embedding_backend = _embedding_backend(cfg)

    eps = 1e-6
    dim = vecs.shape[1] if vecs.ndim == 2 else len(vocab)
    if vecs.shape[0] <= 1:
        mean_vec = vecs.mean(axis=0) if vecs.size else np.zeros(dim, dtype=float)
        whiten_matrix = np.eye(dim, dtype=float)
    else:
        mean_vec = vecs.mean(axis=0)
        centered = vecs - mean_vec
        cov = (centered.T @ centered) / max(vecs.shape[0] - 1, 1)
        try:
            U, S, _ = np.linalg.svd(cov, full_matrices=False)
        except np.linalg.LinAlgError:
            U = np.eye(cov.shape[0], dtype=float)
            S = np.ones(cov.shape[0], dtype=float)
        inv_sqrt = np.diag(1.0 / np.sqrt(S + eps))
        whiten_matrix = U @ inv_sqrt @ U.T

    whitened_vecs = whiten_embeddings(vecs, mean_vec, whiten_matrix)
    norms = np.linalg.norm(whitened_vecs, axis=1, keepdims=True)
    norms[norms <= eps] = 1.0
    whitened_vecs = whitened_vecs / norms

    doc_to_indices: Dict[str, List[int]] = defaultdict(list)
    for idx, chunk in enumerate(chunk_records):
        doc_id = str(chunk.get("file", f"doc_{idx}"))
        doc_to_indices[doc_id].append(idx)

    prototypes = _build_doc_prototypes(chunk_records, whitened_vecs, cfg, doc_to_indices)
    # Build segment-level prototypes for fractal (multi-scale) routing
    proto_segments = _build_segment_prototypes(chunk_records, whitened_vecs, cfg)

    calibration = _calibrate_confidence_payload(prototypes, whitened_vecs, doc_to_indices, cfg)

    return _CorpusCache(
        chunks=chunk_records,
        vocab=vocab,
        chunk_vecs=whitened_vecs,
        lattice=lattice,
        sparse_index=sparse_index,
        prototypes=prototypes,
        prototypes_by_segment=proto_segments,
        whiten_mean=mean_vec.astype(float, copy=False),
        whiten_matrix=whiten_matrix.astype(float, copy=False),
        calibration=calibration,
        embedding_backend=embedding_backend,
        embedder=embedder,
        calibration_by_domain={},
        calibration_by_task={},
        metadata={
            "sklearn_version": _current_sklearn_version(),
            "schema_version": 1,
        },
    )








def _serialize_claim(claim: Claim) -> Dict[str, Any]:
    return {
        "key": claim.key,
        "type": claim.type.value,
        "buckets": list(claim.buckets),
        "ctx": claim.ctx,
    }


def _deserialize_claim(payload: Mapping[str, Any]) -> Claim:
    buckets = tuple(payload.get("buckets", ()))
    ctx = payload.get("ctx")
    return Claim(
        key=str(payload.get("key")),
        type=ClaimType(str(payload.get("type"))),
        buckets=buckets,
        ctx=ctx,
    )


def _serialize_prototype(proto: PrototypeRecord) -> Dict[str, Any]:
    return {
        "doc_id": proto.doc_id,
        "centroid": proto.centroid.tolist(),
        "basis": proto.basis.tolist(),
        "timestamp": proto.timestamp,
        "feature_medians": proto.feature_medians,
        "feature_mads": proto.feature_mads,
    }


def _deserialize_prototype(payload: Mapping[str, Any]) -> PrototypeRecord:
    centroid = np.asarray(payload.get("centroid", []), dtype=float)
    if centroid.ndim == 2:
        centroid = centroid.reshape(-1)
    basis = np.asarray(payload.get("basis", []), dtype=float)
    if basis.ndim == 1:
        basis = basis[:, None]
    elif basis.ndim == 0:
        basis = np.zeros((centroid.shape[0], 0), dtype=float)
    timestamp = float(payload.get("timestamp", 0.0))
    medians = dict(payload.get("feature_medians", {}))
    mads = dict(payload.get("feature_mads", {}))
    if not mads:
        mads = {"Delta_d": 1.0, "mean_kNN": 1.0, "dc": 1.0}
    return PrototypeRecord(
        doc_id=str(payload.get("doc_id", "")),
        centroid=centroid,
        basis=basis,
        timestamp=timestamp,
        feature_medians=medians,
        feature_mads=mads,
    )
def _serialize_calibration(payload: CalibrationPayload) -> Dict[str, Any]:
    return {
        "logistic_coefs": dict(payload.logistic_coefs),
        "temperature": float(payload.temperature),
        "tau1": float(payload.tau1),
        "tau2": float(payload.tau2),
    }


def _required_persist_files(root: Path) -> list[Path]:
    return [
        root / "chunks.json",
        root / "chunk_vecs.npy",
        root / "prototypes.json",
        root / "whiten_mean.npy",
        root / "whiten_matrix.npy",
        root / "calibration.json",
        root / "embedding.json",
    ]


def _latest_mtime(paths: Iterable[Path]) -> float:
    latest = 0.0
    for path in paths:
        if path.exists():
            latest = max(latest, path.stat().st_mtime)
    return latest


def _persisted_corpus_is_stale(persist_path: Path, data_root: Path) -> bool:
    required_files = _required_persist_files(persist_path)
    if any(not path.exists() for path in required_files):
        return True

    persisted_mtime = _latest_mtime(required_files)
    data_files = list(data_root.glob("*.txt")) + list(data_root.glob("*.csv"))
    if not data_files:
        return False
    data_mtime = _latest_mtime(data_files)
    return data_mtime > persisted_mtime


def _deserialize_calibration(payload: Mapping[str, Any], fallback_cfg: FRAMConfig | None = None) -> CalibrationPayload:
    cfg = fallback_cfg or FRAMConfig()
    if not payload:
        return _default_calibration(cfg)
    logistic_coefs = dict(payload.get("logistic_coefs", {}))
    if not logistic_coefs:
        return _default_calibration(cfg)
    g = float(logistic_coefs.get("g", 0.0))
    if g < 0.0:
        raise ValueError(
            "calibration coefficient 'g' must be non-negative so increasing "
            "centroid distance cannot increase confidence"
        )
    temperature = float(payload.get("temperature", 1.0))
    tau1 = float(payload.get("tau1", cfg.tau1))
    tau2 = float(payload.get("tau2", cfg.tau2))
    if tau2 >= tau1:
        tau2 = max(1e-6, tau1 - 1e-6)
    return CalibrationPayload(
        logistic_coefs={k: float(v) for k, v in logistic_coefs.items()},
        temperature=float(temperature),
        tau1=float(tau1),
        tau2=float(tau2),
    )


def _append_calibration_record(root: Path, record: Mapping[str, Any]) -> None:
    try:
        calib_dir = root / "observability"
        calib_dir.mkdir(parents=True, exist_ok=True)
        path = calib_dir / "calibration.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:  # pragma: no cover - logging best effort
        pass


def _hierarchy_address(
    doc_id: str,
    chunk_id: int,
    layout_id: str | None = None,
    section: str | None = None,
) -> Dict[str, str]:
    cluster = f"doc:{doc_id}"
    if layout_id:
        segment = f"layout:{layout_id}"
    elif section:
        segment = f"section:{section}"
    else:
        segment = f"seg:{chunk_id // 4}"
    leaf = f"chunk:{chunk_id}"
    return {"cluster": cluster, "segment": segment, "chunk": leaf}

def _slugify(text: str) -> str:
    slug = _SLUG_PATTERN.sub("_", text.lower()).strip("_")
    return slug or "section"


def _heading_sections(text: str) -> List[tuple[int, str]]:
    sections: List[tuple[int, str]] = []
    stack: List[str] = []
    for match in _HEADING_MARKER_RE.finditer(text):
        level = int(match.group(1))
        title = match.group(2).strip()
        if not title:
            continue
        slug = _slugify(title)
        level = max(level, 1)
        stack = stack[: level - 1]
        stack.append(slug)
        sections.append((match.start(), "_".join(stack)))
    return sections


def _section_slug_for_offset(sections: Sequence[tuple[int, str]], offset: int) -> str | None:
    result: str | None = None
    for pos, slug in sections:
        if pos <= offset:
            result = slug
        else:
            break
    if result is None and sections:
        result = sections[0][1]
    return result


def save_corpus_cache(cache: _CorpusCache, dest: Path) -> None:
    """Persist a corpus cache to disk under ``dest``."""

    dest.mkdir(parents=True, exist_ok=True)

    chunks_path = dest / "chunks.json"
    vocab_path = dest / "vocab.json"
    vecs_path = dest / "chunk_vecs.npy"
    lattice_path = dest / "lattice.json"
    versions_manifest_path = dest / "versions.jsonl"
    sparse_path = dest / "sparse_index.json"
    prototypes_path = dest / "prototypes.json"
    whiten_mean_path = dest / "whiten_mean.npy"
    whiten_matrix_path = dest / "whiten_matrix.npy"
    calibration_path = dest / "calibration.json"
    embedding_meta_path = dest / "embedding.json"
    embedder_path = dest / "embedder.joblib"
    meta_path = dest / "corpus.meta.json"

    chunk_payload = [_serialize_chunk(chunk) for chunk in cache.chunks]
    chunks_path.write_text(json.dumps(chunk_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    vocab_path.write_text(json.dumps(cache.vocab, ensure_ascii=False, indent=2), encoding="utf-8")
    np.save(vecs_path, cache.chunk_vecs)
    np.save(whiten_mean_path, cache.whiten_mean)
    np.save(whiten_matrix_path, cache.whiten_matrix)

    lattice_nodes = [
        {
            "node_id": node.node_id,
            "timestamp": node.timestamp.isoformat(),
            "parents": list(node.parents),
            "diff": node.diff,
        }
        for node in getattr(cache.lattice, "_nodes", {}).values()
    ]
    lattice_path.write_text(json.dumps(lattice_nodes, ensure_ascii=False, indent=2), encoding="utf-8")
    write_version_manifest(versions_manifest_path, cache.lattice)

    sparse_index = getattr(cache.sparse_index, "_key_to_docs", {})
    sparse_payload = {key: sorted(list(docs)) for key, docs in sparse_index.items()}
    sparse_path.write_text(json.dumps(sparse_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    proto_payload = [_serialize_prototype(proto) for proto in cache.prototypes]
    prototypes_path.write_text(json.dumps(proto_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    calibration_payload = _serialize_calibration(cache.calibration)
    calibration_path.write_text(json.dumps(calibration_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    for name, payload in (cache.calibration_by_domain or {}).items():
        slug = _slugify(str(name))
        target = dest / f"calibration_{slug}.json"
        try:
            target.write_text(json.dumps(_serialize_calibration(payload), ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            continue
    for name, payload in (cache.calibration_by_task or {}).items():
        slug = _slugify(str(name))
        target = dest / f"calibration_task_{slug}.json"
        try:
            target.write_text(json.dumps(_serialize_calibration(payload), ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            continue

    embedding_meta = {"backend": cache.embedding_backend}
    embedding_meta_path.write_text(json.dumps(embedding_meta, ensure_ascii=False, indent=2), encoding="utf-8")
    if cache.embedder is not None:
        try:
            joblib_dump(cache.embedder, embedder_path)
        except Exception:
            pass
    elif embedder_path.exists():
        try:
            embedder_path.unlink()
        except Exception:
            pass

    metadata = dict(getattr(cache, "metadata", {}) or {})
    current_version = _current_sklearn_version()
    if current_version is not None:
        metadata["sklearn_version"] = current_version
    metadata.setdefault("schema_version", 1)
    metadata.setdefault("ann_backend", "sklearn")
    metadata["persisted_at"] = datetime.now(timezone.utc).isoformat()
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    cache.metadata = metadata


def _serialize_chunk(chunk: Mapping[str, Any]) -> Dict[str, Any]:
    item = dict(chunk)
    claims = item.get("claims")
    if claims is not None:
        item["claims"] = [_serialize_claim(claim) for claim in claims]
    buckets = item.get("buckets")
    if buckets is not None and isinstance(buckets, tuple):
        item["buckets"] = list(buckets)
    hierarchy = item.get("hierarchy")
    if hierarchy is not None and isinstance(hierarchy, dict):
        item["hierarchy"] = dict(hierarchy)
    return item
def load_persisted_corpus(src: Path) -> _CorpusCache:
    """Load a persisted corpus cache previously written with ``save_corpus_cache``."""

    chunks_path = src / "chunks.json"
    vocab_path = src / "vocab.json"
    vecs_path = src / "chunk_vecs.npy"
    lattice_path = src / "lattice.json"
    versions_manifest_path = src / "versions.jsonl"
    sparse_path = src / "sparse_index.json"
    prototypes_path = src / "prototypes.json"
    whiten_mean_path = src / "whiten_mean.npy"
    whiten_matrix_path = src / "whiten_matrix.npy"
    calibration_path = src / "calibration.json"
    embedding_meta_path = src / "embedding.json"
    embedder_path = src / "embedder.joblib"
    meta_path = src / "corpus.meta.json"

    if not (
        chunks_path.exists()
        and vocab_path.exists()
        and vecs_path.exists()
        and (lattice_path.exists() or versions_manifest_path.exists())
        and sparse_path.exists()
    ):
        raise FileNotFoundError(f"Persisted corpus not found under {src}")

    chunk_payload = json.loads(chunks_path.read_text(encoding="utf-8"))
    vocab_payload = json.loads(vocab_path.read_text(encoding="utf-8"))
    vecs = np.load(vecs_path, allow_pickle=False)
    lattice_payload = json.loads(lattice_path.read_text(encoding="utf-8")) if lattice_path.exists() else []
    sparse_payload = json.loads(sparse_path.read_text(encoding="utf-8"))
    proto_payload = json.loads(prototypes_path.read_text(encoding="utf-8")) if prototypes_path.exists() else None
    calibration_payload = json.loads(calibration_path.read_text(encoding="utf-8")) if calibration_path.exists() else None
    if whiten_mean_path.exists() and whiten_matrix_path.exists():
        whiten_mean = np.load(whiten_mean_path, allow_pickle=False)
        whiten_matrix = np.load(whiten_matrix_path, allow_pickle=False)
    else:
        dim = vecs.shape[1] if isinstance(vecs, np.ndarray) and vecs.ndim == 2 else int(len(vocab_payload))
        whiten_mean = np.zeros(dim, dtype=float)
        whiten_matrix = np.eye(dim, dtype=float)

    embedding_backend = _embedding_backend(FRAMConfig())
    embedder = None
    if embedding_meta_path.exists():
        try:
            metadata = json.loads(embedding_meta_path.read_text(encoding="utf-8"))
            embedding_backend = str(metadata.get("backend", embedding_backend)).lower()
        except Exception:
            pass
    if embedding_backend == "hashing":
        embedder = None
    elif embedding_backend == "tfidf":
        if embedder_path.exists():
            try:
                embedder = joblib_load(embedder_path)
            except Exception:
                embedder = None
        if embedder is None:
            raise RuntimeError("Persisted embedder missing for tfidf backend")
    else:
        embedder = None

    chunks: List[Dict[str, Any]] = []
    for raw in chunk_payload:
        item = dict(raw)
        tokens = item.get("tokens")
        if tokens is not None:
            item["tokens"] = list(tokens)
        claims = item.get("claims")
        if claims is not None:
            item["claims"] = [_deserialize_claim(c) for c in claims]
        layout_buckets = item.get("buckets")
        if layout_buckets is not None:
            item["buckets"] = tuple(layout_buckets) if isinstance(layout_buckets, list) else layout_buckets
        hierarchy = item.get("hierarchy")
        if hierarchy is not None:
            item["hierarchy"] = dict(hierarchy)
        chunks.append(item)

    vocab = {str(k): int(v) for k, v in vocab_payload.items()}

    if versions_manifest_path.exists():
        lattice = VersionLattice.from_manifest(versions_manifest_path)
    else:
        lattice = VersionLattice()
        for node_data in lattice_payload:
            node_id = str(node_data.get("node_id"))
            timestamp = datetime.fromisoformat(str(node_data.get("timestamp")))
            parents = tuple(node_data.get("parents") or ())
            diff = node_data.get("diff")
            lattice.add_node(VersionNode(node_id=node_id, timestamp=timestamp, parents=parents, diff=diff))

    sparse_index = SparseKeyIndex()
    key_to_docs = getattr(sparse_index, "_key_to_docs")
    key_to_docs.clear()
    for key, docs in sparse_payload.items():
        key_to_docs[str(key)] = set(docs)

    if proto_payload is not None:
        prototypes = [_deserialize_prototype(item) for item in proto_payload]
    else:
        cfg = FRAMConfig()
        prototypes = _build_doc_prototypes(chunks, np.asarray(vecs), cfg)

    if calibration_payload is not None:
        calibration = _deserialize_calibration(calibration_payload, FRAMConfig())
    else:
        calibration = _default_calibration(FRAMConfig())

    metadata_payload: Dict[str, Any] = {}
    if meta_path.exists():
        try:
            metadata_payload = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            metadata_payload = {}

    return _CorpusCache(
        chunks=chunks,
        vocab=vocab,
        chunk_vecs=np.asarray(vecs),
        lattice=lattice,
        sparse_index=sparse_index,
        prototypes=prototypes,
        whiten_mean=np.asarray(whiten_mean),
        whiten_matrix=np.asarray(whiten_matrix),
        calibration=calibration,
        embedding_backend=embedding_backend,
        embedder=embedder,
        metadata=metadata_payload,
    )


def _coerce_corpus(cache: Mapping[str, Any] | _CorpusCache) -> _CorpusCache:
    """Convert dict-style caches into the internal dataclass."""

    if isinstance(cache, _CorpusCache):
        return cache
    chunks = list(cache.get("chunks", []))
    vocab = dict(cache.get("vocab", {}))
    chunk_vecs = cache.get("chunk_vecs")
    lattice = cache.get("lattice")
    if chunk_vecs is None or lattice is None:
        raise ValueError("cache must include 'chunk_vecs' and 'lattice'")
    sparse_index = cache.get("sparse_index")
    whitelist_mean = cache.get("whiten_mean")
    whitelist_matrix = cache.get("whiten_matrix")
    proto_payload = cache.get("prototypes", [])
    calibration_payload = cache.get("calibration")
    embedding_backend = str(cache.get("embedding_backend", _embedding_backend(FRAMConfig()))).lower()
    embedder_payload = cache.get("embedder")
    embedder = embedder_payload if not isinstance(embedder_payload, (dict, list)) else None
    prototypes: List[PrototypeRecord] = []
    for item in proto_payload:
        if isinstance(item, PrototypeRecord):
            prototypes.append(item)
        else:
            prototypes.append(_deserialize_prototype(item))

    if not prototypes:
        cfg = FRAMConfig()
        prototypes = _build_doc_prototypes(chunks, np.asarray(chunk_vecs), cfg)

    dim = np.asarray(chunk_vecs).shape[1] if np.asarray(chunk_vecs).ndim == 2 else len(vocab)
    if whitelist_mean is None:
        whitelist_mean = np.zeros(dim, dtype=float)
    if whitelist_matrix is None:
        whitelist_matrix = np.eye(dim, dtype=float)

    if isinstance(calibration_payload, CalibrationPayload):
        calibration = calibration_payload
    elif calibration_payload:
        calibration = _deserialize_calibration(calibration_payload, FRAMConfig())
    else:
        calibration = _default_calibration(FRAMConfig())

    domain_payload = cache.get("calibration_by_domain", {})
    calibration_by_domain: Dict[str, CalibrationPayload] = {}
    if isinstance(domain_payload, Mapping):
        for key, value in domain_payload.items():
            name = str(key).strip().lower()
            if not name:
                continue
            if isinstance(value, CalibrationPayload):
                calibration_by_domain[name] = value
            else:
                try:
                    calibration_by_domain[name] = _deserialize_calibration(value, FRAMConfig())
                except Exception:
                    continue
    task_payload_map = cache.get("calibration_by_task", {})
    calibration_by_task: Dict[str, CalibrationPayload] = {}
    if isinstance(task_payload_map, Mapping):
        for key, value in task_payload_map.items():
            name = str(key).strip().lower()
            if not name:
                continue
            if isinstance(value, CalibrationPayload):
                calibration_by_task[name] = value
            else:
                try:
                    calibration_by_task[name] = _deserialize_calibration(value, FRAMConfig())
                except Exception:
                    continue
    metadata_payload = {}
    if isinstance(cache.get("metadata"), Mapping):
        metadata_payload = dict(cache.get("metadata", {}))
    return _CorpusCache(
        chunks=chunks,
        vocab=vocab,
        chunk_vecs=np.asarray(chunk_vecs),
        lattice=lattice,
        sparse_index=sparse_index,
        prototypes=prototypes,
        whiten_mean=np.asarray(whitelist_mean),
        whiten_matrix=np.asarray(whitelist_matrix),
        calibration=calibration,
        embedding_backend=embedding_backend,
        embedder=embedder,
        calibration_by_domain=calibration_by_domain,
        calibration_by_task=calibration_by_task,
        metadata=metadata_payload,
    )



def corpus_cache_to_dict(cache: _CorpusCache) -> Dict[str, Any]:
    """Convert an internal corpus cache to the dict form used by legacy helpers."""

    domain_serialized = {
        key: _serialize_calibration(payload)
        for key, payload in (cache.calibration_by_domain or {}).items()
    }
    task_serialized = {
        key: _serialize_calibration(payload)
        for key, payload in (cache.calibration_by_task or {}).items()
    }

    return {
        "chunks": list(cache.chunks),
        "vocab": dict(cache.vocab),
        "chunk_vecs": cache.chunk_vecs,
        "lattice": cache.lattice,
        "sparse_index": cache.sparse_index,
        "prototypes": [
            {
                "doc_id": proto.doc_id,
                "centroid": proto.centroid,
                "basis": proto.basis,
                "timestamp": proto.timestamp,
                "feature_medians": proto.feature_medians,
                "feature_mads": proto.feature_mads,
            }
            for proto in cache.prototypes
        ],
        "whiten_mean": cache.whiten_mean,
        "whiten_matrix": cache.whiten_matrix,
        "calibration": _serialize_calibration(cache.calibration),
        "embedding_backend": cache.embedding_backend,
        "calibration_by_domain": domain_serialized,
        "calibration_by_task": task_serialized,
        "metadata": dict(cache.metadata or {}),
    }
def export_claim_log(cache: _CorpusCache, dest: Path, dataset_name: str = "corpus") -> Path:
    """Write a JSONL claim log for coverage training (spec Section 11)."""

    dest.mkdir(parents=True, exist_ok=True)
    target = dest / f"{dataset_name}.jsonl"

    with target.open("w", encoding="utf-8") as handle:
        for chunk in cache.chunks:
            doc_id = str(chunk.get("file", ""))
            chunk_id = int(chunk.get("chunk_id", 0))
            timestamp = chunk.get("timestamp")
            layout_id = chunk.get("layout_id")
            for claim in _chunk_claims(chunk):
                entry = {
                    "doc_id": doc_id,
                    "chunk_id": chunk_id,
                    "timestamp": timestamp,
                    "layout_id": layout_id,
                    "claim": {
                        "key": claim.key,
                        "type": claim.type.value,
                        "buckets": list(claim.buckets),
                        "ctx": claim.ctx,
                    },
                }
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return target


class QueryOrchestrator:
    """Orchestrates the demo retrieval pipeline (docs/F-RAM-roadmap.md, Step 2)."""

    def __init__(
        self,
        config: Optional[FRAMConfig] = None,
        tracer: Optional[TraceWriter] = None,
        *,
        data_root: Optional[Path] = None,
        reranker: Optional[Reranker] = None,
        embedder: Optional[Any] = None,
        persist_path: Optional[Path] = None,
        include_legacy: bool = False,
    ) -> None:
        self.config = config or FRAMConfig()
        self.tracer = tracer
        self.data_root = data_root or Path(__file__).resolve().parents[1] / "examples" / "data"
        index_dir = Path(self.config.STORAGE_ROOT) / self.config.STORAGE_SUBFOLDERS.get("index", "index")
        self.persist_path = persist_path or (index_dir / "demo_corpus")
        self._cache: Optional[_CorpusCache] = None
        self._reranker = reranker or SimpleCosineReranker()
        self._ann_index: Any = None
        self._ann_size: int = 0
        self._embedding_backend = _embedding_backend(self.config)
        self._include_legacy = bool(include_legacy)
        self._session_memory: List[Dict[str, Any]] = []
        self._tc_probe = TransitionalComplexityProbe()
        if embedder is not None:
            self._embedder = embedder
        elif self._embedding_backend == "hashing":
            self._embedder = _make_hashing_vectorizer(self.config)
        elif self._embedding_backend in {"vocab", "tokens", "tfidf"}:
            self._embedder = None
        else:
            raise ValueError(f"Unsupported embedding_backend: {self._embedding_backend}")
        self._ann_backend = _resolve_ann_backend()
        ann_suffix = "faiss" if self._ann_backend == "faiss" else "joblib"
        self._ann_index_filename = f"ann_index.{ann_suffix}"
        if self.persist_path is not None:
            self._ann_index_path = self.persist_path / self._ann_index_filename
            self._ann_meta_path = self.persist_path / "ann_index.meta.json"
            self._ann_legacy_joblib_path = self.persist_path / "ann_index.joblib"
        else:
            self._ann_index_path = None
            self._ann_meta_path = None
            self._ann_legacy_joblib_path = None
        self._ann_fingerprint: Optional[str] = None
        self._ann_loaded_from_disk = False

    def _ensure_ann_index(self, chunk_vecs: np.ndarray) -> None:
        if self._ann_backend == "faiss":
            if faiss is None:
                self._ann_backend = "sklearn"
                if self.persist_path is not None:
                    self._ann_index_filename = "ann_index.joblib"
                    self._ann_index_path = self.persist_path / self._ann_index_filename
            else:
                if self._ann_index is not None and self._ann_size == chunk_vecs.shape[0]:
                    return
                index = faiss.IndexFlatIP(chunk_vecs.shape[1])
                data = np.asarray(chunk_vecs, dtype=np.float32, copy=False)
                if data.dtype != np.float32:
                    data = data.astype(np.float32)
                index.add(data)
                self._ann_index = index
                self._ann_size = chunk_vecs.shape[0]
                if self._ann_fingerprint is not None:
                    self._persist_ann_index(chunk_vecs, self._ann_fingerprint)
                return
        if NearestNeighbors is None:
            self._ann_index = None
            self._ann_size = 0
            return
        if self._ann_index is not None and self._ann_size == chunk_vecs.shape[0]:
            return
        ann = NearestNeighbors(metric="cosine", algorithm="brute")
        ann.fit(chunk_vecs)
        self._ann_index = ann
        self._ann_size = chunk_vecs.shape[0]
        if self._ann_fingerprint is not None:
            self._persist_ann_index(chunk_vecs, self._ann_fingerprint)

    def _persist_ann_index(self, chunk_vecs: np.ndarray, fingerprint: str) -> None:
        if self._ann_index_path is None or self._ann_meta_path is None or self._ann_index is None:
            return
        try:
            if self._ann_backend == "faiss" and faiss is not None:
                faiss.write_index(self._ann_index, str(self._ann_index_path))
                if (
                    self._ann_legacy_joblib_path is not None
                    and self._ann_legacy_joblib_path.exists()
                    and self._ann_legacy_joblib_path != self._ann_index_path
                ):
                    with contextlib.suppress(Exception):
                        self._ann_legacy_joblib_path.unlink()
            else:
                joblib_dump(self._ann_index, self._ann_index_path)
                if (
                    self._ann_backend == "sklearn"
                    and self._ann_legacy_joblib_path is not None
                    and self._ann_index_path != self._ann_legacy_joblib_path
                    and self._ann_legacy_joblib_path.exists()
                ):
                    with contextlib.suppress(Exception):
                        self._ann_legacy_joblib_path.unlink()
            meta: Dict[str, Any] = {
                "fingerprint": fingerprint,
                "size": int(chunk_vecs.shape[0]),
                "backend": self._ann_backend,
                "backend_version": _ann_backend_version(self._ann_backend),
                "file": self._ann_index_path.name if self._ann_index_path is not None else None,
            }
            if self._ann_backend == "sklearn":
                meta["sklearn_version"] = _current_sklearn_version()
            self._ann_meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def _load_ann_from_disk(self, chunk_vecs: np.ndarray, fingerprint: str) -> None:
        if self.persist_path is None or self._ann_meta_path is None or not self._ann_meta_path.exists():
            return
        try:
            meta = json.loads(self._ann_meta_path.read_text(encoding="utf-8"))
        except Exception:
            return
        if meta.get("fingerprint") != fingerprint:
            return
        persisted_backend = str(meta.get("backend") or "sklearn").lower()
        if persisted_backend not in {"faiss", "sklearn"}:
            persisted_backend = "sklearn"
        if self._ann_backend != persisted_backend:
            return
        file_name = meta.get("file")
        index_path: Optional[Path]
        if file_name:
            index_path = self.persist_path / file_name
        else:
            index_path = self._ann_index_path
        if (index_path is None or not index_path.exists()) and self._ann_legacy_joblib_path is not None:
            if self._ann_legacy_joblib_path.exists():
                index_path = self._ann_legacy_joblib_path
        if index_path is None or not index_path.exists():
            return
        if persisted_backend == "faiss":
            if faiss is None:
                return
            persisted_version = meta.get("backend_version")
            current_version = _faiss_version()
            if current_version and persisted_version and persisted_version != current_version:
                return
            try:
                ann = faiss.read_index(str(index_path))
            except Exception:
                return
        else:
            persisted_version = meta.get("sklearn_version") or meta.get("backend_version")
            current_version = _current_sklearn_version()
            if current_version and persisted_version and persisted_version != current_version:
                return
            if current_version and persisted_version is None:
                return
            try:
                ann = joblib_load(index_path)
            except Exception:
                return
        try:
            size = int(meta.get("size", 0))
        except Exception:
            size = chunk_vecs.shape[0]
        self._ann_backend = "faiss" if persisted_backend == "faiss" else "sklearn"
        self._ann_index_filename = index_path.name
        self._ann_index_path = index_path
        self._ann_index = ann
        self._ann_size = size
        self._ann_loaded_from_disk = True

    def _embed_query_counts(
        self,
        text: str,
        tokens: Sequence[str],
        vocab: Mapping[str, int],
        chunk_vecs: np.ndarray,
    ) -> np.ndarray:
        vec_dim = chunk_vecs.shape[1] if isinstance(chunk_vecs, np.ndarray) and chunk_vecs.ndim == 2 else 0
        vocab_size = len(vocab)
        use_embedder = (
            self._embedder is not None
            and (self._embedding_backend != "vocab" or (vec_dim and vec_dim != vocab_size))
        )
        if use_embedder:
            transform = getattr(self._embedder, "transform", None)
            if callable(transform):
                q_data = transform([text])
                if hasattr(q_data, "toarray"):
                    q_array = q_data.toarray()
                else:
                    q_array = np.asarray(q_data)
                if q_array.ndim == 2:
                    q_array = q_array[0]
                return np.asarray(q_array, dtype=float)
            embed_fn = getattr(self._embedder, "embed", None)
            if callable(embed_fn):
                q_array = embed_fn(text)
                return np.asarray(q_array, dtype=float)
            if callable(self._embedder):
                q_array = self._embedder(text)
                return np.asarray(q_array, dtype=float)
            raise TypeError("Embedder must expose transform(), embed(), or be callable")
        if vec_dim and vec_dim != vocab_size:
            raise RuntimeError(
                "Chunk vectors dimension does not match vocab; provide a compatible embedder or rebuild corpus"
            )
        return _vectorize(tokens, vocab)

    def get_embeddings_for_shortlist(
        self,
        query_text: str,
        shortlist_items: Sequence[Mapping[str, Any]],
    ) -> tuple[list[float], list[list[float]]]:
        """Return embeddings for the query and shortlist items without altering scoring."""
        cache = self.ensure_corpus()
        chunk_vecs = getattr(cache, "chunk_vecs", None)
        vocab = getattr(cache, "vocab", {}) or {}
        if not isinstance(chunk_vecs, np.ndarray) or chunk_vecs.size == 0:
            return [], []
        query_tokens = tokenize_text(query_text or "")
        query_vec = self._embed_query_counts(query_text or "", query_tokens, vocab, chunk_vecs)
        episode_vecs: list[list[float]] = []
        for item in shortlist_items:
            text: str = ""
            if isinstance(item, Mapping):
                text = str(item.get("text") or item.get("content") or "")
            else:
                text = str(getattr(item, "text", "") or "")
            tokens = tokenize_text(text)
            vec = self._embed_query_counts(text, tokens, vocab, chunk_vecs)
            episode_vecs.append(vec.astype(float, copy=False).ravel().tolist())
        return query_vec.astype(float, copy=False).ravel().tolist(), episode_vecs

    def _build_cluster_context(
        self,
        seed_idx: int,
        doc_proto_map: Mapping[str, PrototypeRecord],
        doc_to_chunk_indices: Mapping[str, List[int]],
        chunk_vecs: np.ndarray,
        chunks: Sequence[Mapping[str, Any]],
        allowed_versions: Optional[set[str]],
        cand_order: Sequence[int],
        doc_sorted_indices: Mapping[str, Sequence[int]],
        projected_query: Optional[np.ndarray] = None,
        *,
        dropped_counter: Optional[Dict[str, int]] = None,
    ) -> _ClusterContext:
        seed_doc = str(chunks[seed_idx].get("file", ""))
        proto = doc_proto_map.get(seed_doc)
        if proto is not None:
            centroid = proto.centroid.astype(float, copy=False)
            basis = proto.basis.astype(float, copy=False)
            if basis.shape[1] > self.config.hot_rank_cap:
                basis = basis[:, : self.config.hot_rank_cap]
            medians = dict(proto.feature_medians)
            mads = dict(proto.feature_mads)
            timestamp = float(proto.timestamp)
        else:
            indices = list(doc_to_chunk_indices.get(seed_doc, ())) or [seed_idx]
            if chunk_vecs.size:
                doc_vecs = chunk_vecs[indices]
                dim = doc_vecs.shape[1]
            else:
                dim = chunk_vecs.shape[1] if isinstance(chunk_vecs, np.ndarray) and chunk_vecs.ndim == 2 else 0
                doc_vecs = np.zeros((0, dim), dtype=float)
            centroid = _normalize_vector(doc_vecs.mean(axis=0)) if doc_vecs.size else np.zeros((dim,), dtype=float)
            centered = doc_vecs - centroid if doc_vecs.size else np.zeros((0, dim), dtype=float)
            try:
                _, _, vh = np.linalg.svd(centered, full_matrices=False)
            except np.linalg.LinAlgError:
                vh = np.eye(dim, dtype=float)
            available_rank = vh.shape[0] if vh.ndim == 2 else 0
            rank = min(self.config.hot_rank_cap, available_rank)
            basis = vh[:rank].T if vh.ndim == 2 and vh.size and rank > 0 else np.zeros((dim, 0), dtype=float)
            delta_vals: List[float] = []
            dc_vals: List[float] = []
            if doc_vecs.size:
                for vec in doc_vecs:
                    delta_vals.append(float(projection_help_delta(vec, centroid, basis)) if basis.size else 0.0)
                    dc_vals.append(float(centroid_distance(vec, centroid)))
            density_samples: List[float] = []
            if doc_vecs.shape[0] > 1:
                density_samples.append(float(pairwise_mean_knn_dist(centroid, doc_vecs)))
            if not density_samples:
                density_samples.append(0.0)
            delta_median, delta_mad = _robust_stats(delta_vals)
            dc_median, dc_mad = _robust_stats(dc_vals)
            mean_knn_median, mean_knn_mad = _robust_stats(density_samples)
            medians = {"Delta_d": delta_median, "mean_kNN": mean_knn_median, "dc": dc_median}
            mads = {"Delta_d": delta_mad, "mean_kNN": mean_knn_mad, "dc": dc_mad}
            timestamp = _chunk_timestamp(chunks[seed_idx])
        projection_vec = projected_query.astype(float, copy=False) if projected_query is not None else None
        if projection_vec is not None:
            proj_norm = float(np.linalg.norm(projection_vec))
            if proj_norm > 1e-12:
                projection_vec = projection_vec / proj_norm
            else:
                projection_vec = None
        neighbor_indices: List[int] = []
        ordered_indices = list(doc_sorted_indices.get(seed_doc, doc_to_chunk_indices.get(seed_doc, [])))
        primary_pool = [idx for idx in ordered_indices if idx != seed_idx]
        if not primary_pool:
            primary_pool = [idx for idx in doc_to_chunk_indices.get(seed_doc, []) if idx != seed_idx]
        for idx in primary_pool:
            if allowed_versions is not None:
                vid = str(chunks[idx].get("version_id") or chunks[idx].get("file") or "")
                if vid not in allowed_versions:
                    if dropped_counter is not None:
                        dropped_counter["count"] = dropped_counter.get("count", 0) + 1
                    continue
            neighbor_indices.append(int(idx))
            if len(neighbor_indices) >= self.config.k0:
                break
        if len(neighbor_indices) < self.config.k0:
            for idx in cand_order:
                if idx == seed_idx or idx in neighbor_indices:
                    continue
                if allowed_versions is not None:
                    vid = str(chunks[idx].get("version_id") or chunks[idx].get("file") or "")
                    if vid not in allowed_versions:
                        if dropped_counter is not None:
                            dropped_counter["count"] = dropped_counter.get("count", 0) + 1
                        continue
                neighbor_indices.append(int(idx))
                if len(neighbor_indices) >= self.config.k0:
                    break
        return _ClusterContext(
            centroid=centroid,
            basis=basis,
            medians=medians,
            mads=mads,
            timestamp=timestamp,
            neighbor_indices=neighbor_indices,
            projection=projection_vec,
        )

    def _curvature_anchor_candidates(
            self,
            seed_idx: int,
            context: _ClusterContext,
            doc_projections: Mapping[str, np.ndarray],
            chunk_vecs: np.ndarray,
            chunks: Sequence[Mapping[str, Any]],
            ann_indices: Sequence[int],
            cand_order: Sequence[int],
            doc_to_chunk_indices: Mapping[str, Sequence[int]],
            cost_entries: Mapping[int, Mapping[str, float]],
            lambda_tokens: float,
            lambda_rerank: float,
            pairs_scale: float,
        ) -> _AnchorPlan:
            """Select anchor probes by following local curvature with Delta/C-style scoring."""

            fallback = [int(idx) for idx in ann_indices if idx in cand_order]
            if seed_idx >= len(chunks):
                return _AnchorPlan(fallback, {})
            seed_doc = str(chunks[seed_idx].get("file", ""))
            doc_indices_all = list(doc_to_chunk_indices.get(seed_doc, ()))
            if (
                not doc_indices_all
                or not isinstance(chunk_vecs, np.ndarray)
                or chunk_vecs.ndim != 2
                or chunk_vecs.size == 0
            ):
                return _AnchorPlan(fallback, {})
            try:
                doc_vectors_all = chunk_vecs[doc_indices_all]
            except (IndexError, ValueError):
                return _AnchorPlan(fallback, {})
            if doc_vectors_all.size == 0:
                return _AnchorPlan(fallback, {})

            centroid = context.centroid
            basis = context.basis
            dr = int(getattr(self.config, "dr", 3))
            directions, eigenvalues = principal_residual_directions(
                doc_vectors_all, centroid, basis, max(dr, 1)
            )
            if directions.size == 0:
                return _AnchorPlan(fallback, {})
            eigenvalues = eigenvalues[: directions.shape[1]]

            radii = np.linalg.norm(doc_vectors_all - centroid, axis=1)
            base_vec = doc_projections.get(seed_doc, context.projection)
            if base_vec is None or not isinstance(base_vec, np.ndarray) or base_vec.size == 0:
                base_vec = centroid
            base_vec = base_vec.astype(float, copy=False)
            base_norm = float(np.linalg.norm(base_vec))
            if base_norm > 1e-12:
                base_vec = base_vec / base_norm

            doc_candidates = [int(idx) for idx in doc_indices_all if idx in cand_order]
            if not doc_candidates:
                return _AnchorPlan(fallback, {})
            doc_vec_lookup = {idx: chunk_vecs[idx] for idx in doc_candidates}
            order_map = {int(idx): pos for pos, idx in enumerate(cand_order)}
            candidate_scores: Dict[int, float] = {}
            candidate_steps: Dict[int, Dict[str, float]] = {}

            step_cfg = getattr(self.config, "step_s", (0.7, 1.2))
            if isinstance(step_cfg, (list, tuple)):
                step_scales = tuple(float(s) for s in step_cfg if float(s) > 1e-12)
            else:
                step_scales = ()
            if not step_scales:
                step_scales = (0.7, 1.2)

            radial_cfg = getattr(self.config, "radial_pct", (0.6, 0.9))
            if isinstance(radial_cfg, (list, tuple)) and len(radial_cfg) >= 2:
                r_lo_q = float(radial_cfg[0])
                r_hi_q = float(radial_cfg[1])
            else:
                r_lo_q, r_hi_q = 0.6, 0.9
            r_lo_q = float(np.clip(r_lo_q, 0.0, 1.0))
            r_hi_q = float(np.clip(r_hi_q, 0.0, 1.0))
            if r_hi_q < r_lo_q:
                r_lo_q, r_hi_q = r_hi_q, r_lo_q
            if radii.size:
                r_lo = float(np.quantile(radii, r_lo_q))
                r_hi = float(np.quantile(radii, r_hi_q))
            else:
                r_lo = r_hi = 0.0

            def _composite_cost(idx: int) -> float:
                entry = cost_entries.get(int(idx), {})
                reads = float(entry.get("reads", 1.0))
                tokens = float(entry.get("tokens", 0.0))
                pairs_weight = float(entry.get("pairs_scale", pairs_scale))
                cost = reads + lambda_tokens * tokens + lambda_rerank * pairs_weight
                return float(max(cost, 1e-6))

            max_dirs = directions.shape[1]
            for eig_idx in range(max_dirs):
                eigval = float(eigenvalues[eig_idx]) if eig_idx < eigenvalues.size else 0.0
                if eigval <= 0.0:
                    continue
                direction = directions[:, eig_idx]
                base_length = float(np.sqrt(eigval))
                for sign in (-1.0, 1.0):
                    for scale in step_scales:
                        target = float(scale) * base_length
                        if target <= 0.0:
                            continue
                        length = target
                        if r_hi > 0.0:
                            length = float(np.clip(target, r_lo, r_hi))
                        if length <= 0.0:
                            continue
                        candidate_vec = base_vec + sign * length * direction
                        cand_norm = float(np.linalg.norm(candidate_vec))
                        if cand_norm <= 1e-12:
                            continue
                        candidate_vec = candidate_vec / cand_norm
                        best_idx, best_cos = max(
                            (
                                (idx, float(np.dot(doc_vec_lookup[idx], candidate_vec)))
                                for idx in doc_candidates
                            ),
                            key=lambda item: item[1],
                        )
                        cost = _composite_cost(best_idx)
                        score = float(length) / cost
                        existing = candidate_scores.get(best_idx)
                        if existing is None or score > existing:
                            candidate_scores[best_idx] = score
                            candidate_steps[best_idx] = {
                                "eig_index": int(eig_idx),
                                "eig_value": float(eigval),
                                "base_length": float(base_length),
                                "step_scale": float(scale),
                                "step_sign": -1 if sign < 0 else 1,
                                "target_length": float(target),
                                "clamped_length": float(length),
                                "projection_cos": float(best_cos),
                                "radial_low": float(r_lo),
                                "radial_high": float(r_hi),
                                "score": float(score),
                                "composite_cost": float(cost),
                            }

            if not candidate_scores:
                return _AnchorPlan(fallback, {})

            ranked = [
                idx
                for idx, _ in sorted(
                    candidate_scores.items(),
                    key=lambda item: (-item[1], order_map.get(item[0], len(order_map))),
                )
            ]

            seen = set(ranked)
            for idx in fallback:
                if idx not in seen:
                    ranked.append(idx)
                    seen.add(idx)
            return _AnchorPlan(ranked, candidate_steps)

    def run(
        self,
        text: str,
        as_of: Optional[datetime] = None,
        budget_reads: int = 2000,
        domain: Optional[str] = None,
        task: Optional[str] = None,
        cache_override: Mapping[str, Any] | _CorpusCache | None = None,
        memory_chunks: Optional[List[Mapping[str, Any]]] = None,
        *,
        version_id: Optional[str] = None,
        replay_last: bool = True,
    ) -> Dict[str, Any]:
        if cache_override is not None:
            cache = _coerce_corpus(cache_override)
            self._cache = cache
            self._embedding_backend = getattr(cache, "embedding_backend", self._embedding_backend)
            self._embedder = getattr(cache, "embedder", self._embedder)
        else:
            cache = self._ensure_corpus()

        def _normalize_meta(value: Optional[str], fallback: Optional[str], hard_default: str) -> str:
            for candidate in (value, fallback, hard_default):
                if candidate is None:
                    continue
                text = str(candidate).strip()
                if text:
                    return text.lower()
            return hard_default

        cfg_default_domain = getattr(self.config, "default_domain", None)
        cfg_default_task = getattr(self.config, "default_task", None)
        domain = _normalize_meta(domain, cfg_default_domain, "general")
        task = _normalize_meta(task, cfg_default_task, "qa")

        if memory_chunks is not None:
            memory_chunks = [copy.deepcopy(chunk) for chunk in memory_chunks]
        elif replay_last and self._session_memory and budget_reads <= 0:
            memory_chunks = [copy.deepcopy(chunk) for chunk in self._session_memory]
        else:
            memory_chunks = None
        if memory_chunks and getattr(self.config.phase_d, "enable_priority_graph", True):
            try:
                memory_chunks = apply_priority_graph(memory_chunks, self.config.phase_d)
            except Exception:
                pass

        chunks = cache.chunks
        chunk_vecs = cache.chunk_vecs
        vocab = cache.vocab
        lattice = cache.lattice
        sparse_index = cache.sparse_index
        prototypes = cache.prototypes
        whiten_mean = cache.whiten_mean
        whiten_matrix = cache.whiten_matrix
        base_calibration = getattr(cache, "calibration", None)
        calibration_payload = base_calibration
        calibration_source = "global" if base_calibration is not None else "default"
        # Heading marker chunks are hierarchy helpers, not retrieval candidates.
        def _is_heading_marker(chunk: Mapping[str, Any]) -> bool:
            try:
                return int(chunk.get("chunk_id", 0)) >= 10_000_000
            except (TypeError, ValueError):
                return False

        if domain:
            domain_map = getattr(cache, "calibration_by_domain", {}) or {}
            domain_key = str(domain).strip().lower()
            domain_override = domain_map.get(domain_key)
            if domain_override is not None:
                calibration_payload = domain_override
                calibration_source = f"domain:{domain_key}"

        if task:
            task_map = getattr(cache, "calibration_by_task", {}) or {}
            task_key = str(task).strip().lower()
            task_override = task_map.get(task_key)
            if task_override is not None:
                calibration_payload = task_override
                calibration_source = f"task:{task_key}"

        if calibration_payload is None:
            calibration_payload = _default_calibration(self.config)
            calibration_source = "default"

        coef_source = calibration_payload.logistic_coefs if calibration_payload else {}
        logistic_coefs = {k: float(v) for k, v in coef_source.items()}
        if not logistic_coefs:
            logistic_coefs = _default_calibration(self.config).logistic_coefs
        else:
            for key in ("a", "b", "c", "g", "h", "d"):
                logistic_coefs.setdefault(key, 0.0)
        temperature = float(calibration_payload.temperature) if calibration_payload else 1.0
        tau1 = float(calibration_payload.tau1) if calibration_payload else float(self.config.tau1)
        tau2 = float(calibration_payload.tau2) if calibration_payload else float(self.config.tau2)

        overrides: Dict[str, float] = {}
        if domain and domain in self.config.domain_overrides:
            overrides.update(self.config.domain_overrides[domain])
        if task and task in self.config.task_overrides:
            overrides.update(self.config.task_overrides[task])

        if "tau1" in overrides:
            tau1 = float(overrides["tau1"])
        if "tau2" in overrides:
            tau2 = float(overrides["tau2"])
        if tau2 >= tau1:
            tau2 = max(1e-6, tau1 - 1e-6)

        reads_override = overrides.get("default_query_reads")
        if reads_override is not None:
            reads_budget_total = max(0, int(round(float(reads_override))))
        else:
            reads_budget_total = max(0, int(budget_reads))
        memory_preselected = len(memory_chunks) if memory_chunks else 0
        slot_budget_raw = getattr(self.config, "cognitive_memory_slot_budget", None)
        try:
            slot_budget = int(slot_budget_raw) if slot_budget_raw is not None else None
        except Exception:
            slot_budget = None
        unbounded_memory = slot_budget is not None and slot_budget <= 0
        if unbounded_memory:
            reads_budget_total_eff = max(0, reads_budget_total)
        else:
            reads_budget_total_eff = max(0, reads_budget_total - memory_preselected)

        lambda_tok_effective = float(overrides.get("lambda_tok", self.config.lambda_tok))
        lambda_rerank_effective = float(overrides.get("lambda_rerank", self.config.lambda_rerank))
        pairs_scale_effective = float(overrides.get("pairs_scale", self.config.pairs_scale))
        coverage_gamma_effective = float(overrides.get("coverage_gamma", self.config.coverage_gamma))
        coverage_u_max_effective = int(overrides.get("coverage_u_max", self.config.coverage_u_max))
        section_repeat_penalty_effective = float(
            overrides.get("section_repeat_penalty", self.config.section_repeat_penalty)
        )
        section_penalty_floor_effective = float(
            overrides.get("section_penalty_floor", self.config.section_penalty_floor)
        )

        prototype_bank, proto_docs = _prototype_bank_from_records(prototypes)
        doc_proto_map: Dict[str, PrototypeRecord] = {record.doc_id: record for record in prototypes}
        doc_to_chunk_indices: Dict[str, List[int]] = {}
        for idx, chunk in enumerate(chunks):
            if _is_heading_marker(chunk):
                continue
            doc_id = str(chunk.get("file", ""))
            doc_to_chunk_indices.setdefault(doc_id, []).append(idx)


        t_start = time.perf_counter()
        latency_trace: Dict[str, float] = {}

        as_of_set: Optional[set[str]] = None
        version_map: Dict[str, str] = {}
        excluded_versions = 0
        if as_of is not None or version_id is not None:
            as_of_utc = None
            if as_of is not None:
                as_of_utc = as_of.astimezone(timezone.utc) if as_of.tzinfo else as_of.replace(tzinfo=timezone.utc)
            as_of_set = lattice.select_ids(as_of_utc, version_id=version_id)
            if version_id is not None:
                base_id = lattice.base_id(version_id)
                if as_of_set:
                    version_map = {base_id: version_id}
            elif as_of_utc is not None:
                version_map = lattice.active_version_map(as_of_utc)
                as_of_set = set(version_map.values())
            excluded_versions = max(0, len(lattice) - len(as_of_set or set()))
        allowed_versions: Optional[set[str]] = None
        as_of_dropped: Dict[str, int] = {"count": 0}
        if as_of is not None:
            as_of_utc = as_of.astimezone(timezone.utc) if as_of.tzinfo else as_of.replace(tzinfo=timezone.utc)
            allowed_versions = lattice.active_with_ancestors(as_of_utc)
        elif version_id is not None:
            allowed_versions = set(as_of_set or set())

        def _version_allowed(chunk: Mapping[str, Any]) -> bool:
            if allowed_versions is None:
                return True
            vid = str(chunk.get("version_id") or chunk.get("file") or "")
            allowed = bool(vid) and vid in allowed_versions
            if not allowed:
                as_of_dropped["count"] = as_of_dropped.get("count", 0) + 1
            return allowed

        q_tokens = _tokenize(text)
        q_focus_tokens = _focus_query_tokens(q_tokens)
        q_counts = self._embed_query_counts(text, q_tokens, vocab, chunk_vecs)
        q_whitened = whiten_embeddings(q_counts, whiten_mean, whiten_matrix)
        q_norm = float(np.linalg.norm(q_whitened))
        if q_norm > 1e-12:
            q_vec = q_whitened / q_norm
        else:
            q_vec = np.zeros_like(whiten_mean)
        transitional_complexity = self._tc_probe.update("query_embedding", q_vec)
        routing_scores = np.zeros((0,), dtype=float)
        if prototypes and q_vec.size:
            centroids = [
                proto.centroid
                for proto in prototypes
                if isinstance(getattr(proto, "centroid", None), np.ndarray)
            ]
            if centroids and all(centroid.shape == q_vec.shape for centroid in centroids):
                routing_scores = np.asarray(
                    [
                        float(np.dot(q_vec, _normalize_vector(centroid.astype(float, copy=False))))
                        for centroid in centroids
                    ],
                    dtype=float,
                )
        tc_routing = self._tc_probe.update("routing_scores", routing_scores)
        latency_trace["vectorize_ms"] = (time.perf_counter() - t_start) * 1000.0

        doc_projections: Dict[str, np.ndarray] = {}
        if q_vec.size:
            for doc, proto in doc_proto_map.items():
                projection_vec = subspace_projection(q_vec, proto.centroid, proto.basis) if proto.basis.size else proto.centroid
                doc_projections[doc] = _normalize_vector(projection_vec.astype(float, copy=False))

        sims = (chunk_vecs @ q_vec).astype(float) if q_vec.size and chunk_vecs.size else np.zeros((len(chunks),), dtype=float)
        sorted_indices = list(np.argsort(sims)[::-1]) if sims.size else list(range(len(chunks)))
        if sorted_indices:
            sorted_indices = [idx for idx in sorted_indices if not _is_heading_marker(chunks[idx])]

        ann_indices: List[int] = []
        if q_vec.size and chunk_vecs.size:
            self._ensure_ann_index(chunk_vecs)
            if self._ann_index is not None:
                neighbor_count = min(len(chunks), max(self.config.k0 * 4, self.config.G))
                try:
                    if self._ann_backend == "faiss" and faiss is not None:
                        query_vec = q_vec.astype(np.float32, copy=False)
                        if query_vec.dtype != np.float32:
                            query_vec = query_vec.astype(np.float32)
                        _, ann_idx = self._ann_index.search(query_vec.reshape(1, -1), neighbor_count)
                        ann_indices = [
                            int(idx)
                            for idx in ann_idx[0]
                            if 0 <= int(idx) < chunk_vecs.shape[0]
                            and not _is_heading_marker(chunks[int(idx)])
                        ]
                    elif self._ann_backend == "sklearn" and NearestNeighbors is not None:
                        _, ann_idx = self._ann_index.kneighbors(q_vec.reshape(1, -1), n_neighbors=neighbor_count)
                        ann_indices = [
                            int(idx)
                            for idx in ann_idx[0]
                            if not _is_heading_marker(chunks[int(idx)])
                        ]
                except Exception:
                    ann_indices = []
        if not ann_indices:
            headroom = max(self.config.k0 * 4, self.config.G, reads_budget_total)
            limit = headroom if headroom > 0 else len(sorted_indices)
            ann_indices = sorted_indices[: min(len(sorted_indices), limit)]

        shortlisted_docs: List[str] = []
        if prototype_bank is not None and q_vec.size:
            proto_idx = prototype_bank.shortlist(q_vec, self.config.k0)
            shortlisted_docs = [proto_docs[i] for i in proto_idx if i < len(proto_docs)]

        doc_sorted_indices: Dict[str, List[int]] = {}
        for doc, indices in doc_to_chunk_indices.items():
            if not indices:
                doc_sorted_indices[doc] = []
                continue
            score_map: Dict[int, float] = {}
            if doc in doc_projections and chunk_vecs.ndim == 2 and chunk_vecs.size:
                proj_vec = doc_projections[doc]
                rows = chunk_vecs.shape[0] if chunk_vecs.ndim >= 1 else 0
                for idx in indices:
                    if 0 <= idx < rows:
                        score_map[idx] = float(np.dot(chunk_vecs[idx], proj_vec))
            if len(score_map) != len(indices):
                for idx in indices:
                    if idx not in score_map:
                        score_map[idx] = float(sims[idx]) if sims.size else 0.0
            doc_sorted_indices[doc] = sorted(indices, key=lambda idx: score_map[idx], reverse=True)

        def _extend(order: List[int], indices: Iterable[int], seen: set[int]) -> None:
            for idx in indices:
                if idx in seen:
                    continue
                if _is_heading_marker(chunks[idx]):
                    continue
                if not _version_allowed(chunks[idx]):
                    continue
                seen.add(int(idx))
                order.append(int(idx))

        cand_order: List[int] = []
        seen_indices: set[int] = set()
        _extend(cand_order, ann_indices, seen_indices)
        # Fractal (multi-scale) routing: prioritize top segments when enabled
        hierarchy_scales: List[Dict[str, Any]] = []
        if getattr(self.config, "fractal_enabled", False):
            seg_protos = getattr(cache, "prototypes_by_segment", []) or []
            if seg_protos and q_vec.size:
                bank, seg_ids = _prototype_bank_from_records(seg_protos)
                if bank is not None and len(seg_ids) > 0:
                    top_k = min(self.config.k0, len(seg_ids))
                    try:
                        seg_order_idx = bank.shortlist(q_vec, top_k)
                    except Exception:
                        seg_order_idx = []
                    if not seg_order_idx:
                        # Fallback: choose segments by descending chunk count
                        by_count = sorted(
                            [(seg_id, len(seg_to_indices.get(seg_id, []))) for seg_id in seg_ids],
                            key=lambda t: t[1],
                            reverse=True,
                        )
                        pick = [seg_ids.index(seg_id) for seg_id, _ in by_count[:top_k] if seg_id in seg_ids]
                        seg_order_idx = pick
                    seg_nodes: List[Dict[str, Any]] = []
                    seg_to_indices: Dict[str, List[int]] = defaultdict(list)
                    for idx_i, chunk in enumerate(chunks):
                        h = chunk.get("hierarchy") or {}
                        seg = h.get("segment") if isinstance(h, Mapping) else None
                        if isinstance(seg, str) and seg:
                            seg_to_indices[seg].append(idx_i)
                    for si in seg_order_idx:
                        seg_id = str(seg_ids[si])
                        proto = seg_protos[si]
                        score = float(np.dot(q_vec, _normalize_vector(proto.centroid))) if q_vec.size else 0.0
                        seg_nodes.append({"id": seg_id, "score": score})
                        idxs = seg_to_indices.get(seg_id, [])
                        if idxs:
                            idxs_sorted = sorted(idxs, key=lambda ii: sims[ii] if sims.size else 0.0, reverse=True)
                            _extend(cand_order, idxs_sorted, seen_indices)
                    if seg_nodes:
                        hierarchy_scales.append({"scale": "segment", "nodes": seg_nodes})
        for doc in shortlisted_docs:
            _extend(cand_order, doc_sorted_indices.get(doc, ()), seen_indices)

        if sparse_index is not None and text:
            doc_hits = sparse_index.query(text)
            if allowed_versions is not None:
                doc_hits = [doc for doc in doc_hits if doc in allowed_versions]
            hit_indices: List[int] = []
            for doc in doc_hits:
                hit_indices.extend(doc_sorted_indices.get(doc, ()))
            _extend(cand_order, hit_indices, seen_indices)

        _extend(cand_order, sorted_indices, seen_indices)

        cand_order = _prioritize_candidates_by_query_overlap(
            cand_order,
            chunks,
            q_focus_tokens,
        )

        limit_for_candidates = max(reads_budget_total, self.config.G)
        if limit_for_candidates > 0:
            cand_order = cand_order[: min(len(cand_order), limit_for_candidates)]

        k = min(reads_budget_total, len(cand_order)) if reads_budget_total > 0 else 0
        seed_idx = cand_order[0] if cand_order and k > 0 else None

        trace_scores = [
            {
                "file": chunk.get("file"),
                "chunk_id": int(chunk.get("chunk_id", 0)),
                "score": float(sims[i]) if i < sims.size else 0.0,
                "timestamp": chunk.get("timestamp"),
            }
            for i, chunk in enumerate(chunks)
        ]

        decision_for_selection = "global"
        p_temp: Optional[float] = None
        neigh_idx: List[int] = []
        confidence_trace: Dict[str, Any] = {
            "calibration": {
                "source": calibration_source,
                "tau1": float(tau1),
                "tau2": float(tau2),
                "temperature": float(temperature),
            }
        }
        feature_samples_log: Dict[int, tuple[conf.ClusterFeatures, str]] = {}
        if isinstance(as_of, datetime):
            T_q = float(as_of.astimezone(timezone.utc).timestamp())
        else:
            T_q = float(datetime.now(timezone.utc).timestamp())
        if seed_idx is not None and q_vec.size:
            seed_doc = str(chunks[seed_idx].get("file", ""))
            context = self._build_cluster_context(
                seed_idx=seed_idx,
                doc_proto_map=doc_proto_map,
                doc_to_chunk_indices=doc_to_chunk_indices,
                chunk_vecs=chunk_vecs,
                chunks=chunks,
                allowed_versions=allowed_versions,
                cand_order=cand_order,
                doc_sorted_indices=doc_sorted_indices,
                projected_query=doc_projections.get(seed_doc),
                dropped_counter=as_of_dropped,
            )
            neigh_idx = context.neighbor_indices
            neighbors = (
                chunk_vecs[neigh_idx]
                if neigh_idx and chunk_vecs.size
                else np.zeros((0, q_vec.shape[0]), dtype=float)
            )
            feats = conf.compute_features(
                e=q_vec,
                p_k=context.centroid,
                U_k=context.basis,
                kNN_neighbors=neighbors,
                medians=context.medians,
                mads=context.mads,
                T_q=T_q,
                T_k_median=context.timestamp,
                tau_domain=self.config.tau_domain_days,
            )
            feature_samples_log[int(seed_idx)] = (feats, str(chunks[seed_idx].get("file", "")))
            p_temp = conf.logistic_confidence(feats, coefs=logistic_coefs, temperature=temperature)
            decision_for_selection = conf.conformal_policy(p_temp, tau1, tau2)
            confidence_trace.update(
                {
                    "features": {
                        "Delta_d_z": feats.Delta_d_z,
                        "rho_pos": feats.rho_pos,
                        "mhd": feats.mhd,
                        "d_c_z": feats.d_c_z,
                        "fresh": feats.fresh,
                    },
                    "decision": decision_for_selection,
                }
            )
            projection_vec = context.projection
            if projection_vec is not None and projection_vec.size and q_vec.size:
                confidence_trace["projection"] = {
                    "cos": float(np.dot(q_vec, projection_vec)),
                    "norm": float(np.linalg.norm(projection_vec)),
                }
                confidence_trace["projection_error"] = float(np.linalg.norm(q_vec - projection_vec))

        gamma = float(coverage_gamma_effective)
        u_max = int(coverage_u_max_effective)
        selection_trace = {
            "anchors": [],
            "shards": [],
            "memory": [],
            "celf_stats": {"pops": 0, "recomps": 0, "accepted": 0},
            "budgets": {
                "reads": 0.0,
                "tokens": 0.0,
                "pairs": 0.0,
                "cost": 0.0,
                "reranker_pairs": 0.0,
                "reads_limit": float(reads_budget_total),
                "reads_used": 0.0,
                "lambda_tok": float(lambda_tok_effective),
                "lambda_rerank": float(lambda_rerank_effective),
                "pairs_scale": float(pairs_scale_effective),
            },
        }

        doc_alignment_details: List[Dict[str, Any]] = []
        coverage_weights: Dict[str, float] = {}

        coverage_state: CoverageState | None = None
        coverage_baseline = 0.0
        coverage_start = 0.0
        memory_delta = 0.0
        coverage_breakdown: Dict[str, float] = {
            "memory": 0.0,
            "seed": 0.0,
            "anchors": 0.0,
            "shards": 0.0,
        }
        coverage_stage_values: Dict[str, float] = {"memory": 0.0, "anchors": 0.0, "shards": 0.0}
        memory_details: List[Dict[str, Any]] = []
        memory_budget_reads = 0.0
        memory_budget_tokens = 0.0

        def _build_memory_detail(chunk: Mapping[str, Any], delta: float, claim_count: int) -> Dict[str, Any]:
            detail: Dict[str, Any] = {
                "doc": str(chunk.get("file", "")),
                "source": str(chunk.get("source", "memory")),
                "coverage_delta": float(delta),
                "claims": int(claim_count),
                "tokens": int(len(chunk.get("tokens") or [])),
                "reads": 1.0,
            }
            kind_value = chunk.get("kind")
            if kind_value is not None:
                detail["kind"] = str(kind_value)
            chunk_id_value = chunk.get("chunk_id")
            if chunk_id_value is not None:
                try:
                    detail["chunk_id"] = int(chunk_id_value)
                except (TypeError, ValueError):
                    detail["chunk_id"] = chunk_id_value
            score_value = chunk.get("score")
            if score_value is not None:
                detail["score"] = float(score_value)
            recency_value = chunk.get("recency_weight")
            if recency_value is not None:
                detail["recency_weight"] = float(recency_value)
            pd_value = chunk.get("phase_d_score")
            if pd_value is not None:
                try:
                    detail["phase_d_score"] = float(pd_value)
                except (TypeError, ValueError):
                    pass
            priority_value = chunk.get("phase_d_priority")
            if priority_value is not None:
                try:
                    detail["phase_d_priority"] = float(priority_value)
                except (TypeError, ValueError):
                    pass
            graph_priority_value = chunk.get("graph_priority")
            if graph_priority_value is not None:
                try:
                    detail["graph_priority"] = float(graph_priority_value)
                except (TypeError, ValueError):
                    pass
            final_priority_value = chunk.get("final_priority_for_bridge")
            if final_priority_value is not None:
                try:
                    detail["final_priority"] = float(final_priority_value)
                except (TypeError, ValueError):
                    pass
            hysteresis_value = chunk.get("hysteresis_boost")
            if hysteresis_value is not None:
                try:
                    detail["hysteresis_boost"] = float(hysteresis_value)
                except (TypeError, ValueError):
                    pass
            prev_priority = chunk.get("previous_priority")
            if prev_priority is not None:
                try:
                    detail["previous_priority"] = float(prev_priority)
                except (TypeError, ValueError):
                    pass
            prev_selected = chunk.get("previous_session_selected")
            if prev_selected is not None:
                detail["previous_session_selected"] = bool(prev_selected)
            # Derive hysteresis if missing and config enables it.
            if getattr(self.config.phase_d, "enable_hysteresis", False) and "hysteresis_boost" not in detail:
                try:
                    prev_sel = bool(detail.get("previous_session_selected", False))
                    prev_pri = float(detail.get("previous_priority", 0.0) or 0.0)
                    hyst_w = float(getattr(self.config.phase_d, "hysteresis_weight", 0.0))
                    if prev_sel and hyst_w > 0.0:
                        detail["hysteresis_boost"] = hyst_w * prev_pri
                except Exception:
                    pass
            last_seen_value = chunk.get("last_seen")
            if last_seen_value:
                detail["last_seen"] = last_seen_value
            return detail

        if k == 0 or not cand_order:
            coverage_state = CoverageState(gamma=gamma, u_max=u_max)
            coverage_baseline = coverage_state.value()
            if memory_chunks:
                for mem_chunk in memory_chunks:
                    claims = list(_claim_evidence(mem_chunk))
                    before = coverage_state.value()
                    if claims:
                        coverage_state.apply(claims)
                    after = coverage_state.value()
                    delta = float(after - before)
                    memory_delta += delta
                    memory_details.append(_build_memory_detail(mem_chunk, delta, len(claims)))
                    memory_budget_reads += 1.0
                    token_seq = mem_chunk.get("tokens")
                    token_count = len(token_seq) if isinstance(token_seq, Sequence) else 0
                    if token_count == 0 and mem_chunk.get("text"):
                        token_count = len(tokenize_text(str(mem_chunk.get("text"))))
                    memory_budget_tokens += float(token_count)
            coverage_start = coverage_state.value()
            coverage_breakdown["memory"] = memory_delta
            coverage_stage_values = {
                "memory": coverage_start,
                "anchors": coverage_start,
                "shards": coverage_start,
            }
            top_idx = []
        else:
            claims_map: Dict[int, List[ClaimEvidence]] = {}
            for idx in cand_order:
                chunk_claims = list(_claim_evidence(chunks[idx]))
                matched_tokens: set[str] = set()
                if q_focus_tokens:
                    extra_claims, matched_tokens = _doc_alignment_claims(chunks[idx], q_focus_tokens)
                    if extra_claims:
                        chunk_claims.extend(extra_claims)
                        for token in matched_tokens:
                            coverage_weights.setdefault(f"doc_alignment::{token}", 3.0)
                        entry: Dict[str, Any] = {
                            "id": int(idx),
                            "doc": str(chunks[idx].get("file", "")),
                            "tokens": sorted(matched_tokens),
                        }
                        hierarchy_info = chunks[idx].get("hierarchy")
                        if isinstance(hierarchy_info, Mapping):
                            segment_value = hierarchy_info.get("segment")
                            if isinstance(segment_value, str) and segment_value:
                                entry["segment"] = segment_value
                        doc_alignment_details.append(entry)
                claims_map[idx] = chunk_claims

            cost_entries: Dict[int, Dict[str, float]] = {
                idx: _candidate_cost_entry(chunks[idx], pairs_scale_effective)
                for idx in cand_order
            }



            segment_map: Dict[int, str] = {}
            for idx in cand_order:
                hierarchy_info = chunks[idx].get("hierarchy")
                if isinstance(hierarchy_info, Mapping):
                    segment_value = hierarchy_info.get("segment")
                    if isinstance(segment_value, str) and segment_value:
                        segment_map[idx] = segment_value
            section_repeat_penalty = section_repeat_penalty_effective
            section_penalty_floor = section_penalty_floor_effective

            coverage_state = CoverageState(
                gamma=gamma,
                u_max=u_max,
                weights=coverage_weights if coverage_weights else None,
            )
            coverage_baseline = coverage_state.value()
            if memory_chunks:
                for mem_chunk in memory_chunks:
                    claims = list(_claim_evidence(mem_chunk))
                    before = coverage_state.value()
                    if claims:
                        coverage_state.apply(claims)
                    after = coverage_state.value()
                    delta = float(after - before)
                    memory_delta += delta
                    memory_details.append(_build_memory_detail(mem_chunk, delta, len(claims)))
                    memory_budget_reads += 1.0
                    token_seq = mem_chunk.get("tokens")
                    token_count = len(token_seq) if isinstance(token_seq, Sequence) else 0
                    if token_count == 0 and mem_chunk.get("text"):
                        token_count = len(tokenize_text(str(mem_chunk.get("text"))))
                    memory_budget_tokens += float(token_count)
            coverage_start = coverage_state.value()
            coverage_breakdown["memory"] = memory_delta
            coverage_stage_values = {
                "memory": coverage_start,
                "anchors": coverage_start,
                "shards": coverage_start,
            }

        if getattr(self.config.phase_d, "enable_memory_bridge_priority", True) and memory_details:
            hysteresis_on = bool(getattr(self.config.phase_d, "enable_hysteresis", False))
            hysteresis_w = float(getattr(self.config.phase_d, "hysteresis_weight", 0.0))
            clip_min = float(getattr(self.config.phase_d, "priority_clip_min", 0.0))
            clip_max = float(getattr(self.config.phase_d, "priority_clip_max", 2.0))

            def _priority_for_sort(detail: Mapping[str, Any]) -> float:
                base = detail.get("final_priority")
                if base is None:
                    base = detail.get("phase_d_priority", 1.0)
                    if hysteresis_on and hysteresis_w > 0.0:
                        prev_selected = bool(detail.get("previous_session_selected", False))
                        prev_priority = float(detail.get("previous_priority", 0.0) or 0.0)
                        if prev_selected:
                            base = float(base) + hysteresis_w * prev_priority
                try:
                    return float(np.clip(float(base), clip_min, clip_max))
                except (TypeError, ValueError):
                    return 1.0

            memory_details = sorted(
                memory_details,
                key=lambda d: (
                    -_priority_for_sort(d),
                    -float(d.get("phase_d_priority", 1.0)),
                    str(d.get("doc", "")),
                ),
            )

        selection_trace["memory"] = memory_details
        if memory_budget_reads > 0.0:
            selection_trace["budgets"]["reads"] += float(memory_budget_reads)
            selection_trace["budgets"]["tokens"] += float(memory_budget_tokens)
            selection_trace["budgets"]["cost"] += float(
                memory_budget_reads + lambda_tok_effective * memory_budget_tokens
            )

        selected_ids: List[int] = []
        if not (k == 0 or not cand_order):
            def _record(
                section: str,
                details: List[Dict[str, float]],
                stats: Dict[str, int],
                totals: Dict[str, float],
                residual_steps: Mapping[int, Mapping[str, float]] | None = None,
            ) -> tuple[float, float]:
                stage_delta = 0.0
                seed_delta = 0.0
                if details:
                    entries: List[Dict[str, float]] = []
                    for detail in details:
                        delta = float(detail.get("delta", 0.0))
                        stage_delta += delta
                        if detail.get("seed"):
                            seed_delta += delta
                        entry = {
                            "id": int(detail["id"]),
                            "\u0394": float(detail["delta"]),
                            "C": float(detail["cost"]),
                            "ratio": float(detail["ratio"]),
                            "reads": float(detail.get("reads", 0.0)),
                            "tokens": float(detail.get("tokens", 0.0)),
                            "pairs": float(detail.get("pairs", 0.0)),
                            "seed": bool(detail.get("seed", False)),
                        }
                        if "diversity_multiplier" in detail:
                            entry["diversity_multiplier"] = float(detail["diversity_multiplier"])
                        if section == "anchors" and residual_steps:
                            meta = residual_steps.get(entry["id"])
                            if meta:
                                entry["residual_step"] = dict(meta)
                        entries.append(entry)
                    selection_trace[section] = entries
                selection_trace["celf_stats"]["pops"] += stats.get("pops", 0)
                selection_trace["celf_stats"]["recomps"] += stats.get("recomps", 0)
                selection_trace["celf_stats"]["accepted"] += stats.get("accepted", 0)
                for key in ("reads", "tokens", "pairs", "cost"):
                    selection_trace["budgets"][key] += float(totals.get(key, 0.0))
                return stage_delta, seed_delta

            seed_ids = [cand_order[0]] if cand_order and reads_budget_total > 0 else []
            lambda_base = {
                "lambda_tokens": lambda_tok_effective,
                "lambda_rerank": lambda_rerank_effective,
                "selected_count": memory_preselected,
                "budgets": {"reads": float(reads_budget_total)} if reads_budget_total > 0 else {},
            }

            if decision_for_selection == "anchors":
                anchor_plan = self._curvature_anchor_candidates(
                    seed_idx=seed_idx,
                    context=context,
                    doc_projections=doc_projections,
                    chunk_vecs=chunk_vecs,
                    chunks=chunks,
                    ann_indices=neigh_idx,
                    cand_order=cand_order,
                    doc_to_chunk_indices=doc_to_chunk_indices,
                    cost_entries=cost_entries,
                    lambda_tokens=lambda_tok_effective,
                    lambda_rerank=lambda_rerank_effective,
                    pairs_scale=pairs_scale_effective,
                )
            else:
                anchor_plan = _AnchorPlan([], {})
            anchor_items = anchor_plan.order
            anchor_residual_steps = anchor_plan.residual_steps
            anchor_selected, anchor_stats, anchor_details, anchor_totals = select_celf(
                anchor_items,
                claims_map,
                cost_entries,
                k=k,
                lambdas=lambda_base,
                seed=seed_ids,
                state=coverage_state,
                gamma=gamma,
                u_max=u_max,
                lazy=self.config.use_celf,
                segment_map=segment_map,
                segment_repeat_penalty=section_repeat_penalty,
                segment_penalty_floor=section_penalty_floor,
            )
            selected_ids: List[int] = list(seed_ids) + anchor_selected
            anchor_delta, anchor_seed_delta = _record("anchors", anchor_details, anchor_stats, anchor_totals, anchor_residual_steps)
            coverage_breakdown["seed"] += anchor_seed_delta
            coverage_breakdown["anchors"] += anchor_delta - anchor_seed_delta
            coverage_stage_values["anchors"] = coverage_state.value()

            remaining_pool = [idx for idx in cand_order if idx not in selected_ids]
            total_reads_used = float(anchor_totals.get("reads", 0.0))
            if selected_ids and len(selected_ids) < k and remaining_pool:
                reads_remaining = (
                    max(0.0, float(reads_budget_total) - total_reads_used)
                    if reads_budget_total > 0
                    else 0.0
                )
                lambda_next = {
                    "lambda_tokens": lambda_tok_effective,
                    "lambda_rerank": lambda_rerank_effective,
                    "selected_count": len(selected_ids) + memory_preselected,
                    "budgets": {"reads": reads_remaining} if reads_remaining > 0 else {},
                }
                shard_selected, shard_stats, shard_details, shard_totals = select_celf(
                    remaining_pool,
                    claims_map,
                    cost_entries,
                    k=k,
                    lambdas=lambda_next,
                    state=coverage_state,
                    gamma=gamma,
                    u_max=u_max,
                    lazy=self.config.use_celf,
                    segment_map=segment_map,
                    segment_repeat_penalty=section_repeat_penalty,
                    segment_penalty_floor=section_penalty_floor,
                )
                selected_ids.extend(shard_selected)
                shard_delta, shard_seed_delta = _record("shards", shard_details, shard_stats, shard_totals)
                coverage_breakdown["seed"] += shard_seed_delta
                coverage_breakdown["shards"] += shard_delta - shard_seed_delta
                coverage_stage_values["shards"] = coverage_state.value()
            else:
                coverage_stage_values["shards"] = coverage_state.value()

        top_idx_full = selected_ids[:k]
        if k > 0 and len(top_idx_full) < k and cand_order:
            for idx in cand_order:
                if idx in top_idx_full:
                    continue
                top_idx_full.append(int(idx))
                if len(top_idx_full) >= k:
                    break

        if top_idx_full:
            pairs = [(text, chunks[idx]["text"]) for idx in top_idx_full]
            self._reranker.score(pairs)
            used_pairs = float(len(pairs))
            if used_pairs > 0:
                increment = float(pairs_scale_effective) * used_pairs
                selection_trace["budgets"]["pairs"] += increment
                selection_trace["budgets"]["cost"] += lambda_rerank_effective * increment
                selection_trace["budgets"]["reranker_pairs"] += used_pairs
        if reads_budget_total_eff >= 0 and len(top_idx_full) > reads_budget_total_eff:
            top_idx = top_idx_full[:reads_budget_total_eff]
        else:
            top_idx = top_idx_full
        latency_trace["selection_ms"] = (time.perf_counter() - t_start) * 1000.0

        top_shard_score = 0.0
        if top_idx and sims.size:
            first_idx = top_idx[0]
            if 0 <= first_idx < sims.size:
                top_shard_score = float(sims[first_idx])

        retrieval_chunks = [chunks[idx] for idx in top_idx]
        memory_chunk_list = list(memory_chunks) if memory_chunks else []
        if memory_chunk_list:
            normalized_memory = []
            for chunk in memory_chunk_list:
                if not chunk.get("version_id"):
                    chunk["version_id"] = chunk.get("file")
                if _version_allowed(chunk):
                    normalized_memory.append(chunk)
            memory_chunk_list = normalized_memory
        for chunk in memory_chunk_list:
            if not chunk.get("version_id"):
                chunk["version_id"] = chunk.get("file")
        session_memory_chunks = [
            chunk for chunk in memory_chunk_list if chunk.get("source") != "cognitive_memory"
            and chunk.get("origin") != "cognitive_memory"
        ]
        cognitive_memory_chunks = [
            chunk for chunk in memory_chunk_list if chunk.get("source") == "cognitive_memory"
            or chunk.get("origin") == "cognitive_memory"
        ]
        # Sort cognitive memory chunks by priority when enabled.
        if cognitive_memory_chunks and getattr(self.config.phase_d, "enable_memory_bridge_priority", True):
            blend_w = float(getattr(self.config.phase_d, "memory_bridge_priority_weight", 0.5))
            clip_min = float(getattr(self.config.phase_d, "priority_clip_min", 0.0))
            clip_max = float(getattr(self.config.phase_d, "priority_clip_max", 2.0))
            temporal_on = bool(getattr(self.config.phase_d, "enable_temporal_priority", False))
            temporal_w = float(getattr(self.config.phase_d, "temporal_recency_weight", 0.0))
            temporal_half = float(getattr(self.config.phase_d, "temporal_decay_half_life", 3.0))
            temporal_floor = float(getattr(self.config.phase_d, "temporal_min_floor", 0.2))

            def _chunk_priority(idx_chunk: tuple[int, Mapping[str, Any]]) -> tuple[float, float]:
                idx, chunk = idx_chunk
                final_override = chunk.get("final_priority_for_bridge")
                if final_override is not None:
                    try:
                        final = float(final_override)
                    except (TypeError, ValueError):
                        final = float(chunk.get("phase_d_priority", 1.0))
                    chunk["final_priority_for_bridge"] = final
                else:
                    base_priority = float(chunk.get("phase_d_priority", 1.0))
                    graph_priority = float(chunk.get("graph_priority", base_priority))
                    if not getattr(self.config.phase_d, "enable_memory_bridge_priority", True):
                        blend = 0.0
                    else:
                        blend = blend_w
                    final = (1.0 - blend) * base_priority + blend * graph_priority
                    hysteresis_boost = 0.0
                    if temporal_on:
                        age_seconds = chunk.get("age_seconds")
                        recency = temporal_recency_score(age_seconds, temporal_half, temporal_floor)
                        temporal_factor = (1.0 - temporal_w) + temporal_w * recency
                        final *= temporal_factor
                    if getattr(self.config.phase_d, "enable_hysteresis", False):
                        prev_priority = float(chunk.get("previous_priority", 0.0) or 0.0)
                        prev_selected = bool(chunk.get("previous_session_selected", False))
                        hysteresis_w = float(getattr(self.config.phase_d, "hysteresis_weight", 0.0))
                        if prev_selected and hysteresis_w > 0.0:
                            hysteresis_boost = hysteresis_w * prev_priority
                            final += hysteresis_boost
                        chunk["hysteresis_boost"] = hysteresis_boost
                        chunk["previous_priority"] = prev_priority
                        chunk["previous_session_selected"] = prev_selected
                final = float(np.clip(final, clip_min, clip_max))
                chunk["final_priority_for_bridge"] = final
                return (-final, idx)

            cognitive_memory_chunks = [chunk for _, chunk in sorted(enumerate(cognitive_memory_chunks), key=_chunk_priority)]
            memory_chunk_list = session_memory_chunks + cognitive_memory_chunks
            memory_chunks = list(memory_chunk_list)
        if unbounded_memory:
            retrieval_limit = (
                min(len(retrieval_chunks), reads_budget_total)
                if reads_budget_total > 0
                else len(retrieval_chunks)
            )
            trimmed_retrieval_chunks = retrieval_chunks[:retrieval_limit]
            top_idx = top_idx[:retrieval_limit]
            session_selected = list(session_memory_chunks)
            selected_cognitive_chunks = list(cognitive_memory_chunks)
            max_total = len(session_selected) + len(selected_cognitive_chunks) + len(trimmed_retrieval_chunks)
        else:
            max_total = (
                reads_budget_total
                if reads_budget_total > 0
                else len(retrieval_chunks) + len(memory_chunk_list)
            )
            reserved_for_memory = len(memory_chunk_list)
            retrieval_limit = max(0, min(len(retrieval_chunks), max_total - reserved_for_memory))
            trimmed_retrieval_chunks = retrieval_chunks[:retrieval_limit]
            top_idx = top_idx[:retrieval_limit]
            allocated_memory_slots = max(0, max_total - len(trimmed_retrieval_chunks))
            session_selected = session_memory_chunks[:allocated_memory_slots] if session_memory_chunks else []
            remaining_slots = max(0, allocated_memory_slots - len(session_selected))
            selected_cognitive_chunks = cognitive_memory_chunks[:remaining_slots] if remaining_slots > 0 else []

        merge_enabled = bool(self.config.enable_cognitive_ann_bridge)
        merge_debug = bool(getattr(self.config.phase_d, "debug_observability", False))
        merge_k = max(0, max_total - len(session_selected))

        ann_candidates: List[Dict[str, Any]] = []
        for idx, chunk in zip(top_idx, trimmed_retrieval_chunks):
            payload = dict(chunk)
            payload.setdefault("candidate_id", chunk.get("chunk_id") or chunk.get("id"))
            payload.setdefault("origin", "ann")
            score = payload.get("score", 0.0)
            try:
                if sims.size and 0 <= idx < sims.size:
                    score = float(sims[idx])
            except Exception:
                pass
            try:
                payload["score"] = float(score)
            except Exception:
                payload["score"] = 0.0
            ann_candidates.append(payload)

        cognitive_candidates: List[Dict[str, Any]] = []
        for chunk in selected_cognitive_chunks:
            payload = dict(chunk)
            payload.setdefault("candidate_id", chunk.get("chunk_id") or chunk.get("id"))
            payload.setdefault("origin", "cognitive_memory")
            try:
                payload.setdefault(
                    "score",
                    float(chunk.get("score", chunk.get("priority", 0.0)) or 0.0),
                )
            except Exception:
                payload.setdefault("score", 0.0)
            cognitive_candidates.append(payload)

        fallback_candidates: List[Dict[str, Any]] = []
        if selected_cognitive_chunks:
            fallback_candidates = list(selected_cognitive_chunks)
        elif trimmed_retrieval_chunks:
            fallback_candidates = list(trimmed_retrieval_chunks)

        if merge_debug and merge_enabled:
            preview_ids = [c.get("candidate_id") or c.get("doc_id") for c in cognitive_candidates[:10]]
            selection_trace.setdefault("cognitive_ann_premerge", {})
            selection_trace["cognitive_ann_premerge"] = {
                "count": len(cognitive_candidates),
                "ids": preview_ids,
                "origins": _origin_counts(
                    cognitive_candidates,
                    fallback="cognitive_memory",
                ),
                "scores": [float(c.get("score", 0.0)) for c in cognitive_candidates[:10]],
            }
            selection_trace.setdefault("memory_layers", {})
            selection_trace["memory_layers"].update(
                {
                    "merge_enabled": True,
                    "ann": {
                        "count": len(ann_candidates),
                        "ids": [c.get("candidate_id") or c.get("doc_id") for c in ann_candidates[:10]],
                        "origins": _origin_counts(ann_candidates, fallback="ann"),
                        "scores": [float(c.get("score", 0.0)) for c in ann_candidates[:10]],
                    },
                    "cognitive": {
                        "count": len(cognitive_candidates),
                        "ids": preview_ids,
                        "origins": _origin_counts(
                            cognitive_candidates,
                            fallback="cognitive_memory",
                        ),
                        "scores": [float(c.get("score", 0.0)) for c in cognitive_candidates[:10]],
                    },
                }
            )

        # The ANN bridge exists to blend cognitive candidates into the document
        # shortlist. With no cognitive candidates, preserve the orchestrator's
        # coverage-aware retrieval order instead of re-sorting documents by raw
        # similarity inside merge_with_gates.
        merge_applied = merge_enabled and bool(cognitive_candidates)
        if merge_applied:
            merged_selection = merge_with_gates(
                ann_candidates,
                cognitive_candidates,
                merge_k,
                enabled=True,
                prefer_cognitive=True,
                fallback=fallback_candidates,
            )
        else:
            merged_selection = list(selected_cognitive_chunks) + list(trimmed_retrieval_chunks)

        if merge_debug or merge_enabled:
            selection_trace.setdefault("cognitive_ann_merge", {})
            selection_trace["cognitive_ann_merge"] = {
                "enabled": merge_enabled,
                "applied": merge_applied,
                "before": {
                    "ann": len(trimmed_retrieval_chunks),
                    "cognitive": len(selected_cognitive_chunks),
                },
                "after": len(merged_selection),
                "origins": _origin_counts(merged_selection, fallback="unknown"),
            }
            selection_trace.setdefault("memory_layers", {})
            selection_trace["memory_layers"]["merged"] = {
                "count": len(merged_selection),
                "ids": [c.get("candidate_id") or c.get("doc_id") for c in merged_selection[:10]],
                "origins": _origin_counts(merged_selection, fallback="unknown"),
                "scores": [float(c.get("score", 0.0)) for c in merged_selection[:10]],
            }

        top_chunks = session_selected + merged_selection
        selection_trace["budgets"]["reads_used"] = float(len(top_chunks))

        section_counts: Dict[str, int] = {}
        section_order: List[str] = []
        for chunk in top_chunks:
            hierarchy = chunk.get("hierarchy")
            if isinstance(hierarchy, Mapping):
                segment_value = hierarchy.get("segment")
                if isinstance(segment_value, str):
                    if segment_value not in section_counts:
                        section_order.append(segment_value)
                    section_counts[segment_value] = section_counts.get(segment_value, 0) + 1

        if replay_last:
            limit = max(int(getattr(self.config, "session_memory_k", 0)), 0)
            if limit > 0:
                self._session_memory = [copy.deepcopy(chunk) for chunk in top_chunks[:limit]]
            else:
                self._session_memory = []
        else:
            self._session_memory = []

        if doc_alignment_details:
            selection_trace["doc_alignment"] = doc_alignment_details

        selection_trace["segments"] = [
            {"segment": seg, "count": int(section_counts[seg])}
            for seg in section_order
        ]
        selection_trace["segments_diversity"] = float(
            len([seg for seg in section_order if seg.startswith("section:")])
        ) / float(sum(
            section_counts[seg]
            for seg in section_order
            if seg.startswith("section:")
        ) or 1)

        citations = []
        for chunk in top_chunks:
            file_id = chunk.get("file", "unknown")
            chunk_id = chunk.get("chunk_id", 0)
            citations.append(f"{file_id}:chunk{chunk_id}")

        if os.getenv("FRAM_STRICT_QA_FALLBACK") == "1" and task == "qa" and decision_for_selection == "anchors":
            if not citations or top_shard_score < STRICT_QA_FALLBACK_TAU_SHARD:
                decision_for_selection = "global"
                confidence_trace["decision"] = decision_for_selection

        answer_memory_chunks = session_selected + selected_cognitive_chunks
        answer = _assemble_answer(answer_memory_chunks + trimmed_retrieval_chunks)
        hierarchy_trace = [chunk.get("hierarchy") for chunk in top_chunks]

        distinct_facts: List[str] = []
        seen_facts: set[str] = set()
        for idx in top_idx:
            for claim in _chunk_claims(chunks[idx]):
                key = getattr(claim, "key", str(claim))
                if key not in seen_facts:
                    seen_facts.add(key)
                    if len(distinct_facts) < 10:
                        distinct_facts.append(key)
        if top_idx:
            first_claims = {getattr(claim, "key", str(claim)) for claim in _chunk_claims(chunks[top_idx[0]])}
            union_claims = {getattr(claim, "key", str(claim)) for idx in top_idx for claim in _chunk_claims(chunks[idx])}
            facts_added = max(0, len(union_claims - first_claims))
            selected_claims = len(union_claims)
        else:
            facts_added = 0
            selected_claims = 0

        coverage_final = coverage_state.value() if coverage_state is not None else 0.0
        coverage_total_delta = coverage_final - coverage_baseline
        delta_by_stage = {
            "memory": float(coverage_breakdown.get("memory", 0.0)),
            "seed": float(coverage_breakdown.get("seed", 0.0)),
            "anchors": float(coverage_breakdown.get("anchors", 0.0)),
            "shards": float(coverage_breakdown.get("shards", 0.0)),
        }
        selection_trace["coverage_delta"] = {
            "memory": delta_by_stage["memory"],
            "seed": delta_by_stage["seed"],
            "anchors": delta_by_stage["anchors"],
            "shards": delta_by_stage["shards"],
            "total": float(coverage_total_delta),
        }
        section_list = [seg for seg in section_order if seg.startswith("section:")]
        segment_counts = {seg: int(section_counts[seg]) for seg in section_order}

        coverage_summary = {
            "facts_added": int(facts_added),
            "distinct_facts": distinct_facts,
            "gamma": float(gamma),
            "u_max": int(u_max),
            "selected_claims": int(selected_claims),
            "sections": section_list,
            "segment_counts": segment_counts,
            "section_diversity": float(len(section_list)) / float(sum(section_counts[seg] for seg in section_list) or 1),
            "value_start": float(coverage_baseline),
            "value_after_memory": float(coverage_stage_values.get("memory", coverage_start)),
            "value_after_anchor": float(coverage_stage_values.get("anchors", coverage_start)),
            "value_after_shards": float(
                coverage_stage_values.get(
                    "shards",
                    coverage_stage_values.get("anchors", coverage_start),
                )
            ),
            "value_final": float(coverage_final),
            "delta_total": float(coverage_total_delta),
            "delta_by_stage": delta_by_stage,
            "budgets": {
                key: float(selection_trace["budgets"].get(key, 0.0))
                for key in ("reads", "tokens", "pairs", "cost")
            },
        }
        as_of_block = None
        if as_of is not None:
            as_of_block = {
                "as_of": as_of.isoformat(),
                "active_nodes": sorted(list(allowed_versions or [])),
                "dropped_candidates": int(as_of_dropped.get("count", 0)),
            }
        trace_payload = {
            "as_of": as_of.isoformat() if as_of else None,
            "as_of_filter": as_of_block,
            "sparse_hits": sparse_index.query(text) if sparse_index is not None else [],
            "scores": trace_scores,
            "confidence": confidence_trace,
            "selection": selection_trace,
            "p_temp": float(p_temp) if p_temp is not None else None,
            "coverage": coverage_summary,
            "transitional_complexity": transitional_complexity,
            "tc_routing": tc_routing,
            "domain": domain,
            "task": task,
            "budget_reads": float(reads_budget_total),
            "hierarchy": hierarchy_trace,
            "hierarchy_scales": hierarchy_scales,
            "latency_ms": latency_trace,
        }
        if as_of_set is not None or version_id is not None:
            trace_payload["versioning"] = {
                "as_of": as_of.isoformat() if as_of else None,
                "version_id": version_id,
                "active_versions": version_map,
                "excluded_versions": excluded_versions,
            }

        record = {
            "id": uuid.uuid4().hex,
            "time": datetime.now(timezone.utc).isoformat(),
            "query": text,
            "citations": citations,
            "domain": domain,
            "task": task,
            "trace": trace_payload,
        }
        delta_snippets: List[Dict[str, Any]] = []
        if as_of is not None and lattice is not None:
            seen_versions: Set[str] = set()
            iteration_versions: Iterable[str] = allowed_versions or []
            if not iteration_versions:
                iteration_versions = (
                    str(chunk.get("version_id") or chunk.get("file") or "") for chunk in top_chunks
                )
            for vid in iteration_versions:
                if not vid or vid in seen_versions:
                    continue
                seen_versions.add(str(vid))
                node = getattr(lattice, "_nodes", {}).get(str(vid))
                if node is not None and node.parent_id and node.diff is not None:
                    delta_snippets.append(
                        {"version_id": node.node_id, "parent_id": node.parent_id, "diff": node.diff}
                    )
        if delta_snippets:
            record["delta_snippets"] = delta_snippets
            trace_payload["delta_snippets"] = delta_snippets
        record_id = record["id"]
        record["trace"]["query_id"] = record_id
        record["trace"]["trace_id"] = record_id

        if self.tracer is not None:
            try:
                trace_id = self.tracer.write(record)
            except Exception:  # pragma: no cover - defensive path
                trace_id = record["id"]
        else:
            trace_id = record["id"]

        record["trace"]["trace_id"] = trace_id

        logged_negative = False
        if feature_samples_log:
            for idx, (feat, doc_id) in feature_samples_log.items():
                record_label = 1 if idx in top_idx else 0
                if record_label == 0:
                    logged_negative = True
                _append_calibration_record(
                    self.config.STORAGE_ROOT,
                    {
                        "time": datetime.now(timezone.utc).isoformat(),
                        "trace_id": trace_id,
                        "doc_id": doc_id,
                        "chunk_id": int(idx),
                        "label": int(record_label),
                        "decision": decision_for_selection,
                        "prob": float(p_temp) if p_temp is not None else None,
                        "features": {
                            "Delta_d_z": float(feat.Delta_d_z),
                            "rho_pos": float(feat.rho_pos),
                            "mhd": float(feat.mhd),
                            "d_c_z": float(feat.d_c_z),
                            "fresh": float(feat.fresh),
                        },
                        "query": text,
                        "domain": domain,
                        "task": task,
                        "budget_reads": float(reads_budget_total),
                    },
                )
        if not logged_negative and q_vec.size:
            for extra_idx in sorted_indices:
                if extra_idx in top_idx:
                    continue
                if not _version_allowed(chunks[extra_idx]):
                    continue
                doc_id = str(chunks[extra_idx].get("file", ""))
                candidate_context = self._build_cluster_context(
                    seed_idx=extra_idx,
                    doc_proto_map=doc_proto_map,
                    doc_to_chunk_indices=doc_to_chunk_indices,
                    chunk_vecs=chunk_vecs,
                    chunks=chunks,
                    allowed_versions=allowed_versions,
                    cand_order=cand_order,
                    doc_sorted_indices=doc_sorted_indices,
                    projected_query=doc_projections.get(doc_id),
                    dropped_counter=as_of_dropped,
                )
                cand_neighbors_idx = candidate_context.neighbor_indices
                cand_neighbors = (
                    chunk_vecs[cand_neighbors_idx]
                    if cand_neighbors_idx and chunk_vecs.size
                    else np.zeros((0, q_vec.shape[0]), dtype=float)
                )
                neg_feats = conf.compute_features(
                    e=q_vec,
                    p_k=candidate_context.centroid,
                    U_k=candidate_context.basis,
                    kNN_neighbors=cand_neighbors,
                    medians=candidate_context.medians,
                    mads=candidate_context.mads,
                    T_q=T_q,
                    T_k_median=candidate_context.timestamp,
                    tau_domain=self.config.tau_domain_days,
                )
                _append_calibration_record(
                    self.config.STORAGE_ROOT,
                    {
                        "time": datetime.now(timezone.utc).isoformat(),
                        "trace_id": trace_id,
                        "doc_id": doc_id,
                        "chunk_id": int(extra_idx),
                        "label": 0,
                        "decision": decision_for_selection,
                        "prob": float(p_temp) if p_temp is not None else None,
                        "features": {
                            "Delta_d_z": float(neg_feats.Delta_d_z),
                            "rho_pos": float(neg_feats.rho_pos),
                            "mhd": float(neg_feats.mhd),
                            "d_c_z": float(neg_feats.d_c_z),
                            "fresh": float(neg_feats.fresh),
                        },
                        "query": text,
                        "domain": domain,
                        "task": task,
                        "budget_reads": float(reads_budget_total),
                    },
                )
                break

        return {
            "trace_id": trace_id,
            "answer": answer,
            "citations": citations,
            "coverage": trace_payload["coverage"],
            "record": record,
        }

    def ensure_corpus(self) -> _CorpusCache:
        """Expose corpus warm-up for serving (docs/F-RAM-roadmap.md:18)."""

        return self._ensure_corpus()

    def _ensure_corpus(self) -> _CorpusCache:
        if self._cache is not None:
            return self._cache

        loaded = False
        if self.persist_path is not None and not _persisted_corpus_is_stale(self.persist_path, self.data_root):
            try:
                self._cache = load_persisted_corpus(self.persist_path)
                cache = self._cache
                if cache is not None:
                    vec_dim = cache.chunk_vecs.shape[1] if cache.chunk_vecs.ndim == 2 else 0
                    vocab_size = len(cache.vocab)
                    whiten_dim = cache.whiten_mean.shape[0]
                    if vec_dim == vocab_size == whiten_dim and cache.whiten_matrix.shape[:2] == (vec_dim, vec_dim):
                        doc_files = {chunk.get("file") for chunk in getattr(cache, "chunks", [])}
                        if "docs_ingest_f_ram_roadmap.txt" in doc_files:
                            metadata = {}
                            raw_metadata = getattr(cache, "metadata", {})
                            if isinstance(raw_metadata, Mapping):
                                metadata = dict(raw_metadata)
                            cache.metadata = metadata
                            current_version = _current_sklearn_version()
                            persisted_version = metadata.get("sklearn_version")
                            requires_refresh = False
                            if current_version:
                                if persisted_version is None:
                                    requires_refresh = True
                                elif isinstance(persisted_version, str) and persisted_version != current_version:
                                    requires_refresh = True
                            if requires_refresh:
                                loaded = False
                                self._cache = None
                            else:
                                loaded = True
                        else:
                            loaded = False
                            self._cache = None
                    else:
                        loaded = False
                        self._cache = None
            except FileNotFoundError:
                loaded = False
            except Exception:
                loaded = False

        if not loaded:
            self._cache = load_demo_corpus(
                self.data_root,
                self.config,
                include_legacy=self._include_legacy,
            )
            if self.persist_path is not None:
                try:
                    save_corpus_cache(self._cache, self.persist_path)
                    claims_dir = self.config.STORAGE_ROOT / self.config.STORAGE_SUBFOLDERS.get("claims", "claims")
                    export_claim_log(self._cache, claims_dir, dataset_name="demo_corpus")
                except Exception:
                    pass

        cache = self._cache
        if cache is None:
            raise RuntimeError("Corpus cache unavailable")
        if self.persist_path is not None:
            try:
                for calib_path in self.persist_path.glob("calibration*.json"):
                    if calib_path.name == "calibration.json":
                        continue
                    try:
                        payload_data = json.loads(calib_path.read_text(encoding="utf-8"))
                    except Exception:
                        continue
                    try:
                        calibration_payload = _deserialize_calibration(payload_data, self.config)
                    except Exception:
                        continue
                    stem = calib_path.stem
                    if stem.startswith("calibration_task_"):
                        key = stem[len("calibration_task_"):].strip().lower()
                        if key:
                            cache.calibration_by_task[key] = calibration_payload
                    elif stem.startswith("calibration_"):
                        key = stem[len("calibration_"):].strip().lower()
                        if key:
                            cache.calibration_by_domain[key] = calibration_payload
            except Exception:
                pass
        self._embedding_backend = getattr(cache, "embedding_backend", self._embedding_backend)
        if getattr(cache, "embedder", None) is not None:
            self._embedder = cache.embedder
        elif self._embedding_backend == "hashing":
            self._embedder = _make_hashing_vectorizer(self.config)
        elif self._embedding_backend in {"vocab", "tokens"}:
            self._embedder = None
        elif self._embedding_backend == "tfidf":
            raise RuntimeError("tfidf backend requires persisted embedder")
        else:
            self._embedder = None

        chunk_vecs = cache.chunk_vecs
        self._ann_fingerprint = _embedding_fingerprint(chunk_vecs)
        self._ann_index = None
        self._ann_size = 0
        if self.persist_path is not None:
            self._load_ann_from_disk(chunk_vecs, self._ann_fingerprint)
        # Ensure segment-level prototypes exist for fractal routing
        try:
            seg_protos = getattr(cache, "prototypes_by_segment", None)
        except Exception:
            seg_protos = None
        if not seg_protos:
            try:
                cache.prototypes_by_segment = _build_segment_prototypes(cache.chunks, chunk_vecs, self.config)
            except Exception:
                cache.prototypes_by_segment = []
        if not isinstance(cache.metadata, dict):
            cache.metadata = {}
        cache.metadata["ann_backend"] = self._ann_backend
        if self.persist_path is not None:
            manifest_path = self.persist_path / "versions.jsonl"
            if not manifest_path.exists():
                try:
                    write_version_manifest(manifest_path, cache.lattice)
                except Exception:
                    pass
        return self._cache
















STRICT_QA_FALLBACK_TAU_SHARD = 0.1
