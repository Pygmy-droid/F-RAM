# FRAM v2.2 Codebase Review and Spec Comparison (2026-01-17)

This document maps how the app fits together and compares code behavior to the
FRAM v2.2 spec and cheatsheet. It is written from the code as the source of
truth, per docs/FRAMv2.2-SPEC.md and docs/README.md.

## Scope and method
- Reviewed core runtime: fram_serving/app.py, fram_serving/query_runner.py,
  fram_core/pipeline.py, fram_serving/memory.py.
- Mapped supporting packages: fram_core, fram_index, fram_layout, fram_eval,
  fram_serving, tools, scripts.
- Compared behavior to docs/FRAMv2.2-SPEC.md, docs/FRAMv2.2-cheatsheet.md, and
  docs/Architecture.md.

## Runtime flow (planned, end to end)
1) HTTP /query or MCP fram.query enters fram_serving/app.py.
2) QueryContext is built in fram_serving/query_runner.py with memory stores,
   trace logger, observability paths, and config.
3) run_query orchestrates memory seeding (working memory and cognitive memory),
   optional fractal scoring, then calls QueryOrchestrator.run().
4) QueryOrchestrator.ensure_corpus loads or builds the demo corpus, vectors,
   prototypes, calibration, and ANN index from storage/index/demo_corpus.
5) QueryOrchestrator.run performs:
   - embed and whiten the query (hashing/tfidf/vocab backends)
   - shortlist candidates (ANN or dense scan)
   - subspace projection and confidence features
   - calibrate probability and decide local vs anchors vs global
   - coverage-aware CELF selection (anchors then shards)
   - assemble answer text, citations, and a full trace
6) run_query appends a cognitive episode, optionally writes a memory capsule,
   logs observability events, and returns answer + trace.

