from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer

from fram_serving.config import FRAMConfig
from fram_serving.memory import CognitiveMemoryStore


def _vectorizer():
    return HashingVectorizer(n_features=64, alternate_sign=False, norm="l2")


def _write_episode_with_vec(store: CognitiveMemoryStore, text: str, vectorizer):
    vec = vectorizer.transform([text]).toarray()[0]
    eid = store.append_episode(query=text, answer="", embedding=vec, embedding_backend="hashing")["id"]
    return eid, vec


def test_prior_session_recall_ann_bridge(tmp_path: Path):
    cfg = FRAMConfig().model_copy(
        update={
            "STORAGE_ROOT": tmp_path,
            "enable_cognitive_ann_bridge": True,
            "cognitive_ann_top_k": 2,
            "cognitive_ann_weight": 1.0,
            "cognitive_ann_floor_boost": 0.01,
        }
    )
    vec = _vectorizer()
    store = CognitiveMemoryStore(tmp_path / "memory", config=cfg)
    eid, _ = _write_episode_with_vec(store, "cats love laser pointers", vec)
    # Simulate restart: new store instance reads persisted vectors/meta.
    store_reloaded = CognitiveMemoryStore(tmp_path / "memory", config=cfg)
    cands, obs = store_reloaded.cognitive_ann_candidates(
        "laser pointers and cats",
        vectorizer=vec,
        top_k=2,
        weight=1.0,
        floor_boost=0.01,
    )
    ids = [c["doc_id"] for c in cands]
    assert any(eid in i for i in ids)
    assert obs["applied"] is True
    assert obs["bridge_disabled_reason"] is None or obs["bridge_disabled_reason"] == "bridge_disabled" if not obs["enabled"] else True


def test_gate_off_identity(tmp_path: Path):
    cfg = FRAMConfig().model_copy(update={"STORAGE_ROOT": tmp_path, "enable_cognitive_ann_bridge": False})
    vec = _vectorizer()
    store = CognitiveMemoryStore(tmp_path / "memory", config=cfg)
    _write_episode_with_vec(store, "alpha beta gamma", vec)
    cands, obs = store.cognitive_ann_candidates(
        "alpha beta", vectorizer=vec, top_k=2, weight=1.0, floor_boost=0.0
    )
    assert cands == []
    assert obs["bridge_disabled_reason"] is not None


def test_topk_weight_monotonicity(tmp_path: Path):
    cfg = FRAMConfig().model_copy(
        update={"STORAGE_ROOT": tmp_path, "enable_cognitive_ann_bridge": True, "cognitive_ann_top_k": 2}
    )
    vec = _vectorizer()
    store = CognitiveMemoryStore(tmp_path / "memory", config=cfg)
    _write_episode_with_vec(store, "alpha cat", vec)
    _write_episode_with_vec(store, "beta dog", vec)
    base = store.cognitive_ann_candidates("alpha", vectorizer=vec, top_k=1, weight=0.5, floor_boost=0.0)[0]
    boosted = store.cognitive_ann_candidates("alpha", vectorizer=vec, top_k=1, weight=2.0, floor_boost=0.0)[0]
    base_id = base[0]["doc_id"] if base else None
    boosted_id = boosted[0]["doc_id"] if boosted else None
    assert base_id == boosted_id  # ordering should not invert
    none_hit = store.cognitive_ann_candidates("alpha", vectorizer=vec, top_k=0, weight=1.0, floor_boost=0.0)[0]
    assert none_hit == []


def test_backend_mismatch_reason(tmp_path: Path):
    cfg = FRAMConfig().model_copy(update={"STORAGE_ROOT": tmp_path, "enable_cognitive_ann_bridge": True})
    vec = _vectorizer()
    store = CognitiveMemoryStore(tmp_path / "memory", config=cfg)
    _write_episode_with_vec(store, "alpha", vec)
    # Force fingerprint mismatch by editing meta
    meta_path = tmp_path / "memory" / CognitiveMemoryStore.FILE_VECTOR_META
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["fingerprint"] = "mismatch"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    cands, obs = CognitiveMemoryStore(tmp_path / "memory", config=cfg).cognitive_ann_candidates(
        "alpha", vectorizer=vec, top_k=1, weight=1.0, floor_boost=0.0
    )
    assert cands == []
    assert obs["bridge_disabled_reason"] == "fingerprint_mismatch"


def test_budget_enforcement_flag(tmp_path: Path):
    cfg = FRAMConfig().model_copy(
        update={
            "STORAGE_ROOT": tmp_path,
            "enable_cognitive_ann_bridge": True,
            "cognitive_ann_top_k": 5,
        }
    )
    vec = _vectorizer()
    store = CognitiveMemoryStore(tmp_path / "memory", config=cfg)
    for i in range(3):
        _write_episode_with_vec(store, f"item {i}", vec)
    cands, obs = store.cognitive_ann_candidates(
        "item",
        vectorizer=vec,
        top_k=5,
        weight=1.0,
        floor_boost=0.0,
        budget_cap=1,
    )
    assert len(cands) == 1
    assert obs["budget_exhausted"] is True


def test_ann_ordering_deterministic(tmp_path: Path):
    cfg = FRAMConfig().model_copy(
        update={
            "STORAGE_ROOT": tmp_path,
            "enable_cognitive_ann_bridge": True,
            "cognitive_ann_top_k": 3,
            "cognitive_ann_weight": 1.0,
        }
    )
    vec = _vectorizer()
    store = CognitiveMemoryStore(tmp_path / "memory", config=cfg)
    # Create near-tied vectors by adjusting text slightly.
    ids = []
    ids.append(_write_episode_with_vec(store, "alpha beta gamma", vec)[0])
    ids.append(_write_episode_with_vec(store, "alpha beta delta", vec)[0])
    ids.append(_write_episode_with_vec(store, "alpha beta epsilon", vec)[0])
    res1 = store.cognitive_ann_candidates("alpha beta", vectorizer=vec, top_k=3, weight=1.0, floor_boost=0.0)[0]
    res2 = store.cognitive_ann_candidates("alpha beta", vectorizer=vec, top_k=3, weight=1.0, floor_boost=0.0)[0]
    order1 = [c["doc_id"] for c in res1]
    order2 = [c["doc_id"] for c in res2]
    assert order1 == order2
