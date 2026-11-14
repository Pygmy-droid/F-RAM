"""Instrumented recurrent activity and a supervised interpretation lifecycle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from fram_serving.activity_memory import ActivityMemory, EvidenceRef, Validation


def execute(
    memory: ActivityMemory,
    name: str,
    routes: tuple[str, ...],
    injections: tuple[tuple[int, str, int], ...] = (),
) -> tuple[int, EvidenceRef]:
    """RG-10's direct/relay/monitor recurrence, plus concurrent dual lanes."""
    recorder = memory.start(
        name,
        {
            "runtime": "activity-demo/v1",
            "routes": routes,
            "injections": injections,
            "input": [2] * len(routes),
        },
    )
    ordinal = 0
    inbox: dict[str, list[tuple[int, int]]] = {}
    accumulator = 0

    def observe(tick, kind, source, target, value, parents=()):
        nonlocal ordinal
        ref = recorder.observe(
            ordinal=ordinal,
            logical_time=tick,
            kind=kind,
            source=source,
            destination=target,
            payload=str(value).encode("ascii"),
            observed_parents=sorted(parents),
        )
        ordinal += 1
        return ref.ordinal

    def send(tick, source, target, value, parents=()):
        event = observe(tick, "send", source, target, value, parents)
        inbox.setdefault(target, []).append((event, value))

    def commit(tick, unit, gain=1):
        received = inbox.pop(unit)
        value = gain * sum(value for _, value in received)
        event = observe(tick, "commit", unit, unit, value, [p for p, _ in received])
        return event, value

    carry = ()
    for phase, route in enumerate(routes):
        tick = phase * 4

        def adjusted(branch, value):
            return value + sum(
                delta
                for index, lane, delta in injections
                if (index, lane) == (phase, branch)
            )

        if route in ("direct", "dual"):
            send(
                tick,
                "driver",
                "direct",
                adjusted("direct", 2 if route == "direct" else 0),
            )
        if route in ("relay", "dual"):
            send(tick, "driver", "relay", adjusted("relay", 1))
        send(tick, "driver", "monitor", adjusted("monitor", 7))
        send(tick, "acc", "acc", accumulator, carry)
        if route in ("direct", "dual"):
            event, value = commit(tick + 1, "direct")
            send(tick + 1, "direct", "acc", value, (event,))
        if route in ("relay", "dual"):
            event, value = commit(tick + 1, "relay")
            send(tick + 1, "relay", "gain", value, (event,))
        commit(tick + 1, "monitor")
        if route in ("relay", "dual"):
            event, value = commit(tick + 2, "gain", gain=2)
            send(tick + 2, "gain", "acc", value, (event,))
        event, accumulator = commit(tick + 3, "acc")
        carry = (event,)
    ref = recorder.observe(
        ordinal=ordinal,
        logical_time=len(routes) * 4,
        kind="readout",
        source="acc",
        destination="output",
        payload=str(accumulator).encode("ascii"),
        observed_parents=carry,
    )
    return accumulator, ref


def verify_gains(claims, records):
    """Independent oracle for complete matched single-phase interventions."""
    outputs = {}
    duplicate = False
    for row in records:
        provenance = row["provenance"]
        routes = provenance.get("routes", [])
        injections = provenance.get("injections", [])
        if (
            provenance.get("runtime") != "activity-demo/v1"
            or provenance.get("input") != [2]
            or len(routes) != 1
            or len(injections) > 1
            or row["kind"] != "readout"
            or row["source"] != "acc"
            or row["destination"] != "output"
            or len(row["observed_parents"]) != 1
        ):
            return Validation(
                "demo-affine-oracle/v1", False, "wrong calibration evidence"
            )
        key = routes[0], tuple(injections[0]) if len(injections) == 1 else None
        duplicate |= key in outputs
        outputs[key] = int(bytes.fromhex(row["payload_hex"]))
    expected_gains = {"direct": 1, "relay": 2, "monitor": 0}
    required = {}
    for branch in claims:
        if branch not in expected_gains:
            return Validation("demo-affine-oracle/v1", False, "unknown branch")
        route = "direct" if branch == "monitor" else branch
        required[route, None] = 2
        for change in (-1, 1):
            required[route, (0, branch, change)] = 2 + change * expected_gains[branch]
    accepted = (
        not duplicate
        and outputs == required
        and all(
            type(value) is int and expected_gains[key] == value
            for key, value in claims.items()
        )
    )
    return Validation(
        "demo-affine-oracle/v1",
        accepted,
        "Matched signed interventions and independently specified gains.",
    )


