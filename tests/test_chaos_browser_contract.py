from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

import pytest

from fram_eval.chaos.diagnostics import detect_orbit_period, logistic_lyapunov
from fram_eval.chaos.systems import simulate


ROOT = Path(__file__).resolve().parents[1]
PLAYGROUND = ROOT / "experiments" / "chaos_playground" / "chaos-playground-v2.html"
GOLDEN = ROOT / "experiments" / "chaos_playground" / "golden-default-v1.json"


def _golden() -> dict:
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


def test_opus_playground_source_is_exact_and_self_contained() -> None:
    fixture = _golden()
    source = PLAYGROUND.read_bytes()
    text = source.decode("ascii")

    assert hashlib.sha256(source).hexdigest().upper() == fixture["source"]["sha256"]
    assert not re.search(r"https?://|src=[\"']//|@import|cdn\\.", text)
    for element_id in (
        "helix",
        "bif",
        "mandel",
        "julia",
        "mLyap",
        "mPeriod",
        "mDelta",
        "sceneList",
        "tombList",
    ):
        assert f'id="{element_id}"' in text


def test_default_browser_logistic_metrics_share_the_python_math() -> None:
    logistic = _golden()["logistic"]
    backend = logistic["backend"]
    display = logistic["browser_display"]

    samples = simulate(
        "logistic",
        logistic["x0"],
        logistic["steps"],
        params={"r": logistic["r"]},
        burn_in=logistic["burn_in"],
    )[:, 0]
    exponent = logistic_lyapunov(
        logistic["x0"],
        logistic["r"],
        logistic["steps"],
        burn_in=logistic["burn_in"],
    )
    period = detect_orbit_period(samples, max_period=1024, atol=1e-9, repeats=4)

    assert exponent == pytest.approx(backend["lyapunov"], abs=1e-15)
    assert samples[-1] == pytest.approx(backend["last"], abs=1e-15)
    assert period is backend["period"]
    assert round(exponent, 5) == display["lyapunov"]
    assert round(float(samples[-1]), 6) == display["last"]
    assert display["period"] == "infinity"


def test_browser_cascade_ratios_are_internally_reproducible() -> None:
    rows = _golden()["browser_cascade"]
    onsets = [row["onset"] for row in rows]
    displayed = [row["ratio"] for row in rows]

    # The ratio printed on row i+1 uses the three onsets i, i+1, i+2.
    for index in range(len(onsets) - 2):
        measured = (onsets[index + 1] - onsets[index]) / (
            onsets[index + 2] - onsets[index + 1]
        )
        # The fixture stores the UI's seven-decimal onsets, while the browser
        # computes ratios from its unrounded bisection results. The deepest
        # spacings are small enough that display rounding is amplified.
        assert displayed[index + 1] == pytest.approx(measured, abs=5e-4)

    deepest = next(value for value in reversed(displayed) if value is not None)
    assert deepest == _golden()["logistic"]["browser_display"]["delta"]
    assert abs(deepest - 4.669201609) < 3e-3
    assert math.isfinite(deepest)
