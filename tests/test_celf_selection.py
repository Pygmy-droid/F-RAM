from fastapi.testclient import TestClient
import pytest

from fram_core.coverage import ClaimEvidence, CoverageState, select_celf, greedy_by_gain_cost
from fram_serving.app import app, CFG



def test_select_celf_matches_greedy_delta_cost():
    claims_map = {
        0: [ClaimEvidence("alpha")],
        1: [ClaimEvidence("alpha"), ClaimEvidence("beta")],
        2: [ClaimEvidence("gamma")],
        3: [ClaimEvidence("beta"), ClaimEvidence("delta")],
    }
    items = list(claims_map.keys())
    state = CoverageState(gamma=0.6, u_max=3)
    greedy_selection = greedy_by_gain_cost(
        items,
        claims_map,
        {i: 1.0 for i in items},
        state,
        k=2,
    )

    cost_components = {
        i: {"reads": 1.0, "tokens": 1.0, "pairs_scale": 1.0, "pairs_exponent": 2.0}
        for i in items
    }
    celf_state = CoverageState(gamma=0.6, u_max=3)
    celf_selection, stats, details, totals = select_celf(
        items,
        claims_map,
        cost_components,
        k=2,
        lambdas={"lambda_tokens": 0.0, "lambda_rerank": 0.0},
        state=celf_state,
    )

    assert set(celf_selection) == set(greedy_selection)
    assert stats["pops"] > stats["recomps"]
    assert totals["reads"] >= 0.0
    assert len(details) >= len(celf_selection)


def test_select_celf_eager_mode_respects_budgets_and_seeds():
    claims_map = {
        0: [ClaimEvidence("alpha")],
        1: [ClaimEvidence("beta")],
        2: [ClaimEvidence("gamma")],
    }
    cost_components = {
        0: {"reads": 1.0, "tokens": 1.0},
        1: {"reads": 1.0, "tokens": 1.5},
        2: {"reads": 1.0, "tokens": 2.0},
    }
    state = CoverageState(gamma=0.6, u_max=3)
    initial_value = state.value()

    selected, stats, details, totals = select_celf(
        [1, 2],
        claims_map,
        cost_components,
        k=2,
        lambdas={
            "lambda_tokens": 0.0,
            "lambda_rerank": 0.0,
            "budgets": {"reads": 2.0},
        },
        seed=[0],
        state=state,
        lazy=False,
    )

    assert selected
    assert len(details) > 1
    assert stats["pops"] >= len(selected)
    assert totals["reads"] <= 2.0
    assert details[0]["seed"] is True
    assert any(not entry["seed"] for entry in details[1:])
    assert 0 not in selected
    assert state.value() >= initial_value


def test_section_repeat_penalty_prioritises_new_segments():
    claims_map = {
        0: [ClaimEvidence("alpha", buckets=("segment:section:one",))],
        1: [ClaimEvidence("beta", buckets=("segment:section:one",))],
        2: [ClaimEvidence("gamma", buckets=("segment:section:two",))],
    }
    cost_components = {
        idx: {"reads": 1.0, "tokens": 0.0, "pairs_scale": 1.0, "pairs_exponent": 2.0}
        for idx in claims_map
    }
    state = CoverageState(gamma=0.6, u_max=3)

    selected, stats, details, totals = select_celf(
        [1, 2],
        claims_map,
        cost_components,
        k=3,
        lambdas={"lambda_tokens": 0.0, "lambda_rerank": 0.0},
        seed=[0],
        state=state,
        lazy=False,
        segment_map={0: "section:one", 1: "section:one", 2: "section:two"},
        segment_repeat_penalty=0.5,
        segment_penalty_floor=0.25,
    )

    assert selected == [2, 1]
    non_seed_details = [entry for entry in details if not entry["seed"]]
    assert non_seed_details[0]["id"] == 2
    assert pytest.approx(non_seed_details[0]["diversity_multiplier"]) == pytest.approx(1.0)
    assert non_seed_details[1]["id"] == 1
    assert non_seed_details[1]["diversity_multiplier"] < non_seed_details[0]["diversity_multiplier"]
    assert state.segment_count("section:one") >= 1
    assert state.segment_count("section:two") >= 1


@pytest.mark.slow
def test_query_trace_includes_selection_budgets():
    if not getattr(CFG, "use_celf", True):
        return
    with TestClient(app) as client:
        resp = client.post("/query", json={"text": "How does CELF work?"})
        assert resp.status_code == 200
        body = resp.json()
    selection = body["trace"].get("selection")
    assert isinstance(selection, dict)
    budgets = selection.get("budgets")
    assert isinstance(budgets, dict)
    for key in ("reads", "tokens", "pairs", "cost"):
        value = budgets.get(key)
        assert value is not None
        assert value >= 0.0