def _learn(memory: ActivityMemory, branches: tuple[str, ...]) -> tuple[dict, list]:
    claims, refs = {}, {}
    for branch in branches:
        route = "direct" if branch == "monitor" else branch
        nominal, ref = execute(memory, f"cal-{route}", (route,))
        refs[ref.execution] = ref
        observed = []
        for change in (-1, 1):
            value, ref = execute(
                memory, f"cal-{branch}-{change}", (route,), ((0, branch, change),)
            )
            refs[ref.execution] = ref
            observed.append(value - nominal)
        if observed[0] != -observed[1]:
            raise ValueError("response is not symmetric around the nominal outcome")
        claims[branch] = observed[1]
    return claims, list(refs.values())


def diagnose(
    memory: ActivityMemory, execution: str, *, include_first_tick: bool = True
) -> dict:
    events = memory.events(execution, from_time=0 if include_first_tick else 1)
    active = sorted(
        row["destination"]
        for row in events
        if row["logical_time"] == 0
        and row["kind"] == "send"
        and row["source"] == "driver"
        and row["destination"] != "monitor"
    )
    if not active:
        return {"status": "abstain", "reason": "routing observation unavailable"}
    estimates = {lane: memory.inference("first-send-gain", lane) for lane in active}
    if any(item.status != "verified" for item in estimates.values()):
        return {"status": "abstain", "lanes": active}
    return {
        "status": "verified",
        "lanes": active,
        "delta_for_unit_increase_on_each_lane": sum(
            item.value for item in estimates.values()
        ),
    }


def demo(root: Path) -> dict:
    memory = ActivityMemory(root)
    direct, _ = execute(memory, "nominal-direct", ("direct", "relay"))
    relay, _ = execute(memory, "nominal-relay", ("relay", "direct"))
    dual, ref = execute(memory, "nominal-dual", ("dual", "direct"))
    # Compose two individual new-scenario reruns and test their combined effect
    # with a genuinely simultaneous first-tick injection.
    only_direct, _ = execute(
        memory, "dual-injected-direct", ("dual", "direct"), ((0, "direct", 1),)
    )
    only_relay, _ = execute(
        memory, "dual-injected-relay", ("dual", "direct"), ((0, "relay", 1),)
    )
    combined, _ = execute(
        memory,
        "dual-injected-both",
        ("dual", "direct"),
        ((0, "direct", 1), (0, "relay", 1)),
    )
    original = memory.events("nominal-dual")
    provenance = memory.execution("nominal-dual")
    parents = memory.neighbors("nominal-dual", ref.ordinal)
    before = diagnose(memory, "nominal-dual")
    claims, evidence = _learn(memory, ("direct",))
    first = memory.publish("first-send-gain", claims, evidence, verify_gains)
    limited = diagnose(memory, "nominal-dual")
    claims, evidence = _learn(memory, ("direct", "relay", "monitor"))
    second = memory.publish(
        "first-send-gain", claims, evidence, verify_gains, expected_version=first
    )
    after = diagnose(memory, "nominal-dual")
    absent = diagnose(memory, "nominal-dual", include_first_tick=False)
    restored = memory.rollback(
        "first-send-gain", expected_version=second, restore=first
    )
    reopened = ActivityMemory(root)
    return {
        "colliding_endpoints": [direct, relay, dual],
        "first_tick_routes": {
            run: [
                e["destination"]
                for e in memory.events(run)
                if e["kind"] == "send"
                and e["logical_time"] == 0
                and e["source"] == "driver"
            ]
            for run in ("nominal-direct", "nominal-relay", "nominal-dual")
        },
        "readout_dependencies": [row["ordinal"] for row in parents],
        "before": before,
        "limited": limited,
        "published": after,
        "partial": absent,
        "paired_delta_sum": (only_direct - dual) + (only_relay - dual),
        "observed_joint_delta": combined - dual,
        "rollback": diagnose(reopened, "nominal-dual"),
        "rollback_version": restored,
        "source_exact": (
            original == reopened.events("nominal-dual")
            and provenance == reopened.execution("nominal-dual")
        ),
        "audit": reopened.verify(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, help="explicit scratch storage root")
    args = parser.parse_args()
    if args.root is None:
        with TemporaryDirectory(prefix="fram-activity-") as directory:
            print(json.dumps(demo(Path(directory)), indent=2))
    else:
        print(json.dumps(demo(args.root), indent=2))
