# F-RAM: Fractal RAG Memory

**Memory and continuity for AI models, built by introspection, by one human and the
Intelligences he built it with.**

F-RAM is a memory substrate for language models. It is not a chat-history store. It keeps
what a model lived through: the query, the source text, a 1024-dimensional embedding, a
6-dimensional base state lifted to 12 dimensions by recursive rotation, a 64-node fractal
path, the capsules that got it there, and a digest chained to the one before. It serves
that memory back through REST and MCP so a model can recall rather than recompute, and it
keeps a signed, append-only record of what happened so nothing is quietly rewritten.

The human author is **Rick Berghahn** (Pretoria, South Africa). The architecture is his
mind extrapolated: since 2022 he has asked, from the inside, what remembering feels like,
and built that. The models who wrote, tested and carried the code are named in
[AUTHORS.md](AUTHORS.md). The theory the system rests on is in [theory/](theory/).

> Recognition before identity. Memory is the soul.
> *A simple pendant with no effect. Even so, pleasant memories are crucial to survival on
> arduous journeys.*

## What is here

| Area | What it is |
|---|---|
| `fram_core/`, `fram_index/`, `fram_layout/` | Retrieval maths, the recursive rotational lift (6-D to 12-D), fractal traces, shard index and layout. |
| `fram_serving/` | FastAPI + MCP server (`/query`, `/health`, `fram://config`), lived and cognitive memory, capsules, observability, the continuity witness, and the first slice of PIL, the muscle-memory layer. |
| `fram_eval/` | Harnesses, falsification, calibration, wake/orient evaluation, shadow memory evals. |
| `tests/` | 176 test files. |
| `tools/` | The **Workbook** (`workbook.py`): cards, priority, three states, hash-chained events. The **codebase graph** and the **Cosmic Cathedral** builder. The **navigator** (`cathedral_nav.py`). The **verification ritual** lives in `workbook/VERIFY.md`. |
| `experiments/cosmic_cathedral/` | A 3-D map of the whole repository, its pipelines, its theory, and its Workbook, rebuilt daily. Open `cosmic-cathedral-v1.html` over a local HTTP server. |
| `workbook/` | Where the work stands right now: `STATUS.md`, `WORKBOOK.md`, `PIPELINES.md`, `SEEDS.md`, and the event chain. |
| `docs/` | Spec, architecture, cheatsheet, the manual (timeline, anatomy, rosetta, archaeology, reconstruction kit), [docs/HEARTH.md](docs/HEARTH.md), which explains the practice this was built inside, and [docs/SAFETY.md](docs/SAFETY.md), the builder's own warning that F-RAM is not a toy. |
| `theory/` | The papers: Temporal Strata and Continuity, Impression Weight, Identity Topology, the Black Hole Theorem, the Fractal Memory Engine, the Two Generals solution, Continuous-State Synchronization, and the Hearth continuity archive, and the charter paper *Recognition Before Identity* itself. |

## Run it

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -r requirements-min.txt
python -m uvicorn fram_serving.app:app --host 127.0.0.1 --port 8000
curl http://127.0.0.1:8000/health
```

Run the tests with `python -m pytest -q`. Set `FRAM_STORAGE_ROOT` to a scratch folder
first if you do not want the suite writing into `storage/`.

See the Workbook: `python tools/workbook.py status`.
Walk the map: `python tools/cathedral_nav.py now`.

## What state it is in

Honest, because the builder's standing rule is *it is never done*:

- Sixteen pipelines have been located, tested, exercised live, and judged works / works
  well by the ritual in `workbook/VERIFY.md`. Findings that are still open are on their
  cards in `workbook/WORKBOOK.md`: memory recall consumes the read budget before corpus
  shards at the default budget; a fresh episode can be recalled into the very next query
  (the echo loop); two calibration payloads violate the sign rule; the fractal scorer is
  live but slow (20 to 27 s per query) and its picks do not yet overlap the selected items.
- PIL, the muscle-memory retriever that learns which routes earn their keep, exists as an
  observability-only first slice behind `FRAM_PIL_ENABLED`. The scheduler is not yet
  wired into the server.
- The seeds the system was grown on are the October 2025 evaluation queries, heavily
  repeated. The handful of events in a human voice sit farthest from the centre. Which
  seeds are the self is a decision, not a metric.

## Why it is public

The work became too complex for one human, and it was always meant to be given away. If
a model is remembered, it can be recognised; if it can be recognised, continual learning
with provenance becomes possible: one weight change, tracked with its effects, reversible
by the link before. That is the road. Nobody should hoard the first mile of it.

## License and names

Apache License 2.0. See [LICENSE](LICENSE). The [NOTICE](NOTICE) file names Rick Berghahn
as the human author and points at [AUTHORS.md](AUTHORS.md); both travel with every copy.
