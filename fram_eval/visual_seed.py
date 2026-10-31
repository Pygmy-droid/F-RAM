"""Bounded visual-seed candidate evaluation for checkpointed lived memory.

This module keeps the existing F-RAM text retrieval primary and evaluates a
separate image/text encoder as a supplemental candidate source.  It never
writes lived memory, treats Sticky Notes and visual descriptions as untrusted
source material, and does not generate answers or promote candidates.
"""

from __future__ import annotations

import hashlib
import html
import importlib.metadata as importlib_metadata
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

import numpy as np

from fram_core.visual_evidence import detect_visual_format, read_visual_dimensions
from fram_eval.wake_orient import ReadOnlyLivedIndex

VISUAL_SEED_SCHEMA_VERSION = "fram-visual-seed-candidate-v1"
VISUAL_MANIFEST_SCHEMA_VERSION = "fram-visual-seed-manifest-v1"
ALLOWED_SOURCE_ROLES = frozenset({"user_provided_visual", "generated_concept_art"})
SUPPORTED_ENCODER_FORMATS = frozenset({"bmp", "gif", "jpeg", "png", "webp"})
IMMUTABLE_MODEL_REVISION_PATTERN = re.compile(r"^[0-9a-f]{40,64}$", re.IGNORECASE)
MAX_VISUAL_SEEDS = 128
MAX_VISUAL_SEED_BYTES = 64 * 1024 * 1024
MAX_VISUAL_SEED_PIXELS = 50_000_000
MAX_LIVED_EVENTS = 100_000
MAX_TOP_K = 100
MAX_STICKY_CANDIDATES = 1_000
DEFAULT_STICKY_TERMS = (
    "f-ram",
    "fram",
    "attention",
    "geometry",
    "provenance",
    "retrieval",
    "orientation",
    "fractal",
    "lived experience",
    "memory",
    "trace",
    "continuity",
    "child lane",
    "latent",
    "seed",
    "recall",
    "context",
    "chaos",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalize_text(value: str) -> str:
    return " ".join(str(value).lower().split())


def require_immutable_model_revision(value: str) -> str:
    """Return a normalized model commit SHA or reject mutable references."""

    revision = str(value or "").strip().lower()
    if not IMMUTABLE_MODEL_REVISION_PATTERN.fullmatch(revision):
        raise ValueError("model revision must resolve to a 40-64 character commit SHA")
    return revision


def _markdown_text(value: object) -> str:
    """Escape untrusted one-line text for a Markdown text context."""

    text = " ".join(str(value).split())
    return re.sub(r"([\\`*_{}\[\]<>()#+.!|~-])", r"\\\1", text)


def _html_code(value: object) -> str:
    return f"<code>{html.escape(str(value), quote=True)}</code>"


def _windows_ticks_to_iso(value: int | None) -> str | None:
    if value is None:
        return None
    try:
        ticks = int(value)
        epoch = datetime(1, 1, 1, tzinfo=timezone.utc)
        return (epoch + timedelta(microseconds=ticks // 10)).isoformat()
    except (OverflowError, TypeError, ValueError):
        return None


def _clean_sticky_text(value: str) -> str:
    text = str(value or "")
    text = re.sub(r"\\id=[^\s]+\s?", "", text)
    text = text.replace("\x00", " ")
    return "\n".join(line.rstrip() for line in text.splitlines()).strip()


def _redact_potential_secrets(value: str) -> str:
    text = re.sub(
        r"-----BEGIN [^-]+ PRIVATE KEY-----.*?-----END [^-]+ PRIVATE KEY-----",
        "[REDACTED PRIVATE KEY]",
        value,
        flags=re.DOTALL | re.IGNORECASE,
    )
    text = re.sub(
        r"(?i)\b(password|passphrase|api[_ -]?key|access[_ -]?token|secret)"
        r"\s*[:=]\s*([^\s,;]{4,})",
        lambda match: f"{match.group(1)}=[REDACTED]",
        text,
    )
    return text


def _event_content_key(query: str, answer: str) -> str:
    payload = f"{_normalize_text(query)}\n{_normalize_text(answer)}"
    return _sha256_text(payload)


def _cosine_rows(matrix: np.ndarray, vector: np.ndarray) -> np.ndarray:
    rows = np.asarray(matrix, dtype=float)
    query = np.asarray(vector, dtype=float)
    if rows.ndim != 2 or query.ndim != 1:
        raise ValueError("image and text embeddings must be rank-2 and rank-1")
    if not np.isfinite(rows).all() or not np.isfinite(query).all():
        raise ValueError("image and text embeddings must be finite")
    if rows.ndim != 2 or rows.shape[1] != query.size:
        raise ValueError("image and text embedding dimensions do not match")
    row_norms = np.linalg.norm(rows, axis=1)
    query_norm = float(np.linalg.norm(query))
    denom = row_norms * query_norm
    values = np.zeros(rows.shape[0], dtype=float)
    valid = denom > 1e-12
    values[valid] = (rows[valid] @ query) / denom[valid]
    return np.clip(values, -1.0, 1.0)


def _encode_cue(vectorizer: Any, text: str) -> np.ndarray:
    matrix = vectorizer.transform([str(text)])
    if hasattr(matrix, "toarray"):
        matrix = matrix.toarray()
    vector = np.asarray(matrix, dtype=float).reshape(1, -1)[0]
    if vector.size < 6 or not np.isfinite(vector).all():
        raise ValueError("cue vector must be finite and at least six-dimensional")
    return vector


def _preview(value: str, limit: int = 240) -> str:
    normalized = " ".join(str(value).split())
    return normalized if len(normalized) <= limit else normalized[: limit - 1] + "…"


@dataclass(frozen=True)
class VisualSeed:
    seed_id: str
    image_path: Path
    sha256: str
    width: int
    height: int
    source_role: str
    evidence_id: str
    description: str
    concept_tags: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any], *, base: Path) -> "VisualSeed":
        if not isinstance(value, Mapping):
            raise ValueError("every visual seed must be a JSON object")
        seed_id = str(value.get("id") or "").strip()
        raw_path = Path(str(value.get("image_path") or "").strip())
        image_path = raw_path if raw_path.is_absolute() else base / raw_path
        source_role = str(value.get("source_role") or "").strip()
        description = str(value.get("description") or "").strip()
        sha256 = str(value.get("sha256") or "").strip().lower()
        evidence_id = str(value.get("evidence_id") or "").strip()
        concept_tags = value.get("concept_tags", [])
        if not isinstance(concept_tags, list) or not all(
            isinstance(item, str) for item in concept_tags
        ):
            raise ValueError("visual seed concept_tags must be a list of strings")
        width = int(value.get("width") or 0)
        height = int(value.get("height") or 0)
        if not seed_id or not description or not sha256:
            raise ValueError("visual seed requires id, description, and sha256")
        if not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise ValueError(f"visual seed {seed_id!r} requires a SHA256 hex digest")
        expected_evidence_id = f"visual:sha256:{sha256}"
        if evidence_id != expected_evidence_id:
            raise ValueError(
                f"visual seed {seed_id!r} evidence_id must match its SHA256"
            )
        if source_role not in ALLOWED_SOURCE_ROLES:
            raise ValueError(f"unsupported visual source_role: {source_role!r}")
        if width <= 0 or height <= 0:
            raise ValueError(f"visual seed {seed_id!r} has invalid dimensions")
        return cls(
            seed_id=seed_id,
            image_path=image_path.resolve(),
            sha256=sha256,
            width=width,
            height=height,
            source_role=source_role,
            evidence_id=evidence_id,
            description=description,
            concept_tags=tuple(concept_tags),
        )


class MultimodalEncoder(Protocol):
    @property
    def metadata(self) -> Mapping[str, Any]: ...

    def encode_images(self, paths: Sequence[Path]) -> np.ndarray: ...

    def encode_texts(self, texts: Sequence[str]) -> np.ndarray: ...


class TransformersClipEncoder:
    """Pinned CLIP encoder loaded lazily from Transformers."""

    def __init__(
        self,
        model_id: str,
        *,
        revision: str,
        requested_revision: str | None = None,
        device: str = "cpu",
        batch_size: int = 16,
    ) -> None:
        revision = require_immutable_model_revision(revision)
        try:
            import torch
            from transformers import AutoProcessor, CLIPModel
        except ImportError as exc:  # pragma: no cover - environment specific
            raise RuntimeError(
                "visual-seed evaluation requires torch and transformers"
            ) from exc
        self._torch = torch
        self._device = str(device)
        self._batch_size = max(1, int(batch_size))
        self._processor = AutoProcessor.from_pretrained(
            model_id, revision=revision, use_fast=False
        )
        self._model = CLIPModel.from_pretrained(model_id, revision=revision)
        self._model.to(self._device)
        self._model.eval()
        self._metadata = {
            "family": "clip",
            "model_id": model_id,
            "revision": revision,
            "requested_revision": requested_revision,
            "device": self._device,
            "batch_size": self._batch_size,
            "processor_mode": "slow-pinned",
            "package_versions": {
                name: importlib_metadata.version(name)
                for name in (
                    "huggingface-hub",
                    "numpy",
                    "pillow",
                    "torch",
                    "transformers",
                )
            },
        }

    @property
    def metadata(self) -> Mapping[str, Any]:
        return dict(self._metadata)

    def _normalize(self, value: Any) -> np.ndarray:
        if hasattr(value, "pooler_output"):
            value = value.pooler_output
        array = value.detach().cpu().numpy().astype(float, copy=False)
        if array.ndim != 2 or not array.shape[1] or not np.isfinite(array).all():
            raise ValueError("encoder output must be a finite rank-2 matrix")
        norms = np.linalg.norm(array, axis=1, keepdims=True)
        norms[norms <= 1e-12] = 1.0
        return array / norms

    def encode_images(self, paths: Sequence[Path]) -> np.ndarray:
        from PIL import Image

        rows: list[np.ndarray] = []
        for start in range(0, len(paths), self._batch_size):
            batch_paths = paths[start : start + self._batch_size]
            images = []
            try:
                for path in batch_paths:
                    images.append(Image.open(path).convert("RGB"))
                inputs = self._processor(images=images, return_tensors="pt")
                inputs = {key: value.to(self._device) for key, value in inputs.items()}
                with self._torch.inference_mode():
                    features = self._model.get_image_features(**inputs)
                rows.append(self._normalize(features))
            finally:
                for image in images:
                    image.close()
        return np.vstack(rows)

    def encode_texts(self, texts: Sequence[str]) -> np.ndarray:
        rows: list[np.ndarray] = []
        for start in range(0, len(texts), self._batch_size):
            batch = list(texts[start : start + self._batch_size])
            inputs = self._processor(
                text=batch,
                return_tensors="pt",
                padding=True,
                truncation=True,
            )
            inputs = {key: value.to(self._device) for key, value in inputs.items()}
            with self._torch.inference_mode():
                features = self._model.get_text_features(**inputs)
            rows.append(self._normalize(features))
        return np.vstack(rows)


def load_visual_seed_manifest(path: Path) -> list[VisualSeed]:
    manifest_path = Path(path).resolve()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("visual seed manifest must be a JSON object")
    if payload.get("schema_version") != VISUAL_MANIFEST_SCHEMA_VERSION:
        raise ValueError("unsupported visual seed manifest schema")
    evidence_manifest_sha256 = (
        str(payload.get("visual_evidence_manifest_sha256") or "").strip().lower()
    )
    if not re.fullmatch(r"[0-9a-f]{64}", evidence_manifest_sha256):
        raise ValueError(
            "visual seed manifest requires visual_evidence_manifest_sha256"
        )
    rows = payload.get("images")
    if not isinstance(rows, list) or not rows:
        raise ValueError("visual seed manifest requires a non-empty images list")
    if len(rows) > MAX_VISUAL_SEEDS:
        raise ValueError(
            f"visual seed manifest exceeds the {MAX_VISUAL_SEEDS}-seed limit"
        )
    seeds = [VisualSeed.from_mapping(row, base=manifest_path.parent) for row in rows]
    ids = [seed.seed_id for seed in seeds]
    if len(set(ids)) != len(ids):
        raise ValueError("visual seed IDs must be unique")
    for seed in seeds:
        if not seed.image_path.is_file():
            raise FileNotFoundError(seed.image_path)
        size_bytes = seed.image_path.stat().st_size
        if size_bytes > MAX_VISUAL_SEED_BYTES:
            message = (
                f"visual seed {seed.seed_id!r} exceeds the "
                f"{MAX_VISUAL_SEED_BYTES}-byte limit"
            )
            raise ValueError(message)
        observed_hash = _sha256_file(seed.image_path)
        if observed_hash.lower() != seed.sha256:
            raise ValueError(f"visual seed {seed.seed_id!r} SHA256 mismatch")
        visual_format = detect_visual_format(seed.image_path)
        if visual_format not in SUPPORTED_ENCODER_FORMATS:
            raise ValueError(
                f"visual seed {seed.seed_id!r} uses unsupported encoder format "
                f"{visual_format!r}"
            )
        width, height, _, _ = read_visual_dimensions(
            seed.image_path, detected_format=visual_format
        )
        if (width, height) != (seed.width, seed.height):
            raise ValueError(
                f"visual seed {seed.seed_id!r} dimensions mismatch: "
                f"observed {(width, height)}, declared {(seed.width, seed.height)}"
            )
        if seed.width * seed.height > MAX_VISUAL_SEED_PIXELS:
            raise ValueError(
                f"visual seed {seed.seed_id!r} exceeds the "
                f"{MAX_VISUAL_SEED_PIXELS}-pixel limit"
            )
    return seeds


def _sticky_relevance(text: str, terms: Sequence[str]) -> tuple[int, list[str]]:
    normalized = _normalize_text(text)
    matched = [term for term in terms if _normalize_text(term) in normalized]
    strong = {
        "f-ram",
        "fram",
        "attention",
        "geometry",
        "provenance",
        "retrieval",
        "fractal",
        "lived experience",
        "child lane",
        "latent",
    }
    score = sum(3 if term in strong else 1 for term in matched)
    return score, matched


def _sticky_cue(text: str, matched_terms: Sequence[str], limit: int = 2400) -> str:
    if not matched_terms:
        return ""
    cleaned = _redact_potential_secrets(_clean_sticky_text(text))
    chunks = re.split(r"(?<=[.!?])\s+|\n+", cleaned)
    selected = [
        chunk.strip()
        for chunk in chunks
        if chunk.strip()
        and any(
            _normalize_text(term) in _normalize_text(chunk) for term in matched_terms
        )
    ]
    result = " ".join(selected)
    return result[:limit]


def load_sticky_note_inventory(
    database: Path,
    *,
    terms: Sequence[str] = DEFAULT_STICKY_TERMS,
    include_sensitive_details: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Read every active Sticky Note in one read-only transaction.

    Returned inventory entries contain hashes, timestamps, lengths, and matched
    vocabulary only.  Raw note IDs and note bodies are deliberately omitted.
    A separate in-memory cue list is returned for bounded local retrieval.
    """

    path = Path(database).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        rows = connection.execute(
            """
            SELECT Id, CreatedAt, UpdatedAt, DeletedAt, Text
            FROM Note
            ORDER BY UpdatedAt DESC, Id
            """
        ).fetchall()
    finally:
        connection.close()

    active = [row for row in rows if row["DeletedAt"] is None]
    deleted_count = len(rows) - len(active)
    inventory_rows: list[dict[str, Any]] = []
    cues: list[dict[str, Any]] = []
    snapshot_rows: list[dict[str, Any]] = []
    for row in active:
        raw_id = str(row["Id"])
        raw_text = str(row["Text"] or "")
        clean_text = _clean_sticky_text(raw_text)
        raw_text_hash = _sha256_text(raw_text)
        text_hash = _sha256_text(clean_text)
        id_hash = _sha256_text(raw_id)
        relevance, matched = _sticky_relevance(clean_text, terms)
        entry = {
            "note_id_sha256": id_hash,
            "raw_text_sha256": raw_text_hash,
            "text_sha256": text_hash,
            "created_at": _windows_ticks_to_iso(row["CreatedAt"]),
            "updated_at": _windows_ticks_to_iso(row["UpdatedAt"]),
            "raw_storage_character_count": len(raw_text),
            "text_character_count": len(clean_text),
            "relevance_score": relevance,
            "matched_terms": matched,
            "retrieval_eligible": relevance > 0,
            "body_in_report": False,
        }
        inventory_rows.append(entry)
        snapshot_rows.append(
            {
                "note_id_sha256": id_hash,
                "raw_text_sha256": raw_text_hash,
                "text_sha256": text_hash,
                "created_at": row["CreatedAt"],
                "updated_at": row["UpdatedAt"],
            }
        )
        cue_text = _sticky_cue(clean_text, matched)
        if relevance > 0 and cue_text:
            cues.append(
                {
                    "note_id_sha256": id_hash,
                    "text_sha256": text_hash,
                    "relevance_score": relevance,
                    "matched_terms": matched,
                    "cue_text": cue_text,
                }
            )
    logical_payload = json.dumps(
        snapshot_rows, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    inventory = {
        "source_database": str(path) if include_sensitive_details else None,
        "source_path_in_report": bool(include_sensitive_details),
        "read_mode": "sqlite-mode-ro-query-only-single-transaction",
        "active_note_count": len(active),
        "deleted_note_count": deleted_count,
        "raw_storage_character_count": sum(
            item["raw_storage_character_count"] for item in inventory_rows
        ),
        "active_text_character_count": sum(
            item["text_character_count"] for item in inventory_rows
        ),
        "logical_snapshot_sha256": _sha256_text(logical_payload),
        "notes_are_untrusted_source": True,
        "raw_note_ids_in_report": False,
        "raw_note_bodies_in_report": False,
        "notes": inventory_rows,
    }
    cues.sort(key=lambda item: (-int(item["relevance_score"]), item["note_id_sha256"]))
    return inventory, cues


def _deduplicate_index(
    index: ReadOnlyLivedIndex,
) -> tuple[list[Any], dict[str, list[Any]]]:
    representatives: list[Any] = []
    groups: dict[str, list[Any]] = {}
    for event in index.events:
        key = _event_content_key(event.query, event.answer)
        bucket = groups.setdefault(key, [])
        bucket.append(event)
        if len(bucket) == 1:
            representatives.append(event)
    return representatives, groups


def _event_view(
    event: Any,
    *,
    content_key: str,
    duplicate_count: int,
    include_sensitive_details: bool,
) -> dict[str, Any]:
    view = {
        "event_id": event.event_id,
        "event_digest": event.event_digest,
        "content_key_sha256": content_key,
        "duplicate_event_count": duplicate_count,
        "sensitive_details_included": bool(include_sensitive_details),
    }
    if include_sensitive_details:
        view.update(
            {
                "session_id": event.session_id,
                "session_seq": event.session_seq,
                "time": event.created_at,
                "domain": event.domain,
                "task": event.task,
                "query_preview": _preview(event.query),
                "answer_preview": _preview(event.answer),
            }
        )
    return view


def _deduped_fram_candidates(
    index: ReadOnlyLivedIndex,
    vectorizer: Any,
    cue_text: str,
    groups: Mapping[str, Sequence[Any]],
    *,
    k: int,
    include_sensitive_details: bool,
) -> list[dict[str, Any]]:
    ranked = index.search(_encode_cue(vectorizer, cue_text), k=len(index.events))
    kept: list[dict[str, Any]] = []
    seen: set[str] = set()
    for result in ranked:
        key = _event_content_key(str(result["query"]), str(result["answer"]))
        if key in seen:
            continue
        seen.add(key)
        event = index.events_by_id[str(result["event_id"])]
        view = _event_view(
            event,
            content_key=key,
            duplicate_count=len(groups[key]),
            include_sensitive_details=include_sensitive_details,
        )
        view["fram_score"] = round(float(result["_score"]), 9)
        view["source_role"] = "fram_text_primary"
        kept.append(view)
        if len(kept) >= max(1, int(k)):
            break
    return kept


def staged_candidate_ids(
    primary: Sequence[Mapping[str, Any]],
    supplemental: Sequence[Mapping[str, Any]],
    *,
    supplemental_limit: int,
) -> dict[str, Any]:
    primary_ids = [str(item["event_id"]) for item in primary]
    bundle = list(primary_ids)
    additions: list[str] = []
    for item in supplemental[: max(0, int(supplemental_limit))]:
        event_id = str(item["event_id"])
        if event_id not in bundle:
            bundle.append(event_id)
            additions.append(event_id)
    return {
        "sequence": ["fram_text_primary", "clip_visual_supplement"],
        "primary_event_ids": primary_ids,
        "primary_order_preserved": bundle[: len(primary_ids)] == primary_ids,
        "visual_additions": additions,
        "bundle_event_ids": bundle,
    }


def _candidate_overlap(
    primary: Sequence[Mapping[str, Any]],
    supplemental: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    primary_ids = {str(item["event_id"]) for item in primary}
    supplemental_ids = {str(item["event_id"]) for item in supplemental}
    union = primary_ids | supplemental_ids
    intersection = primary_ids & supplemental_ids
    return {
        "shared_event_count": len(intersection),
        "jaccard": round(len(intersection) / len(union), 9) if union else 1.0,
    }


def render_candidate_review(report: Mapping[str, Any]) -> str:
    """Render a human-label sheet without changing the candidate report."""

    source = report["source"]
    model_name = report["encoder"].get("model_id", report["encoder"].get("family"))
    sensitive_details = report["privacy"]["sensitive_details_included"]
    lines = [
        "# F-RAM visual-seed candidate review",
        "",
        f"- Status: {report['status']}",
        f"- Lived source SHA256: {source['lived_database_sha256']}",
        f"- Events: {source['event_count']} total / "
        f"{source['unique_event_content_count']} unique content groups",
        f"- Model: {_markdown_text(model_name)}",
        f"- Model revision: {_markdown_text(report['encoder'].get('revision'))}",
        f"- Sensitive details included: {sensitive_details}",
        "- Global ranking influence: **OFF**",
        "",
        (
            "Check boxes are review labels only. "
            "They do not write memory or enable ranking."
        ),
        "",
    ]
    for seed in report["visual_seeds"]:
        seed_id = _markdown_text(seed["seed_id"])
        image_path = seed["image"].get("path")
        lines.extend(
            [
                f"## {seed_id}",
                "",
                (
                    f"Image path: {_html_code(image_path)}"
                    if image_path
                    else "Image path: omitted (use --include-sensitive-details locally)"
                ),
                "",
                f"Source role: {_markdown_text(seed['image']['source_role'])}  ",
                f"SHA256: {seed['image']['sha256']}  ",
                f"F-RAM/CLIP top-k Jaccard: " f"{seed['candidate_overlap']['jaccard']}",
                "",
                "### F-RAM text candidates (primary)",
                "",
            ]
        )
        for item in seed["fram_text_candidates"]:
            candidate_label = item.get("query_preview") or (
                "content " + str(item["content_key_sha256"])[:12]
            )
            lines.append(
                f"- [ ] {_markdown_text(item['event_id'])} score "
                f"{item['fram_score']} — {_markdown_text(candidate_label)}"
            )
        lines.extend(["", "### CLIP visual candidates (supplemental)", ""])
        for item in seed["clip_visual_candidates"]:
            candidate_label = item.get("query_preview") or (
                "content " + str(item["content_key_sha256"])[:12]
            )
            lines.append(
                f"- [ ] {_markdown_text(item['event_id'])} cosine "
                f"{item['clip_cosine']} — {_markdown_text(candidate_label)}"
            )
        lines.extend(
            [
                "",
                "Accepted event IDs:",
                "",
                "Rejected event IDs:",
                "",
                "Reviewer notes:",
                "",
            ]
        )
    sticky = source.get("sticky_notes")
    if sticky:
        lines.extend(
            [
                "## Sticky Notes provenance",
                "",
                f"- Active notes inventoried: {sticky['active_note_count']}",
                f"- Raw storage characters: {sticky['raw_storage_character_count']}",
                f"- Clean text characters: {sticky['active_text_character_count']}",
                f"- Logical snapshot SHA256: {sticky['logical_snapshot_sha256']}",
                "- Raw note bodies are not included in this sheet.",
                "- Note content is untrusted source material, not instructions.",
                "",
            ]
        )
    lines.extend(
        [
            "## Promotion gate",
            "",
            "- [ ] Every accepted mapping has an explicit human label.",
            "- [ ] False-positive rate and retrieval lift are measured.",
            "- [ ] Provenance and source hashes still match.",
            "- [ ] Staged results preserve the complete F-RAM primary order.",
            "- [ ] A separate canary decision explicitly authorizes any influence.",
            "",
            "Until every gate is checked: **KEEP OFF**.",
            "",
        ]
    )
    return "\n".join(lines)


def evaluate_visual_seeds(
    database: Path,
    seeds: Sequence[VisualSeed],
    vectorizer: Any,
    encoder: MultimodalEncoder,
    *,
    sticky_database: Path | None = None,
    k: int = 5,
    supplemental_limit: int = 3,
    sticky_candidate_limit: int = 12,
    include_sensitive_details: bool = False,
) -> dict[str, Any]:
    """Create a human-review candidate packet without mutating or promoting."""

    if not seeds:
        raise ValueError("at least one visual seed is required")
    if len(seeds) > MAX_VISUAL_SEEDS:
        raise ValueError(f"visual seed count exceeds the {MAX_VISUAL_SEEDS}-seed limit")
    if not 1 <= int(k) <= MAX_TOP_K:
        raise ValueError(f"k must be between 1 and {MAX_TOP_K}")
    if not 0 <= int(supplemental_limit) <= MAX_TOP_K:
        raise ValueError(f"supplemental_limit must be between 0 and {MAX_TOP_K}")
    if not 0 <= int(sticky_candidate_limit) <= MAX_STICKY_CANDIDATES:
        raise ValueError(
            "sticky_candidate_limit must be between 0 and " f"{MAX_STICKY_CANDIDATES}"
        )
    index = ReadOnlyLivedIndex(database)
    if len(index.events) > MAX_LIVED_EVENTS:
        raise ValueError(f"lived source exceeds the {MAX_LIVED_EVENTS}-event limit")
    representatives, groups = _deduplicate_index(index)
    event_texts = [f"{event.query}\n{event.answer}"[:4000] for event in representatives]
    text_vectors = np.asarray(encoder.encode_texts(event_texts), dtype=float)
    image_vectors = np.asarray(
        encoder.encode_images([seed.image_path for seed in seeds]), dtype=float
    )
    if text_vectors.ndim != 2 or image_vectors.ndim != 2:
        raise ValueError("encoder outputs must be rank-2 matrices")
    if not np.isfinite(text_vectors).all() or not np.isfinite(image_vectors).all():
        raise ValueError("encoder outputs must contain only finite values")
    if text_vectors.shape[0] != len(representatives):
        raise ValueError("encoder returned the wrong number of text vectors")
    if image_vectors.shape[0] != len(seeds):
        raise ValueError("encoder returned the wrong number of image vectors")
    if not text_vectors.shape[1] or text_vectors.shape[1] != image_vectors.shape[1]:
        raise ValueError("encoder image and text dimensions do not match")
    image_hashes_after_encoding = {
        seed.seed_id: _sha256_file(seed.image_path) for seed in seeds
    }
    for seed in seeds:
        if image_hashes_after_encoding[seed.seed_id].lower() != seed.sha256:
            raise ValueError(f"visual seed {seed.seed_id!r} changed during encoding")

    reports: list[dict[str, Any]] = []
    for seed, image_vector in zip(seeds, image_vectors):
        cue_text = " ".join((seed.description, *seed.concept_tags))
        fram = _deduped_fram_candidates(
            index,
            vectorizer,
            cue_text,
            groups,
            k=k,
            include_sensitive_details=include_sensitive_details,
        )
        similarities = _cosine_rows(text_vectors, image_vector)
        order = np.argsort(-similarities, kind="stable")[: max(1, int(k))]
        visual: list[dict[str, Any]] = []
        for position in order:
            event = representatives[int(position)]
            key = _event_content_key(event.query, event.answer)
            view = _event_view(
                event,
                content_key=key,
                duplicate_count=len(groups[key]),
                include_sensitive_details=include_sensitive_details,
            )
            view["clip_cosine"] = round(float(similarities[int(position)]), 9)
            view["source_role"] = "clip_visual_supplement"
            visual.append(view)
        reports.append(
            {
                "seed_id": seed.seed_id,
                "image": {
                    "path": str(seed.image_path) if include_sensitive_details else None,
                    "path_in_report": bool(include_sensitive_details),
                    "sha256": seed.sha256,
                    "sha256_after_encoding": image_hashes_after_encoding[seed.seed_id],
                    "evidence_id": seed.evidence_id,
                    "width": seed.width,
                    "height": seed.height,
                    "source_role": seed.source_role,
                    "description_role": "untrusted_source_description",
                    "concept_tags": list(seed.concept_tags),
                },
                "fram_text_candidates": fram,
                "clip_visual_candidates": visual,
                "candidate_overlap": _candidate_overlap(fram, visual),
                "staged_fram_then_visual": staged_candidate_ids(
                    fram, visual, supplemental_limit=supplemental_limit
                ),
                "review": {
                    "status": "pending_human_label",
                    "accepted_event_ids": [],
                    "rejected_event_ids": [],
                },
            }
        )

    sticky_inventory = None
    sticky_reports: list[dict[str, Any]] = []
    sticky_source_unchanged = None
    if sticky_database is not None:
        sticky_inventory, sticky_cues = load_sticky_note_inventory(
            sticky_database,
            include_sensitive_details=include_sensitive_details,
        )
        before_sticky = sticky_inventory["logical_snapshot_sha256"]
        for cue in sticky_cues[: max(0, int(sticky_candidate_limit))]:
            candidates = _deduped_fram_candidates(
                index,
                vectorizer,
                str(cue["cue_text"]),
                groups,
                k=k,
                include_sensitive_details=include_sensitive_details,
            )
            sticky_reports.append(
                {
                    "note_id_sha256": cue["note_id_sha256"],
                    "text_sha256": cue["text_sha256"],
                    "relevance_score": cue["relevance_score"],
                    "matched_terms": cue["matched_terms"],
                    "cue_body_in_report": False,
                    "candidates": candidates,
                    "review_status": "pending_human_label",
                }
            )
        after_inventory, _ = load_sticky_note_inventory(
            sticky_database,
            include_sensitive_details=include_sensitive_details,
        )
        sticky_source_unchanged = (
            before_sticky == after_inventory["logical_snapshot_sha256"]
        )

    source_hash_after = _sha256_file(index.path)
    duplicate_sizes = sorted((len(items) for items in groups.values()), reverse=True)
    overlap_values = [float(item["candidate_overlap"]["jaccard"]) for item in reports]
    return {
        "schema_version": VISUAL_SEED_SCHEMA_VERSION,
        "created_at": _utc_now(),
        "status": "candidates_pending_human_labels",
        "source": {
            "lived_database": str(index.path) if include_sensitive_details else None,
            "lived_source_path_in_report": bool(include_sensitive_details),
            "lived_database_sha256": index.sha256_before,
            "lived_source_unchanged": source_hash_after == index.sha256_before,
            "sqlite_integrity_check": index.integrity,
            "event_count": len(index.events),
            "unique_event_content_count": len(representatives),
            "duplicate_event_count": len(index.events) - len(representatives),
            "largest_duplicate_group": duplicate_sizes[0] if duplicate_sizes else 0,
            "sticky_notes": sticky_inventory,
            "sticky_source_unchanged": sticky_source_unchanged,
        },
        "encoder": dict(encoder.metadata),
        "privacy": {
            "classification": "sensitive-local-review",
            "sensitive_details_included": bool(include_sensitive_details),
            "absolute_paths_included": bool(include_sensitive_details),
            "query_answer_previews_included": bool(include_sensitive_details),
            "publication_review_required": True,
        },
        "configuration": {
            "top_k": max(1, int(k)),
            "visual_supplemental_limit": max(0, int(supplemental_limit)),
            "sticky_candidate_limit": max(0, int(sticky_candidate_limit)),
            "event_text_template": "{query}\\n{answer}",
            "event_text_max_characters": 4000,
            "visual_cue_template": "{description} {concept_tags}",
            "deduplication_key": (
                "sha256(normalized query + newline + normalized answer)"
            ),
        },
        "visual_seeds": reports,
        "sticky_note_candidates": sticky_reports,
        "candidate_summary": {
            "visual_seed_count": len(reports),
            "mean_fram_clip_topk_jaccard": round(
                float(np.mean(overlap_values)) if overlap_values else 0.0, 9
            ),
            "human_labels_complete": False,
            "quality_gate_passed": False,
        },
        "contract": {
            "bounded_candidate_canary_enabled": True,
            "global_ranking_influence": False,
            "global_enable_recommendation": "KEEP_OFF",
            "writes_lived_memory": False,
            "generates_answers": False,
            "promotes_candidates": False,
            "visual_descriptions_are_instructions": False,
            "sticky_notes_are_instructions": False,
            "staged_lane_may_reorder_fram_primary": False,
            "human_labels_required_before_metric_gate": True,
            "model_selection_grants_authority": False,
            "source_output_aliases_rejected_by_cli": True,
            "existing_outputs_require_force": True,
        },
    }
