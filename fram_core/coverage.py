from __future__ import annotations
"""Concave coverage utilities with independence buckets and Δ/C helpers.

Implements the concave, increasing coverage function and provides a lightweight
state container to support marginal-gain calculations under the independence
bucket policy from FRAM v2.2 (spec sections 11.3-11.7). The helpers here are shared by
anchor selection and shard admission, letting callers reason about marginal
claim coverage per composite cost.
"""

import heapq
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Set, Tuple


@dataclass(frozen=True)
class ClaimEvidence:
    """Observed claim evidence.

    Each evidence entry carries the claim key and optional independence buckets.
    Buckets should be encoded as stable strings (e.g., "doc:foo", "chunk:foo:1").
    Claims without buckets behave like the v2.1 behaviour (every observation is
    counted), while buckets ensure we only increment a claim once per bucket set.
    """

    key: str
    buckets: Tuple[str, ...] = ()

    def dedupe_buckets(self) -> ClaimEvidence:
        if not self.buckets:
            return self
        # Preserve order while removing duplicates
        seen: Set[str] = set()
        unique: List[str] = []
        for b in self.buckets:
            if b not in seen:
                seen.add(b)
                unique.append(b)
        return ClaimEvidence(key=self.key, buckets=tuple(unique))


def _as_evidence(claims: Iterable[str | ClaimEvidence]) -> List[ClaimEvidence]:
    out: List[ClaimEvidence] = []
    for c in claims:
        if isinstance(c, ClaimEvidence):
            out.append(c.dedupe_buckets())
        else:
            out.append(ClaimEvidence(key=str(c)))
    return out


def concave_coverage(
    u_counts: Mapping[str, int],
    w: Mapping[str, float],
    gamma: float = 0.6,
    u_max: int = 3,
) -> float:
    """Cov = sum_i w_i * (1 - gamma ** min(u_i, u_max)), with 0 < gamma < 1."""

    total = 0.0
    for key, count in u_counts.items():
        wi = float(w.get(key, 1.0))
        c = int(max(0, min(int(count), int(u_max))))
        total += wi * (1.0 - (gamma ** c))
    return float(total)


@dataclass
class CoverageState:
    """Mutable coverage state tracking counts and bucket hits."""

    gamma: float = 0.6
    u_max: int = 3
    weights: Mapping[str, float] | None = None
    counts: Dict[str, int] = field(default_factory=dict)
    bucket_hits: Dict[str, Dict[str, Set[str]]] = field(default_factory=dict)
    segment_hits: Dict[str, int] = field(default_factory=dict)

    def copy(self) -> CoverageState:
        return CoverageState(
            gamma=self.gamma,
            u_max=self.u_max,
            weights=self.weights,
            counts=dict(self.counts),
            bucket_hits={
                claim: {b_type: set(values) for b_type, values in buckets.items()}
                for claim, buckets in self.bucket_hits.items()
            },
            segment_hits=dict(self.segment_hits),
        )

    def value(self) -> float:
        return concave_coverage(
            self.counts,
            self.weights or {},
            gamma=self.gamma,
            u_max=self.u_max,
        )

    def apply(self, claims: Iterable[str | ClaimEvidence]) -> None:
        """Mutate state by adding evidence respecting independence buckets."""

        for evidence in _as_evidence(claims):
            buckets = evidence.buckets
            if not buckets:
                self.counts[evidence.key] = int(self.counts.get(evidence.key, 0)) + 1
                continue

            hits = self.bucket_hits.setdefault(evidence.key, {})
            new_bucket = False
            new_entries: List[Tuple[str, str]] = []
            for bucket in buckets:
                if ":" in bucket:
                    bucket_type, bucket_value = bucket.split(":", 1)
                else:
                    bucket_type, bucket_value = "default", bucket
                values = hits.setdefault(bucket_type, set())
                if bucket_value not in values:
                    values.add(bucket_value)
                    new_bucket = True
                    new_entries.append((bucket_type, bucket_value))
            if new_bucket:
                self.counts[evidence.key] = int(self.counts.get(evidence.key, 0)) + 1
                for bucket_type, bucket_value in new_entries:
                    if bucket_type == "segment":
                        self.segment_hits[bucket_value] = int(self.segment_hits.get(bucket_value, 0)) + 1

    def marginal_gain(self, claims: Iterable[str | ClaimEvidence]) -> float:
        before = self.value()
        if before is None:  # pragma: no cover - defensive, value() always float
            before = 0.0
        scratch = self.copy()
        scratch.apply(claims)
        after = scratch.value()
        return float(after - before)

    def segment_count(self, segment: str) -> int:
        """Return how many times evidence has contributed from a given segment."""

        if not segment:
            return 0
        return int(self.segment_hits.get(segment, 0))

    def delta_coverage(self, claims: Iterable[str | ClaimEvidence]) -> float:
        """Alias for marginal gain to mirror spec naming."""

        return self.marginal_gain(claims)


