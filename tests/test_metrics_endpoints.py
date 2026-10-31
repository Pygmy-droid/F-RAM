import math

from fastapi.testclient import TestClient

from fram_serving.app import app, CFG, REL, ALM, _PROB_CACHE, _store_prob


def test_metrics_pipeline_exposes_reliability_stats():
    REL.clear()
    _PROB_CACHE.clear()
    ALM.evaluate(REL, CFG.tau1, CFG.tau2)

    _store_prob("calibration-flow", 0.82)
    _store_prob("second-calibration", 0.31)
    REL.update("calibration-flow", 0.82, 1)
    REL.update("second-calibration", 0.31, 0)
    ALM.evaluate(REL, CFG.tau1, CFG.tau2)

    with TestClient(app) as client:
        metrics = client.get("/metrics")
        assert metrics.status_code == 200
        payload = metrics.json()

    expected_keys = {
        "ece",
        "tau1",
        "tau2",
        "alpha1",
        "alpha2",
        "fn_rate_at_tau1",
        "fn_rate_at_tau2",
        "window_size",
        "window_max",
        "window",
        "last_update",
        "bins",
        "config",
        "alarms",
    }
    assert expected_keys.issubset(payload.keys())
    assert math.isfinite(payload["ece"])
    assert math.isfinite(payload["fn_rate_at_tau1"])
    assert math.isfinite(payload["fn_rate_at_tau2"])
    assert isinstance(payload["alarms"], dict)
    assert payload["window"] == int(CFG.metrics_window)
    assert isinstance(payload["last_update"], str) and payload["last_update"]
    assert isinstance(payload["bins"], list) and payload["bins"]
    for bin_entry in payload["bins"]:
        assert {"p_mid", "acc", "prop"}.issubset(bin_entry.keys())
    config_block = payload["config"]
    assert {"lambda_tok", "lambda_rerank", "pairs_scale", "coverage_gamma", "coverage_u_max"}.issubset(
        config_block.keys()
    )
    assert math.isclose(config_block["lambda_tok"], CFG.lambda_tok)
    assert math.isclose(config_block["lambda_rerank"], CFG.lambda_rerank)
    assert math.isclose(config_block["pairs_scale"], CFG.pairs_scale)
    assert math.isclose(config_block["coverage_gamma"], CFG.coverage_gamma)
    assert config_block["coverage_u_max"] == CFG.coverage_u_max
