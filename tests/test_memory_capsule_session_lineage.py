from __future__ import annotations

import json
from pathlib import Path

from fram_core.pipeline import _make_hashing_vectorizer as _pipeline_make_hashing_vectorizer
from fram_serving.config import FRAMConfig
from fram_serving.memory_capsule import MemoryCapsuleStore

_TURNS = [
    {"role": "user", "text": "first turn about orchids", "time": "2025-12-31T00:00:00+00:00"},
    {"role": "assistant", "text": "second turn about beacons", "time": "2025-12-31T00:00:01+00:00"},
    {"role": "user", "text": "third turn about fog", "time": "2025-12-31T00:00:02+00:00"},
]


def _write(store: MemoryCapsuleStore, vectorizer, *, session_id, created_at) -> dict:
    result = store.write_capsule(
        turns=_TURNS,
        session_id=session_id,
        source={"kind": "test", "tool": "pytest", "version": "v0"},
        vectorizer=vectorizer,
        vectorizer_backend="hashing",
        created_at=created_at,
    )
    return json.loads(Path(result["path"]).read_text(encoding="utf-8"))


def test_session_lineage_disabled_by_default(tmp_path: Path) -> None:
    cfg = FRAMConfig(embedding_dim=16)
    assert cfg.capsule_session_lineage_enabled is False
    vectorizer = _pipeline_make_hashing_vectorizer(cfg)
    store = MemoryCapsuleStore(tmp_path, config=cfg)

    first = _write(store, vectorizer, session_id="s1", created_at="2025-12-31T00:00:00+00:00")
    second = _write(store, vectorizer, session_id="s1", created_at="2025-12-31T00:05:00+00:00")

    assert first["links"] == []
    assert second["links"] == []


def test_session_lineage_finds_previous_capsule_same_session(tmp_path: Path) -> None:
    cfg = FRAMConfig(embedding_dim=16, capsule_session_lineage_enabled=True)
    vectorizer = _pipeline_make_hashing_vectorizer(cfg)
    store = MemoryCapsuleStore(tmp_path, config=cfg)

    first = _write(store, vectorizer, session_id="s1", created_at="2025-12-31T00:00:00+00:00")
    second = _write(store, vectorizer, session_id="s1", created_at="2025-12-31T00:05:00+00:00")

    assert first["links"] == []
    assert len(second["links"]) == 1
    link = second["links"][0]
    assert link["kind"] == "continues"
    assert link["target_capsule_id"] == first["capsule_id"]


def test_session_lineage_ignores_different_session(tmp_path: Path) -> None:
    cfg = FRAMConfig(embedding_dim=16, capsule_session_lineage_enabled=True)
    vectorizer = _pipeline_make_hashing_vectorizer(cfg)
    store = MemoryCapsuleStore(tmp_path, config=cfg)

    _write(store, vectorizer, session_id="s1", created_at="2025-12-31T00:00:00+00:00")
    other_session = _write(store, vectorizer, session_id="s2", created_at="2025-12-31T00:05:00+00:00")

    assert other_session["links"] == []


def test_session_lineage_requires_session_id(tmp_path: Path) -> None:
    cfg = FRAMConfig(embedding_dim=16, capsule_session_lineage_enabled=True)
    vectorizer = _pipeline_make_hashing_vectorizer(cfg)
    store = MemoryCapsuleStore(tmp_path, config=cfg)

    payload = _write(store, vectorizer, session_id=None, created_at="2025-12-31T00:00:00+00:00")
    assert payload["links"] == []


def test_session_lineage_and_rotational_lift_tag_first_capsule_parent_id(tmp_path: Path) -> None:
    cfg = FRAMConfig(
        embedding_dim=16,
        capsule_session_lineage_enabled=True,
        rotational_lift_enabled=True,
        rotational_lift_lift_hops=2,
    )
    vectorizer = _pipeline_make_hashing_vectorizer(cfg)
    store = MemoryCapsuleStore(tmp_path, config=cfg)

    first = _write(store, vectorizer, session_id="s1", created_at="2025-12-31T00:00:00+00:00")
    second = _write(store, vectorizer, session_id="s1", created_at="2025-12-31T00:05:00+00:00")

    first_capsules = first["open_residuals"][0]["capsules"]
    assert first_capsules[0]["parent_id"] is None  # no predecessor for the first capsule

    second_capsules = second["open_residuals"][0]["capsules"]
    assert second_capsules[0]["parent_id"] == first["capsule_id"]
    # Only the first hop is tagged - later hops in the same chain are not the
    # cross-capsule link, they're still internal-to-this-capsule hops.
    assert all(c["parent_id"] is None for c in second_capsules[1:])


def test_session_lineage_scan_limit_stops_before_finding_buried_parent(tmp_path: Path) -> None:
    cfg = FRAMConfig(
        embedding_dim=16,
        capsule_session_lineage_enabled=True,
        capsule_session_lineage_scan_limit=3,
    )
    vectorizer = _pipeline_make_hashing_vectorizer(cfg)
    store = MemoryCapsuleStore(tmp_path, config=cfg)

    _write(store, vectorizer, session_id="s1", created_at="2025-12-31T00:00:00+00:00")
    # Bury the s1 parent behind more capsules than the scan limit allows.
    for i in range(4):
        _write(store, vectorizer, session_id="noise", created_at=f"2025-12-31T00:0{i + 1}:00+00:00")
    child = _write(store, vectorizer, session_id="s1", created_at="2025-12-31T00:10:00+00:00")

    assert child["links"] == []


def test_session_lineage_scan_limit_high_enough_finds_parent(tmp_path: Path) -> None:
    cfg = FRAMConfig(
        embedding_dim=16,
        capsule_session_lineage_enabled=True,
        capsule_session_lineage_scan_limit=10,
    )
    vectorizer = _pipeline_make_hashing_vectorizer(cfg)
    store = MemoryCapsuleStore(tmp_path, config=cfg)

    first = _write(store, vectorizer, session_id="s1", created_at="2025-12-31T00:00:00+00:00")
    for i in range(4):
        _write(store, vectorizer, session_id="noise", created_at=f"2025-12-31T00:0{i + 1}:00+00:00")
    child = _write(store, vectorizer, session_id="s1", created_at="2025-12-31T00:10:00+00:00")

    assert len(child["links"]) == 1
    assert child["links"][0]["target_capsule_id"] == first["capsule_id"]


def test_session_lineage_never_affects_search(tmp_path: Path) -> None:
    cfg_off = FRAMConfig(embedding_dim=16, capsule_session_lineage_enabled=False)
    cfg_on = FRAMConfig(embedding_dim=16, capsule_session_lineage_enabled=True)

    ranking_fields = ("turn_index", "role", "text", "time", "score_raw", "match_type")
    results = {}
    for label, cfg in (("off", cfg_off), ("on", cfg_on)):
        vectorizer = _pipeline_make_hashing_vectorizer(cfg)
        store = MemoryCapsuleStore(tmp_path / label, config=cfg)
        _write(store, vectorizer, session_id="s1", created_at="2025-12-31T00:00:00+00:00")
        _write(store, vectorizer, session_id="s1", created_at="2025-12-31T00:05:00+00:00")
        found = store.search("orchids", k=3, vectorizer=vectorizer, vectorizer_backend="hashing")
        results[label] = [{field: item[field] for field in ranking_fields} for item in found]

    assert results["off"] == results["on"]
