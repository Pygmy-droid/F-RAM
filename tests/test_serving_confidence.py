from fastapi.testclient import TestClient
import pytest

from fram_serving.app import app
import fram_serving.app as serving_module
from fram_serving.config import FRAMConfig
import fram_core.confidence as conf

pytestmark = pytest.mark.slow


def test_confidence_decision_local(monkeypatch):
    cfg = FRAMConfig()
    monkeypatch.setitem(serving_module.CFG.domain_overrides, "general", {"tau1": cfg.tau1, "tau2": cfg.tau2})

    def fake_logit_conf(_features, coefs=None, temperature=1.0):
        return max(cfg.tau1 + 0.05, 0.95)

    monkeypatch.setattr(conf, "logistic_confidence", fake_logit_conf)

    with TestClient(app) as c:
        r = c.post("/query", json={"text": "quick check"})
        assert r.status_code == 200
        js = r.json()
        decision = js["trace"]["confidence"]["decision"]
        assert decision == "local"


def test_confidence_decision_anchors(monkeypatch):
    cfg = FRAMConfig()
    monkeypatch.setitem(serving_module.CFG.domain_overrides, "general", {"tau1": cfg.tau1, "tau2": cfg.tau2})

    mid_p = (cfg.tau1 + cfg.tau2) / 2.0

    def fake_logit_conf(_features, coefs=None, temperature=1.0):
        return float(mid_p)

    monkeypatch.setattr(conf, "logistic_confidence", fake_logit_conf)

    with TestClient(app) as c:
        r = c.post("/query", json={"text": "quick check"})
        assert r.status_code == 200
        js = r.json()
        decision = js["trace"]["confidence"]["decision"]
        assert decision == "anchors"


def test_confidence_decision_global(monkeypatch):
    cfg = FRAMConfig()
    monkeypatch.setitem(serving_module.CFG.domain_overrides, "general", {"tau1": cfg.tau1, "tau2": cfg.tau2})
    low_p = cfg.tau2 - 0.1 if cfg.tau2 > 0.1 else cfg.tau2 * 0.5

    def fake_logit_conf(_features, coefs=None, temperature=1.0):
        return float(max(0.0, low_p))

    monkeypatch.setattr(conf, "logistic_confidence", fake_logit_conf)

    with TestClient(app) as c:
        r = c.post("/query", json={"text": "quick check"})
        assert r.status_code == 200
        js = r.json()
        decision = js["trace"]["confidence"]["decision"]
        assert decision == "global"

