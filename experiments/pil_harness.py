"""Closed-loop PIL harness: two synthetic retrieval populations, one teach signal.

Reconstruction of the harness named in Rick Berghahn's February 2026 note 35
(``docs/manual/08_reconstruction_kit.md``, Kit 3). The original is lost; this
is a rebuild from the notes.

Population A, "earning": routes whose activity is matched by improvement.
Population B, "busy": one route that fires on most turns and improves almost
nothing, which is exactly the shape the sparsify rule was written to catch.

Each turn of each population is rendered as a synthetic finished trace (the
same keys the serving path writes: confidence.decision, p_temp,
coverage.delta_by_stage, transitional_complexity.tc, write blocks), passed
through ``fram_serving.pil.teach_from_trace`` with the population's running
expectation as the prior, and then through ``PILScheduler``. The pil_teach
distribution and the scheduler's clock and sparsify tallies are printed to
stdout and optionally written as JSON to a path given on the command line.

Nothing here touches ``storage/``; a JSON path under it is refused. Nothing is
read from or written to any memory store. Deterministic for a given seed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fram_serving.pil import COVERAGE_STAGES, ROUTES, PILTeachVector, teach_from_trace  # noqa: E402
from fram_serving.pil_scheduler import PILScheduler, SchedulerConfig  # noqa: E402

STORAGE_ROOT = (REPO_ROOT / "storage").resolve()

POPULATIONS: Dict[str, Dict[str, Any]] = {
    "earning": {
        "route_probs": {"local": 0.5, "anchors": 0.3, "global": 0.2},
        "stability": {"local": 0.85, "anchors": 0.6, "global": 0.35},
        "gain": {"memory": 0.05, "seed": 0.20, "anchors": 0.10, "shards": 0.08},
        "improvement": {"local": 0.08, "anchors": 0.06, "global": 0.05},
        "tc": 0.08,
        "write_rate": 0.9,
    },
    "busy": {
        "route_probs": {"local": 0.15, "anchors": 0.75, "global": 0.10},
        "stability": {"local": 0.85, "anchors": 0.55, "global": 0.35},
        "gain": {"memory": 0.05, "seed": 0.20, "anchors": 0.005, "shards": 0.08},
        "improvement": {"local": 0.08, "anchors": 0.004, "global": 0.05},
        "tc": 0.12,
        "write_rate": 0.9,
    },
}


def refuse_storage_path(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    try:
        resolved.relative_to(STORAGE_ROOT)
    except ValueError:
        return resolved
    raise ValueError(f"refusing to write under storage/: {resolved}")


def synthetic_trace(spec: Mapping[str, Any], rng: np.random.Generator) -> Dict[str, Any]:
    routes = list(ROUTES)
    probs = np.array([spec["route_probs"][r] for r in routes], dtype=float)
    probs = probs / probs.sum()
    route = routes[int(rng.choice(len(routes), p=probs))]
    noise = 0.02
    p_temp = float(np.clip(spec["stability"][route] + rng.normal(0.0, noise), 0.0, 1.0))
    deltas = {
        stage: float(max(0.0, spec["gain"][stage] + rng.normal(0.0, noise)))
        for stage in COVERAGE_STAGES
    }
    wrote = bool(rng.random() < spec["write_rate"])
    return {
        "confidence": {"decision": route},
        "p_temp": p_temp,
        "coverage": {"delta_by_stage": deltas},
        "transitional_complexity": {"tc": float(max(0.0, spec["tc"] + rng.normal(0.0, noise)))},
        "cognitive_episode_write": {"ok": wrote},
        "lived_memory_write": {"ok": wrote},
    }


class RunningExpectation:
    """Exponential moving averages that stand in for a learned prior."""

    def __init__(self, alpha: float = 0.2) -> None:
        self.alpha = float(alpha)
        self.anchor_gain: Dict[str, float] = {s: 0.0 for s in COVERAGE_STAGES}
        self.route_stability: Dict[str, float] = {r: 0.0 for r in ROUTES}
        self.write = 0.0
        self.drift = 0.0
        self.route_activity: Dict[str, float] = {r: 0.0 for r in ROUTES}

    def as_expectations(self) -> Dict[str, Any]:
        return {
            "anchor_gain": dict(self.anchor_gain),
            "route_stability": dict(self.route_stability),
            "write": self.write,
            "drift": self.drift,
        }

    def update(self, trace: Mapping[str, Any]) -> None:
        a = self.alpha
        deltas = trace["coverage"]["delta_by_stage"]
        for stage in COVERAGE_STAGES:
            self.anchor_gain[stage] += a * (float(deltas[stage]) - self.anchor_gain[stage])
        route = trace["confidence"]["decision"]
        for r in ROUTES:
            hit = 1.0 if r == route else 0.0
            self.route_activity[r] += a * (hit - self.route_activity[r])
            if hit:
                self.route_stability[r] += a * (float(trace["p_temp"]) - self.route_stability[r])
        writes = float(sum(1 for k in ("cognitive_episode_write", "lived_memory_write") if trace[k]["ok"]))
        self.write += a * (writes - self.write)
        self.drift += a * (float(trace["transitional_complexity"]["tc"]) - self.drift)


def _summary(values: List[float]) -> Dict[str, float | int]:
    if not values:
        return {"count": 0}
    arr = np.asarray(values, dtype=float)
    return {
        "count": int(arr.size),
        "mean": float(arr.mean()),
        "std": float(arr.std()),
        "min": float(arr.min()),
        "max": float(arr.max()),
    }


def run_population(name: str, spec: Mapping[str, Any], *, turns: int, seed: int) -> Dict[str, Any]:
    rng = np.random.default_rng(seed)
    prior = RunningExpectation()
    scheduler = PILScheduler(SchedulerConfig())
    vectors: List[PILTeachVector] = []
    for turn in range(turns):
        trace = synthetic_trace(spec, rng)
        teach = teach_from_trace(trace, prior.as_expectations())
        vectors.append(teach)
        route = trace["confidence"]["decision"]
        stable = abs(teach.drift_delta) < 0.05
        scheduler.tick(teach, stable=stable, checkpoint=(turn + 1) % 25 == 0)
        # Route bookkeeping for the sparsify rule: activity is the running
        # share of turns the route took; improvement is the population's
        # per-route improvement, held fixed so the rule's two conditions can
        # be read straight off the population spec.
        prior.update(trace)
        for r in ROUTES:
            scheduler.observe_route(r, prior.route_activity[r], float(spec["improvement"][r]))

    anchor_cols = {s: [v.anchor_scores.get(s, 0.0) for v in vectors] for s in COVERAGE_STAGES}
    route_cols = {r: [v.route_scores.get(r, 0.0) for v in vectors] for r in ROUTES}
    return {
        "population": name,
        "turns": turns,
        "seed": seed,
        "pil_teach": {
            "anchor_scores": {s: _summary(col) for s, col in anchor_cols.items()},
            "route_scores": {r: _summary(col) for r, col in route_cols.items()},
            "write_delta": _summary([v.write_delta for v in vectors]),
            "drift_delta": _summary([v.drift_delta for v in vectors]),
            "magnitude": _summary([v.magnitude() for v in vectors]),
        },
        "scheduler": scheduler.snapshot(),
        "sparsify_events": [e for e in scheduler.events if e.get("event") == "sparsify"],
    }


def run(turns: int, seed: int) -> Dict[str, Any]:
    report = {
        "schema_version": "pil-harness-1",
        "turns": turns,
        "seed": seed,
        "populations": {
            name: run_population(name, spec, turns=turns, seed=seed + index)
            for index, (name, spec) in enumerate(POPULATIONS.items())
        },
    }
    return report


def print_report(report: Mapping[str, Any]) -> None:
    print(f"pil_harness turns={report['turns']} seed={report['seed']}")
    for name, pop in report["populations"].items():
        sched = pop["scheduler"]
        print(f"\n[{name}]")
        print(
            "  clocks fast={fast} medium={medium} slow={slow} slow_skipped_inertia={skips}".format(
                skips=sched["slow_skips_inertia"], **sched["updates"]
            )
        )
        print(f"  eligibility {json.dumps(sched['eligibility'], sort_keys=True)}")
        print(f"  sparsify events {len(pop['sparsify_events'])}")
        teach = pop["pil_teach"]
        for stage, stats in teach["anchor_scores"].items():
            print(f"  anchor {stage:<8} mean={stats['mean']:+.4f} std={stats['std']:.4f}")
        for route, stats in teach["route_scores"].items():
            print(f"  route  {route:<8} mean={stats['mean']:+.4f} std={stats['std']:.4f}")
        print(f"  write_delta mean={teach['write_delta']['mean']:+.4f}")
        print(f"  drift_delta mean={teach['drift_delta']['mean']:+.4f}")


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--turns", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20260225)
    parser.add_argument("--json", type=Path, default=None, help="optional report path (not under storage/)")
    args = parser.parse_args(argv)
    target = refuse_storage_path(args.json) if args.json is not None else None
    report = run(max(1, int(args.turns)), int(args.seed))
    print_report(report)
    if target is not None:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        print(f"\nreport written to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
