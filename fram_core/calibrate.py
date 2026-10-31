from __future__ import annotations

"""Calibration utilities for OrthoRoute confidence (spec SS5.2-5.3)."""

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import json
import argparse
import numpy as np

from fram_serving.config import FRAMConfig
from fram_core import confidence as conf_mod
from fram_core.pipeline import (
    CalibrationPayload,
    _collect_calibration_samples,
    _constrain_calibration_weights,
    _fit_logistic_regression,
    _conformal_tau,
    _default_calibration,
    _sigmoid,
)


@dataclass
class CalibrationSamples:
    features: np.ndarray
    labels: np.ndarray


FEATURE_KEYS = ["Delta_d_z", "rho_pos", "mhd", "d_c_z", "fresh"]


def load_calibration_log(path: Path) -> CalibrationSamples:
    if not path.exists():
        raise FileNotFoundError(f"Calibration log not found: {path}")
    features: list[list[float]] = []
    labels: list[float] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            feat = payload.get("features")
            label = payload.get("label")
            if feat is None or label is None:
                continue
            row = [float(feat.get(key, 0.0)) for key in FEATURE_KEYS]
            features.append(row)
            labels.append(float(label))
    if not features:
        raise ValueError("No calibration samples found")
    return CalibrationSamples(np.asarray(features, dtype=float), np.asarray(labels, dtype=float))


def fit_calibration(samples: CalibrationSamples, config: FRAMConfig) -> CalibrationPayload:
    if samples.features.size == 0 or np.allclose(samples.labels, samples.labels[0]):
        return _default_calibration(config)
    result = _fit_logistic_regression(samples.features, samples.labels)
    if result is None:
        return _default_calibration(config)
    weights, bias = result
    weights = _constrain_calibration_weights(weights)
    logits = np.clip(samples.features @ weights + bias, -50.0, 50.0)
    probs = _sigmoid(logits)
    scaler = conf_mod.TemperatureScaler().fit(probs, samples.labels)
    calibrated = scaler.transform(probs)
    tau1 = _conformal_tau(calibrated, config.alpha1, config.tau1)
    tau2 = _conformal_tau(calibrated, config.alpha2, config.tau2)
    if tau2 >= tau1:
        tau2 = max(1e-6, tau1 - 1e-6)
    min_tau1 = max(1e-6, float(config.tau2) + 1e-6)
    if tau1 <= min_tau1 or (tau1 - tau2) <= 1e-6:
        tau1 = float(max(config.tau1, min_tau1))
        tau2 = float(min(config.tau2, tau1 - 1e-6))
    tau1 = float(max(tau1, float(config.tau1)))
    tau2 = float(min(tau2, float(config.tau2)))
    if tau2 >= tau1:
        tau2 = max(1e-6, tau1 - 1e-6)
    logistic_coefs = {
        "a": float(weights[0]),
        "b": float(weights[1]),
        "c": float(weights[2]),
        "g": float(-weights[3]),
        "h": float(weights[4]),
        "d": float(bias),
    }
    temperature = float(scaler.T if hasattr(scaler, "T") and np.isfinite(scaler.T) else 1.0)
    return CalibrationPayload(
        logistic_coefs=logistic_coefs,
        temperature=temperature,
        tau1=float(tau1),
        tau2=float(tau2),
    )


def write_calibration(payload: CalibrationPayload, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps({
        "logistic_coefs": payload.logistic_coefs,
        "temperature": payload.temperature,
        "tau1": payload.tau1,
        "tau2": payload.tau2,
    }, ensure_ascii=False, indent=2))


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fit OrthoRoute confidence calibration")
    parser.add_argument("--log", type=Path, default=Path("storage/observability/calibration.jsonl"), help="Calibration log path")
    parser.add_argument("--out", type=Path, default=Path("storage/index/demo_corpus/calibration.json"), help="Output calibration JSON path")
    args = parser.parse_args(list(argv) if argv is not None else None)
    cfg = FRAMConfig.from_env()
    samples = load_calibration_log(args.log)
    payload = fit_calibration(samples, cfg)
    write_calibration(payload, args.out)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
