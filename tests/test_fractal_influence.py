from __future__ import annotations

from copy import deepcopy

from fram_serving.query_runner import FRACTAL_INFLUENCE_ALPHA, _apply_fractal_influence


def test_fractal_influence_flag_off_no_change() -> None:
    candidates = [
        {"doc_id": "cmem:ep:one", "score": 1.0},
        {"doc_id": "cmem:ep:two", "score": 0.9},
    ]
    baseline = deepcopy(candidates)
    out = _apply_fractal_influence(
        candidates,
        {"one": 0.5, "two": -0.25},
        alpha=FRACTAL_INFLUENCE_ALPHA,
        enabled=False,
    )
    assert out == baseline


def test_fractal_influence_on_changes_ranking() -> None:
    candidates = [
        {"doc_id": "cmem:ep:alpha", "score": 1.0},
        {"doc_id": "cmem:ep:beta", "score": 1.0},
    ]
    out = _apply_fractal_influence(
        candidates,
        {"alpha": 0.8, "beta": -0.2},
        alpha=FRACTAL_INFLUENCE_ALPHA,
        enabled=True,
    )
    ranked = sorted(out, key=lambda c: c["score"], reverse=True)
    assert ranked[0]["doc_id"] == "cmem:ep:alpha"
    assert abs(out[0]["score"] - 1.0) <= FRACTAL_INFLUENCE_ALPHA
    assert abs(out[1]["score"] - 1.0) <= FRACTAL_INFLUENCE_ALPHA


def test_fractal_influence_determinism() -> None:
    candidates = [
        {"doc_id": "cmem:ep:alpha", "score": 1.2},
        {"doc_id": "cmem:ep:beta", "score": 0.8},
    ]
    first = _apply_fractal_influence(
        deepcopy(candidates),
        {"alpha": 0.1, "beta": 0.3},
        alpha=FRACTAL_INFLUENCE_ALPHA,
        enabled=True,
    )
    second = _apply_fractal_influence(
        deepcopy(candidates),
        {"alpha": 0.1, "beta": 0.3},
        alpha=FRACTAL_INFLUENCE_ALPHA,
        enabled=True,
    )
    assert first == second
