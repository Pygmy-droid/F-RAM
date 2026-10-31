from fastapi.testclient import TestClient
import pytest

import fram_serving.app as app_module


@pytest.mark.slow
def test_reranker_pairs_cost(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    csv_path = data_dir / "inventory.csv"
    rows = [
        "Product,Price,Qty",
        "Widget,10,5",
        "Gadget,20,2",
        "Thing,30,1",
        "Device,40,8",
        "Tool,50,3",
    ]
    csv_path.write_text("\n".join(rows), encoding="utf-8")

    monkeypatch.setattr(app_module, "DATA_ROOT", data_dir)
    app_module._DOC_CACHE = None
    app_module._ORCHESTRATOR = None

    with TestClient(app_module.app) as client:
        resp = client.post("/query", json={"text": "Price"})
        assert resp.status_code == 200
        payload = resp.json()

    budgets = payload["trace"]["selection"]["budgets"]
    pair_count = budgets.get("reranker_pairs", 0.0)
    assert pair_count >= 3
    expected_pairs = app_module.CFG.pairs_scale * pair_count
    assert budgets["pairs"] >= expected_pairs
    expected_pair_cost = app_module.CFG.lambda_rerank * expected_pairs
    assert budgets["cost"] >= expected_pair_cost

    app_module._DOC_CACHE = None
    app_module._ORCHESTRATOR = None
