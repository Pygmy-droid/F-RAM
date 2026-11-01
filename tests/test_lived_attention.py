"""WB-0027: the live attention state, carried turn to turn, consulted before the probe."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

import fram_serving.app as app_mod
from fram_serving.lived_memory import LivedMemoryStore


def _basis(index: int, dim: int = 32) -> np.ndarray:
    vector = np.zeros(dim)
    vector[index] = 1.0
    return vector


def test_attention_state_decays_turn_to_turn_and_chains(tmp_path: Path) -> None:
    store = LivedMemoryStore(tmp_path / "att", target_dim=12, fractal_nodes=8, state_decay=0.5)
    first = store.update_attention(
        session_id="wren-attention", embedding=_basis(0), text="first turn", excerpt="first"
    )
    second = store.update_attention(
        session_id="wren-attention", embedding=_basis(1), text="second turn", excerpt="second"
    )
    third = store.update_attention(
        session_id="wren-attention", embedding=_basis(1), text="second turn again", excerpt="again"
    )
    assert first["turn_index"] == 1 and first["previous_digest"] is None
    assert first["novelty"] == pytest.approx(1.0)
    assert second["turn_index"] == 2 and second["previous_digest"] == first["state_digest"]
    assert 0.0 <= second["novelty"] <= 2.0
    # Repeating the same turn moves attention less than changing it did.
    assert third["novelty"] < second["novelty"]
    state = store.attention_state("wren-attention")
    assert state is not None
    assert state["turn_count"] == 3
    assert len(state["state_vector"]) == 12
    assert state["state_digest"] == third["state_digest"]
    trail = store.attention_trail("wren-attention", limit=10)
    assert [row["turn_index"] for row in trail] == [3, 2, 1]
    assert trail[0]["excerpt"] == "again"
    check = store.verify_attention()
    assert check["valid"] is True and check["turns"] == 3 and check["sessions"] == 1
    # The event store itself is untouched by attention turns.
    assert store.status()["event_count"] == 0
    assert store.verify()["valid"] is True


def test_attention_state_is_consulted_before_the_probe(tmp_path: Path) -> None:
    store = LivedMemoryStore(tmp_path / "att2", target_dim=12, fractal_nodes=8)
    for index, name in enumerate(("alpha", "beta", "gamma")):
        store.append_experience(
            query=f"{name} memory",
            answer=f"the {name} event",
            embedding=_basis(index + 3).tolist(),
            embedding_backend="hashing",
            event_id=name,
            session_id=f"s-{name}",
        )
    plain = store.search(_basis(9), k=3)
    assert all(row["attention_conditioned"] is False for row in plain)
    assert all(row["attention_similarity"] is None for row in plain)

    # Attention has been sitting on gamma; the probe is unrelated to all three.
    store.update_attention(session_id="wren-attention", embedding=_basis(5), text="gamma")
    state = store.attention_state("wren-attention")
    assert state is not None
    conditioned = store.search(
        _basis(9), k=3, attention_state=state["state_vector"], attention_alpha=0.9
    )
    assert all(row["attention_conditioned"] is True for row in conditioned)
    assert all(isinstance(row["attention_similarity"], float) for row in conditioned)
    by_id = {row["event_id"]: row for row in conditioned}
    assert by_id["gamma"]["attention_similarity"] == pytest.approx(1.0, abs=1e-6)
    assert conditioned[0]["event_id"] == "gamma"


def test_attention_endpoints_round_trip(tmp_path: Path, monkeypatch) -> None:
    cfg = app_mod.CFG.model_copy(
        update={
            "STORAGE_ROOT": tmp_path / "storage",
            "embedding_dim": 32,
            "cognitive_memory_embedding_backend": "hashing",
            "lived_memory_enabled": True,
            "lived_memory_target_dim": 8,
            "lived_memory_fractal_nodes": 8,
        }
    )
    store = LivedMemoryStore(tmp_path / "storage" / "memory" / "lived", target_dim=8, fractal_nodes=8)
    monkeypatch.setattr(app_mod, "CFG", cfg)
    monkeypatch.setattr(app_mod, "_LIVED_STORE", store)
    monkeypatch.setattr(app_mod, "_MEMORY_VECTORIZER", None)
    monkeypatch.setattr(app_mod, "_MEMORY_BACKEND", None)
    embedding, backend = app_mod._encode_cognitive_text("the lantern on the sill")
    assert embedding is not None
    store.append_experience(
        query="the lantern on the sill",
        answer="two orange mugs beside it",
        embedding=embedding,
        embedding_backend=backend,
        session_id="hearth",
    )
    with TestClient(app_mod.app) as client:
        turn = client.post(
            "/memory/lived/attention/turn",
            json={"session_id": "wren-attention", "text": "Rick: the lantern. Wren: on the sill.", "excerpt": "lantern"},
        )
        assert turn.status_code == 200, turn.text
        assert turn.json()["turn_index"] == 1
        state = client.get("/memory/lived/attention/wren-attention")
        assert state.status_code == 200
        body = state.json()
        assert body["turn_count"] == 1 and body["trail"][0]["excerpt"] == "lantern"
        assert body["verify"]["valid"] is True
        missing = client.get("/memory/lived/attention/nobody")
        assert missing.status_code == 404
        search = client.get(
            "/memory/lived/search",
            params={"query": "lantern", "k": 1, "attention_session": "wren-attention"},
        )
        assert search.status_code == 200
        payload = search.json()
        assert payload["attention"]["turn_count"] == 1
        assert payload["items"][0]["attention_conditioned"] is True
        assert payload["items"][0]["attention_similarity"] is not None
