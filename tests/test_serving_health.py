from fastapi.testclient import TestClient
from fram_serving.app import app

def test_health():
    with TestClient(app) as c:
        r = c.get("/health")
        assert r.status_code == 200
        js = r.json()
        assert js.get("status") == "ok"
