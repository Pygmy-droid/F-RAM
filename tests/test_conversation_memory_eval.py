from __future__ import annotations

from pathlib import Path

import numpy as np

from fram_core.pipeline import tokenize_text
from fram_eval.conversation_memory_eval import (
    _cosine_similarity,
    _gate_query_tokens,
    _ifs_query_path,
    _max_overlap_ratio,
    _token_overlap_ratio,
    build_eval_store,
    build_fractal_ranker,
    evaluate_items,
    resolve_live_id_map,
)
from fram_serving.config import FRAMConfig
from fram_serving.fractal_memory import FractalGenerator
from fram_serving.memory import CognitiveMemoryStore


def test_conversation_eval_hits(tmp_path: Path) -> None:
    items = [
        {
            "id": "alpha",
            "query": "Remember the alpha event.",
            "answer": "Alpha happened at noon.",
            "probe": "Remember the alpha event.",
        },
        {
            "id": "beta",
            "query": "Recall the beta event.",
            "answer": "Beta happened at dusk.",
            "probe": "Recall the beta event.",
        },
    ]
    cfg = FRAMConfig()
    store, id_map, vectorizer = build_eval_store(
        items,
        store_root=tmp_path / "cognitive",
        config=cfg,
    )
    metrics = evaluate_items(
        items,
        store=store,
        id_map=id_map,
        query_field="probe",
        vectorizer=vectorizer,
        k_values=(1, 3),
    )
    assert metrics["top1"] >= 0.5
    assert metrics["top3"] == 1.0


def test_conversation_eval_details(tmp_path: Path) -> None:
    items = [
        {
            "id": "alpha",
            "query": "Remember the alpha event.",
            "answer": "Alpha happened at noon.",
            "probe": "Remember the alpha event.",
        },
        {
            "id": "beta",
            "query": "Recall the beta event.",
            "answer": "Beta happened at dusk.",
            "probe": "Recall the beta event.",
        },
    ]
    cfg = FRAMConfig()
    store, id_map, vectorizer = build_eval_store(
        items,
        store_root=tmp_path / "cognitive",
        config=cfg,
    )
    details = []
    metrics = evaluate_items(
        items,
        store=store,
        id_map=id_map,
        query_field="probe",
        vectorizer=vectorizer,
        k_values=(1, 3),
        details=details,
        details_topk=2,
    )
    assert metrics["top3"] == 1.0
    assert len(details) == 2
    assert details[0]["status"] in {"hit", "miss"}
    assert len(details[0]["top_results"]) <= 2


def test_live_probe_resolution(tmp_path: Path) -> None:
    cfg = FRAMConfig()
    store = CognitiveMemoryStore(tmp_path / "cognitive", config=cfg)
    store.append_episode(query="Alpha snapshot", answer="Alpha answer")
    second = store.append_episode(query="Alpha snapshot", answer="Alpha answer two")
    third = store.append_episode(query="Beta check", answer="Beta answer with token")
    items = [
        {
            "id": "alpha",
            "match_episode_id": second["id"],
            "probe": "Alpha snapshot",
            "probe_low_lex": "Alpha event",
        },
        {
            "id": "beta",
            "match_query": "Beta check",
            "match_answer": "token",
            "probe": "Beta check",
            "probe_low_lex": "Beta event",
        },
        {
            "id": "missing",
            "match_episode_id": "deadbeef",
            "probe": "Gamma check",
            "probe_low_lex": "Gamma event",
        },
    ]
    id_map, stats = resolve_live_id_map(items, store=store)
    assert id_map["alpha"] == second["id"]
    assert id_map["beta"] == third["id"]
    assert "missing" not in id_map
    assert stats["matched"] == 2
    assert stats["matched_by_id"] == 1
    assert stats["missing"] == 1
    assert stats["ambiguous"] == 0


def test_fractal_ranker_fallback(tmp_path: Path) -> None:
    items = [
        {
            "id": "alpha",
            "query": "Remember the alpha event.",
            "answer": "Alpha happened at noon.",
            "probe": "Remember the alpha event.",
        },
        {
            "id": "beta",
            "query": "Recall the beta event.",
            "answer": "Beta happened at dusk.",
            "probe": "Recall the beta event.",
        },
    ]
    cfg = FRAMConfig()
    store, id_map, vectorizer = build_eval_store(
        items,
        store_root=tmp_path / "cognitive",
        config=cfg,
    )
    ranker = build_fractal_ranker(
        store,
        vectorizer=vectorizer,
        config=cfg,
        influence_alpha=0.0,
    )
    metrics = evaluate_items(
        items,
        store=store,
        id_map=id_map,
        query_field="probe",
        vectorizer=None,
        ranker=ranker,
        k_values=(1, 3),
    )
    assert metrics["top1"] >= 0.5
    assert metrics["top3"] == 1.0


