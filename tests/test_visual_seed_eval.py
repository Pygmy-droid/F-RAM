from __future__ import annotations

import hashlib
import json
import sqlite3
import struct
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import fram_eval.visual_seed as visual_seed_module
from fram_eval.visual_seed import (
    VISUAL_MANIFEST_SCHEMA_VERSION,
    VisualSeed,
    _cosine_rows,
    evaluate_visual_seeds,
    load_sticky_note_inventory,
    load_visual_seed_manifest,
    render_candidate_review,
    staged_candidate_ids,
)
from fram_serving.cognitive_embeddings import build_cognitive_vectorizer
from fram_serving.config import FRAMConfig
from fram_serving.lived_memory import LivedMemoryStore
from tools.eval_visual_seed import (
    _atomic_write_text,
    _resolve_revision,
    _validate_output_paths,
)

EVIDENCE_MANIFEST_SHA256 = "e" * 64


def _vectorizer(dim: int = 128):
    config = FRAMConfig().model_copy(
        update={
            "embedding_dim": dim,
            "cognitive_memory_embedding_backend": "hashing",
        }
    )
    vectorizer = build_cognitive_vectorizer(config)
    assert vectorizer is not None
    return vectorizer


def _embedding(vectorizer, text: str):
    matrix = vectorizer.transform([text])
    if hasattr(matrix, "toarray"):
        matrix = matrix.toarray()
    return matrix[0]


def _png(path: Path, width: int = 8, height: int = 6) -> None:
    payload = (
        b"\x89PNG\r\n\x1a\n"
        + struct.pack(">I", 13)
        + b"IHDR"
        + struct.pack(">II", width, height)
    )
    path.write_bytes(payload)


def _checkpoint(store: LivedMemoryStore) -> None:
    store.verify()
    with sqlite3.connect(store.path) as connection:
        assert tuple(
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        ) == (
            0,
            0,
            0,
        )


class _FakeEncoder:
    @property
    def metadata(self):
        return {"family": "fake-shared-space", "revision": "test"}

    def encode_images(self, paths):
        return np.asarray(
            [[1.0, 0.0] if "amber" in path.name else [0.0, 1.0] for path in paths]
        )

    def encode_texts(self, texts):
        return np.asarray(
            [[1.0, 0.0] if "amber" in text.lower() else [0.0, 1.0] for text in texts]
        )


