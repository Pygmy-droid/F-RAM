from __future__ import annotations

import numpy as np
import pytest

from fram_core.rotational_lift import (
    LiftCapsule,
    compress_to_invariants,
    passes_reentry_bound,
    project_drop_axis,
    lift_insert_axis,
    recursive_lift,
    recursive_reconstruct,
    reconstruct_from_invariants,
    reentry_distances,
    rotate_plane,
    select_window,
    summarize_errors,
)


def _assert_pairwise_monotonic_nondecreasing(values: list[float]) -> None:
    for earlier, later in zip(values, values[1:]):
        assert later >= earlier - 1e-12, f"expected non-decreasing degradation, got {values}"


def _make_point_cloud(count: int = 360) -> np.ndarray:
    """Deterministic 3D curve, identical construction to the toy simulation's
    ``generate_point_cloud`` (hearthforge/experiments/recursive_rotational_lift)."""

    golden = np.pi * (3.0 - np.sqrt(5.0))
    i = np.arange(count, dtype=float)
    t = (i + 0.5) / count
    z = 1.0 - 2.0 * t
    radius = np.sqrt(np.clip(1.0 - z * z, 0.0, None))
    theta = i * golden
    breathe = 0.88 + 0.12 * np.sin(7.0 * theta)
    x = breathe * radius * np.cos(theta)
    y = breathe * radius * np.sin(theta)
    return np.stack([x, y, z], axis=1)


# --- rotation is a genuine SO(n) element -------------------------------------


def test_rotate_plane_is_orthogonal() -> None:
    rng = np.random.default_rng(7)
    state = rng.normal(size=(25, 6))
    rotated = rotate_plane(state, 1, 4, theta=0.837)
    assert np.allclose(np.linalg.norm(state, axis=1), np.linalg.norm(rotated, axis=1))
    # Inner products between distinct rows are also preserved (Q^T Q = I).
    assert np.allclose(state @ state.T, rotated @ rotated.T, atol=1e-10)


def test_rotate_plane_inverse_recovers_original() -> None:
    rng = np.random.default_rng(11)
    state = rng.normal(size=(10, 4))
    rotated = rotate_plane(state, 0, 3, theta=1.23)
    restored = rotate_plane(rotated, 0, 3, theta=-1.23)
    assert np.allclose(state, restored, atol=1e-10)


# --- projection/lift primitives ----------------------------------------------


def test_project_lift_roundtrip_exact() -> None:
    rng = np.random.default_rng(3)
    state = rng.normal(size=(15, 5))
    shadow, residual = project_drop_axis(state, axis=2)
    restored = lift_insert_axis(shadow, axis=2, residual=residual)
    assert np.allclose(state, restored)


# --- recursive lift: lossless in the exact-residual path ---------------------


@pytest.mark.parametrize("target_dim", [4, 5, 6, 7, 8])
def test_recursive_lift_reconstruct_lossless(target_dim: int) -> None:
    points = _make_point_cloud(120)
    final_state, capsules = recursive_lift(points, target_dim=target_dim, window_rule="bottom")
    reconstructed = recursive_reconstruct(final_state, capsules)
    errors = reentry_distances(points, reconstructed)
    assert summarize_errors(errors)["max"] < 1e-9


def test_recursive_lift_beats_naive_lossy_baseline() -> None:
    """Mirrors the v0.1 lab note's headline comparison: a residual-preserving
    lift reconstructs exactly; dropping the residual entirely does not."""

    points = _make_point_cloud(120)
    final_state, capsules = recursive_lift(points, target_dim=4, window_rule="bottom")
    exact_reconstruction = recursive_reconstruct(final_state, capsules)
    exact_error = summarize_errors(reentry_distances(points, exact_reconstruction))["max"]

    # Naive lossy baseline: drop the residual axis entirely (set to 0) instead
    # of carrying it forward, exactly like the toy's lossy_reconstruct_from_shadow.
    drop_axis = capsules[0].drop_axis
    shadow, _residual = project_drop_axis(points, drop_axis)
    lossy = lift_insert_axis(shadow, drop_axis, np.zeros(points.shape[0]))
    lossy_error = summarize_errors(reentry_distances(points, lossy))["max"]

    assert exact_error < 1e-9
    assert lossy_error > 0.1
    assert lossy_error > exact_error