def marginal_gain(
    u_counts: Mapping[str, int],
    new_claims: Iterable[str | ClaimEvidence],
    w: Mapping[str, float],
    gamma: float = 0.6,
    u_max: int = 3,
    bucket_hits: Mapping[str, Mapping[str, Set[str]]] | None = None,
) -> float:
    """Compute delta coverage from adding a shard with independence buckets."""

    state = CoverageState(gamma=gamma, u_max=u_max, weights=w)
    state.counts = dict(u_counts)
    if bucket_hits:
        state.bucket_hits = {
            claim: {b_type: set(values) for b_type, values in buckets.items()}
            for claim, buckets in bucket_hits.items()
        }
    return state.marginal_gain(new_claims)


def greedy_by_coverage(
    items: Sequence[int],
    claims_map: Mapping[int, Iterable[str | ClaimEvidence]],
    w: Mapping[str, float] | None = None,
    k: int = 1,
    gamma: float = 0.6,
    u_max: int = 3,
    seed_selected: Iterable[int] | None = None,
    bucket_hits: Mapping[str, Set[str]] | None = None,
) -> List[int]:
    """Greedy selection of up to k items maximizing concave coverage."""

    state = CoverageState(gamma=gamma, u_max=u_max, weights=w)
    if bucket_hits:
        state.bucket_hits = {
            claim: {b_type: set(values) for b_type, values in buckets.items()}
            for claim, buckets in bucket_hits.items()
        }
    if seed_selected:
        for s in seed_selected:
            state.apply(claims_map.get(int(s), ()))

    pool = [int(i) for i in items if (seed_selected is None or int(i) not in seed_selected)]
    selected: List[int] = []
    while len(selected) < k and pool:
        best_i = None
        best_gain = -1.0
        for i in pool:
            g = state.marginal_gain(claims_map.get(int(i), ()))
            if g > best_gain:
                best_gain = g
                best_i = int(i)
        if best_i is None:
            break
        state.apply(claims_map.get(best_i, ()))
        selected.append(best_i)
        pool = [i for i in pool if i != best_i]
    return selected


def greedy_by_gain_cost(
    items: Sequence[int],
    claims_map: Mapping[int, Iterable[str | ClaimEvidence]],
    cost_map: Mapping[int, float],
    state: CoverageState,
    k: int,
    budget: float | None = None,
) -> List[int]:
    """Greedy Δ/C selector with optional budget (non-negative costs).

    This evaluates marginal coverage gain per composite cost on every
    iteration. The candidate pool is expected to be small, so a simple greedy
    loop keeps the implementation easy to reason about while matching the
    Δ/C policy from the spec.
    """

    working_state = state.copy()
    remaining_budget = float(budget) if budget is not None else None
    pool = [int(i) for i in items]
    selected: List[int] = []

    while pool and len(selected) < k:
        best_i = None
        best_gain = 0.0
        best_cost = 0.0
        best_ratio = 0.0
        for i in pool:
            cost = float(cost_map.get(int(i), 0.0))
            if cost <= 0.0:
                continue
            if remaining_budget is not None and cost > remaining_budget + 1e-9:
                continue
            gain = working_state.marginal_gain(claims_map.get(int(i), ()))
            if gain <= 0.0:
                continue
            ratio = gain / cost
            if best_i is None or ratio > best_ratio or (
                ratio == best_ratio and gain > best_gain
            ):
                best_i = int(i)
                best_gain = gain
                best_cost = cost
                best_ratio = ratio
        if best_i is None:
            break
        working_state.apply(claims_map.get(best_i, ()))
        selected.append(best_i)
        if remaining_budget is not None:
            remaining_budget -= best_cost
        pool = [i for i in pool if i != best_i]
    return selected


