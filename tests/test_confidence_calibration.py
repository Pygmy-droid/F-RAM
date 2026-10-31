import numpy as np

from fram_core.confidence import (
    TemperatureScaler,
    compute_features,
    logistic_confidence,
    reliability_bins,
    conformal_thresholds,
)


def _nll(labels: np.ndarray, probs: np.ndarray) -> float:
    eps = 1e-8
    clipped = np.clip(probs, eps, 1.0 - eps)
    return float(-np.mean(labels * np.log(clipped) + (1.0 - labels) * np.log(1.0 - clipped)))


def test_temperature_scaler_reduces_nll_and_ece():
    probs = np.array([0.95, 0.9, 0.85, 0.8, 0.75, 0.7, 0.4, 0.35, 0.3, 0.25, 0.2, 0.15], dtype=float)
    labels = np.array([1, 1, 1, 1, 0, 0, 1, 0, 0, 0, 0, 0], dtype=float)

    scaler = TemperatureScaler().fit(probs, labels)
    scaled = scaler.transform(probs)

    assert scaler.T > 0
    assert _nll(labels, scaled) < _nll(labels, probs)

    raw_ece = reliability_bins(probs, labels)["ece"]
    scaled_ece = reliability_bins(scaled, labels)["ece"]
    assert scaled_ece < raw_ece

    tau1, tau2 = conformal_thresholds(probs, labels)
    assert 0.0 < tau2 < tau1 < 1.0


def test_compute_features_handles_empty_neighbors():
    e = np.array([0.0, 0.0, 0.0])
    p_k = np.array([0.1, -0.2, 0.3])
    U_k = np.zeros((3, 0))
    neighbors = np.zeros((0, 3))
    medians = {"mean_kNN": 0.0, "Delta_d": 0.0, "dc": 0.0}
    mads = {"mean_kNN": 1.0, "Delta_d": 1.0, "dc": 1.0}

    feats = compute_features(
        e=e,
        p_k=p_k,
        U_k=U_k,
        kNN_neighbors=neighbors,
        medians=medians,
        mads=mads,
        T_q=0.0,
        T_k_median=0.0,
        tau_domain=1.0,
    )

    for value in feats.__dict__.values():
        assert np.isfinite(value)

    prob = logistic_confidence(
        feats,
        {"a": 1.0, "b": 1.0, "c": 1.0, "g": 1.0, "h": 1.0, "d": 0.0},
    )
    assert np.isfinite(prob)
    assert 0.0 <= prob <= 1.0
