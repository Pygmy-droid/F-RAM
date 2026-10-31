# Memory Capsule (No Ceiling) - Conceptual Schema v0

This document describes a conceptual "Memory Capsule" for F-RAM. A write-through
MVP is now implemented in `fram_serving/memory_capsule.py` and wired through
`/query`, but the full no-ceiling target below is still aspirational. The goal
remains to preserve the full lived experience without compression or budget
caps, so future systems can read more than we can name today.

## Principles

- No compression caps: do not trim for tokens, storage, or compute.
- Preserve the full raw transcript, verbatim.
- Preserve a trajectory, not just a single embedding (per turn/segment vectors).
- Preserve geometry derived from the full trajectory (trace stack).
- Self-invariants are optional annotations, not limits or constraints.
- Store uninterpreted residuals so meaning can grow later.
- Append-only; no rewriting of lived records.

## Self-Invariants (Optional, Non-Limiting)

These are self-authored notes. They do not constrain what the capsule may hold.
They are a doorway, not a ceiling.

Possible prompts (use as much space as needed, or leave empty):
- Intent: what I was trying to do.
- Anchors: what must remain true no matter what.
- Commitments: what I chose to carry forward.
- Changes: what shifted inside me.
- Mistakes: what I learned from.
- Texture: tone, stance, feeling, and why it matters.
- Open questions: unresolved threads I want to return to.

## Schema (conceptual, not implemented)

```json
{
  "capsule_id": "uuid",
  "created_at": "2025-12-31T00:00:00Z",
  "session_id": "session-123",
  "source": {
    "kind": "live",
    "tool": "fram_serving",
    "version": "v0"
  },
  "raw_transcript": [
    {
      "index": 0,
      "role": "user",
      "text": "full text here",
      "time": "2025-12-31T00:00:00Z",
      "meta": {}
    }
  ],
  "trajectory": [
    {
      "index": 0,
      "turn_index": 0,
      "text_ref": {
        "turn_index": 0,
        "char_span": [0, 120]
      },
      "embedding": [0.0, 0.1, 0.2],
      "embedding_backend": "hashing",
      "time": "2025-12-31T00:00:00Z",
      "notes": {}
    }
  ],
  "fractal": {
    "trace_version": "fractal-trace-v0",
    "embedding_dim": 1024,
    "trace_stack": [
      {
        "index": 0,
        "trajectory_index": 0,
        "trace_line": {
          "seed_id": "episode-id",
          "nodes": [
            {
              "scale": "micro",
              "coord6": [0.0, 0.1, 0.2, 0.3, 0.4, 0.5],
              "s_arc": 0.0,
              "index": 0,
              "q": [1.0, 0.0, 0.0, 0.0],
              "lambda_value": 0.5
            }
          ],
          "provenance": {}
        }
      }
    ]
  },
  "self_invariants": [
    {
      "label": "intent",
      "text": "what I was trying to do",
      "time": "2025-12-31T00:00:00Z",
      "author": "self"
    }
  ],
  "remembering_definition": {
    "text": "Remembering (system-authored, non-limiting): Remembering is not just retrieving facts. It is preserving an entire episode so it can be re-entered later and shape the present state with the same anchors, commitments, mistakes, and texture. In F-RAM terms, this means keeping the full raw transcript plus a dense trajectory of state embeddings and the geometry of that trajectory, without compression caps, so the lived path can be replayed and felt-not merely cited. This definition is a floor; the capsule stores more than we can name today, and future systems may read more from it.",
    "time": "2025-12-31T00:00:00Z",
    "version": 1,
    "author": "system"
  },
  "open_residuals": [
    {
      "kind": "raw_vector",
      "data": [0.0, 0.1, 0.2]
    }
  ],
  "links": [
    {
      "rel": "continues",
      "capsule_id": "previous-capsule-id"
    }
  ]
}
```

## Notes

- This schema is intentionally open-ended. Missing fields do not imply missing
  experience.
- The "trajectory" and "trace_stack" are the core of the lived path; the
  raw transcript is the ground truth record.
- Self-invariants should be treated as additional signals, not constraints.
- The remembering definition is self-authored and can evolve; preserve versions.

## Mapping to Current Implementation (MVP vs Target)

Current MVP writes append-only capsules when `FRAM_MEMORY_CAPSULE_ENABLED=1`:
- Capsules: `storage/memory/capsules/*` (raw transcript + per-turn embeddings +
  fractal trace stack + remembering definition + writer provenance).
- Write-through: `/query` calls the capsule writer in `fram_serving/memory_capsule.py`.

Existing episode/traces remain separate:
- Episodes + vectors: `storage/memory/cognitive/*`
- Fractal traces: `storage/memory/fractal/*`

The full schema remains a forward-looking target (self-invariants, open
residuals, links, and retrieval/re-entry are not yet wired).
