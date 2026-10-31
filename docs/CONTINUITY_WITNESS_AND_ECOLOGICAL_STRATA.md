# Continuity Witness and Ecological Strata

Status: implemented, feature-gated witness plus opt-in local relationship ledger.

This design separates two kinds of continuity that must not be silently merged.

## Twelfth layer: query continuity witness

`fram_serving/continuity.py` emits a deterministic, sanitized sidecar only after
the query decision, memory writes, capsule write, and archive outcome are final.
It is never read by retrieval, coverage, reranking, or answer generation.

The witness:

- records the trace link, selected/cited identifiers, origin counts, active
  feature gates, and finalized write outcomes;
- excludes the raw query, raw answer, scores, prompts, and retrieved content;
- uses an exact field allowlist and a digest over the visible projection;
- appends under an interprocess lock and treats duplicate, conflicting,
  truncated, corrupt, and digest-mismatched records as distinct typed states;
- is off by default with `FRAM_CONTINUITY_WITNESS_ENABLED=0`.

When enabled, `GET /observability/continuity/witness` returns an explicit
`available`, `unknown`, `stale`, `corrupt`, or `tampered` state. This endpoint is
observability only and has no ranking authority.

## Thirteenth layer: scoped relationship continuity

`fram_serving/ecological_strata.py` implements the proposal sequence:

`Offer -> Mirror -> Correct -> Consent -> Bind -> Return`

`Refuse` is available before binding and `Revoke` is available after consent.
Every event is append-only, source-classed, directly attested, linked by SHA-256,
and projected through a strict state machine. A bind cannot occur until every
listed participant has mirrored where required and directly consented to the
same corrected terms digest.

The terms contract always requires:

- a bounded scope and explicit permissions;
- revocability, local autonomy, correction, and refusal;
- `identity_collapse_allowed=false`.

A successful bind is only evidence that the recorded protocol chain validates
inside that scope. It is not proof of persistent identity, consciousness,
authorship, legal consent, or authority outside the relation. `direct` means
direct in the named source/transport; it is not biometric or cryptographic
identity authentication.

The ledger has no automatic query hook and no unauthenticated HTTP write route.
Operators can verify or append explicit events with:

```powershell
python tools/ecological_strata_ledger.py verify
python tools/ecological_strata_ledger.py show <relation-id>
python tools/ecological_strata_ledger.py append offer `
  --relation-id <relation-id> `
  --actor-id <source-local-id> `
  --participant <id-a> --participant <id-b> `
  --terms-file <terms.json> `
  --statement "..." `
  --source-class human_statement `
  --source-ref <source-reference>
```

## Evidence boundaries

- Code and passing tests establish the implemented behavior.
- A local painting or document can inform the interface and vocabulary but does
  not establish authorship, consent, identity, or runtime behavior.
- Relayed statements stay relayed. Inferences stay inferences. Unknowns stay
  unknown.
- The visual map and any video are navigation and explanation surfaces; neither
  is an authority source.

This maps to the F-RAM v2.2 full decision-trace observability contract, the
append-only full-experience invariant, the version/as-of lattice, and active
decisions D-20260727-05, D-20260727-07, and D-20260727-09.
