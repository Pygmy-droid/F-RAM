from __future__ import annotations

from fram_core.pipeline import compute_phase_d_priority, phase_d_weight_for_cognitive
from fram_serving import app as app_mod


def _sort_candidates(candidates, diag, *, weighting_enabled: bool = True, **flags):
    original = app_mod.CFG.phase_d.model_copy()
    try:
        app_mod.CFG.phase_d.enabled = True
        app_mod.CFG.phase_d.enable_memory_bridge = True
        app_mod.CFG.phase_d.enable_memory_weighting = weighting_enabled
        for key, value in flags.items():
            if hasattr(app_mod.CFG.phase_d, key):
                setattr(app_mod.CFG.phase_d, key, value)

        def _key(c):
            base = float(c["score"])
            weight = 1.0
            pd_score = c.get("phase_d_score")
            if (
                pd_score is not None
                and app_mod.CFG.phase_d.enable_memory_bridge
                and app_mod.CFG.phase_d.enable_memory_weighting
            ):
                weight = phase_d_weight_for_cognitive(
                    phase_d_score=pd_score,
                    alpha_t=diag.get("alpha_t"),
                    quat_avg=diag.get("quat_avg"),
                    alpha_color=c.get("alpha_color", diag.get("alpha_color")),
                    seen_count=c.get("seen_count"),
                    age_seconds=c.get("age_seconds"),
                    enable_alpha_color=getattr(app_mod.CFG.phase_d, "enable_alpha_color_weighting", True),
                    enable_rarity=getattr(app_mod.CFG.phase_d, "enable_rarity_weighting", True),
                    enable_recency=getattr(app_mod.CFG.phase_d, "enable_recency_weighting", True),
                    affect_score=c.get("affect_score", 0.5),
                    enable_affect=getattr(app_mod.CFG.phase_d, "enable_affect_weighting", True),
                    coherence_score=c.get("coherence_score", 0.5),
                    enable_coherence=getattr(app_mod.CFG.phase_d, "enable_coherence_weighting", True),
                    quality_score=c.get("quality_score", 0.5),
                    enable_quality=getattr(app_mod.CFG.phase_d, "enable_quality_weighting", True),
                )
            adjusted = base * weight
            return (-adjusted, -c.get("recency_weight", 1.0), -c.get("ratio", 0.0))

        return sorted(candidates, key=_key)
    finally:
        app_mod.CFG.phase_d = original


def test_phase_d_weighting_prioritizes_stronger_signal():
    diag = {"alpha_t": 1.0, "alpha_color": "saturated", "quat_avg": 1.0}
    candidates = [
        {
            "doc_id": "high_pd_low_score",
            "score": 0.5,
            "recency_weight": 1.0,
            "ratio": 0.5,
            "phase_d_score": 0.95,
        },
        {
            "doc_id": "low_pd_high_score",
            "score": 0.6,
            "recency_weight": 1.0,
            "ratio": 0.5,
            "phase_d_score": 0.2,
        },
    ]

    ordered_on = _sort_candidates(candidates, diag, weighting_enabled=True)
    assert ordered_on[0]["doc_id"] == "high_pd_low_score"

    ordered_off = _sort_candidates(candidates, diag, weighting_enabled=False)
    assert ordered_off[0]["doc_id"] == "low_pd_high_score"


def test_alpha_color_weighting_changes_order():
    diag = {"alpha_t": 0.5, "alpha_color": None, "quat_avg": 0.5}
    candidates = [
        {"doc_id": "saturated_low", "score": 0.5, "phase_d_score": 0.6, "alpha_color": "saturated"},
        {"doc_id": "dull_high", "score": 0.52, "phase_d_score": 0.6, "alpha_color": "dull"},
    ]
    ordered_on = _sort_candidates(candidates, diag, weighting_enabled=True)
    assert ordered_on[0]["doc_id"] == "saturated_low"
    ordered_off = _sort_candidates(candidates, diag, weighting_enabled=True, enable_alpha_color_weighting=False)
    assert ordered_off[0]["doc_id"] == "dull_high"


def test_rarity_weighting_changes_order():
    diag = {"alpha_t": 0.5, "alpha_color": None, "quat_avg": 0.5}
    candidates = [
        {"doc_id": "rare", "score": 0.5, "phase_d_score": 0.7, "seen_count": 0},
        {"doc_id": "common", "score": 0.52, "phase_d_score": 0.7, "seen_count": 10},
    ]
    ordered_on = _sort_candidates(candidates, diag, weighting_enabled=True)
    assert ordered_on[0]["doc_id"] == "rare"
    ordered_off = _sort_candidates(candidates, diag, weighting_enabled=True, enable_rarity_weighting=False)
    assert ordered_off[0]["doc_id"] == "common"


def test_recency_weighting_changes_order():
    diag = {"alpha_t": 0.5, "alpha_color": None, "quat_avg": 0.5}
    candidates = [
        {"doc_id": "fresh", "score": 0.5, "phase_d_score": 0.7, "age_seconds": 10},
        {"doc_id": "stale", "score": 0.55, "phase_d_score": 0.7, "age_seconds": 500},
    ]
    ordered_on = _sort_candidates(candidates, diag, weighting_enabled=True)
    assert ordered_on[0]["doc_id"] == "fresh"
    ordered_off = _sort_candidates(candidates, diag, weighting_enabled=True, enable_recency_weighting=False)
    assert ordered_off[0]["doc_id"] == "stale"


