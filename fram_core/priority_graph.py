from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, MutableMapping, Sequence, Set

import numpy as np

_TOKEN_SPLIT = r"\w+"


@dataclass
class PriorityGraphConfig:
    enable_priority_graph: bool = True
    similarity_threshold: float = 0.6
    cluster_boost_weight: float = 0.25
    aggregation_mode: str = "mean"
    priority_clip_min: float = 0.0
    priority_clip_max: float = 2.0


def _tokenize(text: str) -> Set[str]:
    import re

    return set(re.findall(_TOKEN_SPLIT, text.lower()))


def _candidate_tokens(candidate: Mapping[str, object]) -> Set[str]:
    tokens: Set[str] = set()
    for key in ("group", "lineage", "doc_id", "text"):
        value = candidate.get(key)
        if isinstance(value, str):
            tokens.update(_tokenize(value))
    return tokens


def _similarity(a: Mapping[str, object], b: Mapping[str, object]) -> float:
    group_a = a.get("group")
    group_b = b.get("group")
    if isinstance(group_a, str) and isinstance(group_b, str) and group_a == group_b:
        return 1.0
    tokens_a = _candidate_tokens(a)
    tokens_b = _candidate_tokens(b)
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = len(tokens_a & tokens_b)
    union = len(tokens_a | tokens_b)
    return intersection / float(max(union, 1))


def build_priority_graph(
    candidates: Sequence[Mapping[str, object]],
    similarity_threshold: float,
) -> Dict[int, Set[int]]:
    """Return an adjacency map (index -> neighbor indices) based on similarity."""
    graph: Dict[int, Set[int]] = defaultdict(set)
    n = len(candidates)
    for i in range(n):
        for j in range(i + 1, n):
            sim = _similarity(candidates[i], candidates[j])
            if sim >= similarity_threshold:
                graph[i].add(j)
                graph[j].add(i)
    return graph


def _cluster_indices(graph: Mapping[int, Set[int]], total_nodes: int) -> List[List[int]]:
    """Return connected components from an adjacency map."""
    seen = set()
    clusters: List[List[int]] = []
    for node in range(total_nodes):
        if node in seen:
            continue
        stack = [node]
        component: List[int] = []
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            component.append(cur)
            for neigh in graph.get(cur, set()):
                if neigh not in seen:
                    stack.append(neigh)
        clusters.append(component)
    return clusters


def score_priority_clusters(
    candidates: Sequence[MutableMapping[str, object]],
    graph: Mapping[int, Set[int]],
    *,
    aggregation_mode: str = "mean",
    cluster_boost_weight: float = 0.25,
    priority_clip_min: float = 0.0,
    priority_clip_max: float = 2.0,
    enable_priority_graph: bool = True,
) -> List[MutableMapping[str, object]]:
    """Attach graph_priority to each candidate using cluster-level aggregation."""
    total_nodes = len(candidates)
    clusters = _cluster_indices(graph, total_nodes)
    updated: List[MutableMapping[str, object]] = []
    for cluster in clusters:
        base_priorities: List[float] = []
        for idx in cluster:
            base_priorities.append(float(candidates[idx].get("phase_d_priority", 1.0)))
        if aggregation_mode == "max":
            cluster_priority = max(base_priorities) if base_priorities else 1.0
        else:
            cluster_priority = float(np.mean(base_priorities)) if base_priorities else 1.0

        for idx in cluster:
            candidate = dict(candidates[idx])
            base_priority = float(candidate.get("phase_d_priority", 1.0))
            graph_priority = base_priority
            if enable_priority_graph and len(cluster) > 1:
                graph_priority = base_priority + cluster_boost_weight * cluster_priority
            graph_priority = float(np.clip(graph_priority, priority_clip_min, priority_clip_max))
            candidate["graph_priority"] = graph_priority
            updated.append(candidate)
    return updated


def apply_priority_graph(
    candidates: Sequence[MutableMapping[str, object]],
    config: Mapping[str, object],
) -> List[MutableMapping[str, object]]:
    """Build and score the priority graph, returning candidates with graph_priority."""
    enable_graph = bool(getattr(config, "enable_priority_graph", True))
    if not enable_graph or not candidates:
        return [dict(c) | {"graph_priority": float(c.get("phase_d_priority", 1.0))} for c in candidates]

    threshold = float(getattr(config, "priority_graph_similarity_threshold", 0.6))
    boost = float(getattr(config, "priority_graph_cluster_boost_weight", 0.25))
    mode = str(getattr(config, "priority_graph_aggregation_mode", "mean")).lower()
    if mode not in {"mean", "max"}:
        mode = "mean"
    priority_clip_min = float(getattr(config, "priority_clip_min", 0.0))
    priority_clip_max = float(getattr(config, "priority_clip_max", 2.0))

    graph = build_priority_graph(candidates, threshold)
    return score_priority_clusters(
        candidates,
        graph,
        aggregation_mode=mode,
        cluster_boost_weight=boost,
        priority_clip_min=priority_clip_min,
        priority_clip_max=priority_clip_max,
        enable_priority_graph=enable_graph,
    )
