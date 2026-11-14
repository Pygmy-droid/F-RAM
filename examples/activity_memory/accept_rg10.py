"""Replay RG-10 with a live observer attached to its original record hook."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory

from fram_serving.activity_memory import ActivityMemory


def accept(module_path: Path, root: Path) -> dict[str, int]:
    spec = importlib.util.spec_from_file_location("rg10_acceptance", module_path)
    if spec is None or spec.loader is None:
        raise ValueError("expected the external RG-10 rg10.py")
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    memory = ActivityMemory(root)
    digest = hashlib.sha256(module_path.read_bytes()).hexdigest()
    expected = 0
    for word in fixture.WORDS:
        for phase, channel in ((-1, "nominal"), (0, "primary"), (0, "monitor")):
            run_id = f"{''.join(map(str, word))}-{channel}"
            intervention = {} if phase < 0 else {(phase, channel): 1}
            recorder = memory.start(
                run_id,
                {
                    "fixture_sha256": digest,
                    "role_seed": 10101,
                    "routes": word,
                    "intervention": channel,
                },
            )
            original = fixture.Network.record

            def observed(self, tick, op, source, destination, value, parents):
                ordinal = original(self, tick, op, source, destination, value, parents)
                recorder.observe(
                    ordinal=ordinal,
                    logical_time=self.phase * 4 + tick,
                    kind=op,
                    source=source,
                    destination=destination,
                    payload=str(value).encode("ascii"),
                    observed_parents=sorted(parents),
                )
                return ordinal

            fixture.Network.record = observed
            try:
                raw = fixture.execute(10101, word, intervention)
            finally:
                fixture.Network.record = original
            fixture.audit(raw, word, intervention)
            names = dict(zip(raw["role_ids"], fixture.ROLES))
            captured = memory.events(run_id)
            restored = [
                [
                    row["ordinal"],
                    phase_index,
                    row["logical_time"] - phase_index * 4,
                    row["kind"],
                    row["source"],
                    row["destination"],
                    int(bytes.fromhex(row["payload_hex"])),
                    row["observed_parents"],
                ]
                for row, (_, phase_index, *_rest) in zip(
                    captured, raw["events"], strict=True
                )
            ]
            original_events = [
                [i, p, t, op, names[src], names[dst], val, sorted(parents)]
                for i, p, t, op, src, dst, val, parents in raw["events"]
            ]
            if restored != original_events:
                raise ValueError("RG-10 capture differs from runtime observations")
            expected += len(raw["events"])
    result = memory.verify()
    if result["events"] != expected:
        raise ValueError("event count differs")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("rg10_module", type=Path)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="fram-rg10-") as directory:
        print(accept(args.rg10_module, Path(directory)))
