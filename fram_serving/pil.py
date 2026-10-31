"""PIL teaching vector: the first slice of the muscle-memory retriever.

Reconstruction from Rick Berghahn's February 2026 note 35, as carried by
``docs/manual/08_reconstruction_kit.md`` (Kit 3). The original module was lost;
this file is a rebuild from the notes, not the original.

Posture (``docs/FRAM_PIL.md``, ``docs/breathing_flame_notes_2026-02-01.md``):

* No decision authority. Nothing here is read by selection, ranking, or
  routing. It only describes what routing did.
* No memory writes. Pure functions over plain inputs; no I/O.
* No symbols. The vector carries scalars keyed by structural names (coverage
  stage, confidence route). No tokens, no text, no semantic labels.
* Constraint memory stays sovereign. A constraint refusal still yields a
  teach vector, but one that teaches nothing (all deltas zero).

Terms, in the simplest reading of the note:

* an *anchor* is a coverage stage (``memory``, ``seed``, ``anchors``,
  ``shards``), whose observed gain is its coverage delta in the trace;
* a *route* is the confidence decision (``local``, ``anchors``, ``global``),
  whose observed stability is the calibrated probability that chose it;
* ``write_delta`` is observed completed memory writes minus expected;
* ``drift_delta`` is observed transitional complexity minus expected.

Expected values default to zero, so with no prior the teach vector simply
reports what was observed. A caller with a prior (the scheduler, the harness)
passes it in; the query path in this slice passes none.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional

COVERAGE_STAGES: tuple[str, ...] = ("memory", "seed", "anchors", "shards")
ROUTES: tuple[str, ...] = ("local", "anchors", "global")

# Sparsify rule constants from note 35. The predicate lives here so the
# scheduler and the harness share one definition.
SPARSIFY_ACTIVITY_THRESHOLD = 0.6
SPARSIFY_IMPROVEMENT_FLOOR = 0.02

_WRITE_KEYS: tuple[str, ...] = (
    "cognitive_episode_write",
    "lived_memory_write",
    "memory_capsule_write",
    "archive_write",
)


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(parsed):
        return default
    return parsed


def _signed_deltas(
    observed: Mapping[str, Any],
    expected: Mapping[str, Any] | None,
    keys: Iterable[str],
) -> Dict[str, float]:
    expected = expected or {}
    out: Dict[str, float] = {}
    for key in sorted(set(keys) | set(observed.keys())):
        out[str(key)] = _finite(observed.get(key, 0.0)) - _finite(expected.get(key, 0.0))
    return out


def sparsify_suggestion(
    activity: Mapping[str, Any],
    improvement: Mapping[str, Any],
    *,
    activity_threshold: float = SPARSIFY_ACTIVITY_THRESHOLD,
    improvement_floor: float = SPARSIFY_IMPROVEMENT_FLOOR,
) -> List[str]:
    """Routes whose activity is high and whose improvement is low.

    This is the predicate of the note 35 sparsify rule, nothing more. It
    suggests; it does not apply decay or change eligibility. Sorted for
    determinism.
    """

    suggested: List[str] = []
    for route in sorted(activity.keys()):
        act = _finite(activity.get(route))
        imp = _finite(improvement.get(route), default=float("inf"))
        if act > activity_threshold and imp < improvement_floor:
            suggested.append(str(route))
    return suggested


@dataclass(frozen=True)
class PILTeachVector:
    """Per-decision teaching signal. Observational only."""

    anchor_scores: Dict[str, float] = field(default_factory=dict)
    route_scores: Dict[str, float] = field(default_factory=dict)
    write_delta: float = 0.0
    drift_delta: float = 0.0
    sparsify_suggestion: List[str] = field(default_factory=list)
    route: Optional[str] = None
    observe_only: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": "pil-teach-1",
            "observe_only": bool(self.observe_only),
            "route": self.route,
            "anchor_scores": {k: float(v) for k, v in sorted(self.anchor_scores.items())},
            "route_scores": {k: float(v) for k, v in sorted(self.route_scores.items())},
            "write_delta": float(self.write_delta),
            "drift_delta": float(self.drift_delta),
            "sparsify_suggestion": list(self.sparsify_suggestion),
        }

    def magnitude(self) -> float:
        """L2 norm over every scalar; a convenience for harness summaries."""

        parts = list(self.anchor_scores.values()) + list(self.route_scores.values())
        parts += [self.write_delta, self.drift_delta]
        return math.sqrt(sum(float(p) * float(p) for p in parts))


def teach_vector(
    observed_anchor_gain: Mapping[str, Any],
    observed_route_stability: Mapping[str, Any],
    *,
    expected_anchor_gain: Mapping[str, Any] | None = None,
    expected_route_stability: Mapping[str, Any] | None = None,
    observed_write: float = 0.0,
    expected_write: float = 0.0,
    observed_drift: float = 0.0,
    expected_drift: float = 0.0,
    route_activity: Mapping[str, Any] | None = None,
    route_improvement: Mapping[str, Any] | None = None,
    route: Optional[str] = None,
    observe_only: bool = True,
) -> PILTeachVector:
    """Build a teach vector from plain numbers. Pure and deterministic."""

    anchor_scores = _signed_deltas(observed_anchor_gain, expected_anchor_gain, COVERAGE_STAGES)
    route_scores = _signed_deltas(observed_route_stability, expected_route_stability, ROUTES)
    suggestion: List[str] = []
    if route_activity is not None and route_improvement is not None:
        suggestion = sparsify_suggestion(route_activity, route_improvement)
    return PILTeachVector(
        anchor_scores=anchor_scores,
        route_scores=route_scores,
        write_delta=_finite(observed_write) - _finite(expected_write),
        drift_delta=_finite(observed_drift) - _finite(expected_drift),
        sparsify_suggestion=suggestion,
        route=route,
        observe_only=bool(observe_only),
    )


def _observed_from_trace(trace: Mapping[str, Any]) -> Dict[str, Any]:
    """Read the observed values PIL needs out of a finished query trace.

    Reads only; never mutates the trace. Missing fields read as zero.
    """

    confidence = trace.get("confidence") if isinstance(trace.get("confidence"), Mapping) else {}
    decision = confidence.get("decision")
    route = str(decision) if isinstance(decision, str) and decision else None

    coverage = trace.get("coverage") if isinstance(trace.get("coverage"), Mapping) else {}
    selection = trace.get("selection") if isinstance(trace.get("selection"), Mapping) else {}
    stage_deltas: Mapping[str, Any] = {}
    candidate = coverage.get("delta_by_stage")
    if not isinstance(candidate, Mapping):
        candidate = selection.get("coverage_delta")
    if isinstance(candidate, Mapping):
        stage_deltas = {k: v for k, v in candidate.items() if k in COVERAGE_STAGES}
    anchor_gain = {stage: _finite(stage_deltas.get(stage, 0.0)) for stage in COVERAGE_STAGES}

    prob = trace.get("p_temp")
    if prob is None:
        prob = confidence.get("prob", confidence.get("p"))
    stability = _finite(prob)
    route_stability = {r: 0.0 for r in ROUTES}
    if route is not None:
        route_stability[route] = stability

    writes = 0.0
    for key in _WRITE_KEYS:
        block = trace.get(key)
        if isinstance(block, Mapping) and block.get("ok"):
            writes += 1.0

    tc_block = trace.get("transitional_complexity")
    drift = _finite(tc_block.get("tc")) if isinstance(tc_block, Mapping) else 0.0

    return {
        "route": route,
        "anchor_gain": anchor_gain,
        "route_stability": route_stability,
        "write": writes,
        "drift": drift,
    }


def teach_from_trace(
    trace: Mapping[str, Any],
    expectations: Mapping[str, Any] | None = None,
    *,
    observe_only: bool = True,
) -> PILTeachVector:
    """Teach vector for one routing decision, read from its trace.

    ``expectations`` may carry ``anchor_gain`` and ``route_stability`` maps and
    ``write`` and ``drift`` scalars. With none given, every expected value is
    zero and the vector reports the observed values signed as they stand.
    """

    observed = _observed_from_trace(trace)
    expectations = expectations or {}
    exp_anchor = expectations.get("anchor_gain")
    exp_route = expectations.get("route_stability")
    return teach_vector(
        observed["anchor_gain"],
        observed["route_stability"],
        expected_anchor_gain=exp_anchor if isinstance(exp_anchor, Mapping) else None,
        expected_route_stability=exp_route if isinstance(exp_route, Mapping) else None,
        observed_write=observed["write"],
        expected_write=_finite(expectations.get("write", 0.0)),
        observed_drift=observed["drift"],
        expected_drift=_finite(expectations.get("drift", 0.0)),
        route=observed["route"],
        observe_only=observe_only,
    )


def attach_teach_to_trace(trace: Any, cfg: Any) -> Optional[Dict[str, Any]]:
    """Attach a ``pil_teach`` block to a finished trace when the flag is on.

    This is the only thing PIL does in the query path in this slice. It runs
    after selection, ranking, and every memory write have completed, so it can
    change none of them. With ``pil_enabled`` off (the default) the trace is
    left untouched and ``None`` is returned. Any failure is swallowed:
    observability must not break the main flow.
    """

    if not isinstance(trace, dict):
        return None
    if not bool(getattr(cfg, "pil_enabled", False)):
        return None
    try:
        observe_only = bool(getattr(cfg, "pil_observe_only", True))
        block = teach_from_trace(trace, observe_only=observe_only).to_dict()
    except Exception:
        return None
    trace["pil_teach"] = block
    return block