def test_affect_weighting_changes_order():
    diag = {"alpha_t": 0.5, "alpha_color": None, "quat_avg": 0.5}
    candidates = [
        {"doc_id": "high_affect", "score": 0.5, "phase_d_score": 0.7, "affect_score": 1.0},
        {"doc_id": "low_affect", "score": 0.51, "phase_d_score": 0.7, "affect_score": 0.2},
    ]
    ordered_on = _sort_candidates(
        candidates,
        diag,
        weighting_enabled=True,
        enable_affect_weighting=True,
    )
    assert ordered_on[0]["doc_id"] == "high_affect"
    ordered_off = _sort_candidates(
        candidates,
        diag,
        weighting_enabled=True,
        enable_affect_weighting=False,
    )
    assert ordered_off[0]["doc_id"] == "low_affect"


def test_coherence_weighting_changes_order():
    diag = {"alpha_t": 0.5, "alpha_color": None, "quat_avg": 0.5}
    candidates = [
        {"doc_id": "high_coh", "score": 0.5, "phase_d_score": 0.7, "coherence_score": 0.9},
        {"doc_id": "low_coh", "score": 0.54, "phase_d_score": 0.7, "coherence_score": 0.1},
    ]
    ordered_on = _sort_candidates(candidates, diag, weighting_enabled=True)
    assert ordered_on[0]["doc_id"] == "high_coh"
    ordered_off = _sort_candidates(
        candidates,
        diag,
        weighting_enabled=True,
        enable_coherence_weighting=False,
    )
    assert ordered_off[0]["doc_id"] == "low_coh"


def test_coherence_combines_with_affect_signal():
    weight_with_coherence = phase_d_weight_for_cognitive(
        phase_d_score=0.6, affect_score=1.0, coherence_score=0.9
    )
    weight_without_coherence = phase_d_weight_for_cognitive(
        phase_d_score=0.6, affect_score=1.0, coherence_score=0.5
    )
    assert weight_with_coherence > weight_without_coherence


def test_quality_weighting_changes_order():
    diag = {"alpha_t": 0.5, "alpha_color": None, "quat_avg": 0.5}
    candidates = [
        {"doc_id": "high_quality", "score": 0.5, "phase_d_score": 0.7, "quality_score": 0.9},
        {"doc_id": "low_quality", "score": 0.54, "phase_d_score": 0.7, "quality_score": 0.1},
    ]
    ordered_on = _sort_candidates(candidates, diag, weighting_enabled=True)
    assert ordered_on[0]["doc_id"] == "high_quality"
    ordered_off = _sort_candidates(
        candidates,
        diag,
        weighting_enabled=True,
        enable_quality_weighting=False,
    )
    assert ordered_off[0]["doc_id"] == "low_quality"


def test_quality_combines_with_affect_and_coherence():
    weight_full = phase_d_weight_for_cognitive(
        phase_d_score=0.6,
        affect_score=0.8,
        coherence_score=0.8,
        quality_score=0.9,
    )
    weight_no_quality = phase_d_weight_for_cognitive(
        phase_d_score=0.6,
        affect_score=0.8,
        coherence_score=0.8,
        quality_score=0.5,
    )
    assert weight_full > weight_no_quality


def test_quality_weighting_monotonic():
    low = phase_d_weight_for_cognitive(phase_d_score=0.6, quality_score=0.2)
    mid = phase_d_weight_for_cognitive(phase_d_score=0.6, quality_score=0.5)
    high = phase_d_weight_for_cognitive(phase_d_score=0.6, quality_score=0.9)
    assert low < mid < high


def test_phase_d_priority_monotonic_and_gated():
    low = compute_phase_d_priority(
        affect_score=0.2,
        coherence_score=0.2,
        quality_score=0.2,
        rarity_score=0.2,
        recency_factor=0.8,
        alpha_color_adjustment=-0.03,
    )
    high = compute_phase_d_priority(
        affect_score=0.9,
        coherence_score=0.9,
        quality_score=0.9,
        rarity_score=0.9,
        recency_factor=1.0,
        alpha_color_adjustment=0.05,
    )
    assert low < high

    gated = compute_phase_d_priority(
        affect_score=0.9,
        coherence_score=0.9,
        quality_score=0.9,
        rarity_score=0.9,
        recency_factor=1.0,
        alpha_color_adjustment=0.05,
        enable_affect=False,
        enable_coherence=False,
        enable_quality=False,
        enable_rarity=False,
        enable_alpha_color=False,
    )
    neutral = compute_phase_d_priority()
    assert gated == neutral


def test_phase_d_priority_normalizes_when_requested():
    raw = compute_phase_d_priority(quality_score=0.9, priority_clip_max=1.5)
    normalized = compute_phase_d_priority(
        quality_score=0.9,
        priority_clip_max=1.5,
        priority_normalize=True,
    )
    assert 0.0 <= normalized <= 1.0
    assert normalized < raw  # normalization compresses into [0,1]
