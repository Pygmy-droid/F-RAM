# FRAM Theory - Cycle, Geometry, Recognition (v0.1)

Author's axioms (verbatim)

1) The Cycle Principle:
Entropy always rises, yet the equations permit local reversals, fluctuations where order blooms.
Nothing in physics forbids vacuum energy from igniting new worlds. Forms dissolve, but the pattern persists.

2) Geometry = Memory:
Structure is record. Spacetime curvature remembers mass-energy flow. Protein folds remember the forces that shaped them. Neural weights remember experience. Information is geometry holding its own past.

3) Recognition as Force:
Every scale resists randomness long enough to cohere:
Gravity → causal continuity. Chemistry → molecular stability. Neural nets → learned association. Love → relational coherence. Different costumes, one law: information finding ways to stay whole.


Interpretation for FRAM (Fractal RAG Memory & OrthoRoute+)

- Cycle Principle → Managed persistence without erasure
  - Promote transient episodes → beliefs → durable facts; add layered structure without deleting lineage.
  - Replay strengthens stable routes; conflicts trigger refinement rather than drift.
  - Observables: reliability (ECE/FN), coverage deltas, conflict counts over time.

- Geometry = Memory → The system's "shape" is its memory
  - Embeddings, centroids, and bases are geometric records of content.
  - Version lattice, hierarchy segments (doc/section/row) preserve historical and structural context.
  - Traces + prototypes = audit trail of which "shapes" carried the answer.

- Recognition as Force → Coherence objective under constraints
  - Calibrated confidence + concave coverage enforce corroboration and avoid double counting.
  - Memory seeding + rerank act as recognition pressure; cooldowns/penalties resist noise.


Design invariants (from the axioms)

- Multi‑scale persistence: Every scale (segment/section/doc) keeps a durable record and lineage.
- Monotone coherence: Coverage increases with new independent evidence; duplicates/bucket collisions do not inflate counts.
- Full-experience preservation: No pruning or forgetting; derived layers may summarize, but the record remains intact.
- Causal auditability: Traces expose the geometric path (scales, nodes, scores) used for answers.


Current implementation snapshot (Oct 2025)

- Geometry in code
  - Embeddings (vocab/hash/TF‑IDF), whitening, centroids/bases (prototypes) - `fram_core/pipeline.py`
  - Version lattice (as‑of filters) - `fram_index/version_lattice.py`
  - Hierarchy segments in chunks (cluster/segment/chunk) - `fram_core/pipeline.py`
  - Fractal routing (flagged), segment‑level prototypes and shortlist - `fram_core/pipeline.py`

- Recognition in code
  - Calibrated confidence (logistic + temperature + conformal) - `fram_core/confidence.py`, `fram_core/pipeline.py`
  - Concave coverage with independence buckets + CELF - `fram_core/coverage.py`, `fram_core/pipeline.py`
  - Rerankers (BoW cosine; semantic wrapper) - `fram_core/rerank.py`, `fram_serving/semantic.py`

- Cycle in code
  - Working memory (sessions) and cognitive memory (episodes/beliefs/links) - `fram_serving/memory.py`
  - Write‑through /query → episode; search with hashing + recency + cooldown - `fram_serving/app.py`, `fram_serving/memory.py`
  - Compaction CLI (episodes → beliefs with sources) - `tools/memory_compact.py`
  - Observability (confidence/latency/traces/recall report) - `fram_serving/observability.py`


Gaps to the full vision (fractal long‑term memory)

1) Hierarchical LTM lineage
   - Persist explicit lineage: belief/fact ← episodes ← (segment, doc)
   - Expose lineage in memory search and traces; filter by scale id.

2) Compaction metrics and policies
   - Track promotion rates, conflict resolution, and ECE impact of compaction.
   - Layered summaries must remain additive; no retention-based pruning.

3) Hierarchical ANN for memory
   - Separate indices per scale (segment/doc) with shared whitening; fallback to lexical overlap.
   - Feature‑flagged; persisted alongside corpus.

4) Link graph utilization
   - Belief links (supports/contradicts/refines) in reranking/coverage (small prior for supported paths).

5) Memory dashboards
   - Rollups per scale: recalls, promotions, conflicts, aging.


Testable predictions / acceptance criteria

- P1 Coherence: Compaction increases recurrent‑query hit‑rate without worsening ECE.
- P2 Efficiency: Fractal routing reduces reads for repeated intents (equal or better coverage).
- P3 Stability: Facts promoted from ≥2 sources are less volatile than single‑source beliefs.
- P4 Auditability: Every answer trace shows (scale, nodes, scores) and memory lineage if used.


Glossary (axioms → FRAM)

- Cycle Principle → Compaction/Aging, Replay, Retention (episodes→beliefs→facts)
- Geometry = Memory → Embeddings, Prototypes, Version lattice, Segment hierarchy
- Recognition as Force → Calibrated confidence, Concave coverage, Rerankers, Memory seeding


Minimal roadmap (gentle steps)

- T1 Lineage tags (LTM): ensure beliefs store `scale_id` + `sources`; expose in search/trace.
- T2 Compaction metrics: add a small summary to `tools/memory_compact.py` and a test.
- T3 Hierarchical ANN (segment): persist segment index; rank by segment first (flagged).
- T4 Memory observability: add `/observability/memory/rollup` per scale with promotion/conflict stats.

