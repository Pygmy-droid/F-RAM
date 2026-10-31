from __future__ import annotations

from fram_core.anchors import select_by_novelty


def test_select_by_novelty_skips_seed_generator():
    facts_map = {
        0: {"alpha"},
        1: {"beta"},
        2: {"gamma"},
    }
    seeds = (idx for idx in [0])

    result = select_by_novelty([0, 1, 2], facts_map, k=2, already_selected=seeds)

    assert 0 not in result
    assert len(result) == 2
    assert set(result).issubset({1, 2})


def test_select_by_novelty_handles_empty_facts():
    facts_map = {
        0: set(),
        1: {"beta"},
        2: set(),
    }
    result = select_by_novelty([0, 1, 2], facts_map, k=2, already_selected=[1])
    assert 1 not in result
    assert len(result) == 2
    assert set(result).issubset({0, 2})
