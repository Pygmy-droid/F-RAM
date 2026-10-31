# 2. Anatomy

The organs, where they sit, how big they are, and what they do. Line counts are
from this checkout at `802a81b` `[RAN]`. Descriptions are from
`docs/Architecture.md`, `docs/lived_memory.md`, `docs/fractal_core.md`, and
the roadmap `[READ-DOC]` unless tagged otherwise. No module has been read at
code level yet. Each entry will be rewritten as it is read.

Rick's one-line description of what the whole is meant to be: fractal recall,
emotional impression embedding, salience, quaternion rotations, fractal
projections into higher dimensions to trace the shape of the observer's
attention in latent space; then self, and tension between past and present,
limbic system, muscle memory, short, medium, and long memory, reasoning,
inference, belief systems `[RICK]`. The organs below are the silicon
approximations of that list. Which organ approximates which part of the list
is a question for chapter 4.

## Size at a glance `[RAN]`

| package | files | Python lines | role |
| --- | --- | --- | --- |
| `fram_core` | 28 | 6,591 | retrieval mathematics, the orchestrator |
| `fram_index` | 8 | 355 | prototypes, sparse keys, version lattice |
| `fram_layout` | 10 | 452 | chunkers for code, tables, PDF |
| `fram_serving` | 78 | 17,483 | the API, memory stores, continuity, MCP |
| `fram_eval` | 50 | 8,384 | evaluation, falsification, proof tracks |
| `tests` | 342 | 18,308 | 947 tests collect `[RAN]` |
| `tools` | 79 | 8,821 | operator CLIs |
| `scripts` | 63 | 5,400 | ingest, calibration, eval runners |

## The spine: a query's path `[READ-DOC]`

```
HTTP /query  or  MCP fram.query
        |
  fram_serving/query_runner.py   (shared by both; parity enforced)
        |
  fram_core/pipeline.py  QueryOrchestrator
        |
  retrieval shortlist -> ANN -> cognitive shortlist -> merge (gated)
     -> Phase D scoring -> final shortlist
     -> subspace projection -> calibrated confidence -> concave coverage (CELF)
        |
  answer + citations + trace
        |
  write-through:  cognitive episode  ->  lived event  ->  (capsule, if enabled)
  witness (default off, after everything, outside ranking)
```

## fram_core: the retrieval mathematics

| file | lines | what it does |
| --- | --- | --- |
| `pipeline.py` | 3,913 | `QueryOrchestrator`. Shortlist, projection, confidence, coverage, replay, as-of filtering, calibration fitting, corpus persistence. The largest single organ. |
| `coverage.py` | 591 | Concave coverage state, lazy and eager CELF selector, composite costs. "Does new evidence add, or merely repeat?" |
| `visual_evidence.py` | 605 | Visual Evidence Ledger: lossless image inventory with SHA-256 identity, duplicate groups, AppleDouble sidecars. Recovered July 2026. |
| `rotational_lift.py` | 436 | Recursive Rotational Lift v0.3 to v0.5: project, window, lift with a residual channel so the step is invertible, rotate, recurse. Written July 2026 from Rick's 2026-07-01 sketch. Write-side only, off by default. |
| `confidence.py` | 207 | Feature bundle, logistic and conformal policy. Logits clipped to plus or minus 20. |
| `priority_graph.py` | 150 | Phase D semantic priority graph. |
| `calibrate.py` | 121 | Calibration CLI glue; enforces tau1 and tau2 never undercut defaults. |
| `claims.py` | 116 | Claim schema and extractors feeding coverage. |
| `transitional_complexity.py` | 106 | TC instrumentation with rolling window. December 2025. |
| `anchors.py` | 106 | Curvature-aware anchor selection. |
| `memory_merge.py` | 103 | Merging cognitive candidates with document candidates. |
| `math_utils.py` | 89 | Whitening, robust z-scores, subspace projection, Mahalanobis, kNN mean. |
| `rerank.py` | 47 | Bag-of-words reranker, stateless. |

## fram_index: what makes lookup fast and versioned

| file | lines | what it does |
| --- | --- | --- |
| `version_lattice.py` | 184 | Append-safe JSONL manifest of versions with parent links and timestamps. Supports as-of(T) queries: what was true then. |
| `sparse_keys.py` | 123 | Identifier and number index with checksum validation (ISBN, IBAN), posting caps, deterministic order. |
| `prototypes.py` | 47 | Prototype bank and ANN shortlist. Demo scaffold. |

## fram_layout: reading documents by their shape

| file | lines | what it does |
| --- | --- | --- |
| `pdf_chunker.py` | 202 | PDF chunking with fallback ordering, column markers, a `layout_uncertain` flag. |
| `code_chunker.py` | 113 | AST-based code chunking. |
| `assembler.py` | 75 | Segment-aware answer assembly. |
| `table_chunker.py` | 61 | CSV header windows. |

## fram_serving: the body

