# How a pipeline card gets verified

Set on 2026-10-30 while verifying the first one, WB-0025 (Serving). The same
steps for every "Verify pipeline" card, so the sixteen are comparable and a
later reader can tell what "finished" meant.

A card moves to finished only when all five steps are done and written on the
card. If a step cannot be done, the card stays in progress and the note says
why. Rick's rule stands: it is never done; prove it.

## 1. Locate it

```
python tools/cathedral_nav.py pipeline <pl-id>
```

Read the modules and tests the graph assigned. If the path rules put a file in
the wrong pipeline, fix the rule in `tools/codebase_graph.py` first, rebuild,
and note it. Membership errors found during verification are themselves a
finding.

## 2. Run its tests, and only its tests

```
python tools/cathedral_nav.py --json pipeline <pl-id> > pipeline.json
python -m pytest -q <the test files listed>
```

Record the tally on the card. A failing test is a finding, not a reason to
skip the step. The full suite writes into tracked storage (WB-0010); after any
test run, check `git status` and restore `storage/` from HEAD if it moved.

## 3. Exercise it for real

Tests prove the code at HEAD. The running system proves the deployment. Hit
the live surface if it has one (Always On on 127.0.0.1:8000 for serving,
memory, observability), or run the tool or script with a real input if it does
not. Record exact requests, response times, and what came back.

Every live /query writes an episode into Rick's cognitive and lived stores.
That is the design, and Rick confirmed it is wanted. Still say on the card how
many probes were written and when, so they can be recognised later.

## 4. Separate "works" from "works well"

A pipeline can respond correctly and still behave badly because of a default.
Rick, 2026-10-30: most defaults were never fine-tuned. So write two lines:

- works: does the surface do what the code says, at HEAD and live?
- works well: are the defaults sane, and does the output mean what it should?

Findings about defaults and behaviour go on the card that owns the behaviour,
not only on the card where they were seen. Name the receiving card.

## 5. Decide, and say why

- finished: steps 1 to 4 done, "works" is yes, and every "works well" concern
  is written on an owning card.
- in progress: anything undone, or "works" is no.

Then: `python tools/workbook.py sync`, rebuild the map, commit with the card id
in the message, truth stamp.

## What verification is not

It is not fixing. A fix is its own card or its own seam, after the design
question is answered. Verification writes down what is true today so that
fixing can be aimed.