def test_recursive_lift_determinism() -> None:
    points = _make_point_cloud(60)
    state_a, capsules_a = recursive_lift(points, target_dim=6, window_rule="bottom")
    state_b, capsules_b = recursive_lift(points, target_dim=6, window_rule="bottom")
    assert np.allclose(state_a, state_b)
    assert capsules_a == capsules_b


def test_lift_capsule_fields() -> None:
    points = _make_point_cloud(10)
    _final_state, capsules = recursive_lift(points, target_dim=4, window_rule="bottom")
    assert len(capsules) == 1
    capsule = capsules[0]
    assert isinstance(capsule, LiftCapsule)
    assert capsule.previous_dim == 3
    assert capsule.residual_mode == "exact"
    assert capsule.window_rule == "bottom"
    assert capsule.parent_id is None
    # The documented default hop->axis schedule (2, then 0, then 1) and the
    # rotation plane/angle it implies - these were previously unchecked, so a
    # schedule regression could pass silently (only forward/inverse
    # self-consistency was verified, which is invariant to which axis is used).
    assert capsule.drop_axis == 2
    assert capsule.rotation_plane == (2, 3)
    assert capsule.rotation_theta == pytest.approx(np.pi)


def test_recursive_lift_default_drop_axis_schedule_matches_docstring() -> None:
    points = _make_point_cloud(10)
    _final_state, capsules = recursive_lift(points, target_dim=6, window_rule="bottom")
    assert [c.drop_axis for c in capsules] == [2, 0, 1]


def test_recursive_lift_rejects_target_dim_smaller_than_input() -> None:
    points = _make_point_cloud(5)
    with pytest.raises(ValueError):
        recursive_lift(points, target_dim=2, window_rule="bottom")


def test_recursive_lift_rejects_zero_width_input() -> None:
    zero_width = np.zeros((5, 0))
    with pytest.raises(ValueError):
        recursive_lift(zero_width, target_dim=4, window_rule="bottom")


# --- degradation modes: reconstruction should degrade, not stay perfect or explode ---


def test_residual_quantization_degrades_monotonically() -> None:
    points = _make_point_cloud(120)
    bit_levels = [16, 12, 8, 4, 2, 1]
    rms_by_bits = []
    for bits in bit_levels:
        final_state, capsules = recursive_lift(
            points, target_dim=6, window_rule="bottom", residual_mode="quantized", quantize_bits=bits
        )
        reconstructed = recursive_reconstruct(final_state, capsules)
        rms_by_bits.append(summarize_errors(reentry_distances(points, reconstructed))["rms"])

    # Fewer bits (later in the list) must not reconstruct better than more bits.
    for coarser, finer in zip(rms_by_bits[1:], rms_by_bits[:-1]):
        assert coarser >= finer - 1e-12
    assert rms_by_bits[0] < 1e-2  # 16 bits: nearly exact
    assert rms_by_bits[-1] > 0.5  # 1 bit: badly degraded


def test_residual_dropout_degrades_with_probability() -> None:
    points = _make_point_cloud(120)
    dropout_ps = [0.0, 0.05, 0.10, 0.25, 0.50, 1.0]
    rms_by_p = []
    for p in dropout_ps:
        # Reconstruct the rng with the SAME fixed seed for every p (rather
        # than drawing a fresh seed per p): this couples the underlying
        # uniform draws so only the threshold changes, which is what makes
        # the dropout mask - and therefore the reconstruction error - a
        # genuinely monotonic (not just endpoint-ordered) function of p.
        final_state, capsules = recursive_lift(
            points,
            target_dim=6,
            window_rule="bottom",
            residual_mode="dropout",
            dropout_p=p,
            rng=np.random.default_rng(20260701),
        )
        reconstructed = recursive_reconstruct(final_state, capsules)
        rms_by_p.append(summarize_errors(reentry_distances(points, reconstructed))["rms"])

    _assert_pairwise_monotonic_nondecreasing(rms_by_p)
    assert rms_by_p[0] < 1e-9  # p=0: exact
    assert rms_by_p[-1] > rms_by_p[0]  # p=1: strictly worse than exact


