import math

import numpy as np
import pytest

from fram_core.transitional_complexity import TransitionalComplexityProbe


def test_tc_is_zero_for_constant_stream():
    probe = TransitionalComplexityProbe()
    vec = np.array([1.0, 0.0, 0.0, 0.0])

    first = probe.update("stream", vec)
    second = probe.update("stream", vec)

    assert first["tc"] == pytest.approx(0.0)
    assert second["tc"] == pytest.approx(0.0)
    assert second["delta_l2"] == pytest.approx(0.0)
    assert second["delta_entropy"] == pytest.approx(0.0)
    assert second["curvature_l2"] == pytest.approx(0.0)


def test_tc_increases_for_changing_stream():
    probe = TransitionalComplexityProbe()
    v0 = np.array([1.0, 0.0, 0.0, 0.0])
    v1 = np.array([0.0, 1.0, 0.0, 0.0])

    probe.update("stream", v0)
    out = probe.update("stream", v1)

    assert out["delta_l2"] == pytest.approx(math.sqrt(2.0))
    assert out["tc"] > 0.0
    assert out["delta_entropy"] > 0.0


def test_tc_regression_snapshot_simple_basis_walk():
    probe = TransitionalComplexityProbe()
    seq = [
        np.array([1.0, 0.0, 0.0, 0.0]),
        np.array([1.0, 0.0, 0.0, 0.0]),
        np.array([0.0, 1.0, 0.0, 0.0]),
        np.array([0.0, 0.0, 1.0, 0.0]),
        np.array([0.0, 0.0, 0.0, 1.0]),
    ]

    expected = [
        {"delta_l2": 0.0, "delta_entropy": 0.0, "curvature_l2": 0.0, "tc": 0.0},
        {"delta_l2": 0.0, "delta_entropy": 0.0, "curvature_l2": 0.0, "tc": 0.0},
        {
            "delta_l2": math.sqrt(2.0),
            "delta_entropy": 0.5,
            "curvature_l2": math.sqrt(2.0),
            "tc": math.sqrt(2.0) * 1.5,
        },
        {
            "delta_l2": math.sqrt(2.0),
            "delta_entropy": 0.5,
            "curvature_l2": math.sqrt(6.0),
            "tc": math.sqrt(2.0) * 1.5,
        },
        {
            "delta_l2": math.sqrt(2.0),
            "delta_entropy": 0.5,
            "curvature_l2": math.sqrt(6.0),
            "tc": math.sqrt(2.0) * 1.5,
        },
    ]

    for vec, exp in zip(seq, expected, strict=True):
        out = probe.update("stream", vec)
        assert out["delta_l2"] == pytest.approx(exp["delta_l2"])
        assert out["delta_entropy"] == pytest.approx(exp["delta_entropy"])
        assert out["curvature_l2"] == pytest.approx(exp["curvature_l2"])
        assert out["tc"] == pytest.approx(exp["tc"])

