from fastapi.testclient import TestClient
import pytest

import fram_serving.app as app_module


@pytest.mark.slow
def test_query_indexes_csv_tables(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    csv_path = data_dir / "inventory.csv"
    csv_path.write_text("Product,Price,Qty\nWidget,10,5\nGadget,20,2\n", encoding="utf-8")

    monkeypatch.setattr(app_module, "DATA_ROOT", data_dir)
    app_module._DOC_CACHE = None
    app_module._ORCHESTRATOR = None

    with TestClient(app_module.app) as client:
        resp = client.post("/query", json={"text": "Price"})
        assert resp.status_code == 200
        payload = resp.json()

    assert any("inventory.csv" in citation for citation in payload["citations"])
    coverage = payload["trace"]["coverage"]
    assert any(fact.startswith("Price=") for fact in coverage.get("distinct_facts", []))

    app_module._DOC_CACHE = None
    app_module._ORCHESTRATOR = None
