"""Cross-source ranking uses similarity without changing lived search policy."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from fram_eval.production_memory_eval import (
    ExactTraceCache,
    build_context,
    capture_selection,
    isolated_evaluation,
    snapshot_memory,
    tree_manifest,
)
from fram_serving.config import FRAMConfig
from fram_serving.lived_memory import LivedMemoryStore
from fram_serving.memory import CognitiveMemoryStore

CLOCK = datetime(2027, 1, 1, tzinfo=timezone.utc)
BASIS = np.eye(8)


class CueVectorizer:
    """Independent query directions make target source membership explicit."""

    def transform(self, texts):
        return np.stack(
            [BASIS[1] if "lived cue" in text else BASIS[0] for text in texts]
        )


def _fixture(tmp_path, *, ann=False, aged=False, equal_negative=False):
    source = tmp_path / "source" / "memory"
    cfg = FRAMConfig(
        STORAGE_ROOT=tmp_path / "source",
        embedding_dim=8,
        cognitive_memory_embedding_backend="hashing",
        cognitive_memory_k=8,
        cognitive_memory_trace_k=16,
        cognitive_memory_slot_budget=0,
        cognitive_memory_token_budget=0,
        cognitive_memory_query_recall_weight=0.0,
        cognitive_memory_half_life_hours=12.0,
        enable_cognitive_ann_bridge=ann,
        cognitive_ann_top_k=8,
        cognitive_ann_weight=1.0,
        cognitive_ann_floor_boost=0.01,
        fractal_enabled=False,
        fractal_influence_enabled=False,
        memory_capsule_enabled=False,
        lived_memory_enabled=True,
        lived_memory_target_dim=12,
        lived_memory_fractal_nodes=8,
        lived_memory_recall_k=8,
    )
    cognitive = CognitiveMemoryStore(source / "cognitive", config=cfg)
    # Write synthetic dates through the normal append path, not by editing memory.
    stamp = CLOCK - timedelta(hours=108 if aged else 0)
    cognitive._now_iso = lambda: stamp.isoformat()
    embedding = (
        0.9 * BASIS[0] + np.sqrt(0.19) * BASIS[2]
        if aged
        else 0.4 * BASIS[0] + 0.1 * BASIS[1] + np.sqrt(0.83) * BASIS[2]
    )
    episode = cognitive.append_episode(
        query="cognitive cue: archive location",
        answer="The archive is in the blue cabinet.",
        embedding=embedding.tolist(),
        embedding_backend="hashing",
    )
    lived = LivedMemoryStore(tmp_path / "fixture-live", target_dim=12, fractal_nodes=8)
    vectors = (
        {"moderate": 0.6 * BASIS[0] + 0.8 * BASIS[1]}
        if aged
        else {
            "neutral": np.zeros(8),
            "opposed": -BASIS[0],
            "relevant": BASIS[1],
            "related": 0.6 * BASIS[1] + 0.8 * BASIS[3],
        }
    )
    if equal_negative:
        vectors = {"short": -BASIS[0], "long": -BASIS[0]}
    for name, vector in vectors.items():
        lived.append_experience(
            query=f"lived cue: {name} garden visit",
            answer=(
                "A longer synthetic experience with several additional garden details."
                if name == "long"
                else f"Synthetic {name} experience."
            ),
            embedding=vector.tolist(),
            embedding_backend="hashing",
            event_id=name,
            session_id=f"independent-{name}",
            created_at=(
                CLOCK - timedelta(hours=1 if name == "long" else 0)
            ).isoformat(),
        )
    assert lived.verify()["valid"]
    (source / "lived").mkdir()
    with closing(sqlite3.connect(lived.path)) as origin:
        with closing(
            sqlite3.connect(source / "lived" / "lived_memory.sqlite3")
        ) as backup:
            origin.backup(backup)
            backup.execute("PRAGMA journal_mode=DELETE")
    before = tree_manifest(source)
    snapshot_memory(source, tmp_path / "run" / "memory")
    ctx = build_context(tmp_path / "run", cfg)
    vectorizer = CueVectorizer()
    ctx.get_memory_vectorizer = lambda: vectorizer
    ctx.encode_cognitive_text = lambda text: (
        vectorizer.transform([text])[0].tolist(),
        "hashing",
    )
    return ctx, source, before, f"cmem:ep:{episode['id']}"


def _capture(ctx, query):
    with isolated_evaluation(ctx.cfg.STORAGE_ROOT, ExactTraceCache(), CLOCK):
        return capture_selection(ctx, query)


@pytest.mark.parametrize("ann", [False, True])
def test_relevant_cognitive_beats_neutral_lived_without_source_offset(tmp_path, ann):
    ctx, source, before, episode_id = _fixture(tmp_path, ann=ann)
    lived = ctx.lived_memory_store.search(BASIS[0], k=8)
    neutral = next(row for row in lived if row["event_id"] == "neutral")
    # The full embedding is neutral; the unchanged projection blend can add
    # a small similarity. It must not gain an additional +0.5 source offset.
    assert neutral["embedding_similarity"] == 0.0
    assert abs(neutral["_score_raw"]) < 0.1
    assert neutral["_score"] > 0.4
    capture = _capture(ctx, "cognitive cue")
    selected = {row["id"]: row for row in capture["selected"]}
    assert capture["selected"][0]["id"] == episode_id
    assert selected[episode_id]["score"] == pytest.approx(0.41 if ann else 0.4)
    assert selected[episode_id]["score"] < neutral["_score"]
    assert selected["lmem:event:neutral"]["score"] == neutral["_score_raw"]
    assert tree_manifest(source) == before


@pytest.mark.parametrize("ann", [False, True])
def test_relevant_lived_wins_and_within_lived_order_is_preserved(tmp_path, ann):
    ctx, source, before, episode_id = _fixture(tmp_path, ann=ann)
    direct = ctx.lived_memory_store.search(BASIS[1], k=8)
    capture = _capture(ctx, "lived cue")
    assert direct[0]["event_id"] == "relevant"
    assert capture["selected"][0]["id"] == "lmem:event:relevant"
    by_id = {row["id"]: row for row in capture["selected"]}
    assert by_id[episode_id]["score"] == pytest.approx(0.11 if ann else 0.1)
    selected_lived = [row for row in capture["selected"] if row["kind"] == "lived"]
    assert [row["id"] for row in selected_lived] == [
        f"lmem:event:{row['event_id']}" for row in direct
    ]
    for selected, original in zip(selected_lived, direct):
        assert selected["score"] == pytest.approx(original["_score_raw"])
        assert selected["score_raw"] == pytest.approx(original["_score_raw"])
        assert selected["lineage"] == original["lineage"]
    assert tree_manifest(source) == before


def test_nonpositive_lived_candidates_remain_eligible_and_reach_orchestrator(
    tmp_path, monkeypatch
):
    ctx, source, before, _ = _fixture(tmp_path)
    original_search = ctx.lived_memory_store.search

    def search_with_exact_zero(*args, **kwargs):
        results = original_search(*args, **kwargs)
        # Exercise the exact allowed zero boundary without changing stored
        # embeddings, projection math, or other real source results.
        neutral = next(row for row in results if row["event_id"] == "neutral")
        neutral.update(_score_raw=0.0, _score=0.5)
        return results

    monkeypatch.setattr(ctx.lived_memory_store, "search", search_with_exact_zero)
    direct = ctx.lived_memory_store.search(BASIS[0], k=8)
    capture = _capture(ctx, "cognitive cue")
    rows = {row["id"]: row for row in capture["selected"]}
    assert rows["lmem:event:opposed"]["score"] < 0.0
    assert rows["lmem:event:neutral"]["score"] == 0.0
    assert {row["id"] for row in rows.values() if row["kind"] == "lived"} == {
        f"lmem:event:{row['event_id']}" for row in direct
    }
    chunks = {chunk["file"]: chunk for chunk in capture["chunks"]}
    for name in ("neutral", "opposed"):
        doc_id = f"lmem:event:{name}"
        assert chunks[doc_id]["score"] == rows[doc_id]["score"]
        assert chunks[doc_id]["text"]
    assert tree_manifest(source) == before


def test_scale_correction_preserves_existing_cognitive_recency_weight(tmp_path):
    ctx, source, before, episode_id = _fixture(tmp_path, aged=True)
    capture = _capture(ctx, "cognitive cue")
    rows = {row["id"]: row for row in capture["selected"]}
    cognitive = rows[episode_id]
    lived = rows["lmem:event:moderate"]
    assert cognitive["score_raw"] == pytest.approx(0.9)
    assert cognitive["recency_weight"] == pytest.approx(0.1)
    assert cognitive["score"] == pytest.approx(0.09)
    assert cognitive["score"] < lived["score"] < cognitive["score_raw"]
    assert lived["recency_weight"] == 1.0
    assert capture["selected"][0]["id"] == "lmem:event:moderate"
    assert tree_manifest(source) == before


def test_equal_negative_lived_scores_use_shared_score_per_token_tie_rule(tmp_path):
    ctx, source, before, _ = _fixture(tmp_path, equal_negative=True)
    direct = ctx.lived_memory_store.search(BASIS[0], k=8)
    assert [row["event_id"] for row in direct] == ["short", "long"]
    assert direct[0]["_score_raw"] == direct[1]["_score_raw"] < 0.0
    capture = _capture(ctx, "cognitive cue")
    lived = [row for row in capture["selected"] if row["kind"] == "lived"]
    # Unlike the positive normalized API score, a negative shared ranking score
    # divided by more tokens is larger. Keep that common tie rule explicit.
    assert [row["id"] for row in lived] == ["lmem:event:long", "lmem:event:short"]
    assert lived[0]["tokens"] > lived[1]["tokens"]
    assert lived[0]["score"] == lived[1]["score"] == direct[0]["_score_raw"]
    assert ctx.lived_memory_store.search(BASIS[0], k=8) == direct
    assert tree_manifest(source) == before


def test_lived_search_api_retains_normalized_scores_and_source_bytes(
    tmp_path, monkeypatch
):
    from fastapi.testclient import TestClient

    from fram_serving import app as app_mod

    ctx, source, before, _ = _fixture(tmp_path)
    store = ctx.lived_memory_store
    expected = store.search(BASIS[0], k=8)
    monkeypatch.setattr(app_mod, "_get_lived_store", lambda: store)
    monkeypatch.setattr(app_mod, "_encode_cognitive_text", ctx.encode_cognitive_text)
    response = TestClient(app_mod.app).get(
        "/memory/lived/search", params={"query": "cognitive cue", "k": 8}
    )
    assert response.status_code == 200
    assert response.json()["items"] == expected
    for row in response.json()["items"]:
        assert row["_score"] == pytest.approx(0.5 * (row["_score_raw"] + 1.0))
    _capture(ctx, "cognitive cue")
    assert store.search(BASIS[0], k=8) == expected
    assert tree_manifest(source) == before
