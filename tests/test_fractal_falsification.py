from __future__ import annotations

import numpy as np
import pytest

from fram_eval.fractal_falsification import (
    _normalize_trajectory,
    aggregate_seed_results,
    generate_trajectories,
    rankdata,
    simulate_aizawa,
    spearman_rho,
    topk_accuracy,
)


def test_rankdata_ties() -> None:
    values = [10.0, 20.0, 20.0, 30.0]
    ranks = rankdata(values)
    assert np.allclose(ranks, np.array([1.0, 2.5, 2.5, 4.0]))


def test_spearman_rho_identity() -> None:
    data = [1.0, 2.0, 3.0, 4.0]
    assert np.isclose(spearman_rho(data, data), 1.0)


def test_spearman_rho_reverse() -> None:
    a = [1.0, 2.0, 3.0, 4.0]
    b = list(reversed(a))
    assert np.isclose(spearman_rho(a, b), -1.0)


def test_topk_accuracy_hit_rate() -> None:
    true_dists = np.array(
        [
            [0.0, 1.0, 2.0],
            [1.0, 0.0, 0.1],
            [2.0, 0.1, 0.0],
        ],
        dtype=float,
    )
    scores = np.array(
        [
            [0.0, 0.9, 0.1],
            [0.1, 0.0, 0.8],
            [0.2, 0.7, 0.0],
        ],
        dtype=float,
    )
    assert np.isclose(topk_accuracy(true_dists, scores, k=1), 1.0)


def test_normalize_handles_nonfinite() -> None:
    traj = np.array([[0.0, 1.0], [np.inf, np.nan]], dtype=float)
    normalized = _normalize_trajectory(traj)
    assert np.isfinite(normalized).all()


def test_aggregate_seed_results_mean() -> None:
    seed_results = [
        {
            "logistic": {
                "classic": {
                    "baseline": {"pairs": 2.0, "spearman_rho": 0.2, "top1": 0.5, "top3": 1.0},
                    "ablations": {"shuffle": {"pairs": 2.0, "spearman_rho": 0.1, "top1": 0.4, "top3": 0.9}},
                }
            }
        },
        {
            "logistic": {
                "classic": {
                    "baseline": {"pairs": 2.0, "spearman_rho": 0.4, "top1": 0.75, "top3": 0.8},
                    "ablations": {"shuffle": {"pairs": 2.0, "spearman_rho": 0.3, "top1": 0.6, "top3": 0.7}},
                }
            }
        },
    ]
    aggregate = aggregate_seed_results(seed_results)
    baseline = aggregate["logistic"]["classic"]["baseline"]
    assert np.isclose(baseline["spearman_rho"], 0.3)
    assert np.isclose(baseline["top1"], 0.625)
    assert "spearman_rho_stdev" in baseline
    shuffle = aggregate["logistic"]["classic"]["ablations"]["shuffle"]
    assert np.isclose(shuffle["top3"], 0.8)


def test_simulate_aizawa_shape() -> None:
    traj = simulate_aizawa((0.1, 0.0, 0.0), 256)
    assert traj.shape == (256, 3)
    assert traj.dtype == np.float64


def test_simulate_aizawa_deterministic() -> None:
    first = simulate_aizawa((0.1, 0.0, 0.0), 512)
    second = simulate_aizawa((0.1, 0.0, 0.0), 512)
    assert np.array_equal(first, second)


def test_simulate_aizawa_stays_bounded() -> None:
    traj = simulate_aizawa((0.1, 0.0, 0.0), 20000)
    assert np.isfinite(traj).all()
    assert np.abs(traj).max() < 10.0


def test_simulate_aizawa_parameters_are_keyword_overridable() -> None:
    baseline = simulate_aizawa((0.1, 0.0, 0.0), 128)
    altered = simulate_aizawa((0.1, 0.0, 0.0), 128, b=0.9)
    assert not np.allclose(baseline, altered)


def test_simulate_aizawa_normalizes_like_neighbours() -> None:
    traj = simulate_aizawa((0.1, 0.0, 0.0), 512)
    normalized = _normalize_trajectory(traj)
    assert normalized.shape == traj.shape
    assert np.isfinite(normalized).all()


def test_generate_trajectories_accepts_aizawa() -> None:
    rng = np.random.RandomState(7)
    trajectories = generate_trajectories("aizawa", count=4, steps=64, rng=rng)
    assert len(trajectories) == 4
    for traj in trajectories:
        assert traj.shape == (64, 3)
        assert np.isfinite(traj).all()


def test_generate_trajectories_aizawa_deterministic_for_seed() -> None:
    first = generate_trajectories("aizawa", count=3, steps=64, rng=np.random.RandomState(11))
    second = generate_trajectories("aizawa", count=3, steps=64, rng=np.random.RandomState(11))
    for lhs, rhs in zip(first, second):
        assert np.array_equal(lhs, rhs)


def test_generate_trajectories_still_rejects_unknown_system() -> None:
    with pytest.raises(ValueError):
        generate_trajectories("not-a-system", count=1, steps=8, rng=np.random.RandomState(0))
