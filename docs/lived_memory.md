# Durable Lived Memory

F-RAM's lived-memory path is executable storage, not a Markdown transcript.
Each completed query can become a durable event containing its actual query,
answer, citations, source identifiers, metadata, and full embedding. Events are
stored transactionally in `storage/memory/lived/lived_memory.sqlite3` and are
available again after a process restart.

## Event and continuity model

`fram_serving.lived_memory.LivedMemoryStore` maintains one ordered lineage per
session. Every event records its session sequence and parent event. A
`BEGIN IMMEDIATE` SQLite transaction atomically appends the event and advances
the session head, so concurrent writers cannot silently fork a local lineage.
SQLite runs in WAL mode with full synchronous writes and a configurable busy
timeout. First-open WAL and schema initialization is serialized so concurrent
cold writers do not race while changing journal mode.

Each event also participates in a SHA-256 chain. The event digest covers the
text and identifiers plus hashes of the embedding, projections, rolling state,
and fractal path. The next event carries the previous state digest. `verify()`
recomputes the chain, validates vector/path shapes, and compares every observed
session head with the persisted session state.

## Fractal projection and lived state

For an embedding `e_n`, the existing deterministic `FractalGenerator` produces
a shared six-dimensional projection `p_n`. The existing exact recursive-lift
operator maps that carrier into `D` dimensions (12 by default), yielding
`h_n`. The same event seed produces a 64-node six-dimensional fractal path,
which is also lifted exactly into `D` dimensions and stored with its lift
capsules and generator provenance.

Each session carries a rolling lived state:

```text
s_1 = h_1
s_n = decay * s_(n-1) + (1 - decay) * h_n
```

The shipped decay is `0.82`. Recall combines full-embedding similarity (70%),
event projection similarity (20%), and lived-state similarity (10%). If stored
and query embedding dimensions differ, recall falls back to projection (75%)
plus lived state (25%). The projection is a derived memory view; it is not
evidence of identity, consciousness, authorship, or authority.

## Runtime behavior

Lived memory is enabled by default. `/query` recalls the most relevant events
as `lmem:event:<event_id>` cognitive candidates and appends the finalized
query/answer only when the existing cognitive persistence gate authorizes a
write. A lived-memory failure is reported in the query trace and does not
erase the primary answer.

Mixed cognitive ranking uses the lived event's existing combined cosine
similarity (`_score_raw`). Lived search/API results retain their normalized
`_score = 0.5 * (_score_raw + 1)` and within-lived ordering. Removing that
lived-only offset at the merge boundary does not change similarity blends,
recency rules, candidate eligibility, or stored events; it supplies a common
zero point, not a probability calibration across memory sources.
Strict unequal lived similarities retain their relative mixed-ranking order.
Equal-score ties use the same corrected score-per-token rule as other candidates,
so their mixed-ranking order can change; search/API ordering remains unchanged.

Read and integrity surfaces:

- `GET /memory/lived/status`
- `GET /memory/lived/verify`
- `GET /memory/lived/search?query=...&k=4`
- `GET /memory/lived/session/{session_id}`

The operator CLI mirrors those surfaces:

```powershell
python tools/lived_memory.py --root storage/memory/lived status
python tools/lived_memory.py --root storage/memory/lived verify
python tools/lived_memory.py --root storage/memory/lived search "What is in memory?"
python tools/lived_memory.py --root storage/memory/lived session default
```

Configuration:

- `FRAM_LIVED_MEMORY_ENABLED` (default `1`)
- `FRAM_LIVED_MEMORY_TARGET_DIM` (default `12`)
- `FRAM_LIVED_MEMORY_FRACTAL_NODES` (default `64`)
- `FRAM_LIVED_MEMORY_RECALL_K` (default `4`)
- `FRAM_LIVED_MEMORY_SCAN_LIMIT` (default `5000`)
- `FRAM_LIVED_MEMORY_STATE_DECAY` (default `0.82`)
- `FRAM_LIVED_MEMORY_BUSY_TIMEOUT_SECONDS` (default `5.0`)

Changing projection dimension or fractal-node count requires a new store or an
explicit migration; the store refuses a silent schema mismatch.

## Backup ZIP import

`tools/import_lived_memory_zip.py` converts the cognitive episodes in a full
F-RAM backup directly into the SQLite store. It preserves stored embeddings
when present. If a historical episode lacks a vector, the importer creates a
deterministic hashing vector from the original query and answer and labels its
provenance `derived_during_import`; it never presents a reconstructed vector as
an original. Deterministic event IDs make repeat imports idempotent.

The default `--lineage-mode separate` gives every source episode its own root
session. This prevents a backup lacking session/parent evidence from acquiring
one inferred rolling state merely because its records shared an archive. The
seeds remain globally searchable and can be resumed explicitly. A seed is a
provenance-preserving memory root, not an identity claim. Operators can request
`--lineage-mode single` only when they intentionally want one chronological
archive lineage and accept that it is an import construction.

```powershell
python tools/import_lived_memory_zip.py `
  --zip C:\path\to\FRAM_backup.zip `
  --output storage\memory\lived `
  --session backup-session `
  --lineage-mode separate `
  --report import-report.json
```

The report records the source ZIP hash and Git head, stored-versus-derived
embedding counts, failures, and a complete post-import verification result.

## Opening a legacy mixed import

`tools/open_lived_memory_seeds.py` transforms a legacy store without modifying
it. Imported events that retain a source ZIP hash and source episode ID become
independent `seed:<zip-hash-prefix>:<episode-id>` roots. Non-imported live
sessions pass through with their existing session IDs and ordering.

```powershell
python tools/open_lived_memory_seeds.py `
  --source storage\memory\lived\snapshots\legacy.sqlite3 `
  --output storage\memory\opened `
  --report opened-seeds-report.json
```

The command refuses to overwrite its destination, opens the source in immutable
read-only mode, hashes it before and after access, records any SQLite sidecar
creation or cleanup, checks that every opened seed has sequence 1 and no parent,
and runs full digest-chain verification on the destination. It refuses a source
with a non-empty WAL so uncheckpointed events cannot be silently omitted.