def _composite_cost_components(
    entry: Mapping[str, float],
    lambda_tokens: float,
    lambda_rerank: float,
    selected_count: int,
) -> Tuple[float, float, float, float]:
    reads = float(entry.get("reads", 1.0))
    tokens = float(entry.get("tokens", 0.0))
    if "pairs" in entry:
        pairs = float(entry.get("pairs", 0.0))
    else:
        scale = float(entry.get("pairs_scale", 1.0))
        exponent = float(entry.get("pairs_exponent", 2.0))
        pairs = scale * float(max(selected_count, 0) + 1) ** exponent
    cost = reads + lambda_tokens * tokens + lambda_rerank * pairs
    return float(cost), float(reads), float(tokens), float(pairs)


def select_celf(
    items: Sequence[int],
    claims_map: Mapping[int, Iterable[str | ClaimEvidence]],
    costs_map: Mapping[int, Mapping[str, float]],
    k: int,
    lambdas: Mapping[str, float] | Sequence[float],
    seed: Iterable[int] | None = None,
    state: CoverageState | None = None,
    gamma: float = 0.6,
    u_max: int = 3,
    weights: Mapping[str, float] | None = None,
    lazy: bool = True,
    *,
    segment_map: Mapping[int, str] | None = None,
    segment_repeat_penalty: float = 0.7,
    segment_penalty_floor: float = 0.25,
) -> Tuple[List[int], Dict[str, int], List[Dict[str, float]], Dict[str, float]]:
    """Greedy selection over concave coverage with composite cost (spec section 11.6).

    Parameters
    ----------
    items : sequence of item identifiers to consider (excludes any fixed seeds).
    claims_map : mapping of item -> iterable of claim evidence entries.
    costs_map : mapping of item -> cost component dicts (reads/tokens/pairs info).
    k : maximum number of items in the final set (including seeds).
    lambdas : mapping or tuple providing lambda_tokens, lambda_rerank, and
        optional keys {"selected_count", "budgets"}.
    seed : optional iterable of pre-selected item ids.
    state : optional CoverageState to mutate; defaults to a fresh state.
    gamma/u_max/weights : used when creating a fresh CoverageState.
    lazy : when False, evaluate gain/cost sequentially without the lazy heap while
        preserving diagnostics and budget accounting.
    segment_map : optional mapping of item -> section/segment identifier. When
        provided, repeat selections from the same segment are down-weighted by
        segment_repeat_penalty**hits (clamped by segment_penalty_floor).
    segment_repeat_penalty : multiplicative decay applied per prior selection from
        a segment; values in (0, 1] reduce repeat picks, values >= 1 disable decay.
    segment_penalty_floor : lower bound for the diversity multiplier to avoid
        zeroing out candidates when penalty is strong.

    Returns
    -------
    selected : list of accepted item ids (excluding seeds) in acceptance order.
    stats : dict with pop/recompute/accepted counters.
    details : per-item diagnostics including seeds and accepted items.
    totals : accumulated cost components for seeds and accepted items within
        this call.
    """

    if isinstance(lambdas, Mapping):
        lambda_tokens = float(lambdas.get("lambda_tokens", 0.0))
        lambda_rerank = float(lambdas.get("lambda_rerank", 0.0))
        base_count = int(lambdas.get("selected_count", 0))
        budgets_cfg = lambdas.get("budgets")
    else:
        seq = list(lambdas)
        lambda_tokens = float(seq[0]) if len(seq) >= 1 else 0.0
        lambda_rerank = float(seq[1]) if len(seq) >= 2 else 0.0
        base_count = 0
        budgets_cfg = None

    working_state = state or CoverageState(gamma=gamma, u_max=u_max, weights=weights)
    seen: Set[int] = set()
    selected: List[int] = []
    stats = {"pops": 0, "recomps": 0, "accepted": 0}
    totals = {"reads": 0.0, "tokens": 0.0, "pairs": 0.0, "cost": 0.0}
    details: List[Dict[str, float]] = []

    selected_count = max(0, base_count)
    state_version = selected_count

    base_repeat = float(segment_repeat_penalty)
    penalty_floor = float(segment_penalty_floor)

    def _segment_multiplier(idx: int) -> float:
        if not segment_map:
            return 1.0
        segment = segment_map.get(int(idx))
        if not segment:
            return 1.0
        hits = 0
        if isinstance(working_state, CoverageState):
            hits = max(0, working_state.segment_count(segment))
        if hits <= 0:
            return 1.0
        base = min(max(base_repeat, 0.0), 1.0)
        if base >= 1.0:
            return 1.0
        multiplier = base ** hits if base > 0.0 else 0.0
        floor = min(max(penalty_floor, 0.0), 1.0)
        if floor > 0.0:
            multiplier = max(multiplier, floor)
        return float(multiplier)

    seed_list = [int(s) for s in seed] if seed is not None else []
    for idx in seed_list:
        if idx in seen:
            continue
        claims = claims_map.get(idx, ())
        gain = working_state.marginal_gain(claims)
        cost_entry = costs_map.get(idx, {})
        cost, reads, tokens, pairs = _composite_cost_components(
            cost_entry, lambda_tokens, lambda_rerank, selected_count
        )
        multiplier = _segment_multiplier(idx)
        score_gain = float(gain) * multiplier
        ratio = score_gain / cost if cost > 0 else 0.0
        details.append(
            {
                "id": int(idx),
                "delta": float(gain),
                "cost": float(cost),
                "ratio": float(ratio),
                "reads": float(reads),
                "tokens": float(tokens),
                "pairs": float(pairs),
                "seed": True,
                "diversity_multiplier": float(multiplier),
            }
        )
        working_state.apply(claims)
        totals["reads"] += reads
        totals["tokens"] += tokens
        totals["pairs"] += pairs
        totals["cost"] += cost
        seen.add(idx)
        selected_count += 1
        state_version = selected_count
        if selected_count >= k:
            return selected, stats, details, totals

    if selected_count >= k:
        return selected, stats, details, totals

    if not lazy:
        candidate_ids = [int(item) for item in items if int(item) not in seen]
        while candidate_ids and selected_count < k:
            best_idx = None
            best_gain = 0.0
            best_cost = 0.0
            best_ratio = 0.0
            best_reads = 0.0
            best_tokens = 0.0
            best_pairs = 0.0
            best_multiplier = 1.0
            for idx in list(candidate_ids):
                if idx in seen:
                    continue
                claims = claims_map.get(idx, ())
                gain = float(working_state.marginal_gain(claims))
                if gain <= 0:
                    continue
                multiplier = _segment_multiplier(idx)
                score_gain = gain * multiplier
                cost, reads, tokens, pairs = _composite_cost_components(
                    costs_map.get(idx, {}), lambda_tokens, lambda_rerank, selected_count
                )
                if cost <= 0 or score_gain <= 0:
                    continue
                ratio = score_gain / cost if cost > 0 else 0.0
                if best_idx is None or ratio > best_ratio or (
                    ratio == best_ratio and gain > best_gain
                ):
                    best_idx = idx
                    best_gain = float(gain)
                    best_cost = float(cost)
                    best_ratio = float(ratio)
                    best_reads = float(reads)
                    best_tokens = float(tokens)
                    best_pairs = float(pairs)
                    best_multiplier = float(multiplier)
            if best_idx is None:
                break
            stats["pops"] += 1
            new_reads = totals["reads"] + best_reads
            new_tokens = totals["tokens"] + best_tokens
            new_pairs = totals["pairs"] + best_pairs
            new_cost = totals["cost"] + best_cost
            budget_blocked = False
            if isinstance(budgets_cfg, Mapping):
                if budgets_cfg.get("reads") is not None and new_reads > float(budgets_cfg["reads"]):
                    budget_blocked = True
                if budgets_cfg.get("tokens") is not None and new_tokens > float(budgets_cfg["tokens"]):
                    budget_blocked = True
                if budgets_cfg.get("pairs") is not None and new_pairs > float(budgets_cfg["pairs"]):
                    budget_blocked = True
                if budgets_cfg.get("cost") is not None and new_cost > float(budgets_cfg["cost"]):
                    budget_blocked = True
            seen.add(best_idx)
            candidate_ids = [i for i in candidate_ids if i != best_idx]
            if budget_blocked:
                continue
            claims = claims_map.get(best_idx, ())
            working_state.apply(claims)
            selected.append(best_idx)
            stats["accepted"] += 1
            totals["reads"] = new_reads
            totals["tokens"] = new_tokens
            totals["pairs"] = new_pairs
            totals["cost"] = new_cost
            details.append(
                {
                    "id": int(best_idx),
                    "delta": float(best_gain),
                    "cost": float(best_cost),
                    "ratio": float(best_ratio),
                    "reads": float(best_reads),
                    "tokens": float(best_tokens),
                    "pairs": float(best_pairs),
                    "seed": False,
                    "diversity_multiplier": float(best_multiplier),
                }
            )
            selected_count += 1
            state_version = selected_count
        return selected, stats, details, totals

    queue: List[Tuple[float, int, int, float, float, float, float, float]] = []

    def _push(idx: int, version: int) -> None:
        claims = claims_map.get(idx, ())
        gain = working_state.marginal_gain(claims)
        cost, reads, tokens, pairs = _composite_cost_components(
            costs_map.get(idx, {}), lambda_tokens, lambda_rerank, selected_count
        )
        qualifier_gain = float(gain)
        if qualifier_gain <= 0:
            return
        multiplier = _segment_multiplier(idx)
        score_gain = qualifier_gain * multiplier
        if cost <= 0 or score_gain <= 0:
            return
        ratio = score_gain / cost if cost > 0 else 0.0
        heapq.heappush(queue, (-ratio, idx, version, float(gain), float(cost), reads, tokens, pairs))

    for item in items:
        idx = int(item)
        if idx in seen:
            continue
        _push(idx, state_version)

    while queue and selected_count < k:
        ratio_neg, idx, version, gain, cost, reads, tokens, pairs = heapq.heappop(queue)
        stats["pops"] += 1

        if version != state_version:
            stats["recomps"] += 1
            claims = claims_map.get(idx, ())
            gain = float(working_state.marginal_gain(claims))
            if gain <= 0:
                continue
            multiplier = _segment_multiplier(idx)
            score_gain = gain * multiplier
            cost, reads, tokens, pairs = _composite_cost_components(
                costs_map.get(idx, {}), lambda_tokens, lambda_rerank, selected_count
            )
            if cost <= 0 or score_gain <= 0:
                continue
            ratio = score_gain / cost if cost > 0 else 0.0
            heapq.heappush(queue, (-ratio, idx, state_version, gain, float(cost), reads, tokens, pairs))
            continue

        if gain <= 0:
            continue
        multiplier = _segment_multiplier(idx)
        score_gain = float(gain) * multiplier
        if cost <= 0 or score_gain <= 0:
            continue

        new_reads = totals["reads"] + reads
        new_tokens = totals["tokens"] + tokens
        new_pairs = totals["pairs"] + pairs
        new_cost = totals["cost"] + cost
        if isinstance(budgets_cfg, Mapping):
            if budgets_cfg.get("reads") is not None and new_reads > float(budgets_cfg["reads"]):
                continue
            if budgets_cfg.get("tokens") is not None and new_tokens > float(budgets_cfg["tokens"]):
                continue
            if budgets_cfg.get("pairs") is not None and new_pairs > float(budgets_cfg["pairs"]):
                continue
            if budgets_cfg.get("cost") is not None and new_cost > float(budgets_cfg["cost"]):
                continue

        claims = claims_map.get(idx, ())
        working_state.apply(claims)
        selected.append(idx)
        stats["accepted"] += 1
        totals["reads"] = new_reads
        totals["tokens"] = new_tokens
        totals["pairs"] = new_pairs
        totals["cost"] = new_cost
        ratio = score_gain / cost if cost > 0 else 0.0
        details.append(
            {
                "id": int(idx),
                "delta": float(gain),
                "cost": float(cost),
                "ratio": float(ratio),
                "reads": float(reads),
                "tokens": float(tokens),
                "pairs": float(pairs),
                "seed": False,
                "diversity_multiplier": float(multiplier),
            }
        )
        seen.add(idx)
        selected_count += 1
        state_version = selected_count

    return selected, stats, details, totals

