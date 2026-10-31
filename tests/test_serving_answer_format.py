from fastapi.testclient import TestClient
import pytest

import fram_serving.app as app_module


@pytest.mark.slow
def test_answer_preserves_capitalization_and_spacing():
    app_module._DOC_CACHE = None
    app_module._ORCHESTRATOR = None
    with TestClient(app_module.app) as client:
        resp = client.post("/query", json={"text": "coverage"})
        assert resp.status_code == 200
        answer = resp.json()["answer"]

    assert answer
    assert "\n\n" in answer
    assert answer != answer.lower()
