from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from fram_serving.config import FRAMConfig
from fram_serving.memory import CognitiveMemoryStore
from fram_core.pipeline import _make_hashing_vectorizer as _pipeline_make_hashing_vectorizer


def test_append_and_search_episodes_and_beliefs(tmp_path: Path):
    cfg = FRAMConfig()
    vectorizer = _pipeline_make_hashing_vectorizer(cfg)
    store = CognitiveMemoryStore(tmp_path, config=cfg)
    backend = str(cfg.cognitive_memory_embedding_backend)

    def embed(text: str) -> list[float]:
        mat = vectorizer.transform([text])
        if hasattr(mat, "toarray"):
            arr = mat.toarray()[0]
        else:
            arr = np.asarray(mat, dtype=float).ravel()
        return arr.tolist()

    episode_text_1 = "What is OrthoRoute?\nOrthoRoute is the calibrated routing strategy in FRAM v2.2."
    episode_embedding_1 = embed(episode_text_1)
    ep1 = store.append_episode(
        query="What is OrthoRoute?",
        domain="general",
        task="qa",
        answer="OrthoRoute is the calibrated routing strategy in FRAM v2.2.",
        citations=["docs:FRAMv2.2-SPEC.md"],
        embedding=episode_embedding_1,
    )
    episode_text_2 = "How do anchors work?\nAnchors walk residual eigenpairs and probe curvature"
    episode_embedding_2 = embed(episode_text_2)
    ep2 = store.append_episode(
        query="How do anchors work?",
        domain="roadmap",
        task="qa",
        answer="Anchors walk residual eigenpairs and probe curvature",
        citations=["docs:FRAMv2.2-cheatsheet.md"],
        embedding=episode_embedding_2,
    )
    belief_text = "FRAM uses conformal thresholds tau1/tau2 to decide widening"
    belief_embedding = embed(belief_text)
    bl1 = store.append_belief(
        text=belief_text,
        source_episode=ep1["id"],
        confidence=0.85,
        embedding=belief_embedding,
    )
    expected_dim = len(episode_embedding_1)

    # Basic search over combined pool
    hits = store.search("conformal thresholds in FRAM", k=5, vectorizer=vectorizer)
    assert hits, "expected some hits"
    kinds = {h["kind"] for h in hits}
    assert {"episode", "belief"} & kinds, "expected episodes or beliefs in results"
    assert hits[0]["id"] == bl1["id"]

    # Filters apply to episodes
    road_hits = store.search("anchors residual eigenpairs", k=5, filters={"domain": "roadmap"}, vectorizer=vectorizer)
    assert any(h["kind"] == "episode" and h.get("domain") == "roadmap" for h in road_hits)

    # Kind filters narrow the pool to episodes or beliefs
    episode_hits = store.search(
        "conformal thresholds in FRAM", k=5, filters={"kinds": ["episode"]}, vectorizer=vectorizer
    )
    assert episode_hits
    assert all(h["kind"] == "episode" for h in episode_hits)
    belief_hits = store.search(
        "conformal thresholds in FRAM", k=5, filters={"kinds": ["belief"]}, vectorizer=vectorizer
    )
    assert belief_hits
    assert all(h["kind"] == "belief" for h in belief_hits)

    # Vector metadata recorded once embeddings are supplied
    meta_path = tmp_path / CognitiveMemoryStore.FILE_VECTOR_META
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["embedding_backend"] == backend
    assert meta["dim"] == expected_dim

    # Episode vectors persisted with ids
    episode_vectors_path = tmp_path / CognitiveMemoryStore.FILE_EPISODE_VECTORS
    assert episode_vectors_path.exists()
    episode_vectors = [json.loads(line) for line in episode_vectors_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(entry["id"] == ep1["id"] for entry in episode_vectors)
    assert all(len(entry["vector"]) == expected_dim for entry in episode_vectors)

    belief_vectors_path = tmp_path / CognitiveMemoryStore.FILE_BELIEF_VECTORS
    assert belief_vectors_path.exists()
    belief_vectors = [json.loads(line) for line in belief_vectors_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(entry["id"] == bl1["id"] for entry in belief_vectors)
    assert all(len(entry["vector"]) == expected_dim for entry in belief_vectors)

def test_summarize_window(tmp_path: Path):
    store = CognitiveMemoryStore(tmp_path)
    for i in range(3):
        store.append_episode(query=f"q{i}", domain="d", task="t", answer=f"a{i}")
    for i in range(2):
        store.append_belief(text=f"b{i}")
    store.append_link(src_id="x", dst_id="y", link_type="supports")

    summary = store.summarize(window=2)
    assert summary["counts"]["episodes"] >= 3
    assert summary["counts"]["beliefs"] >= 2
    assert summary["counts"]["links"] >= 1
    assert len(summary["recent"]["episodes"]) <= 2
    assert len(summary["recent"]["beliefs"]) <= 2
    assert len(summary["recent"]["links"]) <= 2


def test_beliefs_do_not_emit_legitimacy_tiers(tmp_path: Path) -> None:
    store = CognitiveMemoryStore(tmp_path)
    entry = store.append_belief(text="FRAM belief with citations", citations=["docs:note.md"])
    assert "promotion_status" not in entry
    assert "promotion_reason" not in entry

    records = list(store._iter_belief_records())
    assert records, "expected belief record to persist"
    last = records[-1]
    assert "promotion_status" not in last
    assert "promotion_reason" not in last


def test_query_recall_weight_boosts_query_matches(tmp_path: Path) -> None:
    cfg = FRAMConfig(cognitive_memory_query_recall_weight=0.7)
    vectorizer = _pipeline_make_hashing_vectorizer(cfg)
    store = CognitiveMemoryStore(tmp_path, config=cfg)

    def embed(text: str) -> list[float]:
        mat = vectorizer.transform([text])
        if hasattr(mat, "toarray"):
            arr = mat.toarray()[0]
        else:
            arr = np.asarray(mat, dtype=float).ravel()
        return arr.tolist()

    base_text = "alpha beta"
    embedding = embed(base_text)
    ep1 = store.append_episode(
        query="gamma delta",
        domain="general",
        task="qa",
        answer=base_text,
        embedding=embedding,
    )
    ep2 = store.append_episode(
        query="alpha beta",
        domain="general",
        task="qa",
        answer=base_text,
        embedding=embedding,
    )

    hits = store.search("alpha beta", k=2, vectorizer=vectorizer)
    assert hits, "expected search hits"
    assert hits[0]["id"] == ep2["id"]


def test_backfill_embeddings_writes_vectors(tmp_path: Path) -> None:
    cfg = FRAMConfig()
    vectorizer = _pipeline_make_hashing_vectorizer(cfg)
    store = CognitiveMemoryStore(tmp_path, config=cfg)
    store.append_episode(query="hello", domain="general", task="qa", answer="world")
    store.append_belief(text="alpha beta")

    result = store.backfill_embeddings(vectorizer=vectorizer, backend="hashing", batch_size=2)
    assert result["episodes_written"] == 1
    assert result["beliefs_written"] == 1

    episode_vectors_path = tmp_path / CognitiveMemoryStore.FILE_EPISODE_VECTORS
    belief_vectors_path = tmp_path / CognitiveMemoryStore.FILE_BELIEF_VECTORS
    meta_path = tmp_path / CognitiveMemoryStore.FILE_VECTOR_META
    assert episode_vectors_path.exists()
    assert belief_vectors_path.exists()
    assert meta_path.exists()


def test_semantic_backend_uses_separate_vector_files(tmp_path: Path) -> None:
    cfg = FRAMConfig(cognitive_memory_embedding_backend="semantic")
    store = CognitiveMemoryStore(tmp_path, config=cfg)
    store.append_episode(
        query="q",
        domain="general",
        task="qa",
        answer="a",
        embedding=[0.1, 0.2],
        embedding_backend="semantic",
    )

    episode_vectors_path = tmp_path / "episodes.vectors.semantic.jsonl"
    meta_path = tmp_path / "vectors.meta.semantic.json"
    assert episode_vectors_path.exists()
    assert meta_path.exists()


def test_cognitive_memory_half_life_hours_defaults_to_prior_hardcoded_value() -> None:
    # fram_serving/memory.py's _recency_weight previously read this via
    # getattr(self._config, "cognitive_memory_half_life_hours", 12.0) with no
    # matching FRAMConfig field to actually set it - so it always silently
    # resolved to this same 12.0 fallback. This field now exists for real;
    # the default is pinned to match so existing behavior is unchanged.
    assert FRAMConfig().cognitive_memory_half_life_hours == 12.0


def _search_with_half_life(tmp_path: Path, half_life_hours: float) -> bool:
    """Returns True if the old-but-highly-relevant episode wins the search."""

    cfg = FRAMConfig(cognitive_memory_half_life_hours=half_life_hours)
    vectorizer = _pipeline_make_hashing_vectorizer(cfg)
    store = CognitiveMemoryStore(tmp_path, config=cfg)

    def embed(text: str) -> list[float]:
        mat = vectorizer.transform([text])
        if hasattr(mat, "toarray"):
            arr = mat.toarray()[0]
        else:
            arr = np.asarray(mat, dtype=float).ravel()
        return arr.tolist()

    old_ep = store.append_episode(
        query="lumen recall cue",
        domain="general",
        task="qa",
        answer="lumen recall cue details explained",
        embedding=embed("lumen recall cue details explained"),
    )
    fresh_ep = store.append_episode(
        query="totally unrelated topic",
        domain="general",
        task="qa",
        answer="a cue about something else entirely",
        embedding=embed("a cue about something else entirely"),
    )

    # Backdate the highly-relevant episode to 90 days old, matching the
    # ~26-93 day age range of the probes that collapsed in the real
    # 2026-01-21 eval run this test is reproducing the mechanism of.
    episodes_path = tmp_path / CognitiveMemoryStore.FILE_EPISODES
    old_iso = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
    records = [
        json.loads(line) for line in episodes_path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    for record in records:
        if record["id"] == old_ep["id"]:
            record["time"] = old_iso
    episodes_path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")

    hits = store.search("lumen recall cue", k=2, vectorizer=vectorizer)
    assert hits, "expected search hits"
    winner = hits[0]["id"]
    assert winner in (old_ep["id"], fresh_ep["id"])
    return winner == old_ep["id"]


def test_cognitive_memory_half_life_hours_reproduces_and_fixes_eval_anomaly(tmp_path: Path) -> None:
    """Reproduces the mechanism diagnosed as the root cause of the
    2026-01-21 conversation-memory eval's top1=0.000 collapse across all
    retrieval modes: under the (previously hardcoded, now configurable) 12h
    half-life, a fresh-but-barely-relevant episode outranks an old-but-
    highly-relevant one. A realistic half-life for a long-lived benchmark
    corpus (here, a multi-year value) lets the truly relevant episode win -
    proving cognitive_memory_half_life_hours is now genuinely read, not
    just accepted and ignored.
    """

    old_wins_default = _search_with_half_life(tmp_path / "default", 12.0)
    old_wins_long = _search_with_half_life(tmp_path / "long", 24.0 * 365)

    assert old_wins_default is False
    assert old_wins_long is True


def test_cognitive_memory_half_life_hours_zero_is_not_silently_overridden(tmp_path: Path) -> None:
    """An explicit half_life=0.0 (maximal decay) must not be coerced back to
    the 12.0 default via a falsy-zero `or` fallback - it's a meaningful,
    reachable configuration (clamped to a tiny positive scale downstream,
    not a divide-by-zero), not the same thing as "unset"."""

    cfg = FRAMConfig(cognitive_memory_half_life_hours=0.0)
    vectorizer = _pipeline_make_hashing_vectorizer(cfg)
    store = CognitiveMemoryStore(tmp_path, config=cfg)

    def embed(text: str) -> list[float]:
        mat = vectorizer.transform([text])
        arr = mat.toarray()[0] if hasattr(mat, "toarray") else np.asarray(mat, dtype=float).ravel()
        return arr.tolist()

    ep = store.append_episode(
        query="alpha beta", domain="general", task="qa", answer="alpha beta", embedding=embed("alpha beta")
    )

    # Backdate by 10 minutes - under half_life=0.0 (scale clamped to 1e-3h),
    # that's already ~167x the clamped scale, crushing the weight well below
    # 0.01; under the 12.0-hour default the same 10 minutes would barely
    # register (weight ~0.986).
    episodes_path = tmp_path / CognitiveMemoryStore.FILE_EPISODES
    old_iso = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    records = [json.loads(line) for line in episodes_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for record in records:
        if record["id"] == ep["id"]:
            record["time"] = old_iso
    episodes_path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")

    hits = store.search("alpha beta", k=1, vectorizer=vectorizer)
    assert hits
    assert hits[0]["_recency_weight"] < 0.01
