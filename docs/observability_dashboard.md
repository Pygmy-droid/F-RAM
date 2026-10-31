# Observability Dashboard (v2.2)

Endpoint: `/observability/dashboard` (HTML).

Aggregates:
- `/observability/storage` (active/archive sizes, compaction/archive meta, snapshots, connectors)
- `/observability/calibration` (latest calibration run meta)
- `/observability/as_of` (recent as-of filters: active_nodes, dropped counts, delta snippet previews)
- `/observability/phase_d_memory` (includes ANN bridge when enabled)
- `/observability/summary` (trace metrics)

Template: `fram_serving/templates/observability_dashboard.html` (no charts; structured JSON blocks).

Storage summary also exposes connector meta (`connectors_latest.json`) and snapshots; calibration meta from `calibration_latest.json`.

## As-of observability
- Trace block `as_of_filter` now includes {as_of, active_nodes, dropped_candidates} when queries specify as-of(T).
- Delta snippets (`version_id`, `parent_id`, `diff`) appear in responses/trace when serving older snapshots to highlight lattice diffs.

