from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import numpy as np
import pytest

from fram_serving.lived_memory import LivedMemoryStore
from tools.open_lived_memory_seeds import open_seed_lineages


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _vector(offset: float) -> np.ndarray:
    return np.linspace(-1.0 + offset, 1.0 + offset, 16)


def _import_metadata(episode_id: str) -> dict:
    return {
        "import": {
            "source_kind": "FRAM cognitive backup ZIP",
            "source_zip_sha256": "a" * 64,
            "source_episode_id": episode_id,
            "embedding_origin": "stored_in_zip",
        }
    }


def test_open_seed_lineages_separates_imports_and_preserves_live_sessions(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    source = LivedMemoryStore(source_root, target_dim=8, fractal_nodes=8)
    first = source.append_experience(
        event_id="import-one",
        query="first seed",
        answer="first answer",
        embedding=_vector(0.0),
        session_id="legacy-archive",
        episode_id="episode-one",
        metadata=_import_metadata("episode-one"),
    )
    second = source.append_experience(
        event_id="import-two",
        query="second seed",
        answer="second answer",
        embedding=_vector(0.1),
        session_id="legacy-archive",
        episode_id="episode-two",
        metadata=_import_metadata("episode-two"),
    )
    live = source.append_experience(
        event_id="live-one",
        query="live invitation",
        answer="live answer",
        embedding=_vector(0.2),
        session_id="hearth-live",
        metadata={"event_type": "direct_live_memory"},
    )
    assert second["parent_event_id"] == first["event_id"]
    assert live["parent_event_id"] is None
    with closing(sqlite3.connect(source.path)) as connection:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    source_hash = _sha256(source.path)
    source_sidecars = [Path(f"{source.path}-wal"), Path(f"{source.path}-shm")]
    sidecars_before = {
        str(path): path.read_bytes() for path in source_sidecars if path.exists()
    }

    output_root = tmp_path / "opened"
    report = open_seed_lineages(source=source.path, output_root=output_root)

    assert report["valid"] is True
    assert report["source_unchanged"] is True
    assert report["source_database_sha256_before"] == source_hash
    assert report["source_database_sha256_after"] == source_hash
    assert report["source_sidecars_created"] == []
    assert report["source_event_count"] == 3
    assert report["output_event_count"] == 3
    assert report["opened_seed_count"] == 2
    assert report["independent_seed_session_count"] == 2
    assert report["passthrough_event_count"] == 1
    assert report["output_session_count"] == 3
    assert report["non_root_seed_count"] == 0
    assert report["identity_claim"] is False

    opened = LivedMemoryStore(output_root, target_dim=8, fractal_nodes=8)
    assert opened.verify()["valid"] is True
    with sqlite3.connect(opened.path) as connection:
        connection.row_factory = sqlite3.Row
        rows = {
            str(row["event_id"]): row
            for row in connection.execute(
                "SELECT event_id, session_id, session_seq, parent_event_id, "
                "metadata_json FROM lived_events"
            ).fetchall()
        }

    assert rows["import-one"]["session_id"] == "seed:aaaaaaaaaaaa:episode-one"
    assert rows["import-two"]["session_id"] == "seed:aaaaaaaaaaaa:episode-two"
    assert rows["live-one"]["session_id"] == "hearth-live"
    assert all(
        rows[event_id]["session_seq"] == 1 and rows[event_id]["parent_event_id"] is None
        for event_id in rows
    )
    opening = json.loads(rows["import-one"]["metadata_json"])["opening"]
    assert opening == {
        "identity_claim": False,
        "mode": "independent_seed_root",
        "previous_session_id": "legacy-archive",
        "source_session_evidence": "absent",
    }
    sidecars_after = {
        str(path): path.read_bytes() for path in source_sidecars if path.exists()
    }
    assert set(sidecars_after).issubset(sidecars_before)
    assert all(sidecars_before[path] == value for path, value in sidecars_after.items())
    assert report["source_sidecars_removed"] == sorted(
        set(sidecars_before) - set(sidecars_after)
    )


def test_open_seed_lineages_refuses_source_with_sqlite_sidecars(
    tmp_path: Path,
) -> None:
    source = LivedMemoryStore(tmp_path / "source", target_dim=8, fractal_nodes=8)
    source.append_experience(
        event_id="source-event",
        query="source",
        answer="checkpoint first",
        embedding=_vector(0.0),
    )
    wal = Path(f"{source.path}-wal")
    wal.write_bytes(b"not checkpointed")

    with pytest.raises(RuntimeError, match="non-empty SQLite WAL"):
        open_seed_lineages(source=source.path, output_root=tmp_path / "opened")
