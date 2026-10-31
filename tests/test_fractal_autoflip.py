from __future__ import annotations

from fram_eval.fractal_autoflip import recommend_fractal_influence


def _payload(results: dict) -> dict:
    return {"results": results}


def test_autoflip_recommend_true() -> None:
    conversation = _payload(
        {
            "semantic": {
                "probe": {"top1": 0.30, "count": 10},
                "probe_low_lex": {"top1": 0.25, "count": 10},
            },
            "lexical": {
                "probe": {"top1": 0.20, "count": 10},
                "probe_low_lex": {"top1": 0.20, "count": 10},
            },
            "fractal": {
                "probe": {"top1": 0.35, "count": 10},
                "probe_low_lex": {"top1": 0.28, "count": 10},
            },
        }
    )
    shadow = _payload(
        {
            "semantic": {
                "probe": {"avg_delta": 0.10, "count": 10},
                "probe_low_lex": {"avg_delta": 0.08, "count": 10},
            },
            "lexical": {
                "probe": {"avg_delta": 0.09, "count": 10},
                "probe_low_lex": {"avg_delta": 0.07, "count": 10},
            },
            "fractal": {
                "probe": {"avg_delta": 0.16, "count": 10},
                "probe_low_lex": {"avg_delta": 0.08, "count": 10},
            },
        }
    )
    result = recommend_fractal_influence(
        conversation,
        shadow,
        fields=["probe", "probe_low_lex"],
        low_lex_fields=["probe_low_lex"],
        min_count=5,
    )
    assert result["recommend_enable"] is True


def test_autoflip_recommend_false_on_shadow_gap() -> None:
    conversation = _payload(
        {
            "semantic": {"probe": {"top1": 0.30, "count": 10}},
            "lexical": {"probe": {"top1": 0.25, "count": 10}},
            "fractal": {"probe": {"top1": 0.31, "count": 10}},
        }
    )
    shadow = _payload(
        {
            "semantic": {"probe": {"avg_delta": 0.10, "count": 10}},
            "lexical": {"probe": {"avg_delta": 0.09, "count": 10}},
            "fractal": {"probe": {"avg_delta": 0.12, "count": 10}},
        }
    )
    result = recommend_fractal_influence(
        conversation,
        shadow,
        fields=["probe"],
        low_lex_fields=[],
        min_count=5,
        shadow_margin=0.05,
    )
    assert result["recommend_enable"] is False
    assert result["fields"]["probe"]["criteria"]["shadow_ok"] is False
