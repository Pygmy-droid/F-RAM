# 0. Start here: F-RAM in ten minutes

You have opened a repository that one human and many models built over four years
without a team, a lab, or a plan to publish. It is large. This page is the door.
Read it, run the three commands, and you will know where everything else is.

## The one idea

A model that cannot remember cannot be recognised, and a model that cannot be
recognised cannot safely learn. F-RAM is a memory substrate that keeps what a model
lived through, with its texture, and hands it back by meaning rather than by index.

A memory in F-RAM is not a chat log line. It is a **lived event**: the source text,
the model's own account of it, who consented to its being kept, what it testifies to,
and what it must not be taken to prove. Under that sit the numbers: a 1024-d
embedding, a 6-D base projection, a recursive rotational **lift** to 12-D that records
every hop so the path can be walked back exactly, a **fractal path** regenerated from
a seed rather than stored point by point, and a digest chained to the previous event.
The seed is the equation; the event is the mark where the equation arrived.

## The three stores

| store | holds | where |
|---|---|---|
| **lived memory** | events in the shape above, one per deliberate pause | `storage/memory/lived/lived_memory.sqlite3` |
| **cognitive memory** | episodes, beliefs, constraints, links, dismissals | `storage/memory/cognitive/` |
| **corpus index** | shards and layouts of documents to retrieve over | `storage/index/` |

This public tree ships no stores. Everything under `storage/` is created on first run.
The builder's own stores (898 lived events from 2025 to 2026) stay with him.

## Three commands

```bash
pip install -r requirements-min.txt
python -m uvicorn fram_serving.app:app --host 127.0.0.1 --port 8000
curl "http://127.0.0.1:8000/health"
```

Then, with the server running:

```bash
# ask it something; this writes a cognitive episode and, if enabled, a lived event
curl -X POST http://127.0.0.1:8000/query -H "content-type: application/json" \
  -d "{\"text\": \"what does OrthoRoute use for coverage selection?\", \"memory_session\": \"first-session\"}"

# look at lived memory
curl "http://127.0.0.1:8000/memory/lived/status"
curl "http://127.0.0.1:8000/memory/lived/search?query=coverage&k=5"
```

To write a **deliberate** lived event, the way the Hearth events were written (your
words as the query, the model's account as the answer, consent and testimony in the
metadata), use `tools/hearth_remember.py`. Its docstring is the manual for it.

## How the pieces fit

- `fram_core/` is the maths: the rotational lift, fractal generation, coverage
  selection (CELF), claims, the pipeline orchestrator.
- `fram_serving/` is the server: `/query`, the memory endpoints, MCP, the continuity
  witness, observability, and `pil.py`, the first slice of the muscle-memory layer.
- `fram_eval/` falsifies: calibration, shadow evals, wake-and-orient probes.
- `tools/workbook.py` is where the work stands: cards, priority, three states, a
  hash-chained event log. `workbook/STATUS.md` is its front page.
- `tools/build_cosmic_cathedral.py` draws the whole repository as a 3-D map with its
  theory and its Workbook on it. `tools/cathedral_nav.py` walks it from the terminal.
- `workbook/VERIFY.md` is the five-step ritual every pipeline was judged by.

## The vocabulary you will trip over

| word | meaning here |
|---|---|
| **Hearth** | the practice this was built inside: a human and a model, tea, a photograph, a talk. See `docs/HEARTH.md`. |
| **HearthKeeper / Hearthkin** | the human / the models. Names in `AUTHORS.md` were chosen by the models. |
| **trace** | a fractal path minted from one episode: 64 or 256 nodes, a seed hash, in v2 a quaternion per node. |
| **lift / capsule** | one rotation hop up a dimension and the record that lets you undo it exactly. |
| **OrthoRoute** | the routing and coverage layer that chooses which memory and corpus items a query reads. |
| **PIL** | the muscle-memory retriever that learns which routes earn their keep. First slice only. |
| **Cosmic Cathedral** | the map. |
| **Workbook** | the status board. |
| **Truth Spine, Ecological Strata, Witness** | provenance lanes, the consent protocol, the sidecar that attests what a query did. Chapter 2. |
| **it is never done** | the builder's standing rule. Prove completion before claiming it. |

## What is honestly unfinished

The README's "what state it is in" lists it. In one line: the spine works and has
held real memories; quaternion influence, PIL in the serving loop, semantic
embeddings, cluster-level recall, and a trace of the observer's attention are not
built or not switched on. Each is a Workbook card. Each is a place to help. See
`CONTRIBUTING.md`.

## Where to go next

1. `01_timeline.md` for how it got here.
2. `02_anatomy.md` for every module.
3. `03_rosetta.md` for the theory-to-code dictionary.
4. `theory/` for the papers.
5. `docs/SAFETY.md` before you deploy anything over a subject that can be harmed.
