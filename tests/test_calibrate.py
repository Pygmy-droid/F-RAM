import json
from pathlib import Path

import numpy as np
import pytest

from fram_core.calibrate import load_calibration_log, fit_calibration, write_calibration
from fram_serving.config import FRAMConfig


def test_load_calibration_log(tmp_path: Path) -> None:
    log = tmp_path / "calibration.jsonl"
    lines = [
        '{"features": {"Delta_d_z": 0.1, "rho_pos": 0.2, "mhd": 0.3, "d_c_z": -0.4, "fresh": 0.9}, "label": 1}',
        '{"features": {"Delta_d_z": -0.2, "rho_pos": -0.1, "mhd": 0.1, "d_c_z": 0.2, "fresh": 0.5}, "label": 0}',
    ]
    log.write_text('\n'.join(lines))
    samples = load_calibration_log(log)
    assert samples.features.shape == (2, 5)
    assert samples.labels.tolist() == [1.0, 0.0]


def test_fit_calibration_and_write(tmp_path: Path) -> None:
    log = tmp_path / "calibration.jsonl"
    rows = []
    rng = np.random.default_rng(42)
    for _ in range(50):
        feats = rng.normal(size=5)
        label = 1 if feats[0] + 0.5 * feats[1] - 0.4 * feats[3] > 0 else 0
        rows.append(json.dumps({
            "features": {
                "Delta_d_z": float(feats[0]),
                "rho_pos": float(feats[1]),
                "mhd": float(feats[2]),
                "d_c_z": float(feats[3]),
                "fresh": float(feats[4]),
            },
            "label": label,
        }))
    log.write_text('\n'.join(rows))
    samples = load_calibration_log(log)
    cfg = FRAMConfig()
    payload = fit_calibration(samples, cfg)
    assert payload.logistic_coefs
    assert payload.logistic_coefs["g"] >= 0.0
    out = tmp_path / "calibration.json"
    write_calibration(payload, out)
    parsed = json.loads(out.read_text())
    assert parsed['tau1'] >= parsed['tau2']
