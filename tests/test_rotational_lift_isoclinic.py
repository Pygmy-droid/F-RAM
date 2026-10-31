"""Isoclinic (paired) rotations in the recursive rotational lift.

The formal sketch (``2026-07-01_recursive_rotational_lift_payload.md`` S4)
specifies each capsule as carrying ``Q_{n+1} in SO(n+1)`` - a full rotation.
``LiftCapsule`` previously stored a single ``(plane, theta)``, a strict
subgroup that cannot represent a rotation acting in two planes at once.

These tests pin the widened representation: legacy behaviour is bit-identical,
round-trips stay exact, and the capsule can now record the isoclinic form the
Hopf fiber action takes.
"""

from __future__ import annotations

import numpy as np
import pytest

from fram_core.rotational_lift import (
    LiftCapsule,
    isoclinic_partner_plane,
    recursive_lift,
    recursive_reconstruct,
    rotate_plane,
)
from fram_eval.hopf_transport import base_points, qnormalize


def _states(n: int = 6, d: int = 3, seed: int = 20260727) -> np.ndarray:
    return np.random.default_rng(seed).normal(size=(n, d))


# --------------------------------------------------------------------------
# backward compatibility: the default path must not move at all
# --------------------------------------------------------------------------


def test_default_mode_is_single_and_records_no_sequence():
    _, capsules = recursive_lift(_states(), target_dim=6)
    assert capsules, "expected at least one hop"
    for cap in capsules:
        assert cap.rotations is None
        assert cap.rotation_sequence == ((cap.rotation_plane, cap.rotation_theta),)


def test_legacy_capsule_without_rotations_still_reconstructs():
    """A capsule built the old way (no ``rotations`` kwarg) must still work."""
    state = _states(4, 3)
    final, capsules = recursive_lift(state, target_dim=5)
    legacy = [
        LiftCapsule(
            previous_dim=c.previous_dim,
            drop_axis=c.drop_axis,
            rotation_plane=c.rotation_plane,
            rotation_theta=c.rotation_theta,
            window_rule=c.window_rule,
            residual_mode=c.residual_mode,
        )
        for c in capsules
    ]
    assert np.allclose(recursive_reconstruct(final, legacy), state, atol=1e-12)


# --------------------------------------------------------------------------
# the widened representation
# --------------------------------------------------------------------------


def test_isoclinic_mode_records_two_disjoint_planes():
    _, capsules = recursive_lift(_states(4, 3), target_dim=6, rotation_mode="isoclinic")
    paired = [c for c in capsules if c.rotations is not None]
    assert paired, "expected at least one paired hop once dim >= 4"
    for cap in paired:
        assert len(cap.rotations) == 2
        (p1, t1), (p2, t2) = cap.rotations
        assert set(p1).isdisjoint(set(p2)), "planes must be disjoint to be isoclinic"
        assert t2 == pytest.approx(-t1), "isoclinic means equal and opposite angles"
        # legacy fields still mirror the first rotation
        assert cap.rotation_plane == p1 and cap.rotation_theta == pytest.approx(t1)


def test_isoclinic_round_trip_is_exact():
    state = _states(8, 3)
    final, capsules = recursive_lift(state, target_dim=7, rotation_mode="isoclinic")
    assert np.allclose(recursive_reconstruct(final, capsules), state, atol=1e-12)


def test_isoclinic_changes_the_final_state():
    """If pairing made no difference the widening would be pointless."""
    state = _states(5, 3)
    single, _ = recursive_lift(state, target_dim=6)
    paired, _ = recursive_lift(state, target_dim=6, rotation_mode="isoclinic")
    assert not np.allclose(single, paired)


def test_rotations_preserve_norm_in_both_modes():
    state = _states(6, 3)
    for mode in ("single", "isoclinic"):
        final, capsules = recursive_lift(state, target_dim=6, rotation_mode=mode)
        for cap in capsules:
            probe = np.random.default_rng(1).normal(size=(3, cap.previous_dim + 1))
            rotated = probe
            for plane, angle in cap.rotation_sequence:
                rotated = rotate_plane(rotated, plane[0], plane[1], angle)
            assert np.allclose(
                np.linalg.norm(rotated, axis=1), np.linalg.norm(probe, axis=1), atol=1e-12
            )


