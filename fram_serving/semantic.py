from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from fram_core.pipeline import tokenize_text


def _tokenize_lower(text: str | None) -> List[str]:
    if not text:
        return []
    return [token.lower() for token in tokenize_text(text) if token]


def _unique(seq: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    ordered: List[str] = []
    for item in seq:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


@dataclass
class SituationContext:
    text: str
    tokens: List[str]
    expansions: List[str]
    entities: List[str]
    aliases: List[str]
    audit: List[str]
    clock: Dict[str, Any] | None = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "tokens": self.tokens,
            "expansions": self.expansions,
            "entities": self.entities,
            "aliases": self.aliases,
            "audit": self.audit,
            "clock": self.clock or {},
        }


class EntityGraph:
    def __init__(self, mapping: Optional[Dict[str, Iterable[str]]] = None):
        self._graph: Dict[str, Set[str]] = defaultdict(set)
        if mapping:
            for src, targets in mapping.items():
                self.add_edges(src, targets)

    def add_edges(self, source: str, targets: Iterable[str]) -> None:
        if not source:
            return
        src = source.lower()
        for target in targets:
            if not target:
                continue
            self._graph[src].add(str(target).lower())

    def neighbors(self, entity: str) -> Set[str]:
        if not entity:
            return set()
        return set(self._graph.get(str(entity).lower(), set()))

    def bridge_score(self, context_entities: Set[str], candidate_entities: Set[str]) -> float:
        if not context_entities or not candidate_entities:
            return 0.0
        hits = 0.0
        for entity in candidate_entities:
            ent = entity.lower()
            if ent in context_entities:
                hits += 1.0
                continue
            neighbors = self.neighbors(ent)
            if neighbors & context_entities:
                hits += 0.5
        return hits / len(candidate_entities)


@dataclass
class CandidateFeatures:
    id: str
    text: str
    tokens: Set[str]
    metadata: Dict[str, Any]
    entities: Set[str]


@dataclass
class RerankResult:
    id: str
    score: float
    raw_score: float
    model: str


class RelevanceReranker:
    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or "heuristic"

    def rank(self, query_context: str, candidates: Sequence[CandidateFeatures]) -> List[RerankResult]:
        query_tokens = set(_tokenize_lower(query_context))
        results: List[RerankResult] = []
        for candidate in candidates:
            if not candidate.tokens or not query_tokens:
                overlap = 0.0
            else:
                overlap = len(query_tokens & candidate.tokens) / max(len(query_tokens), 1)
            results.append(RerankResult(id=candidate.id, score=overlap, raw_score=overlap, model=self.model_name))
        return results


def build_situation(
    query: str,
    *,
    task: Optional[str] = None,
    domain: Optional[str] = None,
    recent_turns: Optional[Sequence[str]] = None,
    goals: Optional[Sequence[str]] = None,
    clock: Optional[Dict[str, Any]] = None,
    tau_expand: float = 0.72,
    max_terms: int = 16,
) -> SituationContext:
    """
    Combine query, task/domain hints, recent turns, and goals into a single
    situation string. Guard expansions with a simple overlap threshold so we
    only add context that is semantically close to the query.
    """

    base_tokens = _tokenize_lower(query)
    audit: List[str] = [f"query='{query}' ({len(base_tokens)} tokens)"]
    parts: List[str] = [query]

    candidate_sources: List[tuple[str, str]] = []
    if task:
        candidate_sources.append(("task", task))
    if domain:
        candidate_sources.append(("domain", domain))
    if goals:
        for goal in goals:
            candidate_sources.append(("goal", str(goal)))
    if recent_turns:
        for idx, turn in enumerate(recent_turns[-5:]):
            candidate_sources.append((f"turn_{idx+1}", str(turn)))

    accepted_terms: List[str] = []
    for label, text in candidate_sources:
        tokens = _tokenize_lower(text)
        if not tokens:
            continue
        overlap = 0.0
        if base_tokens and tokens:
            overlap = len(set(base_tokens) & set(tokens)) / max(len(tokens), 1)
        if overlap >= tau_expand:
            accepted_terms.extend(tokens)
            parts.append(text)
            audit.append(f"accepted {label} (overlap={overlap:.2f})")
        else:
            audit.append(f"skipped {label} (overlap={overlap:.2f})")

    merged_tokens = _unique(base_tokens + accepted_terms)
    if max_terms > 0:
        merged_tokens = merged_tokens[:max_terms]

    text_concat = " ".join(parts).strip()
    entities = _unique(_tokenize_lower(" ".join(candidate for label, candidate in candidate_sources if label == "goal")))
    aliases: List[str] = []
    if task:
        aliases.append(task.lower())
    if domain:
        aliases.append(domain.lower())
    aliases = _unique(aliases)

    return SituationContext(
        text=text_concat,
        tokens=merged_tokens,
        expansions=accepted_terms,
        entities=entities,
        aliases=aliases,
        audit=audit,
        clock=clock,
    )
