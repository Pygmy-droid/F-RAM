# Connector Ingestion (v2.2)

Read-only connector stubs allow FRAM to harvest external sources into calibration runs without touching runtime retrieval.

- Config: `enable_connector_ingestion`, `connector_max_items`, `connector_refresh_seconds`.
- Registry: `fram_serving/connectors/registry.py` lists sources and returns deterministic fake items (no external calls).
- Harvest: `scripts/harvest_calibration.py` reads connectors when enabled, records counts, and writes `storage/observability/connectors_latest.json`.
- Observability: surfaced in storage summary (`/observability/storage`) and dashboard.
- Tests: `tests/test_connectors_registry.py` exercises fake sources, disable flag, and max-items bounds.
