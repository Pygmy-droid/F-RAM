# Activity Memory v0.1

Activity Memory records events emitted by a computational process while it runs. It joins execution identity and source provenance to lossless event bytes, logical ordering, and explicitly observed dependencies. A separate version history stores host-validated interpretations. The API is local and opt-in. It sits beside the lived-event store and its generated geometry, with no FastAPI, MCP, retrieval-ranking, or live-deployment hook.

## Start a run and record activity

```python
from fram_serving.activity_memory import ActivityMemory

memory = ActivityMemory("/path/to/scratch-storage")
run = memory.start("run-001", {"instrument": "my-runtime/v1", "clock": "logical"})
message = run.observe(
    ordinal=0, logical_time=0, kind="send",
    source="driver", destination="worker", payload=b"\x00\xff",
)
result = run.observe(
    ordinal=1, logical_time=1, kind="commit",
    source="worker", destination="worker", payload=b"\x03",
    observed_parents=[message.ordinal],
    unresolved_links=["upstream timing signal"],
)
assert memory.neighbors("run-001", result.ordinal)[0]["digest"] == message.digest
assert bytes.fromhex(memory.events("run-001")[0]["payload_hex"]) == b"\x00\xff"
```

The store uses `memory/activity/activity.sqlite3` beneath the explicitly supplied F-RAM storage root. SQLite serializes writers. Identical start and event retries are idempotent; conflicting retries, ordinal gaps, backward logical time, and non-prior dependencies are rejected. Multiple events can share a tick. Assign contiguous ordinals within each run at the instrumentation boundary, then submit in ordinal order. Parent ordinals address events in that run. Page a trace or one-hop neighbors with `after` and `limit`. Traverse parents or children by repeated one-hop reads. A source/destination pair records a reported runtime event. A parent edge records a dependency the instrument observed. Unresolved links are retained as explicit descriptions and have no traversable edge.

## Validate, publish and reuse

Call `publish(relation, claims, evidence_refs, validator, expected_version=0)` with a fixed mapping of query keys to JSON results and exact evidence references. The callback receives the proposed mapping and bound evidence with execution provenance. The host supplies the independent verifier and its policy. If the verifier accepts, the store records its identifier and detail, evidence references, claims, and version digest. Refusal or an invalid evidence reference appends nothing. A later publication must name the current version to avoid lost updates. It supersedes the full previous mapping.

`inference(relation, key, as_of=...)` reads the published mapping without reopening its evidence. Missing mappings and keys return a typed abstention. “Verified” means accepted by the recorded trusted validator for that query scope. Call `rollback(relation, expected_version=..., restore=...)` to append a restoration to an earlier checkpoint. Version 0 is the empty checkpoint. The log and original evidence remain addressable. `verify()` audits the event and interpretation hash chains, indexed dependency edges, evidence references, and version replay.

## Reproduce the lifecycle

```sh
python -m examples.activity_memory.demo
python -m pytest -q tests/test_activity_memory.py
python -m examples.activity_memory.accept_rg10 /path/to/RG-10-Trace-the-Thought/rg10.py
```

The first command uses a disposable database. Pass a fresh `--root` to retain it. It records RG-10-style direct/relay histories with the same nominal endpoint and a new concurrent dual-lane execution that also ends at 4. The partial publication cannot answer the dual-lane query. After signed intervention validation and supersession, the predicted joint perturbation is +3, and independent single-lane and simultaneous paired executions measure +3. Removing the routing observation makes the demo abstain. Rollback restores the earlier coverage. The optional acceptance command loads the original external RG-10 fixture as Python code and attaches an observer at its live record hook. Provide a trusted local fixture file. It compares captured fields and parent links to the independently audited source tape. No RG-10 files are shipped or changed.

## Observation and trust boundary

The synthetic instrument observes enqueued messages, integer unit commits, dependencies to observed sends, logical ticks, and readout. For the external fixture it additionally records the reset event. A known input and test conditions appear in declared provenance. The demo infers a response to a specific perturbation only after checking actual matched interventions. Its arithmetic and validator apply to the example runtime. The store has no general causal engine and accepts no inference solely from graph proximity.

Payload bytes are exact; provenance round-trips as canonical JSON data. Files are append-only through this API, with SQLite triggers guarding updates and deletes. Digests are integrity checks, not signatures or externally anchored receipts. A filesystem administrator capable of replacing the database can also replace its digests. Recorder completeness and whether a supplied edge is truly observed depend on instrumentation. There is no observation of omitted instructions, opaque model internals, wall-clock hardware activity, human experience or subjective states. v0.1 uses synchronous per-event transactions and a bounded retrieval API. Batching, retention policy, and network interfaces are future work.
