from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from fram_core.pipeline import _make_hashing_vectorizer as _pipeline_make_hashing_vectorizer
from fram_core.rotational_lift import LiftCapsule, recursive_reconstruct
from fram_serving.config import FRAMConfig
from fram_serving.memory_capsule import MemoryCapsuleStore

_TURNS = [
    {"role": "user", "text": "first turn about orchids", "time": "2025-12-31T00:00:00+00:00"},
    {"role": "assistant", "text": "second turn about beacons", "time": "2025-12-31T00:00:01+00:00"},
    {"role": "user", "text": "third turn about fog", "time": "2025-12-31T00:00:02+00:00"},
]


def _write(store: MemoryCapsuleStore, vectorizer, *, session_id: str, created_at: str) -> dict:
    result = store.write_capsule(
        turns=_TURNS,
        session_id=session_id,
        source={"kind": "test", "tool": "pytest", "version": "v0"},
        vectorizer=vectorizer,
        vectorizer_backend="hashing",
        created_at=created_at,
    )
    return json.loads(Path(result["path"]).read_text(encoding="utf-8"))


def _capsule_embeddings(payload: dict) -> np.ndarray:
    return np.array([e["embedding"] for e in payload["trajectory"]], dtype=float)


def _reconstruct_from_open_residuals(payload: dict) -> np.ndarray:
    record = payload["open_residuals"][0]
    final_state = np.array(record["final_state"], dtype=float)
    capsules = [
        LiftCapsule(
            previous_dim=c["previous_dim"],
            drop_axis=c["drop_axis"],
            rotation_plane=tuple(c["rotation_plane"]),
            rotation_theta=c["rotation_theta"],
            window_rule=c["window_rule"],
            residual_mode=c["residual_mode"],
            parent_id=c.get("parent_id"),
        )
        for c in record["capsules"]
    ]
    return recursive_reconstruct(final_state, capsules)


def test_lineage_window_defaults_to_zero() -> None:
    assert FRAMConfig().rotational_lift_lineage_window == 0


def test_lineage_window_zero_preserves_own_trajectory_only(tmp_path: Path) -> None:
    cfg = FRAMConfig(
        embedding_dim=16,
        rotational_lift_enabled=True,
        capsule_session_lineage_enabled=True,
        rotational_lift_lineage_window=0,
    )
    vectorizer = _pipeline_make_hashing_vectorizer(cfg)
    store = MemoryCapsuleStore(tmp_path, config=cfg)

    _write(store, vectorizer, session_id="s1", created_at="2025-12-31T00:00:00+00:00")
    second = _write(store, vectorizer, session_id="s1", created_at="2025-12-31T00:05:00+00:00")

    invariant = second["self_invariants"][0]
    assert invariant["trajectory_length"] == 3
    assert invariant["own_turn_count"] == 3
    assert invariant["ancestor_capsule_ids"] == []


def test_lineage_window_combines_immediate_parent_trajectory(tmp_path: Path) -> None:
    cfg = FRAMConfig(
        embedding_dim=16,
        rotational_lift_enabled=True,
        capsule_session_lineage_enabled=True,
        rotational_lift_lineage_window=1,
        rotational_lift_lift_hops=2,
    )
    vectorizer = _pipeline_make_hashing_vectorizer(cfg)
    store = MemoryCapsuleStore(tmp_path, config=cfg)

    first = _write(store, vectorizer, session_id="s1", created_at="2025-12-31T00:00:00+00:00")
    second = _write(store, vectorizer, session_id="s1", created_at="2025-12-31T00:05:00+00:00")

    invariant = second["self_invariants"][0]
    assert invariant["own_turn_count"] == 3
    assert invariant["trajectory_length"] == 6
    assert invariant["ancestor_capsule_ids"] == [first["capsule_id"]]

    residual_record = second["open_residuals"][0]
    assert residual_record["own_turn_count"] == 3
    assert residual_record["trajectory_length"] == 6
    assert residual_record["ancestor_capsule_ids"] == [first["capsule_id"]]

    expected_combined = np.concatenate(
        [_capsule_embeddings(first), _capsule_embeddings(second)], axis=0
    )
    reconstructed = _reconstruct_from_open_residuals(second)
    assert np.allclose(expected_combined, reconstructed, atol=1e-8)