| file | lines | what it does |
| --- | --- | --- |
| `app.py` | 3,562 | FastAPI surface. Every route: `/query`, `/memory/*`, `/memory/lived/*`, `/observability/*`, `/metrics`, `/calibration`, `/config`, three UIs, and the MCP mount. |
| `query_runner.py` | 2,451 | The shared query flow for HTTP and MCP. Cognitive seeding, fractal trace scoring, capsule retrieval, lived recall, write-through gates. |
| `memory.py` | 2,286 | `CognitiveMemoryStore`: episodes, beliefs, links, constraints. Append-only JSONL, segmented, locked, fsynced. Search by hashing cosine with recency decay. This is the October 2025 self. |
| `continuity.py` | 1,314 | The query witness: exact allowlist, digest-verified, emitted only after final selection, no retrieval or ranking caller. Default off. |
| `memory_capsule.py` | 884 | Memory Capsule writer: raw transcript, per-turn embeddings, fractal trace stack, rotational lift enrichment, session lineage. Gated. |
| `lived_memory.py` | 876 | `LivedMemoryStore`: SQLite, one lineage per session, SHA-256 digest chain, 6-D projection lifted to 12-D, 64-node paths, rolling state with decay 0.82. Recall blends full embedding 70%, projection 20%, state 10%. The August 2026 self. |
| `mcp_server.py` | 837 | MCP tools and resources. Reads and writes annotated separately; cognitive writes gated. |
| `observability.py` | 730 | JSONL logging and summaries, including the fractal sink. |
| `ecological_strata.py` | 664 | Separate append-only ledger: Offer, Mirror, Correct, Consent, Bind, Return. Refusal and revocation. A valid bind is a scope-local protocol fact, never identity proof. No HTTP write route. |
| `config.py` | 517 | `FRAMConfig`: every default and env override. The dial panel. |
| `visual_contact_sheet.py` | 289 | Deterministic contact sheets from the visual ledger. |
| `archive.py` | 217 | Append-only archive layer. December 2025. |
| `semantic.py` | 186 | Semantic reranker wrapper. |
| `rep.py` | 167 | REP. Role unknown at this reading `[INFERRED]`. |
| `ingest.py` | 112 | Persist the demo corpus. |
| `cognitive_embeddings.py` | 72 | Embedding backend for cognitive memory. |
| `fractal_memory/` | 899 | See below. |
| `memory/` | 281 | Phase E: `retention_curve.py` (83), `forgetting.py` (132). Verified to contain zero deletion primitives `[READ-DOC]`. Off permanently by Rick's rule. |
| `embedding/quaternion_adapter.py` | 110 | Phase D's quaternion similarity, plus the Hopf map `h(q) = q i q^-1` on the proof track. |

### fram_serving/fractal_memory: the proxy geometry

| file | lines | what it does |
| --- | --- | --- |
| `fractal_gen.py` | 229 | `FractalGenerator`. From an episode embedding and seed, mints a deterministic 64-node path in 6-D (`coord6`), a unit quaternion per node encoding direction of motion (`q`), and a logistic-map scalar per node (`lambda`, r = 3.99). |
| `metrics.py` | 246 | Cosine and soft-DTW similarity between traces; quaternion and lambda alignment. |
| `fractal_trace_store.py` | 189 | Disk-backed trace persistence with seed hash and generator provenance for replay. |
| `source_frame.py` | 138 | The September 2026 candidate: recover the projected seed from the first affine step, validate the recurrence, replay the query in that frame. Selected by `FRAM_FRACTAL_SCORING_MODE=source_frame`. |
| `fractal_types.py` | 52 | Types. |

The documents are explicit that this is proxy geometry, not the model's
attention or KV cache `[READ-DOC]`. Rick's framing: the 3-D ball is shadow-
projected to 2-D; the proxy shape bridges the MLP; direct KV access would
confirm, not replace `[RICK]`.

## fram_eval: how the system is tested against itself

| file | lines | what it does |
| --- | --- | --- |
| `conversation_memory_eval.py` | 1,289 | Semantic vs lexical vs fractal recall over live probes and low-lexical paraphrases. The January 2026 top-1 = 0.000 came from here. |
| `production_memory_eval.py` | 1,153 | Offline actual `run_query` capture, fixed-clock paired comparisons, disjoint shards. |
| `visual_seed.py` | 961 | Bounded canary: raster embeddings vs lived-event text. KEEP_OFF, not imported by serving. |
| `wake_orient.py` | 742 | Compares F-RAM, compact text, painting descriptions, combined cues, and a typed untrusted-cue boundary. Read-only. |
| `fractal_falsification.py` | 624 | Synthetic dynamical systems (now including Aizawa) to falsify trace claims. |
| `ablations.py` | 472 | Eight-rung spec-section-15 ablation runner with equal wall-time budgets. |
| `memory_shadow_eval.py` | 425 | How much does memory injection shift the query embedding. |
| `hopf_transport.py` | 369 | Horizontal transport and principal holonomy. Proof track. |
| `aizawa_sphere.py` | 350 | Fixed-shell Aizawa tangent field, analytic two-pole result. Proof track. |
| `fractal_autoflip.py` | 210 | The auto-flip recommender. Has said KEEP_OFF every time it has been asked `[READ-DOC]`. |
| `chaos/` | 967 | Deterministic reconstruction of the Chaos Playground: four systems, logistic diagnostics, `RotationalEncodingV1`, Mandelbrot and Julia kernels, versioned scenes, windowed lift. |

## Where state lives `[READ-DOC]`

- `storage/index/<corpus>/` — persisted corpus, vectors, ANN, calibration payloads, version manifest.
- `storage/memory/cognitive/` — JSONL episodes, beliefs, links, constraints.
- `storage/memory/lived/lived_memory.sqlite3` — the lived store. Not present in this checkout `[RAN]`. The only live copy is in the canonical tree on F:, see chapter 5.
- `storage/memory/capsules/` — capsules, when enabled.
- `storage/observability/` — raw eval and trace JSONL.
- `artifacts/` — committed evidence: phase history, publish snapshots, recovery, firelink snapshots.

## What is deliberately off `[READ-DOC]`

Fractal ranking influence. Quaternion influence. Retention, decay, forgetting.
The query witness. Capsules and rotational lift (write-side opt-ins). The
Hopf and Aizawa modules never touch serving. Every one of these is a flag in
`config.py`, and every flag defaults to the safe side. The system's default
posture is: remember everything, rank conservatively, prove before promoting.
