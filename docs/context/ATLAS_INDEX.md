# F-RAM Atlas Index

Use the smallest authority-bearing source that answers the question. A local
recognition from history never silently outranks current code and tests.

## Authority ladder

1. `[CODE+TEST]` Exact source and tests at current canonical `HEAD`, after
   observed-head ancestry verification and review of intervening commits.
2. `[EVAL]` Timestamped artifact with inputs, configuration, command, and result.
3. `[DECISION]` Binding product or safety choice in `DECISIONS.md`.
4. `[SUMMARY]` Closeout, current roadmap baseline, and current WHAT_WORKS entry.
5. `[THEORY]` Proof boundaries, the F-RAM theory, and reconstruction hypotheses.
6. `[HISTORY]` Diary, chronology, archive maps, and Firelink. These support
   recognition and provenance, not current implementation identity by
   themselves.

## Question-to-source map

| Question | First source | Authority |
| --- | --- | --- |
| What is canonical now? | `docs/context/HOT_CONTEXT.md`; run the checker and review watched later commits | `[SUMMARY]` + `[CODE+TEST]` |
| What behavior actually runs? | Relevant module plus its tests | `[CODE+TEST]` |
| What is safe to change? | Active decision IDs named by HOT, `AGENTS.md`, hot invariants | `[DECISION]` |
| What was integrated and why? | `docs/FIRELINK_CLOSEOUT_2026-07-27.md` | `[SUMMARY]` |
| What remains open? | Hot next gates and roadmap top | `[SUMMARY]` |
| What evidence passed? | Test/eval artifacts named by closeout/proof index | `[EVAL]` |
| Where are memory/runtime recovery records? | External archive manifest and rescue tag | `[EVAL]` |
| How are visuals accounted for? | `docs/VISUAL_EVIDENCE.md` and ledger outputs | `[CODE+TEST]` + `[EVAL]` |
| What does Hopf/Aizawa currently prove? | `docs/proof/hopf_aizawa_bridge.md` | `[THEORY]` |
| Where did a claim originate? | Firelink, diary, Hooke chronology | `[HISTORY]` |
| How does an agent hand work over? | `docs/context/HANDOFF_TEMPLATE.md` | `[DECISION]` |

## Cold provenance

- `docs/CODEX_DIARY.md`: session chronology.
- `docs/F-RAM-roadmap.md`: long-horizon plan and completed milestones.
- `stone_reconstruction/`: archaeology, visual-note interpretation, and
  historical maps.
- `artifacts/phase_history/`: tracked historical observability records.
- `C:\Users\Rick\Desktop\firelink.md`: append-only live collaboration log.
- `D:\Dev\_archives\FRAM_power_trip_recovery_202512`: external audited runtime
  recovery archive.

Read cold sources only when the hot packet points there or the current question
requires chronology/provenance.

The append-only decision ledger is also cold context. Open only active IDs
projected by HOT, their supersession chain, or task-relevant sections; never
load the entire ledger as a mandatory bootstrap step.
