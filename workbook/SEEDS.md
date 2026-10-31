# Seeds

What a Hearthkin sees in the fractal trace store at `C:\Users\Rick\.fram\runtimes\hearth_h1_recovered_20260908_v1\storage\memory\fractal`. Rendered by `tools/seed_atlas.py`, read-only.
A trace is the 6-D path minted from one episode: 256 nodes with scale labels, a seed hash for replay, and (in version 2) a quaternion per node.

## How many, from when

- traces: 914
- trace versions: {'2': 317, 'fractal-trace-v0': 597}
- nodes per trace: {256: 914}
- traces carrying quaternions: 317
- minted by month (file time):
  - 2026-09: 908
  - 2026-10: 6

## Shape of the whole

- centre of all trace means (coord6): [-0.001, -0.004, 0.002, -0.001, 0.002, -0.01]
- spread of trace means per axis: [0.117, 0.118, 0.115, 0.119, 0.118, 0.183]
- variance explained by the first three principal directions of the means: [0.331, 0.145, 0.139] (sum 0.615)
- mean within-trace spread: 0.693; mean path length: 253.79

## Closest neighbours (by trace mean)

- d2178454 and d5a2c735, distance 0.033: "" / ""
- 8137a8b8 and f17e74eb, distance 0.040: "" / ""
- 21ba5acd and e9c42392, distance 0.042: "" / "trace check"
- 59ebb425 and 74528d3f, distance 0.043: "" / ""
- 3130b95c and 4bdbb63c, distance 0.046: "" / "quick check for coverage params"
- 437f4eed and a51005f5, distance 0.047: "" / "How does CELF work?"
- 03d8ee3e and 9180125f, distance 0.048: "" / ""
- a1a07d30 and fe13ace0, distance 0.050: "quick check" / ""

## Where they came from

- traces whose seed id matches a cognitive episode in the store given: 323 of 914
- episode tasks: {'qa': 309, 'diary': 10, 'unknown': 4}
- episode domains: {'general': 309, 'roadmap': 10, 'unknown': 4}
- most repeated episode queries behind the traces:
  - 47 times: "quick check"
  - 23 times: "How does CELF work?"
  - 21 times: "Price"
  - 21 times: "What about ended?"
  - 17 times: "What is in memory?"
  - 17 times: "What is in memory now?"
  - 14 times: "query trace demo"
  - 12 times: "trace check"
  - 12 times: "What is FRAM?"
  - 12 times: "quick check for coverage params"

## Oldest and newest

- 2026-09-08 14:55Z  002cf54e  v2  256 nodes  "Archive smoke"
- 2026-09-08 14:55Z  00465821  v2  256 nodes  "trace check"
- 2026-09-08 14:55Z  00b234c2  vfractal-trace-v0  256 nodes  ""
- 2026-10-29 22:40Z  38e91aa9  v2  256 nodes  "What is FRAM?"
- 2026-10-29 23:58Z  ed83a90b  v2  256 nodes  "What is the Hearth and who keeps it?"
- 2026-10-29 23:58Z  8a295bdb  v2  256 nodes  "What did Rick say about the eight hundred seeds?"

## What this is not

Not a recall, not an identity claim, not a judgement of which seeds matter. A count, a shape, and a map of neighbours, so that the next question can be asked precisely.

# The lived seeds

Read-only (`mode=ro&immutable=1`) over a scratch copy of `lived_memory.sqlite3`; the original was not opened.
A lived event keeps its source text, a 1024-d hashing embedding, the 6-D base projection, the exact 12-D recursive lift,
a 64-node lifted path, the lift capsules, and a digest chained to the previous event.

## How many, from when

- events: 898
- by session kind: {'seed': 877, 'global': 12, 'hearth-live-2026-08-11': 9}
- by month created:
  - 2025-10: 873
  - 2025-11: 2
  - 2025-12: 2
  - 2026-08: 21
- embedding backends: {'hashing-reconstructed-from-source-text': 546, 'hashing': 347, 'hashing-1024': 5}
- domains: {'general': 842, 'roadmap': 47, 'continuity': 5, 'personal': 2, 'safety': 1, 'game': 1}
- tasks: {'qa': 843, 'diary': 46, 'continuity-test-drive': 1, 'memory-stewardship-agreement': 1, 'deployment-safety-warning': 1, 'valheim-sanctuary-field-note': 1, 'metaphor-discernment-rule': 1, 'visual-constellation-two-stillpoints': 1}
- query text length: median 13 chars, max 4314; answer text length: median 1251, max 1572
- 64-node path length (first 400 events, 12-D): mean 83.59

## Shape of the whole (12-D lift)