def test_shadow_noise_degrades_with_sigma() -> None:
    points = _make_point_cloud(120)
    sigmas = [0.0, 0.01, 0.05, 0.10]
    rms_by_sigma = []
    for sigma in sigmas:
        final_state, capsules = recursive_lift(
            points,
            target_dim=6,
            window_rule="bottom",
            shadow_noise_sigma=sigma,
            rng=np.random.default_rng(1234),
        )
        reconstructed = recursive_reconstruct(final_state, capsules)
        rms_by_sigma.append(summarize_errors(reentry_distances(points, reconstructed))["rms"])

    _assert_pairwise_monotonic_nondecreasing(rms_by_sigma)
    assert rms_by_sigma[0] < 1e-9
    assert rms_by_sigma[-1] > rms_by_sigma[0]


# --- window selection ---------------------------------------------------------


@pytest.mark.parametrize("rule", ["bottom", "top", "middle_abs", "random", "high_magnitude"])
def test_window_rules_produce_valid_subset(rule: str) -> None:
    scores = np.linspace(-1.0, 1.0, 50)
    selected = select_window(scores, rule=rule, fraction=0.6)
    assert selected.size == 30
    assert len(set(selected.tolist())) == selected.size
    assert selected.min() >= 0
    assert selected.max() < scores.size
    assert list(selected) == sorted(selected.tolist())


def test_select_window_unknown_rule_raises() -> None:
    with pytest.raises(ValueError):
        select_window(np.zeros(10), rule="nonexistent")


# --- understanding-as-compression (payload section 6) -------------------------


def test_compress_to_invariants_reentry_bound_on_low_rank_trajectory() -> None:
    rng = np.random.default_rng(42)
    t = np.linspace(0, 4 * np.pi, 200)
    basis_true = rng.normal(size=(2, 10))
    trajectory = np.outer(np.sin(t), basis_true[0]) + np.outer(np.cos(t), basis_true[1])
    trajectory += rng.normal(scale=1e-4, size=trajectory.shape)  # tiny noise, effectively rank 2

    z, basis, mean = compress_to_invariants(trajectory, n_components=2)
    assert z.shape == (200, 2)
    reconstructed = reconstruct_from_invariants(z, basis, mean)
    assert passes_reentry_bound(trajectory, reconstructed, epsilon=1e-2)


def test_compress_to_invariants_more_components_never_worse() -> None:
    rng = np.random.default_rng(5)
    trajectory = rng.normal(size=(40, 8))

    z_low, basis_low, mean_low = compress_to_invariants(trajectory, n_components=1)
    err_low = summarize_errors(
        reentry_distances(trajectory, reconstruct_from_invariants(z_low, basis_low, mean_low))
    )["rms"]

    z_high, basis_high, mean_high = compress_to_invariants(trajectory, n_components=6)
    err_high = summarize_errors(
        reentry_distances(trajectory, reconstruct_from_invariants(z_high, basis_high, mean_high))
    )["rms"]

    assert err_high <= err_low + 1e-12


def test_passes_reentry_bound_false_when_epsilon_too_tight() -> None:
    rng = np.random.default_rng(9)
    trajectory = rng.normal(size=(30, 6))
    z, basis, mean = compress_to_invariants(trajectory, n_components=1)
    reconstructed = reconstruct_from_invariants(z, basis, mean)
    assert not passes_reentry_bound(trajectory, reconstructed, epsilon=1e-9)
