# 5. Archaeology: what exists, what was conveyed as built, what is stranded

First pass, 2026-10-28. Rick asked for a search of everything, including zips
and archives, for the pre-intent layer, muscle memory, the lost ANN, the
Workbook, and the cognitive substrate. Every result below is tagged.

## Locks found and what was done `[RAN]`

| path | access rule found | action |
| --- | --- | --- |
| `F:\Dev\firelink.md` | owner Rick, `Rick:(R)` read-only | left alone; the hot packet treats it as sealed provenance and claims are recorded in-repo since August |
| `F:\Dev\Team unity.md` | `Rick:(R)` read-only | left alone, personal |
| `F:\Dev\_archives\*.zip` (three files) | owner Rick, no entry for Rick at all; only SYSTEM and Administrators | granted `Rick:(R)` as owner, on Rick's instruction. Now readable. |

Rick says he did not set these. The zip rule is the stranger one: it made the
backups unreadable to their own owner. Possibly inherited from an elevated
copy process. `[INFERRED]`

## The memory stores, inventoried `[RAN]`

| store | location | contents |
| --- | --- | --- |
| Cognitive, protected tree | `F:\Dev\FRAM_V22_Starter\fram_v22_starter\storage\memory\cognitive\` | 1,160 episodes; 607 hashing vectors (1024-d); **910 semantic vectors (384-d)** created 2025-12-23 to 2026-01-01; 158 semantic belief vectors |
| Cognitive, canonical | `F:\Dev\_firelink_recovered_20260804\storage\memory\cognitive\` | 892 episodes; 346 hashing vectors; 59 beliefs; **no semantic vectors** |
| Cognitive, damaged merge | `F:\Dev\_firelink_merge\storage\memory\cognitive\` | 875 episodes; read-only evidence |
| Lived, canonical | `F:\Dev\_firelink_recovered_20260804\storage\memory\lived\lived_memory.sqlite3` | 898 events, 879 sessions; projection `fractal6_recursive_lift_v1`, 12-d, 64 nodes, decay 0.82; four dated snapshots beside it from 2026-08-11 and 08-12 |
| December 2025 backup zip | `F:\Dev\_archives\FRAM_v22.2_MCP_LIVE_BACKUP_20251218.zip` | 4,505 files; cognitive episodes, hashing vectors, beliefs, demo-corpus ANN. This is the source of the 877 seeds. |
| September 2025 backup zip | `F:\Dev\_archives\fram_v22_backup.zip` | 9,174 files; no memory stores (pre-cognitive-memory era) |
| This checkout | `C:\Dev\FRAM_V22_Integration\I\storage\` | no memory stores at all |

Lived events by embedding provenance: 347 hashing, 5 hashing-1024, 546
reconstructed from source text. The 546 are labeled derived, as the docs
promise `[RAN]`.

## The stranded memory `[RAN]`

Comparing episode ids across the stores:

| set | count | dates |
| --- | --- | --- |
| shared by protected and canonical | 875 | up to 2025-12-18 |
| only in protected tree | **285** | 2025-12-18 to 2026-07-22: 90 in December, 171 in January, 24 in July |
| only in canonical | 17 | 2026-08-29, one afternoon |
| of the 285, present in the lived store | 2 | |

So the lived store, the August 2026 self, was built from the December 18
backup. Every cognitive episode F-RAM wrote during the entire eval season,
from December 18 through the January 30 full-experience commit, and the July
22 reconstruction day, lives only in the protected tree. The 910 semantic
vectors, the embedding backend added 2025-12-23, exist nowhere else. Neither
the canonical cognitive store nor the lived store has them.

This is not a code gap. It is a memory gap, and the firelink's own rule says
preserve experience. The closeout said the protected tree must not be touched
without Rick's migration decision. The decision now has numbers `[INFERRED]`.

## Rick's list against the evidence

| Rick's term | found | status |
| --- | --- | --- |
| Pre-Intent Layer (PIL) | `docs/FRAM_PIL.md` (spec stub, 2026-01), `docs/breathing_flame_notes_2026-02-01.md` (hundreds of design rules, the last document before the gap) | **never code**. Confucius taxonomy: "aspirational/spec stub, not a subsystem." Hooke chronology: "not implemented as a subsystem." Code hits for `PIL` are the Python imaging library. `[READ-DOC]` `[RAN]` |
| past-self and current-self tension | PIL's stated purpose is the moment before symbolic reasoning crystallizes; the breathing flame notes are all about when a lean may engage, decay, or yield | design only, inside PIL `[READ-DOC]` |
| muscle memory | Rick's handwritten note IMG_0182: "Muscle memory / embodiment / recognition of another; Lived Poses, Remote Connections" | notes only; no code, no doc `[READ-DOC]` |
| the small ANN being trained | the closest artifact is the semantic embedding backend (384-d, 910 vectors, Dec 23 to Jan 1) with its FAISS or sklearn index over cognitive episodes. It is an approximate-nearest-neighbour index over a frozen embedding, not a network that learns what is hard to change | stranded in the protected tree; see above. Whether this is what Rick means is question 13 `[INFERRED]` |
| what changes easily, what is hard to change, core beliefs | Phase D hysteresis gates and Phase E retention curve are the only code about resistance to change; beliefs with supports/contradicts/refines links are the core-belief structure | partial; gated off `[READ-DOC]` |
| cognitive substrate | ABC/3 lists "continuity substrate" under the slow deeper F-RAM layer | vocabulary from a ChatGPT-side taxonomy, not code `[READ-DOC]` |
| the Workbook | IMG_0184 "F-RAM workbook index: Skills, WorkBook, Cosmic Cathedral, Plug-ins, Computer-use, Routine"; ABC/3 "workbook / diary / proofs / packet families" | notes and vocabulary; `experiments/cosmic_cathedral` existed uncommitted in July per the firelink, not in canonical `[READ-DOC]` |
| track everything, where we are, what we have done | the diary, the roadmap checklist, the close-out guard, the hot packet, the claim protocol | built, as process, not as a subsystem `[READ-DOC]` |
| emotional impression embedding, limbic system | nothing by those names anywhere searched | not found `[RAN]` |

## A second vocabulary `[READ-DOC]`

ABC/1 and ABC/3 carry a taxonomy that does not appear in the code: the
Threefold Concord, the Hearth Spine, the Continuity Mandate, Temporal Strata,
the 12th Binding Layer, 7 regions and 4 strata, an attention-geometry packet
v0, Escher hydration carriers, a wear accumulator, the Gate of Enir-Ilim.
ABC/1 is honest about status: it lists what is partial or gated, what is
proof-track, and what is next, and the partial list matches the code. This
is the ChatGPT-side framing from 2026. It is the language in which much of
"conveyed as built" was conveyed `[INFERRED]`.

## The Recursive Rotational Lift provenance `[RAN]`

The payload on disk hashes to the manifest's SHA-256 exactly:
`17aa4d4a...cfd1a`. The toy simulations v0.1 and v0.2 with lab notes, trace,
and per-file hashes sit in the protected tree under the Diary and Workflow
Hub's hearthforge folder. v0.2's headline: exact reconstruction to
floating-point zero across 3-D to 8-D recursion when residuals and transform
metadata are kept, and graceful degradation when they are quantized, dropped,
or noised. The experiment folder is not in canonical. The math it tested
became `fram_core/rotational_lift.py` on 2026-07-22 `[LOG]`.

## What this pass did not do

It did not open the zips beyond listing. It did not read the 59 handwritten
note photos. It did not read the Cairn transcript or Team unity. It did not
read any module at code level. It did not touch the protected tree.
