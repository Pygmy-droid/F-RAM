import math
from fram_core.coverage import (
    ClaimEvidence,
    CoverageState,
    concave_coverage,
    greedy_by_coverage,
    greedy_by_gain_cost,
    marginal_gain,
)


def test_concave_coverage_increasing_and_diminishing():
    w = {"A": 1.0}
    # 0 -> 1
    c0 = concave_coverage({"A": 0}, w, gamma=0.6, u_max=3)
    c1 = concave_coverage({"A": 1}, w, gamma=0.6, u_max=3)
    c2 = concave_coverage({"A": 2}, w, gamma=0.6, u_max=3)
    assert c1 > c0
    assert c2 > c1
    # Diminishing returns: second increment smaller than first
    assert (c1 - c0) > (c2 - c1)


def test_greedy_by_coverage_prefers_new_claims():
    claims_map = {
        1: {"Alice", "3D"},
        2: {"Alice", "Clinic"},
        3: {"Bob", "30mm"},
    }
    sel = greedy_by_coverage([1, 2, 3], claims_map, k=2, gamma=0.6, u_max=3)
    # Expect it to pick a pair that maximizes union size; any of (1,3) or (2,3)
    assert len(sel) == 2
    union = set()
    for i in sel:
        union |= claims_map[i]
    assert len(union) >= 3


def test_independence_buckets_block_duplicate_evidence():
    state = CoverageState(gamma=0.6, u_max=3)
    first = {ClaimEvidence("Alpha", ("doc:A", "layout:A:0"))}
    duplicate_same_block = {ClaimEvidence("Alpha", ("doc:A", "layout:A:0"))}
    duplicate_new_layout = {ClaimEvidence("Alpha", ("doc:A", "layout:A:1"))}
    fresh_doc = {ClaimEvidence("Alpha", ("doc:B", "layout:B:0"))}

    state.apply(first)
    gain_same_block = state.marginal_gain(duplicate_same_block)
    gain_new_layout = state.marginal_gain(duplicate_new_layout)
    gain_new_doc = state.marginal_gain(fresh_doc)

    assert gain_same_block <= 0.0
    assert gain_new_layout > 0.0
    assert gain_new_doc > 0.0


def test_greedy_by_gain_cost_prefers_higher_ratio():
    state = CoverageState(gamma=0.6, u_max=3)
    claims_map = {
        1: {"Alpha"},
        2: {"Beta"},
    }
    # Item 1 has the same gain but higher cost -> item 2 should win
    cost_map = {1: 10.0, 2: 1.0}

    selected = greedy_by_gain_cost([1, 2], claims_map, cost_map, state, k=1)
    assert selected == [2]
