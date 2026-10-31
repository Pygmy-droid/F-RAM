# Publish Snapshot (2026-01-21)

Purpose: provide a publish-safe, frozen reference set of evaluation artifacts,
policy statements, and redacted traces without exposing internal mechanics.

Snapshot location
- artifacts/publish/2026-01-21/

Included
- Evaluation artifacts (memory + shadow + fractal reports)
- Policy summary (default-off gating posture)
- Redacted trace summary and sample
- Publish-safe PDF summary (FRAM_publish_snapshot_2026-01-21.pdf)
- manifest.json with checksums and provenance commands

Excluded
- Internal mechanics, routing heuristics, and raw trace JSONL
- Private configuration values or raw observability logs
- Source code or datasets

Verification
- Use artifacts/publish/2026-01-21/manifest.json for checksums and provenance.
