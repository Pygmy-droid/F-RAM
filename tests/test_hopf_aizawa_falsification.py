from __future__ import annotations

import numpy as np
import pytest

from experiments.hopf_aizawa_falsification import (
    adapter_preimage_report,
    bounded_evidence_payload,
    rotational_lift_falsification_report,
    z2_versus_s1_report,
)


def test_z2_is_two_points_inside_a_continuous_hopf_fiber() -> None:
    report = z2_versus_s1_report(samples=256)
    assert report.max_base_drift < 1e-12
    assert report.so3_spread_at_sign_flip < 1e-14
    assert report.max_so3_spread_along_fiber == pytest.approx(2.0 * np.sqrt(2.0))
    assert report.sampled_phases_matching_original_rotation == 2
    assert report.fiber_arclength == pytest.approx(2.0 * np.pi, abs=2e-4)


def test_rotational_lift_report_separates_positive_and_negative_bridges() -> None:
    report = rotational_lift_falsification_report(samples=48, phase_samples=64)
    assert report.paired_givens_max_error < 1e-14
    assert report.single_givens_mean_error > 0.3
    assert min(report.max_shadow_drift_by_axis.values()) > 1.8
    assert report.normalized_lift_base_error_mean > 1.2
    assert report.base_endpoint_distance < 1e-12
    assert report.lifted_endpoint_distance > 1.0


def test_exact_recursive_reentry_is_independent_of_loop_winding() -> None:
    report = rotational_lift_falsification_report(samples=16, phase_samples=32)
    assert set(report.exact_recursive_reentry_by_winding) == {1, 2, 4}
    assert max(report.exact_recursive_reentry_by_winding.values()) < 1e-12


def test_adapter_noninjectivity_uses_kernel_and_fiber_preimages() -> None:
    report = adapter_preimage_report(dimension=32, samples=12, phase_samples=12)
    assert report.rank == 4
    assert report.kernel_dimension == 28
    assert report.generic_preimage_dimension == 30
    assert report.positive_scale_invariance_error < 1e-12
    assert report.hopf_sign_quotient_error < 1e-12
    assert report.kernel_invariance_error < 1e-11
    assert report.fiber_preimage_error < 1e-11
    assert report.max_relative_preimage_displacement > 0.5


def test_adapter_report_rejects_dimensions_without_full_row_rank_contract() -> None:
    with pytest.raises(ValueError, match="at least 4"):
        adapter_preimage_report(dimension=3)


def test_bounded_evidence_payload_is_deterministic_and_claim_bounded() -> None:
    first = bounded_evidence_payload()
    second = bounded_evidence_payload()
    assert first == second
    assert first["schema"] == "fram-hopf-aizawa-falsification-1"
    assert "no Chern-number claim" in first["claims"]["holonomy"]
    assert "no attractor-recurrence claim" in first["claims"]["defects"]
