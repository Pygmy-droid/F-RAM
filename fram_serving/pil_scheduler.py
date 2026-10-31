"""PIL multi-rate clocks, inertia threshold, and sparsify rule.

Reconstruction from Rick Berghahn's February 2026 note 35 via
``docs/manual/08_reconstruction_kit.md`` (Kit 3). The note named three files,
``scheduler.py`` (clocks), ``identity_update.py`` (inertia), and
``routing_policy.py`` (sparsify). None exist in this tree under those or any
other name (audited 2026-10-30: ``priority_graph``, ``routing_policy``,
``scheduler``, ``identity_update``, ``pil``), so the three rules are gathered
here in one small module until any of them earns its own file.

What the clocks mean, in Rick's words from the kit: what changes easily
(FAST), what changes with evidence (MEDIUM), what is hard to change (SLOW with
inertia).

Posture: this module holds state in memory and emits events as plain dicts.
It performs no I/O, writes no memory, and nothing in the serving path reads
its eligibility values in this slice. Eligibility is a number that is
observed, not a number that is obeyed.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Tuple

from fram_serving.pil import (
    SPARSIFY_ACTIVITY_THRESHOLD,
    SPARSIFY_IMPROVEMENT_FLOOR,
    PILTeachVector,
)

FAST = "fast"
MEDIUM = "medium"
SLOW = "slow"

SPARSIFY_DECAY_MIN = 0.1
SPARSIFY_DECAY_MAX = 0.3


@dataclass(frozen=True)
class SchedulerConfig:
    medium_every_stable_turns: int = 10
    slow_delta_threshold: float = 0.05
    inertia_epsilon: float = 0.01
    sparsify_window: int = 10
    sparsify_activity_threshold: float = SPARSIFY_ACTIVITY_THRESHOLD
    sparsify_improvement_floor: float = SPARSIFY_IMPROVEMENT_FLOOR
    sparsify_decay: float = 0.25

    def __post_init__(self) -> None:
        if self.medium_every_stable_turns < 1:
            raise ValueError("medium_every_stable_turns must be >= 1")
        if self.sparsify_window < 1:
            raise ValueError("sparsify_window must be >= 1")
        if not (SPARSIFY_DECAY_MIN <= self.sparsify_decay <= SPARSIFY_DECAY_MAX):
            raise ValueError(
                f"sparsify_decay must stay within {SPARSIFY_DECAY_MIN} to "
                f"{SPARSIFY_DECAY_MAX}; got {self.sparsify_decay}"
            )
        if self.inertia_epsilon < 0.0 or self.slow_delta_threshold < 0.0:
            raise ValueError("inertia_epsilon and slow_delta_threshold must be >= 0")


@dataclass(frozen=True)
class TickResult:
    turn: int
    fired: Tuple[str, ...]
    slow_skipped_inertia: bool
    slow_delta: float
    events: List[Dict[str, Any]] = field(default_factory=list)

    def fired_set(self) -> set[str]:
        return set(self.fired)


class PILScheduler:
    """Multi-rate clocks with inertia and the sparsify rule."""

    def __init__(self, config: SchedulerConfig | None = None) -> None:
        self.config = config or SchedulerConfig()
        self.turn = 0
        self.stable_turns = 0
        self.fast_updates = 0
        self.medium_updates = 0
        self.slow_updates = 0
        self.slow_skips = 0
        self.eligibility: Dict[str, float] = {}
        self._windows: Dict[str, Deque[Tuple[float, float]]] = {}
        self.events: List[Dict[str, Any]] = []

    # Clocks

    def tick(
        self,
        teach: PILTeachVector | None = None,
        *,
        stable: bool = True,
        checkpoint: bool = False,
        slow_delta: Optional[float] = None,
    ) -> TickResult:
        """Advance one turn and report which clocks ran.

        FAST runs every turn. MEDIUM runs when the count of stable turns
        reaches a multiple of ``medium_every_stable_turns``; an unstable turn
        does not add to that count and does not reset it. SLOW is scheduled on
        a checkpoint or when ``|slow_delta|`` exceeds ``slow_delta_threshold``,
        then the inertia threshold applies: a scheduled SLOW update whose
        ``|slow_delta|`` is below ``inertia_epsilon`` is skipped and recorded.

        ``slow_delta`` defaults to the teach vector's ``drift_delta`` when a
        vector is given, else zero.
        """

        cfg = self.config
        self.turn += 1
        fired: List[str] = [FAST]
        self.fast_updates += 1
        events: List[Dict[str, Any]] = []

        if stable:
            self.stable_turns += 1
            if self.stable_turns % cfg.medium_every_stable_turns == 0:
                fired.append(MEDIUM)
                self.medium_updates += 1

        if slow_delta is None:
            slow_delta = float(teach.drift_delta) if teach is not None else 0.0
        delta = float(slow_delta)
        magnitude = abs(delta)
        slow_scheduled = bool(checkpoint) or magnitude > cfg.slow_delta_threshold
        skipped = False
        if slow_scheduled:
            if magnitude < cfg.inertia_epsilon:
                skipped = True
                self.slow_skips += 1
                events.append(
                    {
                        "event": "slow_skipped_inertia",
                        "turn": self.turn,
                        "slow_delta": delta,
                        "epsilon": cfg.inertia_epsilon,
                        "checkpoint": bool(checkpoint),
                    }
                )
            else:
                fired.append(SLOW)
                self.slow_updates += 1

        if teach is not None:
            events.extend(self._record_suggestions(teach))

        self.events.extend(events)
        return TickResult(
            turn=self.turn,
            fired=tuple(fired),
            slow_skipped_inertia=skipped,
            slow_delta=delta,
            events=events,
        )

    def _record_suggestions(self, teach: PILTeachVector) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for route in teach.sparsify_suggestion:
            out.append({"event": "sparsify_suggested", "turn": self.turn, "route": str(route)})
        return out

    # Sparsify rule

    def observe_route(self, route: str, activity: float, improvement: float) -> List[Dict[str, Any]]:
        """Record one turn of a route's activity and improvement, then apply
        the sparsify rule if the window is full.

        Over window W, if mean activity > threshold and mean improvement <
        floor, multiply the route's eligibility by ``(1 - decay)`` and emit a
        sparsify event. The window is cleared after a fire so one stretch of
        evidence is counted once; the route must earn another full window
        before it can be sparsified again.
        """

        cfg = self.config
        key = str(route)
        self.eligibility.setdefault(key, 1.0)
        window = self._windows.setdefault(key, deque(maxlen=cfg.sparsify_window))
        window.append((float(activity), float(improvement)))
        if len(window) < cfg.sparsify_window:
            return []
        mean_activity = sum(a for a, _ in window) / len(window)
        mean_improvement = sum(i for _, i in window) / len(window)
        if not (
            mean_activity > cfg.sparsify_activity_threshold
            and mean_improvement < cfg.sparsify_improvement_floor
        ):
            return []
        before = self.eligibility[key]
        after = before * (1.0 - cfg.sparsify_decay)
        self.eligibility[key] = after
        window.clear()
        event = {
            "event": "sparsify",
            "turn": self.turn,
            "route": key,
            "window": cfg.sparsify_window,
            "activity": mean_activity,
            "improvement": mean_improvement,
            "decay": cfg.sparsify_decay,
            "eligibility_before": before,
            "eligibility_after": after,
        }
        self.events.append(event)
        return [event]

    # Reporting

    def snapshot(self) -> Dict[str, Any]:
        return {
            "schema_version": "pil-scheduler-1",
            "turn": self.turn,
            "stable_turns": self.stable_turns,
            "updates": {
                FAST: self.fast_updates,
                MEDIUM: self.medium_updates,
                SLOW: self.slow_updates,
            },
            "slow_skips_inertia": self.slow_skips,
            "eligibility": {k: float(v) for k, v in sorted(self.eligibility.items())},
            "sparsify_events": sum(1 for e in self.events if e.get("event") == "sparsify"),
            "config": {
                "medium_every_stable_turns": self.config.medium_every_stable_turns,
                "slow_delta_threshold": self.config.slow_delta_threshold,
                "inertia_epsilon": self.config.inertia_epsilon,
                "sparsify_window": self.config.sparsify_window,
                "sparsify_activity_threshold": self.config.sparsify_activity_threshold,
                "sparsify_improvement_floor": self.config.sparsify_improvement_floor,
                "sparsify_decay": self.config.sparsify_decay,
            },
        }
