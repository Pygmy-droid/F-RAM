from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


def _candidate_key(candidate: Mapping[str, Any]) -> Optional[str]:
    """Best-effort stable key for deduping candidates across sources."""
    for field in ("candidate_id", "id"):
        value = candidate.get(field)
        if value is not None:
            return f"id:{value}"
    file_id = candidate.get("file") or candidate.get("doc_id")
    chunk_id = candidate.get("chunk_id")
    if file_id is not None or chunk_id is not None:
        return f"fc:{file_id}:{chunk_id}"
    return None


def _origin_for_candidate(candidate: Mapping[str, Any], fallback: str) -> str:
    return str(
        candidate.get("origin")
        or candidate.get("source")
        or candidate.get("kind")
        or fallback
    )


def _score(candidate: Mapping[str, Any]) -> float:
    try:
        return float(candidate.get("score", 0.0))
    except Exception:
        return 0.0


def merge_cognitive_ann_results(
    ann_candidates: Sequence[Mapping[str, Any]],
    cognitive_candidates: Sequence[Mapping[str, Any]],
    k: int,
    *,
    prefer_cognitive: bool = True,
) -> List[Dict[str, Any]]:
    """
    Merge ANN and cognitive memory candidates into a single shortlist.

    - Dedupes by candidate_id/id or (file, chunk_id) when available.
    - Sorts by score descending; ties prefer cognitive when prefer_cognitive is True.
    - Preserves source tags via the `origin` field.
    """
    merged: List[Dict[str, Any]] = []
    seen: set[str] = set()

    def _ingest(seq: Iterable[Mapping[str, Any]], fallback_origin: str) -> None:
        for cand in seq:
            key = _candidate_key(cand)
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            origin = _origin_for_candidate(cand, fallback_origin)
            payload = dict(cand)
            payload.setdefault("origin", origin)
            merged.append(payload)

    if prefer_cognitive:
        _ingest(cognitive_candidates, "cognitive_memory")
        _ingest(ann_candidates, "ann")
    else:
        _ingest(ann_candidates, "ann")
        _ingest(cognitive_candidates, "cognitive_memory")

    def _priority(entry: Mapping[str, Any]) -> Tuple[float, int]:
        origin = str(entry.get("origin", ""))
        origin_rank = 0 if origin == "cognitive_memory" else 1 if origin == "ann" else 2
        return (-_score(entry), origin_rank)

    merged.sort(key=_priority)
    return merged[: max(0, int(k))]


def merge_with_gates(
    ann_candidates: Sequence[Mapping[str, Any]],
    cognitive_candidates: Sequence[Mapping[str, Any]],
    k: int,
    *,
    enabled: bool,
    prefer_cognitive: bool = True,
    fallback: Optional[Sequence[Mapping[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Gate-aware merge wrapper. Returns ANN candidates untouched when disabled.
    """
    if not enabled:
        # Return ann candidates as-is (respect k)
        return list(ann_candidates)[: max(0, int(k))]

    merged = merge_cognitive_ann_results(
        ann_candidates, cognitive_candidates, k, prefer_cognitive=prefer_cognitive
    )
    if merged:
        return merged
    if fallback:
        return list(fallback)[: max(0, int(k))]
    return []
