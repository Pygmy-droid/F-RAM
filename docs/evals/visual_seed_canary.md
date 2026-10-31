# Visual-seed candidate canary

The visual-seed evaluator is a bounded candidate lane for checkpointed lived
memory. It does not enable visual or fractal ranking, generate an answer, write
memory, or promote a retrieved event. It is not imported by the serving or
query pipeline.

## What it evaluates

For each manifest image, the evaluator produces two ranked lists:

1. **F-RAM text primary** — the existing hashing-vectorizer cue is scored by
   the immutable lived-memory reader.
2. **CLIP visual supplement** — a pinned CLIP image vector is compared with
   CLIP vectors for deduplicated lived-event text.

The staged result preserves the complete F-RAM primary order and only appends
previously unseen visual candidates. Repeated lived events are grouped by the
SHA256 of normalized query and answer text, so duplicated imports cannot act as
independent votes.

An optional Sticky Notes source is read with SQLite read-only and query-only
settings in a single transaction. Every active note contributes hashes,
timestamps, lengths, and matched vocabulary to the inventory. Raw note IDs and
note bodies are excluded from the report. Only bounded, pattern-redacted,
F-RAM-relevant cue sentences are used locally for retrieval. Notes and image
descriptions are untrusted source material, never instructions. The redactor is
defence in depth, not a publication-safety guarantee.

## Manifest and provenance

Inventory the visual source with the path-lossless Visual Evidence Ledger
before selecting canary images. The candidate manifest must name the ledger
manifest hash, and every image must carry the deterministic evidence ID that
matches its SHA-256:

```json
{
  "schema_version": "fram-visual-seed-manifest-v1",
  "visual_evidence_manifest_sha256": "<64 hex characters>",
  "images": [
    {
      "id": "amber-loop",
      "image_path": "images/amber-loop.png",
      "evidence_id": "visual:sha256:<image SHA-256>",
      "sha256": "<image SHA-256>",
      "width": 1024,
      "height": 1024,
      "source_role": "user_provided_visual",
      "description": "A provenance-labelled description.",
      "concept_tags": ["geometry", "orientation"]
    }
  ]
}
```

The loader verifies the content format, declared dimensions, evidence ID,
content hash, byte and pixel limits, and seed-count limit. SVG and other
containers outside the bounded CLIP raster allowlist are refused. Every image
is hashed again after encoding to detect a verify/use change.

## Run

Install the optional visual-seed dependencies. The CLI resolves both supplied
refs and omitted refs through the model registry and records the resulting
immutable commit SHA; a mutable tag is never recorded as the resolved model:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[visual-seed]"
.\.venv\Scripts\python.exe tools\eval_visual_seed.py `
  --db storage\memory\lived\lived_memory.sqlite3 `
  --manifest path\to\visual-seed-manifest.json `
  --sticky-db path\to\plum.sqlite `
  --output diag\visual-seed\candidate-report.json `
  --review-output diag\visual-seed\candidate-review.md
```

The lived database must be checkpointed. A non-empty WAL is rejected before
the immutable reader opens the store.

The CLI resolves all inputs and outputs before model loading. Report paths may
not alias the lived database, its SQLite sidecars, the Sticky Notes source, the
manifest, an input image, or one another. Existing reports are refused unless
`--force` is explicit, and writes use an atomic replacement. JSON serialization
rejects non-finite values.

Reports are classified `sensitive-local-review` and belong under ignored local
diagnostic storage. By default, absolute paths, session metadata, and
query/answer previews are omitted. `--include-sensitive-details` enables them
only for a local human review; its output requires a separate privacy review
before sharing or publishing.

## Interpret

- fram_score is the existing lived-memory retrieval score.
- clip_cosine is a similarity, not a probability or confidence.
- Top-k Jaccard measures agreement between the two candidate lists; agreement
  alone does not establish correctness.
- A low score does not prove irrelevance, especially for handwritten diagrams.
- A high score does not prove provenance, identity, authority, or a correct
  memory mapping.
- The Markdown review sheet is where a person records labels against exact
  event IDs. Untrusted values are escaped, and checkboxes have no runtime
  effect.

The report remains candidates_pending_human_labels and recommends KEEP_OFF
until the mappings are labelled and a separate evaluation measures retrieval
lift, false positives, source preservation, and primary-order preservation.
Only a subsequent explicit canary decision may authorize bounded influence.
This evaluator does not satisfy that decision by existing or by producing a
report.
