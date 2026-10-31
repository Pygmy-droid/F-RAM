from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Sequence
import numpy as np
from .math_utils import subspace_projection, robust_z, mhd, pairwise_mean_knn_dist


class TemperatureScaler:
    """One-parameter temperature scaling (spec §5.3).

    Fit rescales logits to tighten negative log-likelihood and subsequently
    improves calibration metrics such as ECE.
    """

    def __init__(self) -> None:
        self.T: float = 1.0

    @staticmethod
    def _logits_from_probs(probs: np.ndarray) -> np.ndarray:
        probs = np.clip(probs, 1e-6, 1.0 - 1e-6)
        return np.log(probs) - np.log1p(-probs)

    def fit(self, probs: Sequence[float], labels: Sequence[float]) -> "TemperatureScaler":
        probs_arr = np.asarray(probs, dtype=float)
        labels_arr = np.asarray(labels, dtype=float)
        if probs_arr.size == 0 or labels_arr.size == 0:
            self.T = 1.0
            return self

        logits = self._logits_from_probs(probs_arr)
        if not np.isfinite(logits).all() or np.allclose(logits, 0.0):
            self.T = 1.0
            return self

        w = 1.0  # inverse temperature
        for _ in range(50):
            z = w * logits
            # clip logits to avoid overflow in exp
            z = np.clip(z, -50.0, 50.0)
            p = 1.0 / (1.0 + np.exp(-z))
            grad = np.mean((p - labels_arr) * logits)
            hess = np.mean(p * (1.0 - p) * (logits ** 2))
            if not np.isfinite(grad) or not np.isfinite(hess) or hess <= 0.0:
                break
            step = grad / (hess + 1e-12)
            w_new = w - step
            if w_new <= 0.0 or not np.isfinite(w_new):
                break
            if abs(w_new - w) < 1e-6:
                w = w_new
                break
            w = w_new

        if w <= 0.0 or not np.isfinite(w):
            self.T = 1.0
        else:
            self.T = float(1.0 / w)
        return self

    def transform(self, probs: Sequence[float]) -> np.ndarray:
        probs_arr = np.asarray(probs, dtype=float)
        if probs_arr.size == 0:
            return probs_arr.astype(float)
        logits = self._logits_from_probs(probs_arr)
        logits = np.clip(logits, -20.0, 20.0)
        scaled = logits / max(self.T, 1e-6)
        scaled = np.clip(scaled, -20.0, 20.0)
        probs_scaled = 1.0 / (1.0 + np.exp(-scaled))
        return np.clip(probs_scaled, 1e-3, 1.0 - 1e-3)

@dataclass
class ClusterFeatures:
    Delta_d_z: float
    rho_pos: float
    mhd: float
    d_c_z: float
    fresh: float

def compute_features(
    e: np.ndarray,
    p_k: np.ndarray,
    U_k: np.ndarray,
    kNN_neighbors: np.ndarray,
    medians: dict,
    mads: dict,
    T_q: float,
    T_k_median: float,
    tau_domain: float,
) -> ClusterFeatures:
    """Compute the calibrated feature bundle (numbers only, no learning here)."""
    mu_k = subspace_projection(e, p_k, U_k)
    Delta_d = float(np.dot(e - p_k, e - p_k) - np.dot(mu_k - p_k, mu_k - p_k))
    mean_kNN = pairwise_mean_knn_dist(mu_k, kNN_neighbors)
    if not np.isfinite(mean_kNN):
        mean_kNN = float(medians.get("mean_kNN", 0.0))
    rho_pos = -robust_z(mean_kNN, medians.get("mean_kNN", 0.0), mads.get("mean_kNN", 1.0))
    mhd_val = mhd(e, p_k, U_k)
    d_c = np.linalg.norm(e - p_k)
    d_c_z = robust_z(d_c, medians.get("dc", 0.0), mads.get("dc", 1.0))
    fresh = float(np.exp(-abs(T_q - T_k_median) / (tau_domain if tau_domain > 0 else 1.0)))
    return ClusterFeatures(Delta_d_z=robust_z(Delta_d, medians.get("Delta_d", 0.0), mads.get("Delta_d", 1.0)),
                           rho_pos=float(rho_pos),
                           mhd=float(mhd_val),
                           d_c_z=float(d_c_z),
                           fresh=float(fresh))

