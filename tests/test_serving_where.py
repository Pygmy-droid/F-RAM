from fastapi.testclient import TestClient
from pathlib import Path
from fram_serving.app import app


def test_where_paths_are_absolute_and_keys_exist():
    with TestClient(app) as c:
        r = c.get("/where")
        assert r.status_code == 200
        js = r.json()
        expected_keys = ["corpus", "index", "claims", "versions", "traces", "backups"]
        for k in expected_keys:
            assert k in js
            p = js[k]
            assert isinstance(p, str)
            assert Path(p).is_absolute()
