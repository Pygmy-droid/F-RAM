"""PIL first slice (WB-0008): teach vector, clocks, inertia, sparsify, flag.

Reconstruction tests from note 35 via docs/manual/08_reconstruction_kit.md.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from fram_serving import pil
from fram_serving.config import FRAMConfig
from fram_serving.pil_scheduler import FAST, MEDIUM, SLOW, PILScheduler, SchedulerConfig

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "experiments" / "pil_harness.py"


def _trace(route: str = "anchors", p: float = 0.62, writes_ok: bool = True) -> dict:
    return {
        "confidence": {"decision": route},
        "p_temp": p,
        "coverage": {"delta_by_stage": {"memory": 0.1, "seed": 0.3, "anchors": 0.05, "shards": 0.0}},
        "transitional_complexity": {"tc": 0.2},
        "cognitive_episode_write": {"ok": writes_ok},
        "lived_memory_write": {"ok": writes_ok},
        "selection": {"budgets": {"reads": 5}},
    }


class _Cfg:
    def __init__(self, enabled: bool, observe_only: bool = True) -> None:
        self.pil_enabled = enabled
        self.pil_observe_only = observe_only


# Teach vector


def test_teach_vector_is_deterministic_and_signed() -> None:
    a = pil.teach_vector(
        {"memory": 0.1, "seed": 0.3},
        {"anchors": 0.62},
        expected_anchor_gain={"memory": 0.15, "seed": 0.1},
        expected_route_stability={"anchors": 0.7},
        observed_write=2,
        expected_write=1.5,
        observed_drift=0.2,
        expected_drift=0.25,
        route="anchors",
    )
    b = pil.teach_vector(
        {"memory": 0.1, "seed": 0.3},
        {"anchors": 0.62},
        expected_anchor_gain={"memory": 0.15, "seed": 0.1},
        expected_route_stability={"anchors": 0.7},
        observed_write=2,
        expected_write=1.5,
        observed_drift=0.2,
        expected_drift=0.25,
        route="anchors",
    )
    assert a == b and a.to_dict() == b.to_dict()
    assert a.anchor_scores["memory"] == pytest.approx(-0.05)
    assert a.anchor_scores["seed"] == pytest.approx(0.2)
    assert a.anchor_scores["anchors"] == 0.0 and a.anchor_scores["shards"] == 0.0
    assert a.route_scores["anchors"] == pytest.approx(-0.08)
    assert a.route_scores["local"] == 0.0
    assert a.write_delta == pytest.approx(0.5)
    assert a.drift_delta == pytest.approx(-0.05)
    assert a.sparsify_suggestion == []
    assert json.dumps(a.to_dict(), sort_keys=True) == json.dumps(b.to_dict(), sort_keys=True)


def test_teach_from_trace_reads_only_observed_values() -> None:
    trace = _trace()
    before = json.dumps(trace, sort_keys=True)
    teach = pil.teach_from_trace(trace)
    assert json.dumps(trace, sort_keys=True) == before  # no mutation
    assert teach.route == "anchors"
    assert teach.route_scores == {"anchors": 0.62, "global": 0.0, "local": 0.0}
    assert teach.anchor_scores["seed"] == pytest.approx(0.3)
    assert teach.write_delta == 2.0
    assert teach.drift_delta == pytest.approx(0.2)
    with_prior = pil.teach_from_trace(trace, {"write": 2.0, "drift": 0.3, "route_stability": {"anchors": 0.6}})
    assert with_prior.write_delta == 0.0
    assert with_prior.drift_delta == pytest.approx(-0.1)
    assert with_prior.route_scores["anchors"] == pytest.approx(0.02)


def test_constraint_refusal_trace_teaches_nothing() -> None:
    teach = pil.teach_from_trace({"confidence": {"decision": "constraint_refusal"}, "coverage": {}})
    assert teach.route == "constraint_refusal"
    assert all(v == 0.0 for v in teach.anchor_scores.values())
    assert all(v == 0.0 for v in teach.route_scores.values())
    assert teach.write_delta == 0.0 and teach.drift_delta == 0.0


def test_sparsify_suggestion_predicate() -> None:
    activity = {"anchors": 0.9, "local": 0.9, "global": 0.3}
    improvement = {"anchors": 0.0, "local": 0.05, "global": 0.0}
    assert pil.sparsify_suggestion(activity, improvement) == ["anchors"]
    assert pil.sparsify_suggestion({"anchors": 0.6}, {"anchors": 0.0}) == []  # threshold is strict
    assert pil.sparsify_suggestion({"anchors": 0.9}, {"anchors": 0.02}) == []  # floor is strict


# Flag


def test_flag_off_attaches_nothing() -> None:
    trace = _trace()
    before = json.dumps(trace, sort_keys=True)
    assert pil.attach_teach_to_trace(trace, _Cfg(enabled=False)) is None
    assert "pil_teach" not in trace
    assert json.dumps(trace, sort_keys=True) == before
    assert pil.attach_teach_to_trace("not a dict", _Cfg(enabled=True)) is None


def test_flag_on_attaches_only_pil_teach() -> None:
    trace = _trace()
    keys_before = set(trace)
    block = pil.attach_teach_to_trace(trace, _Cfg(enabled=True))
    assert block is not None and trace["pil_teach"] is block
    assert set(trace) == keys_before | {"pil_teach"}
    assert block["observe_only"] is True
    assert block["schema_version"] == "pil-teach-1"
    assert set(block) == {
        "schema_version",
        "observe_only",
        "route",
        "anchor_scores",
        "route_scores",
        "write_delta",
        "drift_delta",
        "sparsify_suggestion",
    }
    # Everything the block carries is numeric or a structural key; no text.
    assert all(isinstance(v, float) for v in block["anchor_scores"].values())
    assert all(isinstance(v, float) for v in block["route_scores"].values())


def test_config_flag_defaults_off_and_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FRAM_PIL_ENABLED", raising=False)
    monkeypatch.delenv("FRAM_PIL_OBSERVE_ONLY", raising=False)
    cfg = FRAMConfig()
    assert cfg.pil_enabled is False and cfg.pil_observe_only is True
    assert FRAMConfig.from_env().pil_enabled is False
    monkeypatch.setenv("FRAM_PIL_ENABLED", "1")
    assert FRAMConfig.from_env().pil_enabled is True
    assert FRAMConfig.from_env().pil_observe_only is True


# Clocks and inertia


def test_clock_cadence_fast_every_turn_medium_every_ten_stable() -> None:
    sched = PILScheduler()
    fired = [sched.tick(stable=True).fired_set() for _ in range(9)]
    assert all(f == {FAST} for f in fired)
    assert sched.tick(stable=True).fired_set() == {FAST, MEDIUM}  # stable turn 10
    # An unstable turn runs FAST only and does not count toward MEDIUM.
    assert sched.tick(stable=False).fired_set() == {FAST}
    for _ in range(9):
        assert MEDIUM not in sched.tick(stable=True).fired_set()
    assert MEDIUM in sched.tick(stable=True).fired_set()  # stable turn 20
    assert sched.snapshot()["updates"] == {FAST: 21, MEDIUM: 2, SLOW: 0}


def test_slow_runs_on_checkpoint_or_large_delta_only() -> None:
    sched = PILScheduler()
    assert SLOW not in sched.tick(slow_delta=0.04).fired_set()
    assert SLOW not in sched.tick(slow_delta=0.05).fired_set()  # strictly greater
    assert SLOW in sched.tick(slow_delta=0.051).fired_set()
    assert SLOW in sched.tick(slow_delta=-0.2).fired_set()
    assert SLOW in sched.tick(checkpoint=True, slow_delta=0.03).fired_set()
    assert sched.slow_updates == 3


def test_inertia_skips_slow_update_below_epsilon() -> None:
    sched = PILScheduler(SchedulerConfig(inertia_epsilon=0.01))
    result = sched.tick(checkpoint=True, slow_delta=0.001)
    assert SLOW not in result.fired_set()
    assert result.slow_skipped_inertia is True
    assert sched.slow_skips == 1 and sched.slow_updates == 0
    assert result.events and result.events[0]["event"] == "slow_skipped_inertia"
    # Without a checkpoint and below threshold nothing is scheduled, so nothing is skipped.
    quiet = sched.tick(slow_delta=0.001)
    assert quiet.slow_skipped_inertia is False and sched.slow_skips == 1


def test_slow_delta_defaults_to_teach_drift_delta() -> None:
    sched = PILScheduler()
    teach = pil.teach_vector({}, {}, observed_drift=0.3)
    assert SLOW in sched.tick(teach).fired_set()
    quiet = pil.teach_vector({}, {}, observed_drift=0.0)
    assert SLOW not in sched.tick(quiet).fired_set()


# Sparsify rule


def test_sparsify_fires_after_full_window_and_decays_eligibility() -> None:
    sched = PILScheduler()
    events = []
    for _ in range(9):
        assert sched.observe_route("anchors", 0.9, 0.0) == []
    events = sched.observe_route("anchors", 0.9, 0.0)
    assert len(events) == 1 and events[0]["event"] == "sparsify"
    assert events[0]["eligibility_before"] == 1.0
    assert sched.eligibility["anchors"] == pytest.approx(0.75)
    # The window was cleared: nine more turns do not fire, the tenth does.
    for _ in range(9):
        assert sched.observe_route("anchors", 0.9, 0.0) == []
    assert sched.observe_route("anchors", 0.9, 0.0)
    assert sched.eligibility["anchors"] == pytest.approx(0.75 * 0.75)
    assert sched.snapshot()["sparsify_events"] == 2


def test_sparsify_does_not_fire_when_route_earns_or_is_quiet() -> None:
    sched = PILScheduler()
    for _ in range(20):
        assert sched.observe_route("local", 0.9, 0.05) == []  # active and improving
        assert sched.observe_route("global", 0.3, 0.0) == []  # idle and useless
    assert sched.eligibility == {"local": 1.0, "global": 1.0}
    assert sched.snapshot()["sparsify_events"] == 0


def test_sparsify_decay_stays_within_bounds() -> None:
    SchedulerConfig(sparsify_decay=0.1)
    SchedulerConfig(sparsify_decay=0.3)
    with pytest.raises(ValueError):
        SchedulerConfig(sparsify_decay=0.5)
    with pytest.raises(ValueError):
        SchedulerConfig(sparsify_decay=0.05)


# Harness


def _load_harness():
    spec = importlib.util.spec_from_file_location("pil_harness_module", HARNESS)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_harness_is_deterministic_and_writes_only_where_told(tmp_path: Path, capsys) -> None:
    harness = _load_harness()
    out_a = tmp_path / "a" / "pil.json"
    out_b = tmp_path / "b" / "pil.json"
    assert harness.main(["--turns", "60", "--seed", "7", "--json", str(out_a)]) == 0
    assert harness.main(["--turns", "60", "--seed", "7", "--json", str(out_b)]) == 0
    assert out_a.read_text(encoding="utf-8") == out_b.read_text(encoding="utf-8")
    report = json.loads(out_a.read_text(encoding="utf-8"))
    assert set(report["populations"]) == {"earning", "busy"}
    busy = report["populations"]["busy"]
    assert busy["sparsify_events"], "the busy population should trip the sparsify rule"
    assert all(e["route"] == "anchors" for e in busy["sparsify_events"])
    assert report["populations"]["earning"]["sparsify_events"] == []
    assert busy["scheduler"]["updates"]["fast"] == 60
    stdout = capsys.readouterr().out
    assert "[busy]" in stdout and "sparsify events" in stdout
    assert not list((tmp_path / "a").glob("storage")), "harness must not create storage/"


def test_harness_refuses_paths_under_storage(tmp_path: Path) -> None:
    harness = _load_harness()
    with pytest.raises(ValueError):
        harness.refuse_storage_path(harness.STORAGE_ROOT / "observability" / "pil.json")
    assert harness.refuse_storage_path(tmp_path / "ok.json") == (tmp_path / "ok.json").resolve()