## Entry points and surfaces
- HTTP API: fram_serving/app.py
  - /query, /memory (create/control/append/dismiss/search), /observability/*,
    /metrics, /time, /where, /label, /calibration, /config, /health
  - /ui/memory, /ui/observability, /ui/experiments
- MCP: fram_serving/mcp_server.py exposing fram.query and memory tools
- CLI: fram_serving/cli.py and scripts/*

## Package map (how pieces connect)

### fram_serving
- app.py: FastAPI, config wiring, global stores, endpoint handlers, UIs.
- query_runner.py: wraps QueryOrchestrator with memory seeding, fractal scoring,
  trace/observability logging, and episode/capsule writes.
- memory.py: WorkingMemoryStore and CognitiveMemoryStore, including ANN-backed
  cognitive search, belief/episode persistence, and recall weighting.
- observability.py: trace log writer, reliability/ECE tracking, metrics windows.
- fractal_memory/*: trace generation, scoring, storage, and replay helpers.
- memory_capsule.py: append-only capsule writer; storage/memory/capsules.
- mcp_server.py and mcp_auth.py: MCP tools and auth gate.
- ingest.py: CLI helper for the demo corpus.
- semantic.py: lightweight relevance reranker for /search/expand and /rank/relevance.

### fram_core
- pipeline.py: QueryOrchestrator, corpus ingest/load, shortlist, projection,
  confidence, coverage, anchor selection, trace assembly.
- confidence.py: robust feature bundle, logistic confidence, temperature scaling,
  conformal thresholds.
- coverage.py: concave coverage, independence buckets, CELF selection and costs.
- claims.py: typed claim extraction (regex heuristics) and table claim helpers.
- anchors.py: residual direction helpers for anchor candidates.
- math_utils.py: whitening, projection, robust z, subspace match, kNN distance.
- rerank.py: cosine reranker placeholder used for pair-cost accounting.

### fram_index
- prototypes.py: lightweight centroid + basis store, cosine shortlist.
- sparse_keys.py: minimal identifier/number index for sparse hits.
- version_lattice.py: timestamp-based lattice stub for as_of filtering.

### fram_layout
- pdf_chunker.py: pdfplumber extraction with fallback line chunking.
- table_chunker.py: CSV parsing and header+row window builder.
- code_chunker.py: Python AST chunking for definitions and methods.
- assembler.py: layout-aware assembly (segment headers, table header ordering).

### fram_eval
- conversation_memory_eval.py, memory_shadow_eval.py: eval harnesses.
- metrics.py: calibration, retrieval, QA, citation, efficiency, and freshness
  metrics.
- ablations.py: the ordered spec-section-15 ablation ladder, equal-budget
  runner, QueryOrchestrator result normalization, JSON artifacts, and optional
  plotting.
- datasets.py: validated JSONL cases and deterministic table/code/PDF smoke
  datasets.
- fractal_falsification.py, fractal_autoflip.py: fractal diagnostics.

### tools and scripts
- Ingest: scripts/ingest_project_docs.py, scripts/ingest_demo.py
- Calibration: scripts/calibrate_confidence.py, tools/calibration_*.py
- Memory bootstrap + logging: tools/bootstrap_memory.py, tools/log_chat_turn.py
- Observability: tools/trace_summary.py, tools/cognitive_memory_summary.py

## Storage and observability map
- storage/index/demo_corpus: vectors, prototypes, ANN index, calibration payloads
- storage/observability: confidence, latency, memory logs, tc windows, trace logs
- storage/memory: working memory JSONL sessions
- storage/memory/cognitive: episodes, beliefs, links, vectors, ANN metadata
- storage/memory/capsules: memory capsules (when enabled)

## Spec vs code status (high level)

Status guide: Implemented = present in code path, Partial = simplified or demo,
Stub = minimal placeholder.

- Spec 3-4 (prototype routing + subspace projection): Implemented (demo form)
  via hashing/tfidf/vocab vectors and per-doc SVD bases in fram_core/pipeline.py.
- Spec 5 (confidence/calibration/conformal): Implemented with robust z features,
  logistic regression, temperature scaling, and conformal taus. Domain/task
  payloads load from calibration_*.json if present.
- Spec 8 (multi-anchor selection): Partial. Curvature-based candidate probes are
  computed, then coverage-based CELF is used to select anchors and shards, but
  no claim sketches or Jaccard diversity are used.
- Spec 9 (sparse concept-key index): Partial. Simple identifier/number map with
  checksum validation (ISBN/IBAN) and posting caps; still no Aho-Corasick.
- Spec 11 (claim-aware coverage): Implemented concave coverage, buckets, and
  CELF selection. Claim extraction is heuristic regex, not full NER/relation
  models.
- Spec 13 (version lattice/as-of): Partial. As-of selection uses per-doc latest
  mapping and explicit version selection; still no DAG diffs, per-version
  centering, or delta snippets.
- Spec 14 (layout chunking): Partial. Deterministic fallback ordering, table
  header windows, and layout uncertainty flags; still no Hilbert ordering,
  region confidence, or multi-column graph logic.
- Spec 15 (eval/ablations): Implemented core metric coverage, typed dataset
  loading, the eight-rung equal-budget ladder, JSON reporting, and the existing
  conversational/fractal harnesses under fram_eval/.
- Extras beyond spec: cognitive memory, memory capsules, fractal trace scoring,
  observability UIs.

## Docs vs code deltas (noted)
- docs/FRAMv2.2-SPEC.md describes a Jaccard-based anchor diversity penalty.
  The code uses a section/segment repeat penalty (section_repeat_penalty) in
  fram_core/coverage.py and fram_core/pipeline.py, matching the cheatsheet.
- docs/Architecture.md lists fram_core/anchors.py for anchor selection, but the
  selection logic is in fram_core/pipeline.py (anchors.py only provides residual
  directions).
- docs/FRAMv2.2-SPEC.md describes a full sparse-key index and version lattice;
  code has lightweight stubs in fram_index/sparse_keys.py and
  fram_index/version_lattice.py.

## Testing map (where behavior is locked in)
- Query path and confidence: tests/test_pipeline_orchestrator.py,
  tests/test_serving_query.py, tests/test_serving_confidence.py
- Coverage and CELF: tests/test_coverage_core.py, tests/test_celf_selection.py
- Memory: tests/test_memory_api.py, tests/test_cognitive_memory_*.py,
  tests/test_memory_capsule.py
- Observability and UI: tests/test_observability_*.py, tests/test_metrics.py
- Layout: tests/test_pdf_chunker.py, tests/test_table_layout.py,
  tests/test_code_chunker.py, tests/test_layout_assembler.py

## Suggested reading order
1) fram_serving/app.py
2) fram_serving/query_runner.py
3) fram_core/pipeline.py
4) fram_serving/memory.py
5) fram_core/confidence.py and fram_core/coverage.py

## Known gaps vs spec (summary)
- Full prototype bank / ANN routing (spec Section 7) is demo-only.
- Claim extraction is heuristic (spec Section 11.2).
- Layout and version lattice are partial stubs (spec Sections 13-14).
- Anchor diversity uses section penalties, not Jaccard (spec Section 8).