def test_unknown_rotation_mode_rejected():
    with pytest.raises(ValueError, match="unknown rotation_mode"):
        recursive_lift(_states(), target_dim=5, rotation_mode="corkscrew")


def test_partner_plane_is_deterministic_and_absent_when_too_small():
    assert isoclinic_partner_plane((0, 1), 4) == (2, 3)
    assert isoclinic_partner_plane((0, 3), 4) == (1, 2)
    assert isoclinic_partner_plane((0, 1), 3) is None


@pytest.mark.parametrize(
    "plane, dim",
    [
        ((0, 0), 4),
        ((-1, 1), 4),
        ((0, 4), 4),
    ],
)
def test_partner_plane_rejects_invalid_primary_plane(plane, dim):
    with pytest.raises(ValueError, match="rotation plane"):
        isoclinic_partner_plane(plane, dim)


def test_rotate_plane_rejects_degenerate_axes_instead_of_changing_norm():
    state = np.array([1.0, 2.0, 3.0])
    with pytest.raises(ValueError, match="axes must be distinct"):
        rotate_plane(state, 0, 0, np.pi / 4.0)


def test_paired_mode_is_not_claimed_globally_isoclinic_above_four_dimensions():
    state = np.eye(6)
    final, capsules = recursive_lift(state, target_dim=7, rotation_mode="isoclinic")
    assert final.shape == (6, 7)
    assert any(c.rotations is not None for c in capsules)


# --------------------------------------------------------------------------
# the falsification: does pairing move the S3 landing?
# --------------------------------------------------------------------------


def test_appended_coordinate_not_rotation_breaks_unit_norm():
    """Pin the *cause* of the off-S3 landing.

    Claimed in firelink.md: widening the rotation would make ``recursive_lift``
    land on S3. Rotations are orthogonal, so they cannot change a norm; the
    lift also *appends* ``derived_coordinate``, which can. This test asserts
    the mechanism explicitly so the claim cannot be quietly re-adopted.
    """
    unit = np.array([[0.6, 0.8, 0.0]])
    assert np.linalg.norm(unit) == pytest.approx(1.0)

    dev = {}
    for mode in ("single", "isoclinic"):
        final, _ = recursive_lift(unit, target_dim=4, rotation_mode=mode)
        dev[mode] = abs(float(np.linalg.norm(final)) - 1.0)

    # Both modes miss the unit sphere, and pairing does not rescue it.
    assert dev["single"] > 1e-6
    assert dev["isoclinic"] > 1e-6
    assert dev["isoclinic"] == pytest.approx(dev["single"], abs=1e-12), (
        "isoclinic pairing must not change the norm deviation - rotations are "
        "orthogonal, so the deviation comes from the appended coordinate"
    )


def test_independent_hopf_base_measurement_stays_near_chance_after_pairing():
    """Score Opus's explicit handoff prediction with an independent sample."""

    rng = np.random.default_rng(20260727)
    points = rng.normal(size=(1024, 3))
    points /= np.linalg.norm(points, axis=1, keepdims=True)

    means = {}
    norm_deviations = {}
    for mode in ("single", "isoclinic"):
        lifted, _ = recursive_lift(points, target_dim=4, rotation_mode=mode)
        remapped = base_points(qnormalize(lifted))
        geodesic = np.arccos(
            np.clip(np.einsum("ij,ij->i", remapped, points), -1.0, 1.0)
        )
        means[mode] = float(geodesic.mean())
        norm_deviations[mode] = np.abs(np.linalg.norm(lifted, axis=1) - 1.0)

    chance = np.pi / 2.0
    assert means["single"] == pytest.approx(chance, abs=0.12)
    assert means["isoclinic"] == pytest.approx(chance, abs=0.12)
    assert abs(means["single"] - means["isoclinic"]) < 0.05
    np.testing.assert_allclose(
        norm_deviations["single"],
        norm_deviations["isoclinic"],
        atol=1e-12,
    )
