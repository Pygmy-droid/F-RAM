from fastapi.testclient import TestClient

from fram_serving.app import app


def test_memory_ui_served():
    with TestClient(app) as client:
        resp = client.get("/ui/memory")
    assert resp.status_code == 200
    html = resp.text
    assert "FRAM Working-Memory Sessions" in html
    assert "/memory" in html
    assert "loadSessions" in html
    assert "Cognitive Seeds" in html
    assert "Cognitive Seeding" in html