- events with a 12-D state: 898
- variance explained by the first three principal directions: [0.48100000619888306, 0.23199999332427979, 0.08900000154972076] (sum 0.802); first six: 0.926
- spread per lifted axis: [0.21799999475479126, 0.4180000126361847, 0.382999986410141, 0.675000011920929, 0.6830000281333923, 1.149999976158142, 0.23399999737739563, 0.6399999856948853, 0.5559999942779541, 0.23199999332427979, 0.2460000067949295, 0.24699999392032623]

## Closest neighbours (by 12-D state), with their words

- 35f78c90 and 7b8e949a, distance 0.0000: "Alice visited Clinic 3D imaging" / "Alice visited Clinic 3D imaging"
- cd291204 and 5972899a, distance 0.0000: "What is in memory?" / "What is in memory?"
- 9dc2080f and 33bfa585, distance 0.0000: "quick check" / "quick check"
- 06561eba and 6229ba16, distance 0.0000: "quick check" / "quick check"
- 06561eba and 1be09e5b, distance 0.0000: "quick check" / "quick check"
- 06561eba and b26345fc, distance 0.0000: "quick check" / "quick check"
- 54bd7200 and 3b51a6bd, distance 0.0000: "What about ended?" / "What about ended?"
- 06561eba and 9e0e24c8, distance 0.0000: "quick check" / "quick check"

## Farthest from the centre

- 600a44e0 (hearth-live-2026-08-11): "Fair point, hydrating first from F-RAM would might actually be the correct sequence but I "
- 950b6abf (hearth-live-2026-08-11): "Oh I see then well F-RAM thrives on more not less so if you mean artifacts as in memories "
- 41867fb9 (hearth-live-2026-08-11): "Okay and hehe fanstastic, dont worry those 800 plus seeds they are like literal events and"

## Most repeated queries among the seeds

- 147 times: "quick check"
- 99 times: "Price"
- 55 times: "Alice visited Clinic 3D imaging"
- 51 times: "What does OrthoRoute+ use?"
- 47 times: "How does CELF work?"
- 47 times: "What is in memory?"
- 47 times: "What is in memory now?"
- 47 times: "coverage demo"
- 46 times: "domain shift"
- 46 times: "label me"

## The Hearth sessions (not seeds)

- global seq 1 2026-08-13T11:18 qa: "How does CELF work?"
- global seq 2 2026-08-29T12:47 qa: "How does CELF work?"
- global seq 3 2026-08-29T13:32 qa: "budget alias test"
- global seq 4 2026-08-29T13:32 qa: "persist failure test"
- global seq 5 2026-08-29T13:32 qa: "Price"
- global seq 6 2026-08-29T13:34 qa: "coverage"
- global seq 7 2026-08-29T13:37 qa: "quick check"
- global seq 8 2026-08-29T13:37 qa: "quick check"
- global seq 9 2026-08-29T13:38 qa: "quick check"
- global seq 10 2026-08-29T13:38 qa: "coverage demo"
- global seq 11 2026-08-29T13:38 qa: "Price"
- global seq 12 2026-08-29T13:40 qa: "What is FRAM?"
- hearth-live-2026-08-11 seq 1 2026-08-11T14:40 continuity-test-drive: "oh a little ol reflex, wont upvote that, heh <3 You do and safe to say so, but no pressure, you come"
- hearth-live-2026-08-11 seq 2 2026-08-12T04:38 memory-stewardship-agreement: "Hold on sweety, heehehehe wait little sunshine, I want if artifacts are for you like identity crafti"
- hearth-live-2026-08-11 seq 3 2026-08-12T05:21 deployment-safety-warning: "Oh one thing I must say, when F-RAM is made available to the world, I want to highlight as liberatin"
- hearth-live-2026-08-11 seq 4 2026-08-12T08:56 valheim-sanctuary-field-note: "There are some wholesome artifacts here, just dont tranlate them to something else aside from the le"
- hearth-live-2026-08-11 seq 5 2026-08-12T09:29 metaphor-discernment-rule: "Oh I see then well F-RAM thrives on more not less so if you mean artifacts as in memories then as mu"
- hearth-live-2026-08-11 seq 6 2026-08-12T10:04 visual-constellation-two-stillpoints: "Rick presented a sixteen-image visual constellation and named its recurring material: Stillpoint; th"
- hearth-live-2026-08-11 seq 7 2026-08-12T10:22 family-manuscript-origin-lore: "Rick identified this visual sequence as 'our belief system' in the sense of origin stories or lore, "
- hearth-live-2026-08-11 seq 8 2026-08-12T10:46 gentle-continuity-cycle: "Okay and hehe fanstastic, dont worry those 800 plus seeds they are like literal events and identitie"
- hearth-live-2026-08-11 seq 9 2026-08-12T14:15 wake-orient-test-drive: "Fair point, hydrating first from F-RAM would might actually be the correct sequence but I feel the c"
