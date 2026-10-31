"""Evaluation metrics for calibration and coverage (spec §§15,17)."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Iterable, List, Sequence


@dataclass(frozen=True)
class ReliabilityBin:
    lower: float
    upper: float
    count: int
    accuracy: float
    confidence: float


def _ensure_sequences(preds: Sequence[float], labels: Sequence[int]) -> List[tuple[float, int]]:
    if len(preds) != len(labels):  # pragma: no cover - defensive guard
        raise ValueError("preds and labels must be the same length")
    return list(zip(preds, labels))


def reliability_curve(
    preds: Sequence[float], labels: Sequence[int], n_bins: int = 10
) -> List[ReliabilityBin]:
    pairs = _ensure_sequences(preds, labels)
    if n_bins <= 0:
        raise ValueError("n_bins must be > 0")
    bins: List[ReliabilityBin] = []
    bin_width = 1.0 / n_bins
    for i in range(n_bins):
        lower = i * bin_width
        upper = lower + bin_width
        bucket = [pair for pair in pairs if lower <= pair[0] < upper or (i == n_bins - 1 and pair[0] == 1.0)]
        count = len(bucket)
        if count == 0:
            bins.append(ReliabilityBin(lower, upper, 0, 0.0, 0.0))
            continue
        accuracy = sum(label for _, label in bucket) / count
        confidence = sum(prob for prob, _ in bucket) / count
        bins.append(ReliabilityBin(lower, upper, count, accuracy, confidence))
    return bins


def expected_calibration_error(
    preds: Sequence[float], labels: Sequence[int], n_bins: int = 10
) -> float:
    bins = reliability_curve(preds, labels, n_bins=n_bins)
    total = sum(b.count for b in bins)
    if total == 0:
        return 0.0
    ece = 0.0
    for b in bins:
        if b.count == 0:
            continue
        ece += (b.count / total) * abs(b.accuracy - b.confidence)
    return float(ece)


def mean_absolute_calibration_error(
    preds: Sequence[float], labels: Sequence[int], n_bins: int = 10
) -> float:
    bins = reliability_curve(preds, labels, n_bins=n_bins)
    diffs = [abs(b.accuracy - b.confidence) for b in bins if b.count > 0]
    return float(sum(diffs) / len(diffs)) if diffs else 0.0


def recall_at_k(
    ranked_ids: Sequence[str], relevant_ids: Iterable[str], k: int
) -> float:
    """Return the fraction of relevant IDs present in the first ``k`` results."""
    if k <= 0:
        raise ValueError("k must be > 0")
    relevant = {str(item) for item in relevant_ids}
    if not relevant:
        return 0.0
    retrieved = {str(item) for item in ranked_ids[:k]}
    return len(retrieved & relevant) / len(relevant)


def reciprocal_rank(ranked_ids: Sequence[str], relevant_ids: Iterable[str]) -> float:
    """Return the reciprocal rank of the first relevant result, or zero."""
    relevant = {str(item) for item in relevant_ids}
    for rank, item in enumerate(ranked_ids, start=1):
        if str(item) in relevant:
            return 1.0 / rank
    return 0.0


def mean_reciprocal_rank(
    rankings: Sequence[Sequence[str]], relevant: Sequence[Iterable[str]]
) -> float:
    """Average reciprocal rank across aligned ranking/relevance collections."""
    if len(rankings) != len(relevant):
        raise ValueError("rankings and relevant must be the same length")
    if not rankings:
        return 0.0
    return sum(
        reciprocal_rank(ranking, expected)
        for ranking, expected in zip(rankings, relevant)
    ) / len(rankings)


def misrouting_rate(
    predicted_routes: Sequence[str], expected_routes: Sequence[str]
) -> float:
    """Return the fraction of route decisions that differ from expectation."""
    if len(predicted_routes) != len(expected_routes):
        raise ValueError("predicted_routes and expected_routes must be the same length")
    if not predicted_routes:
        return 0.0
    mismatches = sum(
        str(predicted) != str(expected)
        for predicted, expected in zip(predicted_routes, expected_routes)
    )
    return mismatches / len(predicted_routes)


def missed_evidence_rate(evidence_found: Sequence[bool]) -> float:
    """Return the fraction of evaluated queries whose evidence was not found."""
    if not evidence_found:
        return 0.0
    return sum(not bool(found) for found in evidence_found) / len(evidence_found)


_ARTICLES_RE = re.compile(r"\b(?:a|an|the)\b", re.IGNORECASE)
_NON_WORD_RE = re.compile(r"[^\w\s]", re.UNICODE)


def _normalize_answer(text: str) -> str:
    lowered = str(text).lower()
    without_punctuation = _NON_WORD_RE.sub(" ", lowered)
    without_articles = _ARTICLES_RE.sub(" ", without_punctuation)
    return " ".join(without_articles.split())


def _answer_references(reference: str | Sequence[str]) -> tuple[str, ...]:
    if isinstance(reference, str):
        return (reference,)
    return tuple(str(item) for item in reference)


def qa_exact_match(prediction: str, reference: str | Sequence[str]) -> float:
    """Normalized exact-match score, taking the best of multiple references."""
    normalized = _normalize_answer(prediction)
    references = _answer_references(reference)
    if not references:
        return 0.0
    return float(any(normalized == _normalize_answer(item) for item in references))


def qa_token_f1(prediction: str, reference: str | Sequence[str]) -> float:
    """SQuAD-style token F1, taking the best of multiple references."""

    def score_one(expected: str) -> float:
        predicted_tokens = _normalize_answer(prediction).split()
        expected_tokens = _normalize_answer(expected).split()
        if not predicted_tokens or not expected_tokens:
            return float(predicted_tokens == expected_tokens)
        predicted_counts: dict[str, int] = {}
        expected_counts: dict[str, int] = {}
        for token in predicted_tokens:
            predicted_counts[token] = predicted_counts.get(token, 0) + 1
        for token in expected_tokens:
            expected_counts[token] = expected_counts.get(token, 0) + 1
        overlap = sum(
            min(count, expected_counts.get(token, 0))
            for token, count in predicted_counts.items()
        )
        if overlap == 0:
            return 0.0
        precision = overlap / len(predicted_tokens)
        recall = overlap / len(expected_tokens)
        return 2.0 * precision * recall / (precision + recall)

    references = _answer_references(reference)
    return max((score_one(item) for item in references), default=0.0)


def citation_precision_recall_f1(
    predicted_ids: Iterable[str], expected_ids: Iterable[str]
) -> dict[str, float]:
    """Set-based citation correctness for shard, claim, or document IDs."""
    predicted = {str(item) for item in predicted_ids}
    expected = {str(item) for item in expected_ids}
    if not predicted and not expected:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    overlap = len(predicted & expected)
    precision = overlap / len(predicted) if predicted else 0.0
    recall = overlap / len(expected) if expected else 0.0
    f1 = (
        2.0 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    return {"precision": precision, "recall": recall, "f1": f1}


def _merge_spans(spans: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    normalized: list[tuple[int, int]] = []
    for start, end in spans:
        start_i = int(start)
        end_i = int(end)
        if start_i < 0 or end_i < start_i:
            raise ValueError("citation spans must satisfy 0 <= start <= end")
        if start_i == end_i:
            continue
        normalized.append((start_i, end_i))
    merged: list[tuple[int, int]] = []
    for start, end in sorted(normalized):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def span_citation_correctness(
    predicted_spans: Iterable[tuple[int, int]],
    expected_spans: Iterable[tuple[int, int]],
) -> dict[str, float]:
    """Character-coverage precision/recall/F1 for cited evidence spans."""
    predicted = _merge_spans(predicted_spans)
    expected = _merge_spans(expected_spans)
    predicted_length = sum(end - start for start, end in predicted)
    expected_length = sum(end - start for start, end in expected)
    if predicted_length == 0 and expected_length == 0:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}

    overlap = 0
    i = 0
    j = 0
    while i < len(predicted) and j < len(expected):
        start = max(predicted[i][0], expected[j][0])
        end = min(predicted[i][1], expected[j][1])
        if start < end:
            overlap += end - start
        if predicted[i][1] <= expected[j][1]:
            i += 1
        else:
            j += 1

    precision = overlap / predicted_length if predicted_length else 0.0
    recall = overlap / expected_length if expected_length else 0.0
    f1 = (
        2.0 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    return {"precision": precision, "recall": recall, "f1": f1}


def percentile(values: Sequence[float], quantile: float) -> float:
    """Return a linearly interpolated quantile without requiring NumPy."""
    if not 0.0 <= quantile <= 1.0:
        raise ValueError("quantile must be between 0 and 1")
    cleaned = sorted(float(value) for value in values if math.isfinite(float(value)))
    if not cleaned:
        return 0.0
    position = (len(cleaned) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return cleaned[lower]
    weight = position - lower
    return cleaned[lower] * (1.0 - weight) + cleaned[upper] * weight


def latency_percentiles(latencies_ms: Sequence[float]) -> dict[str, float]:
    """Return the p95 and p99 latency values used by the evaluation harness."""
    return {
        "p95_ms": percentile(latencies_ms, 0.95),
        "p99_ms": percentile(latencies_ms, 0.99),
    }


def as_of_accuracy(checks: Sequence[bool]) -> float:
    """Return the fraction of as-of/version-policy checks that passed."""
    if not checks:
        return 0.0
    return sum(bool(value) for value in checks) / len(checks)