def test_fractal_ranker_cosine_mode(tmp_path: Path) -> None:
    items = [
        {
            "id": "alpha",
            "query": "Remember the alpha event.",
            "answer": "Alpha happened at noon.",
            "probe": "Remember the alpha event.",
        },
    ]
    cfg = FRAMConfig()
    store, _, vectorizer = build_eval_store(
        items,
        store_root=tmp_path / "cognitive",
        config=cfg,
    )
    ranker = build_fractal_ranker(
        store,
        vectorizer=vectorizer,
        config=cfg,
        influence_alpha=0.0,
        cosine_mode="centroid",
    )
    stats = getattr(ranker, "stats", {})
    assert stats["cosine_mode"] == "centroid"


def test_fractal_ranker_soft_dtw_score_mode(tmp_path: Path) -> None:
    items = [
        {
            "id": "alpha",
            "query": "Remember the alpha event.",
            "answer": "Alpha happened at noon.",
            "probe": "Remember the alpha event.",
        },
    ]
    cfg = FRAMConfig()
    store, _, vectorizer = build_eval_store(
        items,
        store_root=tmp_path / "cognitive",
        config=cfg,
    )
    ranker = build_fractal_ranker(
        store,
        vectorizer=vectorizer,
        config=cfg,
        influence_alpha=0.0,
        soft_dtw_score_mode="exp",
    )
    stats = getattr(ranker, "stats", {})
    assert stats["soft_dtw_score_mode"] == "exp"


def test_fractal_ranker_cosine_mode_delta(tmp_path: Path) -> None:
    items = [
        {
            "id": "alpha",
            "query": "Remember the alpha event.",
            "answer": "Alpha happened at noon.",
            "probe": "Remember the alpha event.",
        },
    ]
    cfg = FRAMConfig()
    store, _, vectorizer = build_eval_store(
        items,
        store_root=tmp_path / "cognitive",
        config=cfg,
    )
    ranker = build_fractal_ranker(
        store,
        vectorizer=vectorizer,
        config=cfg,
        influence_alpha=0.0,
        cosine_mode="delta",
    )
    stats = getattr(ranker, "stats", {})
    assert stats["cosine_mode"] == "delta"


def test_fractal_ranker_cosine_mode_turn_hist(tmp_path: Path) -> None:
    items = [
        {
            "id": "alpha",
            "query": "Remember the alpha event.",
            "answer": "Alpha happened at noon.",
            "probe": "Remember the alpha event.",
        },
    ]
    cfg = FRAMConfig()
    store, _, vectorizer = build_eval_store(
        items,
        store_root=tmp_path / "cognitive",
        config=cfg,
    )
    ranker = build_fractal_ranker(
        store,
        vectorizer=vectorizer,
        config=cfg,
        influence_alpha=0.0,
        cosine_mode="turn_hist",
    )
    stats = getattr(ranker, "stats", {})
    assert stats["cosine_mode"] == "turn_hist"


def test_fractal_ranker_cosine_mode_lag_dist(tmp_path: Path) -> None:
    items = [
        {
            "id": "alpha",
            "query": "Remember the alpha event.",
            "answer": "Alpha happened at noon.",
            "probe": "Remember the alpha event.",
        },
    ]
    cfg = FRAMConfig()
    store, _, vectorizer = build_eval_store(
        items,
        store_root=tmp_path / "cognitive",
        config=cfg,
    )
    ranker = build_fractal_ranker(
        store,
        vectorizer=vectorizer,
        config=cfg,
        influence_alpha=0.0,
        cosine_mode="lag_dist",
    )
    stats = getattr(ranker, "stats", {})
    assert stats["cosine_mode"] == "lag_dist"


def test_fractal_ranker_cosine_mode_radius_hist(tmp_path: Path) -> None:
    items = [
        {
            "id": "alpha",
            "query": "Remember the alpha event.",
            "answer": "Alpha happened at noon.",
            "probe": "Remember the alpha event.",
        },
    ]
    cfg = FRAMConfig()
    store, _, vectorizer = build_eval_store(
        items,
        store_root=tmp_path / "cognitive",
        config=cfg,
    )
    ranker = build_fractal_ranker(
        store,
        vectorizer=vectorizer,
        config=cfg,
        influence_alpha=0.0,
        cosine_mode="radius_hist",
    )
    stats = getattr(ranker, "stats", {})
    assert stats["cosine_mode"] == "radius_hist"


