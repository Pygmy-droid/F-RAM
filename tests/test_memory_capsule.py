from __future__ import annotations

import json
from pathlib import Path

from fram_core.pipeline import _make_hashing_vectorizer as _pipeline_make_hashing_vectorizer
from fram_serving.config import FRAMConfig
from fram_serving.memory_capsule import MemoryCapsuleStore, build_capsule_turns


def test_memory_capsule_write(tmp_path: Path) -> None:
    cfg = FRAMConfig(embedding_dim=32, fractal_downsample_target=32)
    vectorizer = _pipeline_make_hashing_vectorizer(cfg)
    store = MemoryCapsuleStore(tmp_path, config=cfg)

    turns = [
        {"role": "user", "text": "Hello memory capsule", "time": "2025-12-31T00:00:00+00:00"},
        {"role": "assistant", "text": "Confirmed.", "time": "2025-12-31T00:00:01+00:00"},
    ]

    result = store.write_capsule(
        turns=turns,
        session_id="session-1",
        source={"kind": "test", "tool": "pytest", "version": "v0"},
        vectorizer=vectorizer,
        vectorizer_backend="hashing",
        created_at="2025-12-31T00:00:02+00:00",
    )

    path = Path(result["path"])
    assert path.exists()

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["capsule_id"]
    assert payload["capsule_version"] == "capsule-mvp-1"
    assert payload["raw_transcript"][0]["role"] == "user"
    assert len(payload["trajectory"]) == 2
    assert payload["fractal"]["embedding_dim"] == 32
    assert len(payload["fractal"]["trace_stack"]) == 2
    writer_config = payload.get("writer_config") or {}
    assert writer_config.get("embedding_dim") == 32
    assert writer_config.get("embedding_backend") == "hashing"
    assert payload["remembering_definition"]["author"] == "system"


def test_build_capsule_turns_includes_memory_entries() -> None:
    entries = [
        {
            "id": "m1",
            "time": "2025-12-31T00:00:00+00:00",
            "text": "first memory",
            "metadata": {"role": "user"},
            "last_seen": "2025-12-31T00:00:01+00:00",
        },
        {
            "id": "m2",
            "time": "2025-12-31T00:00:02+00:00",
            "text": "second memory",
            "metadata": {"speaker": "assistant"},
        },
    ]

    turns = build_capsule_turns(
        memory_entries=entries,
        user_text="live question",
        assistant_text="live answer",
        timestamp="2025-12-31T00:00:03+00:00",
        trace_id="trace-1",
    )

    assert turns[0]["role"] == "user"
    assert turns[0]["meta"]["entry_id"] == "m1"
    assert turns[1]["role"] == "assistant"
    assert turns[-2]["role"] == "user"
    assert turns[-1]["role"] == "assistant"


def test_memory_capsule_search_embedding(tmp_path: Path) -> None:
    cfg = FRAMConfig(embedding_dim=64, memory_capsule_retrieval_half_life_hours=24.0)
    vectorizer = _pipeline_make_hashing_vectorizer(cfg)
    store = MemoryCapsuleStore(tmp_path, config=cfg)

    store.write_capsule(
        turns=[
            {"role": "user", "text": "orchid beacon in the fog", "time": "2025-12-31T00:00:00+00:00"},
            {"role": "assistant", "text": "orchid beacon confirmed", "time": "2025-12-31T00:00:01+00:00"},
        ],
        session_id="session-a",
        source={"kind": "test", "tool": "pytest", "version": "v0"},
        vectorizer=vectorizer,
        vectorizer_backend="hashing",
        created_at="2025-12-31T00:00:02+00:00",
    )
    store.write_capsule(
        turns=[
            {"role": "user", "text": "gopher signal at dusk", "time": "2025-12-31T00:05:00+00:00"},
            {"role": "assistant", "text": "gopher signal acknowledged", "time": "2025-12-31T00:05:01+00:00"},
        ],
        session_id="session-b",
        source={"kind": "test", "tool": "pytest", "version": "v0"},
        vectorizer=vectorizer,
        vectorizer_backend="hashing",
        created_at="2025-12-31T00:05:02+00:00",
    )

    diagnostics = {}
    results = store.search(
        "orchid beacon",
        k=3,
        vectorizer=vectorizer,
        vectorizer_backend="hashing",
        turns_per_capsule=1,
        diagnostics=diagnostics,
    )

    assert results
    assert any("orchid" in item["text"].lower() for item in results)
    assert diagnostics.get("capsules_scanned") == 2
    assert diagnostics.get("returned") == len(results)


def test_memory_capsule_search_lexical_fallback(tmp_path: Path) -> None:
    cfg = FRAMConfig()
    store = MemoryCapsuleStore(tmp_path, config=cfg)

    store.write_capsule(
        turns=[
            {"role": "user", "text": "starlight ridge note", "time": "2025-12-31T00:00:00+00:00"},
            {"role": "assistant", "text": "starlight ridge acknowledged", "time": "2025-12-31T00:00:01+00:00"},
        ],
        session_id="session-lex",
        source={"kind": "test", "tool": "pytest", "version": "v0"},
        vectorizer=None,
        vectorizer_backend=None,
        created_at="2025-12-31T00:00:02+00:00",
    )

    results = store.search(
        "starlight",
        k=2,
        vectorizer=None,
        turns_per_capsule=1,
    )

    assert results
    assert any(item.get("match_type") == "lexical" for item in results)
    assert any("starlight" in item["text"].lower() for item in results)