def logistic_confidence(features: ClusterFeatures, coefs: dict, temperature: float = 1.0) -> float:
    """Simple logistic model with temperature scaling (placeholder).
    coefs must contain keys: a, b, c, g, h, d (bias)."""
    delta = float(np.clip(features.Delta_d_z, -10.0, 10.0))
    rho = float(np.clip(features.rho_pos, -10.0, 10.0))
    mhd_val = float(np.clip(features.mhd, 0.0, 1.0))
    dc = float(np.clip(features.d_c_z, -10.0, 10.0))
    fresh = float(np.clip(features.fresh, 0.0, 1.0))

    z = (
        coefs.get("a", 1.0) * delta
        + coefs.get("b", 1.0) * rho
        + coefs.get("c", 1.0) * mhd_val
        - coefs.get("g", 1.0) * dc
        + coefs.get("h", 1.0) * fresh
        + coefs.get("d", 0.0)
    )
    # temperature scaling on logits: divide z by T
    z = z / max(temperature, 1e-6)
    z = np.clip(z, -20.0, 20.0)
    # sigmoid
    p = 1.0 / (1.0 + np.exp(-z))
    return float(np.clip(p, 1e-3, 1.0 - 1e-3))

def conformal_policy(p_temp: float, tau1: float, tau2: float) -> str:
    """Return 'local' (no widen), 'anchors' (multi-anchor), or 'global' (fallback)."""
    if p_temp >= tau1:
        return "local"
    if p_temp >= tau2:
        return "anchors"
    return "global"


def reliability_bins(
    probs: Sequence[float], labels: Sequence[float], n_bins: int = 15
) -> dict:
    """Return expected calibration error diagnostics (spec §5.3)."""

    probs_arr = np.asarray(probs, dtype=float)
    labels_arr = np.asarray(labels, dtype=float)
    total = probs_arr.size
    if total == 0 or labels_arr.size == 0:
        return {"ece": 0.0, "bins": []}

    edges = np.linspace(0.0, 1.0, num=n_bins + 1)
    bins: list[dict[str, float]] = []
    ece = 0.0
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        if i == n_bins - 1:
            mask = (probs_arr >= lo) & (probs_arr <= hi)
        else:
            mask = (probs_arr >= lo) & (probs_arr < hi)
        count = int(mask.sum())
        if count == 0:
            bin_prob = (lo + hi) / 2.0
            acc = 0.0
            prop = 0.0
        else:
            bin_prob = float(np.mean(probs_arr[mask]))
            acc = float(np.mean(labels_arr[mask]))
            prop = count / total
            ece += prop * abs(acc - bin_prob)
        bins.append({"p_mid": float(bin_prob), "acc": float(acc), "prop": float(prop)})
    return {"ece": float(ece), "bins": bins}


def conformal_thresholds(
    probs: Sequence[float],
    labels: Sequence[float],
    alpha1: float = 0.01,
    alpha2: float = 0.003,
) -> tuple[float, float]:
    """Fit temperature scaling and derive conformal thresholds (spec §5.3)."""

    probs_arr = np.asarray(probs, dtype=float)
    labels_arr = np.asarray(labels, dtype=float)
    if probs_arr.size == 0 or labels_arr.size == 0:
        return 1.0, 0.5

    scaler = TemperatureScaler().fit(probs_arr, labels_arr)
    calibrated = scaler.transform(probs_arr)
    scores = 1.0 - calibrated
    scores = np.clip(scores, 0.0, 1.0)
    n = scores.size

    def _quantile(alpha: float) -> float:
        if n == 0:
            return 0.0
        level = min(max(1.0 - alpha, 0.0), 1.0)
        rank = int(np.ceil((n + 1) * level)) - 1
        rank = min(max(rank, 0), n - 1)
        return float(np.sort(scores)[rank])

    q1 = _quantile(alpha1)
    q2 = _quantile(alpha2)
    tau1 = float(np.clip(1.0 - q1, 1e-6, 1.0 - 1e-6))
    tau2 = float(np.clip(1.0 - q2, 1e-6, 1.0 - 1e-6))
    if tau2 >= tau1:
        tau2 = max(1e-6, tau1 - 1e-6)
    return tau1, tau2
