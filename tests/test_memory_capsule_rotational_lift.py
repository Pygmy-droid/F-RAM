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


def _write_capsule_payload(tmp_path: Path, cfg: FRAMConfig, turns=None) -> dict:
    vectorizer = _pipeline_make_hashing_vectorizer(cfg)
    store = MemoryCapsuleStore(tmp_path, config=cfg)
    result = store.write_capsule(
        turns=turns if turns is not None else _TURNS,
        session_id="session-rl",
        source={"kind": "test", "tool": "pytest", "version": "v0"},
        vectorizer=vectorizer,
        vectorizer_backend="hashing",
        created_at="2025-12-31T00:00:03+00:00",
    )
    return json.loads(Path(result["path"]).read_text(encoding="utf-8"))


def test_rotational_lift_disabled_by_default(tmp_path: Path) -> None:
    cfg = FRAMConfig(embedding_dim=16)
    assert cfg.rotational_lift_enabled is False
    payload = _write_capsule_payload(tmp_path, cfg)
    assert payload["self_invariants"] == []
    assert payload["open_residuals"] == []


def test_rotational_lift_enabled_populates_self_invariants(tmp_path: Path) -> None:
    cfg = FRAMConfig(
        embedding_dim=16,
        rotational_lift_enabled=True,
        rotational_lift_invariant_components=2,
    )
    payload = _write_capsule_payload(tmp_path, cfg)

    assert len(payload["self_invariants"]) == 1
    invariant = payload["self_invariants"][0]
    assert invariant["kind"] == "rotational_lift_pca_invariants"
    assert invariant["source"] == "fram_core.rotational_lift v0.3"
    assert invariant["trajectory_length"] == 3
    assert invariant["embedding_dim"] == 16
    assert 1 <= invariant["n_components"] <= 2
    assert isinstance(invariant["reentry_passed"], bool)
    assert invariant["reentry_max_distance"] >= 0.0
    assert len(invariant["z"]) == 3
    assert len(invariant["basis"]) == 16


def test_rotational_lift_enabled_populates_open_residuals(tmp_path: Path) -> None:
    cfg = FRAMConfig(
        embedding_dim=16,
        rotational_lift_enabled=True,
        rotational_lift_lift_hops=2,
    )
    payload = _write_capsule_payload(tmp_path, cfg)

    assert len(payload["open_residuals"]) == 1
    residual_record = payload["open_residuals"][0]
    assert residual_record["kind"] == "rotational_lift_chain"
    assert residual_record["target_dim"] == 16 + 2
    assert residual_record["hops"] == 2
    assert len(residual_record["capsules"]) == 2
    # Exact residual mode: the chain should be reconstructible to (near) zero error.
    assert residual_record["reconstruction_error_max"] < 1e-8


def test_rotational_lift_open_residuals_reconstruct_from_disk(tmp_path: Path) -> None:
    """The stored open_residuals chain must be literally re-enterable: reload
    it from the JSON on disk (not from in-memory objects) and recover the
    original trajectory embeddings exactly."""

    cfg = FRAMConfig(embedding_dim=16, rotational_lift_enabled=True, rotational_lift_lift_hops=2)
    payload = _write_capsule_payload(tmp_path, cfg)

    original = np.array([entry["embedding"] for entry in payload["trajectory"]], dtype=float)
    residual_record = payload["open_residuals"][0]
    final_state = np.array(residual_record["final_state"], dtype=float)
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
        for c in residual_record["capsules"]
    ]

    reconstructed = recursive_reconstruct(final_state, capsules)
    assert np.allclose(original, reconstructed, atol=1e-8)


def test_rotational_lift_enabled_but_single_turn_skips_enrichment(tmp_path: Path) -> None:
    cfg = FRAMConfig(embedding_dim=16, rotational_lift_enabled=True)
    payload = _write_capsule_payload(
        tmp_path,
        cfg,
        turns=[{"role": "assistant", "text": "solo turn", "time": "2025-12-31T00:00:00+00:00"}],
    )
    assert len(payload["trajectory"]) == 1
    assert payload["self_invariants"] == []
    assert payload["open_residuals"] == []


def test_rotational_lift_never_affects_search(tmp_path: Path) -> None:
    """Purely additive: enabling rotational lift must not change search results."""

    cfg_off = FRAMConfig(embedding_dim=16, rotational_lift_enabled=False)
    cfg_on = FRAMConfig(embedding_dim=16, rotational_lift_enabled=True)

    results = {}
    for label, cfg in (("off", cfg_off), ("on", cfg_on)):
        store_dir = tmp_path / label
        vectorizer = _pipeline_make_hashing_vectorizer(cfg)
        store = MemoryCapsuleStore(store_dir, config=cfg)
        store.write_capsule(
            turns=_TURNS,
            session_id="session-rl",
            source={"kind": "test", "tool": "pytest", "version": "v0"},
            vectorizer=vectorizer,
            vectorizer_backend="hashing",
            created_at="2025-12-31T00:00:03+00:00",
        )
        results[label] = store.search("orchids", k=3, vectorizer=vectorizer, vectorizer_backend="hashing")

    # capsule_id/capsule_path (uuid4 + timestamped filename) differ between the
    # two independent stores by design. score/recency_weight are wall-clock
    # dependent (recomputed from datetime.now() at search time) and will
    # legitimately differ by floating-point noise between two sequential
    # calls regardless of rotational_lift - score_raw is the pre-recency,
    # deterministic ranking signal that actually matters here.
    ranking_fields = ("turn_index", "role", "text", "time", "score_raw", "match_type")

    def _strip(items):
        return [{field: item[field] for field in ranking_fields} for item in items]

    assert _strip(results["off"]) == _strip(results["on"])
