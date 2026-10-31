"""Soft-DTW's negative self-cost must not invert distance-to-score ordering."""

import numpy as np
import pytest

from fram_serving.fractal_memory import soft_dtw_distance, soft_dtw_similarity


def test_actual_identical_path_beats_perturbations_across_old_pole():
    path = np.zeros((16, 6))
    distances = np.array(
        [soft_dtw_distance(path, path + shift) for shift in (0, 0.03, 0.1, 0.2)]
    )
    assert distances[0] < -1 < distances[-1]
    assert np.all(np.diff(distances) > 0)
    old_scores = 1.0 / (1.0 + distances)
    assert np.argmax(old_scores) != 0  # Reproduces the previous defect.
    scores = soft_dtw_similarity(distances)
    assert np.all(np.diff(scores) < 0)
    assert np.argmax(scores) == 0


@pytest.mark.parametrize("distance", [0.0, 0.01, 1.0, 10.0, 1e12])
def test_nonnegative_contract_is_unchanged(distance):
    assert soft_dtw_similarity(distance) == 1.0 / (1.0 + distance)


def test_no_pole_and_continuity_at_zero():
    distances = np.array([-1e6, -2, -1.00001, -1, -0.99999, -1e-9, 0, 1e-9, 10])
    scores = soft_dtw_similarity(distances)
    assert np.isfinite(scores).all()
    assert ((0 < scores) & (scores < 2)).all()
    assert np.all(np.diff(scores) < 0)
    assert abs(scores[5] - scores[7]) < 3e-9


def test_nonfinite_distances_receive_no_positive_evidence():
    np.testing.assert_array_equal(
        soft_dtw_similarity(np.array([np.nan, np.inf, -np.inf])), [0, 0, 0]
    )