def test_lineage_window_first_capsule_has_no_ancestors(tmp_path: Path) -> None:
    cfg = FRAMConfig(
        embedding_dim=16,
        rotational_lift_enabled=True,
        capsule_session_lineage_enabled=True,
        rotational_lift_lineage_window=1,
    )
    vectorizer = _pipeline_make_hashing_vectorizer(cfg)
    store = MemoryCapsuleStore(tmp_path, config=cfg)

    first = _write(store, vectorizer, session_id="s1", created_at="2025-12-31T00:00:00+00:00")

    invariant = first["self_invariants"][0]
    assert invariant["own_turn_count"] == 3
    assert invariant["trajectory_length"] == 3
    assert invariant["ancestor_capsule_ids"] == []


def test_lineage_window_walks_multiple_ancestors(tmp_path: Path) -> None:
    cfg = FRAMConfig(
        embedding_dim=16,
        rotational_lift_enabled=True,
        capsule_session_lineage_enabled=True,
        rotational_lift_lineage_window=2,
        rotational_lift_lift_hops=2,
    )
    vectorizer = _pipeline_make_hashing_vectorizer(cfg)
    store = MemoryCapsuleStore(tmp_path, config=cfg)

    a = _write(store, vectorizer, session_id="s1", created_at="2025-12-31T00:00:00+00:00")
    b = _write(store, vectorizer, session_id="s1", created_at="2025-12-31T00:05:00+00:00")
    c = _write(store, vectorizer, session_id="s1", created_at="2025-12-31T00:10:00+00:00")

    invariant = c["self_invariants"][0]
    assert invariant["own_turn_count"] == 3
    assert invariant["trajectory_length"] == 9
    # Oldest ancestor first.
    assert invariant["ancestor_capsule_ids"] == [a["capsule_id"], b["capsule_id"]]

    expected_combined = np.concatenate(
        [_capsule_embeddings(a), _capsule_embeddings(b), _capsule_embeddings(c)], axis=0
    )
    reconstructed = _reconstruct_from_open_residuals(c)
    assert np.allclose(expected_combined, reconstructed, atol=1e-8)


def test_lineage_window_skips_dimension_mismatched_ancestor_and_its_id(tmp_path: Path) -> None:
    """An ancestor written under a different embedding_dim contributes no
    embeddings (silently skipped, dimension mismatch) - so it must not be
    listed in ancestor_capsule_ids either. Provenance must not claim an
    ancestor contributed when none of its turns actually did."""

    cfg_a = FRAMConfig(
        embedding_dim=16,
        rotational_lift_enabled=True,
        capsule_session_lineage_enabled=True,
        rotational_lift_lineage_window=1,
    )
    store = MemoryCapsuleStore(tmp_path, config=cfg_a)
    vectorizer_a = _pipeline_make_hashing_vectorizer(cfg_a)
    first = _write(store, vectorizer_a, session_id="s1", created_at="2025-12-31T00:00:00+00:00")

    cfg_b = FRAMConfig(
        embedding_dim=8,
        rotational_lift_enabled=True,
        capsule_session_lineage_enabled=True,
        rotational_lift_lineage_window=1,
    )
    store._config = cfg_b  # reuse the same on-disk store under a reconfigured backend
    vectorizer_b = _pipeline_make_hashing_vectorizer(cfg_b)
    second = _write(store, vectorizer_b, session_id="s1", created_at="2025-12-31T00:05:00+00:00")

    assert second["links"][0]["target_capsule_id"] == first["capsule_id"]  # lineage link unaffected
    invariant = second["self_invariants"][0]
    assert invariant["own_turn_count"] == 3
    assert invariant["trajectory_length"] == 3  # ancestor's mismatched-dim turns contributed nothing
    assert invariant["ancestor_capsule_ids"] == []  # and must not be listed as provenance either


def test_lineage_window_never_affects_search(tmp_path: Path) -> None:
    ranking_fields = ("turn_index", "role", "text", "time", "score_raw", "match_type")
    results = {}
    for label, window in (("off", 0), ("on", 2)):
        cfg = FRAMConfig(
            embedding_dim=16,
            rotational_lift_enabled=True,
            capsule_session_lineage_enabled=True,
            rotational_lift_lineage_window=window,
        )
        vectorizer = _pipeline_make_hashing_vectorizer(cfg)
        store = MemoryCapsuleStore(tmp_path / label, config=cfg)
        _write(store, vectorizer, session_id="s1", created_at="2025-12-31T00:00:00+00:00")
        _write(store, vectorizer, session_id="s1", created_at="2025-12-31T00:05:00+00:00")
        found = store.search("orchids", k=3, vectorizer=vectorizer, vectorizer_backend="hashing")
        results[label] = [{field: item[field] for field in ranking_fields} for item in found]

    assert results["off"] == results["on"]
