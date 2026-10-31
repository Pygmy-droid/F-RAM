from __future__ import annotations

import json
import sqlite3
import zipfile
from pathlib import Path

from tools.import_lived_memory_zip import import_zip


def _line(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False) + "\n"


def test_zip_import_preserves_stored_vectors_and_labels_reconstruction(
    tmp_path: Path,
) -> None:
    archive_path = tmp_path / "backup.zip"
    episodes = [
        {
            "type": "episode",
            "id": "stored",
            "time": "2025-12-18T07:00:00+00:00",
            "query": "stored event",
            "answer": "keeps its vector",
            "citations": ["doc:one"],
            "trace_id": "trace-one",
        },
        {
            "type": "episode",
            "id": "derived",
            "time": "2025-12-18T07:01:00+00:00",
            "query": "derived event",
            "answer": "reconstructs a labeled vector",
            "citations": [],
            "trace_id": "trace-two",
        },
    ]
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(".git\\HEAD", "ref: refs/heads/main\n")
        archive.writestr(".git\\refs\\heads\\main", "abc123\n")
        archive.writestr(
            "storage\\memory\\cognitive\\episodes.jsonl",
            "".join(_line(item) for item in episodes),
        )
        archive.writestr(
            "storage\\memory\\cognitive\\episodes.vectors.jsonl",
            _line({"id": "stored", "vector": [1.0, 0.0, 0.5, 0.0, 0.25, 0.0]}),
        )
        archive.writestr(
            "storage\\memory\\cognitive\\vectors.meta.json",
            json.dumps({"embedding_backend": "hashing", "dim": 6}),
        )

    output = tmp_path / "lived"
    report = import_zip(
        zip_path=archive_path,
        output_root=output,
        session_id="zip-session",
        target_dim=8,
        fractal_nodes=8,
        scan_limit=100,
        state_decay=0.82,
    )
    repeated = import_zip(
        zip_path=archive_path,
        output_root=output,
        session_id="zip-session",
        target_dim=8,
        fractal_nodes=8,
        scan_limit=100,
        state_decay=0.82,
    )

    assert report["source_git_head"] == "abc123"
    assert report["imported"] == 2
    assert report["stored_embeddings"] == 1
    assert report["reconstructed_embeddings"] == 1
    assert report["failed_count"] == 0
    assert report["lineage_mode"] == "separate"
    assert report["identity_claim"] is False
    assert report["status"]["session_count"] == 2
    assert report["verification"]["valid"] is True
    assert repeated["imported"] == 0
    assert repeated["skipped_existing"] == 2
    assert repeated["verification"]["event_count"] == 2

    with sqlite3.connect(output / "lived_memory.sqlite3") as connection:
        rows = connection.execute(
            "SELECT session_id, session_seq, parent_event_id "
            "FROM lived_events ORDER BY session_id"
        ).fetchall()
    assert len({row[0] for row in rows}) == 2
    assert all(row[1] == 1 and row[2] is None for row in rows)


def test_zip_import_can_explicitly_reproduce_single_archive_lineage(
    tmp_path: Path,
) -> None:
    archive_path = tmp_path / "backup.zip"
    episodes = [
        {
            "type": "episode",
            "id": f"episode-{index}",
            "time": f"2025-12-18T07:0{index}:00+00:00",
            "query": f"query {index}",
            "answer": f"answer {index}",
            "citations": [],
            "trace_id": f"trace-{index}",
        }
        for index in range(2)
    ]
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(".git/HEAD", "abc123\n")
        archive.writestr(
            "storage/memory/cognitive/episodes.jsonl",
            "".join(_line(item) for item in episodes),
        )
        archive.writestr(
            "storage/memory/cognitive/episodes.vectors.jsonl",
            "".join(
                _line(
                    {
                        "id": f"episode-{index}",
                        "vector": [1.0, float(index), 0.5, 0.0, 0.25, 0.0],
                    }
                )
                for index in range(2)
            ),
        )
        archive.writestr(
            "storage/memory/cognitive/vectors.meta.json",
            json.dumps({"embedding_backend": "hashing", "dim": 6}),
        )

    report = import_zip(
        zip_path=archive_path,
        output_root=tmp_path / "single",
        session_id="explicit-archive",
        target_dim=8,
        fractal_nodes=8,
        scan_limit=100,
        state_decay=0.82,
        lineage_mode="single",
    )

    assert report["lineage_mode"] == "single"
    assert report["status"]["session_count"] == 1
    assert report["verification"]["valid"] is True
