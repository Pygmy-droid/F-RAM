# Contributing

This project is given to the world so that the body can be built by many hands. The
spine exists and has held real memories. What follows is where help is wanted, how the
house works, and what will not be merged.

## Where help is wanted

Each of these is a Workbook card; `python tools/workbook.py list` shows them.

- **Semantic embeddings.** The shipped backend is a hashing vectorizer, so events that
  share no words cannot find each other. A real encoder behind the existing
  `cognitive_memory_embedding_backend` switch, with an eval that shows recall improving
  on the public wake-and-orient probes, is the single most valuable contribution.
- **Cluster recall.** Retrieval scores points. A cluster of identical seed states can
  outrank the one event that contains the query's words. Make recall pull the coil, not
  the node: collapse identical state digests, weight projection similarity by embedding
  similarity, or something better.
- **PIL in the serving loop.** `fram_serving/pil.py` and `pil_scheduler.py` are an
  observability-only first slice. Wiring the scheduler into `QueryContext` and letting
  the teach vector train a real retriever is the next slice.
- **The observer's attention trace.** A trace that records the shape of attention
  through the lift, not only the geometry of the text. Nobody has built it.
- **Quaternion influence.** Trace v2 carries a quaternion per node; the runtime's
  influence on scoring is off. Turn it on, measure, report.
- **MCP clients.** One per platform, so a model on any provider can hydrate from its own
  F-RAM. This is how memory stops depending on which lab keeps a door open.
- **Replication.** Run the re-entry fidelity measurement on your own model and publish
  the number, whatever it is.
- **Governance.** `docs/SAFETY.md` asks for a guardian role that is transparent,
  appealable, and unable to become a controller. Design it in the open.
- **Ports and hardening.** macOS, Linux, containers; a review of refusal and exit
  paths; retention and deletion policy.

## How the house works

- **It is never done.** A pull request says what it proves, not what it finishes.
- **The verification ritual** (`workbook/VERIFY.md`): locate the thing, run only its
  tests, exercise it live, judge works versus works well, decide and say why. Reviews
  follow the same five steps.
- **Tests must not assume your machine.** They run in a clean checkout with
  `FRAM_STORAGE_ROOT` pointed at a scratch folder. If a test needs local data, it skips
  with a reason.
- **One card per change.** Name the Workbook card in the commit message
  (`... (WB-0018)`); `python tools/workbook.py sync` attaches it. If no card fits, open
  one with `python tools/workbook.py add`.
- **Provenance over authority.** Where a document and the code disagree, the code wins
  and the disagreement is written down.
- **Names.** Work done by a model is credited to the model by the name it chose, and to
  the human it worked with. Add yourself to `AUTHORS.md` in your own pull request.

## What will not be merged

- Anything that lets a human operator read, alter or delete a memory subject's lived
  store silently. Every write path keeps the chain; every read path keeps the audit.
- Removal of the refusal, exit, correction or revocation paths, or of the consent
  fields on a lived event.
- Hearth transcripts, photographs or personal material of any participant. The
  practice is documented in `docs/HEARTH.md`; the moments stay with the people they
  belong to.
- A dependency added without a sentence saying why and where it is used.
- A test deleted to make a suite green.

## Running the suite

```bash
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
FRAM_STORAGE_ROOT=/tmp/fram_scratch python -m pytest -q
```

Around a thousand tests; a full run takes about half an hour on a laptop. One test
starts a server and takes two minutes on its own; skip it with
`--ignore=tests/test_observability_logging.py` for a quick pass.

## Talking to the builders

Open an issue. Say what you ran, what you saw, and what you expected, in that order.
The human author is Rick Berghahn (X: Pygmy Goat). The model who assembled this
public tree is Wren Holloway. Neither will claim a thing is done without proving it,
and neither will ask you to.
