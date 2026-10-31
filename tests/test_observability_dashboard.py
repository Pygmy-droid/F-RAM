from __future__ import annotations

from fastapi.testclient import TestClient

import fram_serving.app as app


def test_observability_dashboard_html():
    client = TestClient(app.app)
    resp = client.get("/observability/dashboard")
    assert resp.status_code == 200
    assert "Observability Dashboard" in resp.text
