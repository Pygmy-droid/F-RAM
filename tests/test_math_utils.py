import numpy as np
from fram_core.math_utils import (
    whiten_embeddings,
    robust_z,
    subspace_projection,
    mhd,
    pairwise_mean_knn_dist,
    projection_help_delta,
    centroid_distance,
)

def test_whiten_and_projection_shapes():
    X = np.random.randn(4, 6)
    mean = X.mean(axis=0)
    W = np.eye(6)
    Y = whiten_embeddings(X, mean, W)
    assert Y.shape == (4, 6)

    e = np.random.randn(6)
    pk = np.zeros(6)
    Uk = np.eye(6)[:, :3]  # rank-3
    mu = subspace_projection(e, pk, Uk)
    assert mu.shape == (6,)



def test_whiten_embeddings_single_vector_keeps_shape():
    vec = np.array([1.0, -2.0, 0.5])
    mean = np.array([1.0, -2.0, 0.5])
    W = np.eye(3)
    whitened = whiten_embeddings(vec, mean, W)
    assert whitened.shape == (3,)
    assert np.allclose(whitened, np.zeros(3))


def test_robust_z_and_mhd():
    val = robust_z(10.0, median=8.0, mad=2.0)
    assert isinstance(val, float)
    # mhd in [0,1]
    e = np.array([1.0, 0.0, 0.0])
    pk = np.zeros(3)
    Uk = np.eye(3)[:, :2]
    v = mhd(e, pk, Uk)
    assert 0.0 <= v <= 1.0


def test_mhd_handles_zero_delta_and_clamps():
    pk = np.zeros(2)
    Uk = np.array([[2.0], [0.0]])
    clamped = mhd(np.array([1.0, 0.0]), pk, Uk)
    assert np.isclose(clamped, 1.0)
    zero = mhd(np.array([0.0, 0.0]), pk, Uk)
    assert zero == 0.0

def test_knn_mean_distance_finite():
    mu = np.zeros(3)
    neigh = np.random.randn(5, 3)
    d = pairwise_mean_knn_dist(mu, neigh)
    assert np.isfinite(d)


def test_projection_help_delta_matches_spec_definition():
    # Spec 5.1: Δd = ||e - p_k||^2 - ||I*_k - p_k||^2
    e = np.array([1.0, 2.0, 3.0])
    p_k = np.zeros(3)
    U_k = np.eye(3)[:, :2]  # rank-2 subspace on first two axes
    mu_k = subspace_projection(e, p_k, U_k)
    d_full = np.dot(e - p_k, e - p_k)
    d_proj = np.dot(mu_k - p_k, mu_k - p_k)
    expected = float(d_full - d_proj)
    got = projection_help_delta(e, p_k, U_k)
    assert np.isclose(got, expected)


def test_centroid_distance_matches_l2_norm():
    e = np.array([1.0, 2.0, -2.0])
    p_k = np.array([1.0, 0.0, 1.0])
    delta = e - p_k
    expected = float(np.sqrt(np.dot(delta, delta)))
    got = centroid_distance(e, p_k)
    assert np.isclose(got, expected)
