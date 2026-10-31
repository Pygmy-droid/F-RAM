from fram_core.memory_merge import merge_cognitive_ann_results
from fram_core.memory_merge import merge_with_gates


def test_merge_prefers_cognitive_on_duplicate_and_orders_by_score():
    ann = [
        {"candidate_id": "a1", "score": 0.9, "origin": "ann"},
        {"candidate_id": "b1", "score": 0.7, "origin": "ann"},
    ]
    cognitive = [
        {"candidate_id": "b1", "score": 0.95, "origin": "cognitive_memory"},
        {"candidate_id": "c1", "score": 0.5, "origin": "cognitive_memory"},
    ]

    merged = merge_cognitive_ann_results(ann, cognitive, k=3)
    ids = [c["candidate_id"] for c in merged]
    origins = [c["origin"] for c in merged]
    scores = [c["score"] for c in merged]

    # Cognitive duplicate should replace ann entry and lead on score.
    assert ids == ["b1", "a1", "c1"]
    assert origins[0] == "cognitive_memory"
    # Ensure ordering follows score
    assert scores[0] >= scores[1] >= scores[2]


def test_merge_respects_k_and_can_prefer_ann_first():
    ann = [
        {"candidate_id": "a1", "score": 0.4},
        {"candidate_id": "b1", "score": 0.3},
    ]
    cognitive = [
        {"candidate_id": "c1", "score": 0.2},
        {"candidate_id": "d1", "score": 0.1},
    ]

    merged = merge_cognitive_ann_results(ann, cognitive, k=2, prefer_cognitive=False)
    ids = [c["candidate_id"] for c in merged]
    assert ids == ["a1", "b1"]  # ANN first, truncated to k
    assert all(c["origin"] == "ann" for c in merged)


def test_merge_uses_file_chunk_key_for_dedup():
    ann = [{"file": "doc", "chunk_id": 1, "score": 0.8}]
    cognitive = [{"file": "doc", "chunk_id": 1, "score": 0.9}]

    merged = merge_cognitive_ann_results(ann, cognitive, k=2)
    assert len(merged) == 1
    assert merged[0]["origin"] == "cognitive_memory"


def test_merge_with_gates_disabled_returns_ann_only():
    ann = [{"candidate_id": "a1", "score": 0.6, "origin": "ann"}]
    cognitive = [{"candidate_id": "c1", "score": 0.9, "origin": "cognitive_memory"}]

    merged = merge_with_gates(ann, cognitive, k=3, enabled=False, fallback=cognitive)
    assert merged == ann  # unchanged when gate off


def test_merge_with_gates_enabled_includes_cognitive():
    ann = [{"candidate_id": "a1", "score": 0.4}]
    cognitive = [{"candidate_id": "c1", "score": 0.9}]

    merged = merge_with_gates(ann, cognitive, k=2, enabled=True, fallback=None)
    ids = [c["candidate_id"] for c in merged]
    assert ids[0] == "c1"  # cognitive wins on score when gate on


def test_merge_with_gates_fallback_to_recency_when_empty():
    merged = merge_with_gates([], [], k=2, enabled=True, fallback=[{"candidate_id": "f1"}])
    assert len(merged) == 1
    assert merged[0]["candidate_id"] == "f1"
