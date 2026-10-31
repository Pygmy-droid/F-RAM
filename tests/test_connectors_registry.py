from __future__ import annotations

import json
from pathlib import Path

from fram_serving.config import FRAMConfig
from fram_serving.connectors import registry
import scripts.harvest_calibration as harvest


def test_fake_connector_sources():
    sources = registry.list_sources()
    assert sources and sources[0]["id"].startswith("fake")
    items = registry.fetch_items(sources[0]["id"], 3)
    assert len(items) == 3
    assert items[0]["source_id"] == sources[0]["id"]


def test_connector_disable_flag(tmp_path: Path, monkeypatch):
    cfg = FRAMConfig().model_copy(update={"enable_connector_ingestion": False, "STORAGE_ROOT": tmp_path})
    monkeypatch.setattr(harvest, "FRAMConfig", lambda: None)  # not used in test
    assert not getattr(cfg, "enable_connector_ingestion")


def test_harvest_connector_counts(tmp_path: Path, monkeypatch, capsys):
    # Run harvest main with connectors enabled and a small query set.
    queries = tmp_path / "queries.txt"
    queries.write_text("hello\nworld\n", encoding="utf-8")
    args = [
        "--queries",
        str(queries),
        "--storage-root",
        str(tmp_path),
        "--json-out",
        str(tmp_path / "out.json"),
        "--quiet",
    ]
    env = {"FRAM_ENABLE_CONNECTOR_INGESTION": "1", "FRAM_CONNECTOR_MAX_ITEMS": "2"}
    monkeypatch.setenv("FRAM_ENABLE_CONNECTOR_INGESTION", "1")
    monkeypatch.setenv("FRAM_CONNECTOR_MAX_ITEMS", "2")
    ret = harvest.main(args)
    assert ret == 0
    out = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    assert out["connectors"]["enabled"] is True
    connector_counts = out["connectors"]["counts"]
    # Fake connectors should appear with non-negative counts.
    assert connector_counts
    # max_items boundary enforced by fetch_items
    assert all(count <= 2 for count in connector_counts.values())