def test_fractal_ranker_cosine_mode_curvature_hist(tmp_path: Path) -> None:
    items = [
        {
            "id": "alpha",
            "query": "Remember the alpha event.",
            "answer": "Alpha happened at noon.",
            "probe": "Remember the alpha event.",
        },
    ]
    cfg = FRAMConfig()
    store, _, vectorizer = build_eval_store(
        items,
        store_root=tmp_path / "cognitive",
        config=cfg,
    )
    ranker = build_fractal_ranker(
        store,
        vectorizer=vectorizer,
        config=cfg,
        influence_alpha=0.0,
        cosine_mode="curvature_hist",
    )
    stats = getattr(ranker, "stats", {})
    assert stats["cosine_mode"] == "curvature_hist"


def test_fractal_ranker_trace_norm_mode_percentile(tmp_path: Path) -> None:
    items = [
        {
            "id": "alpha",
            "query": "Remember the alpha event.",
            "answer": "Alpha happened at noon.",
            "probe": "Remember the alpha event.",
        },
    ]
    cfg = FRAMConfig()
    store, _, vectorizer = build_eval_store(
        items,
        store_root=tmp_path / "cognitive",
        config=cfg,
    )
    ranker = build_fractal_ranker(
        store,
        vectorizer=vectorizer,
        config=cfg,
        influence_alpha=0.0,
        trace_norm_mode="percentile",
    )
    stats = getattr(ranker, "stats", {})
    assert stats["trace_norm_mode"] == "percentile"


def test_fractal_ranker_query_path_mode(tmp_path: Path) -> None:
    items = [
        {
            "id": "alpha",
            "query": "Remember the alpha event.",
            "answer": "Alpha happened at noon.",
            "probe": "Remember the alpha event.",
        },
    ]
    cfg = FRAMConfig()
    store, _, vectorizer = build_eval_store(
        items,
        store_root=tmp_path / "cognitive",
        config=cfg,
    )
    ranker = build_fractal_ranker(
        store,
        vectorizer=vectorizer,
        config=cfg,
        influence_alpha=0.0,
        query_path_mode="ifs",
    )
    stats = getattr(ranker, "stats", {})
    assert stats["query_path_mode"] == "ifs"


def test_fractal_ranker_low_lex_query_path_mode(tmp_path: Path) -> None:
    items = [
        {
            "id": "alpha",
            "query": "Remember the alpha event.",
            "answer": "Alpha happened at noon.",
            "probe": "Remember the alpha event.",
        },
    ]
    cfg = FRAMConfig()
    store, _, vectorizer = build_eval_store(
        items,
        store_root=tmp_path / "cognitive",
        config=cfg,
    )
    ranker = build_fractal_ranker(
        store,
        vectorizer=vectorizer,
        config=cfg,
        influence_alpha=0.0,
        query_path_mode="synthetic",
        low_lex_query_path_mode="ifs",
    )
    stats = getattr(ranker, "stats", {})
    assert stats["low_lex_query_path_mode"] == "ifs"


def test_low_lex_overlap_helpers() -> None:
    tokens = tokenize_text("Recall the phrase")
    assert _token_overlap_ratio(tokens, "Recall the phrase") == 1.0
    assert _token_overlap_ratio(tokens, "Unrelated text") == 0.0
    results = [
        {"kind": "episode", "query": "Recall the phrase", "answer": "Alpha"},
        {"kind": "episode", "query": "Different words", "answer": "Beta"},
    ]
    assert _max_overlap_ratio(tokens, results) == 1.0


def test_low_lex_overlap_answer_mode() -> None:
    tokens = tokenize_text("alpha")
    results = [{"kind": "episode", "query": "alpha cue", "answer": "beta"}]
    assert _max_overlap_ratio(tokens, results, overlap_mode="full") == 1.0
    assert _max_overlap_ratio(tokens, results, overlap_mode="answer") == 0.0


def test_gate_query_tokens_strip_quotes() -> None:
    tokens = _gate_query_tokens("Recall the phrase: 'silver orchard under red rain'.")
    assert "silver" not in tokens
    assert "phrase" in tokens
    fallback = _gate_query_tokens("'amber bell at ridge twelve'")
    assert "amber" in fallback


def test_cosine_similarity_helper() -> None:
    assert _cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert _cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_ifs_query_path_smoke() -> None:
    generator = FractalGenerator(embedding_dim=6, n_nodes=8)
    q6 = np.ones(6, dtype=float)
    path = _ifs_query_path(generator, q6, steps=5, ifs_seed=1, order_seed=2)
    assert path is not None
    assert path.shape == (5, 6)
