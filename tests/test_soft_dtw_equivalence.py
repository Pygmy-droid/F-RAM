"""Parity with the scalar recurrence preserved before the acceleration."""

from __future__ import annotations

import numpy as np
import pytest

from fram_serving.fractal_memory.metrics import (
    min_max_normalize,
    soft_dtw_distance,
)


def scalar_soft_dtw_reference(
    path_a: np.ndarray,
    path_b: np.ndarray,
    *,
    gamma: float = 0.1,
    band: float | None = 0.15,
) -> float:
    """Unchanged scalar algorithm from H1 e9f0537, for regression comparison."""
    seq_a = np.asarray(path_a, dtype=np.float64)
    seq_b = np.asarray(path_b, dtype=np.float64)
    if seq_a.ndim != 2 or seq_b.ndim != 2:
        raise ValueError("paths must be 2-D arrays (steps x dims)")
    if seq_a.shape[0] == 0 or seq_b.shape[0] == 0:
        return float("inf")
    if seq_a.shape[1] != seq_b.shape[1]:
        raise ValueError("paths must share dimensionality")
    n, m = seq_a.shape[0], seq_b.shape[0]
    diff = seq_a[:, None, :] - seq_b[None, :, :]
    cost = np.einsum("ijk,ijk->ij", diff, diff, optimize=True)
    r = np.full((n + 1, m + 1), np.inf, dtype=np.float64)
    r[0, 0] = 0.0
    band_width = None
    if band is not None:
        band_width = max(1, int(band * max(n, m)))
    for i in range(1, n + 1):
        j_start = 1
        j_stop = m + 1
        if band_width is not None:
            center = int((i - 1) * (m / max(n, 1)))
            j_start = max(1, center - band_width)
            j_stop = min(m + 1, center + band_width + 1)
        for j in range(j_start, j_stop):
            prev = np.array(
                [r[i - 1, j], r[i, j - 1], r[i - 1, j - 1]],
                dtype=np.float64,
            )
            v = -prev / gamma
            vmax = float(np.max(v))
            softmin = -gamma * (vmax + np.log(np.exp(v - vmax).sum()))
            r[i, j] = cost[i - 1, j - 1] + softmin
    return float(r[n, m])


@pytest.mark.parametrize(
    "lengths", [(1, 1), (1, 7), (7, 1), (9, 14), (14, 9), (32, 32)]
)
@pytest.mark.parametrize("band", [None, 0.0, 0.15, 0.5, 1.0])
@pytest.mark.parametrize("gamma", [0.001, 0.1, 1.0, 10.0])
def test_scalar_equivalence_across_shapes_bands_and_smoothing(lengths, band, gamma):
    rng = np.random.default_rng(817)
    a = rng.normal(size=(lengths[0], 6))
    b = rng.normal(size=(lengths[1], 6))
    # The historical algorithm can produce NaN for an unreachable narrow band.
    # Preserve this behavior here; changing it is not part of an acceleration.
    with np.errstate(all="ignore"):
        expected = scalar_soft_dtw_reference(a, b, band=band, gamma=gamma)
        actual = soft_dtw_distance(a, b, band=band, gamma=gamma)
    np.testing.assert_allclose(actual, expected, rtol=1e-13, atol=1e-13, equal_nan=True)


@pytest.mark.parametrize(
    "a,b",
    [
        (np.empty((0, 6)), np.ones((3, 6))),
        (np.ones((3, 6)), np.empty((0, 6))),
        (np.empty((0, 4)), np.ones((3, 6))),
        (np.zeros((8, 6)), np.zeros((8, 6))),
        (np.ones((8, 6)), np.ones((8, 6))),
        (np.arange(60, dtype=np.float32).reshape(10, 6)[::2], np.ones((7, 6))),
        (np.full((3, 6), np.nan), np.ones((3, 6))),
        (np.full((3, 6), np.inf), np.ones((3, 6))),
    ],
)
def test_scalar_equivalence_for_empty_degenerate_and_nonfinite_paths(a, b):
    with np.errstate(all="ignore"):
        expected = scalar_soft_dtw_reference(a, b)
        actual = soft_dtw_distance(a, b)
    np.testing.assert_allclose(actual, expected, rtol=1e-13, atol=1e-13, equal_nan=True)


@pytest.mark.parametrize("gamma", [0.0, -0.1, np.inf, np.nan])
def test_preserves_existing_nonstandard_gamma_behavior(gamma):
    a = np.arange(24, dtype=float).reshape(4, 6)
    with np.errstate(all="ignore"):
        expected = scalar_soft_dtw_reference(a, a + 0.25, gamma=gamma)
        actual = soft_dtw_distance(a, a + 0.25, gamma=gamma)
    np.testing.assert_allclose(actual, expected, rtol=1e-13, atol=1e-13, equal_nan=True)


@pytest.mark.parametrize(
    "a,b,message",
    [
        (np.ones(6), np.ones((2, 6)), "paths must be 2-D arrays"),
        (np.ones((2, 6)), np.ones(6), "paths must be 2-D arrays"),
        (np.ones((2, 4)), np.ones((2, 6)), "paths must share dimensionality"),
    ],
)
def test_validation_errors_unchanged(a, b, message):
    for implementation in (scalar_soft_dtw_reference, soft_dtw_distance):
        with pytest.raises(ValueError, match=message):
            implementation(a, b)


def test_default_256_node_scores_and_candidate_ranking_are_unchanged():
    rng = np.random.default_rng(606)
    query = rng.normal(scale=0.1, size=(256, 6)).cumsum(axis=0)
    candidates = [
        query.copy(),
        query + rng.normal(scale=0.05, size=query.shape),
        query + 0.25,
        query[::-1].copy(),
        rng.normal(size=query.shape),
    ]
    reference = np.array(
        [scalar_soft_dtw_reference(query, path) for path in candidates]
    )
    accelerated = np.array([soft_dtw_distance(query, path) for path in candidates])
    np.testing.assert_allclose(accelerated, reference, rtol=1e-13, atol=1e-13)
    reference_scores = min_max_normalize(1.0 / (1.0 + reference))
    accelerated_scores = min_max_normalize(1.0 / (1.0 + accelerated))
    np.testing.assert_allclose(
        accelerated_scores, reference_scores, rtol=1e-13, atol=1e-13
    )
    np.testing.assert_array_equal(
        np.argsort(-accelerated_scores, kind="stable"),
        np.argsort(-reference_scores, kind="stable"),
    )