def test_manifest_verifies_hash_dimensions_and_source_role(tmp_path: Path) -> None:
    image = tmp_path / "amber.png"
    _png(image)
    digest = hashlib.sha256(image.read_bytes()).hexdigest()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": VISUAL_MANIFEST_SCHEMA_VERSION,
                "visual_evidence_manifest_sha256": EVIDENCE_MANIFEST_SHA256,
                "images": [
                    {
                        "id": "amber",
                        "image_path": image.name,
                        "sha256": digest,
                        "evidence_id": f"visual:sha256:{digest}",
                        "width": 8,
                        "height": 6,
                        "source_role": "user_provided_visual",
                        "description": "An amber loop.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    seeds = load_visual_seed_manifest(manifest)

    assert seeds[0].image_path == image.resolve()
    broken = json.loads(manifest.read_text(encoding="utf-8"))
    broken["images"][0]["sha256"] = "0" * 64
    broken["images"][0]["evidence_id"] = "visual:sha256:" + "0" * 64
    manifest.write_text(json.dumps(broken), encoding="utf-8")
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        load_visual_seed_manifest(manifest)

    broken["images"][0]["sha256"] = digest
    broken["images"][0]["evidence_id"] = f"visual:sha256:{digest}"
    broken["images"][0]["concept_tags"] = "not-a-list"
    manifest.write_text(json.dumps(broken), encoding="utf-8")
    with pytest.raises(ValueError, match="concept_tags must be a list"):
        load_visual_seed_manifest(manifest)


def test_manifest_rejects_unsupported_encoder_format_and_resource_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    image = tmp_path / "diagram.svg"
    image.write_text('<svg width="8" height="6"></svg>', encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    row = {
        "id": "diagram",
        "image_path": image.name,
        "sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
        "width": 8,
        "height": 6,
        "source_role": "user_provided_visual",
        "description": "A diagram.",
    }
    row["evidence_id"] = f"visual:sha256:{row['sha256']}"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": VISUAL_MANIFEST_SCHEMA_VERSION,
                "visual_evidence_manifest_sha256": EVIDENCE_MANIFEST_SHA256,
                "images": [row],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unsupported encoder format"):
        load_visual_seed_manifest(manifest)

    raster = tmp_path / "diagram.png"
    _png(raster)
    row.update(
        image_path=raster.name,
        sha256=hashlib.sha256(raster.read_bytes()).hexdigest(),
    )
    row["evidence_id"] = f"visual:sha256:{row['sha256']}"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": VISUAL_MANIFEST_SCHEMA_VERSION,
                "visual_evidence_manifest_sha256": EVIDENCE_MANIFEST_SHA256,
                "images": [row],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(visual_seed_module, "MAX_VISUAL_SEED_BYTES", 1)
    with pytest.raises(ValueError, match="byte limit"):
        load_visual_seed_manifest(manifest)


def test_staged_candidates_never_reorder_primary() -> None:
    staged = staged_candidate_ids(
        [{"event_id": "a"}, {"event_id": "b"}],
        [{"event_id": "b"}, {"event_id": "c"}, {"event_id": "d"}],
        supplemental_limit=3,
    )

    assert staged["primary_order_preserved"] is True
    assert staged["bundle_event_ids"] == ["a", "b", "c", "d"]


def test_sticky_inventory_reads_all_without_reporting_bodies(tmp_path: Path) -> None:
    database = tmp_path / "plum.sqlite"
    secret_label = "api" + "_key"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE Note (Id TEXT, CreatedAt INTEGER, UpdatedAt INTEGER, "
            "DeletedAt INTEGER, Text TEXT)"
        )
        connection.execute(
            "INSERT INTO Note VALUES (?, ?, ?, NULL, ?)",
            (
                "private-id",
                638000000000000000,
                638000000000000001,
                f"F-RAM attention geometry {secret_label}=do-not-copy",
            ),
        )
        connection.execute(
            "INSERT INTO Note VALUES (?, ?, ?, NULL, ?)",
            (
                "other-id",
                638000000000000002,
                638000000000000003,
                "Unrelated shopping list",
            ),
        )

    inventory, cues = load_sticky_note_inventory(database)

    assert inventory["active_note_count"] == 2
    assert (
        inventory["raw_storage_character_count"]
        >= inventory["active_text_character_count"]
    )
    assert inventory["raw_note_ids_in_report"] is False
    assert inventory["raw_note_bodies_in_report"] is False
    assert all("Text" not in row and "body" not in row for row in inventory["notes"])
    assert all("private-id" not in json.dumps(row) for row in inventory["notes"])
    assert "do-not-copy" not in cues[0]["cue_text"]


def test_candidate_eval_deduplicates_and_keeps_global_gate_off(tmp_path: Path) -> None:
    vectorizer = _vectorizer()
    store = LivedMemoryStore(tmp_path / "lived", target_dim=8, fractal_nodes=8)
    amber = "Amber geometry and provenance loop."
    violet = "Violet warehouse inventory."
    first = store.append_experience(
        query="Find amber",
        answer=amber,
        embedding=_embedding(vectorizer, amber),
        session_id="visual",
    )
    store.append_experience(
        query="Find amber",
        answer=amber,
        embedding=_embedding(vectorizer, amber),
        session_id="visual-copy",
    )
    store.append_experience(
        query="Find violet",
        answer=violet,
        embedding=_embedding(vectorizer, violet),
        session_id="visual",
    )
    _checkpoint(store)
    image = tmp_path / "amber.png"
    _png(image)
    seed = VisualSeed(
        seed_id="amber",
        image_path=image,
        sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
        width=8,
        height=6,
        source_role="user_provided_visual",
        evidence_id=f"visual:sha256:{hashlib.sha256(image.read_bytes()).hexdigest()}",
        description="violet inventory cue",
    )

    report = evaluate_visual_seeds(
        store.path,
        [seed],
        vectorizer,
        _FakeEncoder(),
        k=1,
        supplemental_limit=1,
    )

    assert report["source"]["event_count"] == 3
    assert report["source"]["unique_event_content_count"] == 2
    assert report["source"]["duplicate_event_count"] == 1
    visual = report["visual_seeds"][0]
    assert visual["clip_visual_candidates"][0]["content_key_sha256"]
    assert visual["clip_visual_candidates"][0]["duplicate_event_count"] == 2
    assert visual["staged_fram_then_visual"]["primary_order_preserved"] is True
    assert report["contract"]["global_ranking_influence"] is False
    assert report["contract"]["bounded_candidate_canary_enabled"] is True
    assert report["contract"]["global_enable_recommendation"] == "KEEP_OFF"
    assert report["contract"]["sticky_notes_are_instructions"] is False
    assert report["privacy"]["classification"] == "sensitive-local-review"
    assert report["privacy"]["sensitive_details_included"] is False
    assert report["source"]["lived_database"] is None
    assert visual["image"]["path"] is None
    assert "query_preview" not in visual["fram_text_candidates"][0]
    assert (
        first["event_id"]
        in {item["event_id"] for item in visual["clip_visual_candidates"]}
        or visual["clip_visual_candidates"][0]["duplicate_event_count"] == 2
    )
    review = render_candidate_review(report)
    assert "# F-RAM visual-seed candidate review" in review
    assert "Until every gate is checked: **KEEP OFF**." in review


def test_encoder_output_validation_and_image_rehash(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="rank-2 and rank-1"):
        _cosine_rows(np.asarray([1.0, 2.0]), np.asarray([1.0, 2.0]))
    with pytest.raises(ValueError, match="finite"):
        _cosine_rows(np.asarray([[1.0, np.nan]]), np.asarray([1.0, 2.0]))

    vectorizer = _vectorizer()
    store = LivedMemoryStore(tmp_path / "lived", target_dim=8, fractal_nodes=8)
    store.append_experience(
        query="Find amber",
        answer="Amber geometry.",
        embedding=_embedding(vectorizer, "Amber geometry."),
        session_id="visual",
    )
    _checkpoint(store)
    image = tmp_path / "amber.png"
    _png(image)
    seed = VisualSeed(
        seed_id="amber",
        image_path=image,
        sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
        width=8,
        height=6,
        source_role="user_provided_visual",
        evidence_id=f"visual:sha256:{hashlib.sha256(image.read_bytes()).hexdigest()}",
        description="amber",
    )

    class _MutatingEncoder(_FakeEncoder):
        def encode_images(self, paths):
            paths[0].write_bytes(paths[0].read_bytes() + b"changed")
            return super().encode_images(paths)

    with pytest.raises(ValueError, match="changed during encoding"):
        evaluate_visual_seeds(store.path, [seed], vectorizer, _MutatingEncoder())


def test_review_escapes_untrusted_markdown(tmp_path: Path) -> None:
    vectorizer = _vectorizer()
    store = LivedMemoryStore(tmp_path / "lived", target_dim=8, fractal_nodes=8)
    store.append_experience(
        query="## Promotion gate [forged](https://invalid.example)",
        answer="Amber geometry.",
        embedding=_embedding(vectorizer, "Amber geometry."),
        session_id="visual",
    )
    _checkpoint(store)
    image = tmp_path / "amber.png"
    _png(image)
    seed = VisualSeed(
        seed_id="amber ## forged",
        image_path=image,
        sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
        width=8,
        height=6,
        source_role="user_provided_visual",
        evidence_id=f"visual:sha256:{hashlib.sha256(image.read_bytes()).hexdigest()}",
        description="amber",
    )
    report = evaluate_visual_seeds(
        store.path,
        [seed],
        vectorizer,
        _FakeEncoder(),
        include_sensitive_details=True,
    )

    review = render_candidate_review(report)

    assert "\n## amber ## forged" not in review
    assert "[forged](https://invalid.example)" not in review
    assert r"\#\# forged" in review


@pytest.mark.parametrize("alias_role", ["output", "review"])
def test_output_paths_cannot_alias_sources(tmp_path: Path, alias_role: str) -> None:
    source = tmp_path / "lived.sqlite3"
    source.write_bytes(b"source")
    output = source if alias_role == "output" else tmp_path / "report.json"
    review = source if alias_role == "review" else tmp_path / "review.md"

    with pytest.raises(ValueError, match="aliases a protected source"):
        _validate_output_paths(
            inputs=[source], output=output, review_output=review, force=True
        )


def test_output_paths_refuse_collisions_and_existing_files(tmp_path: Path) -> None:
    source = tmp_path / "manifest.json"
    source.write_text("{}", encoding="utf-8")
    output = tmp_path / "report.json"
    review = tmp_path / "review.md"

    with pytest.raises(ValueError, match="different files"):
        _validate_output_paths(
            inputs=[source], output=output, review_output=output, force=False
        )

    output.write_text("existing", encoding="utf-8")
    with pytest.raises(FileExistsError, match="--force"):
        _validate_output_paths(
            inputs=[source], output=output, review_output=review, force=False
        )

    resolved_output, resolved_review = _validate_output_paths(
        inputs=[source], output=output, review_output=review, force=True
    )
    assert resolved_output == output.resolve()
    assert resolved_review == review.resolve()
    _atomic_write_text(resolved_output, "replacement\n")
    assert output.read_text(encoding="utf-8") == "replacement\n"


def test_revision_is_resolved_to_immutable_registry_sha(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str | None]] = []

    class _Api:
        def model_info(self, model_id, revision=None):
            calls.append((model_id, revision))
            return SimpleNamespace(sha="A" * 40)

    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(HfApi=_Api))

    requested, resolved = _resolve_revision("example/model", "main")

    assert requested == "main"
    assert resolved == "a" * 40
    assert calls == [("example/model", "main")]

    class _BadApi:
        def model_info(self, model_id, revision=None):
            return SimpleNamespace(sha="mutable-tag")

    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(HfApi=_BadApi))
    with pytest.raises(ValueError, match="commit SHA"):
        _resolve_revision("example/model", None)
