"""Lossless inventory primitives for FRAM visual evidence.

The visual corpus is evidence, not a disposable media folder.  This module
therefore indexes every recognized visual file, preserves duplicate paths, and
records failures instead of silently skipping them.  It deliberately uses the
standard library so the first forensic pass can run before the full FRAM
scientific environment is available.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import struct
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, Sequence


SCHEMA_VERSION = "fram-visual-evidence-1"
DEFAULT_VISUAL_EXTENSIONS = frozenset(
    {
        ".bmp",
        ".gif",
        ".icns",
        ".ico",
        ".jpeg",
        ".jpg",
        ".png",
        ".svg",
        ".tif",
        ".tiff",
        ".webp",
    }
)


@dataclass(slots=True)
class VisualEvidenceRecord:
    """One path-level visual evidence record.

    Exact duplicates remain separate records because their locations and
    timestamps can carry sequencing or provenance information.
    """

    relative_path: str
    extension: str
    mime_type: str
    detected_format: str | None
    extension_matches_content: bool | None
    origin_class: str
    content_class: str
    size_bytes: int | None
    modified_utc: str | None
    sha256: str | None
    evidence_id: str | None
    width: int | None
    height: int | None
    frame_count: int | None
    metadata_method: str | None
    metadata_error: str | None = None
    duplicate_group: str | None = None
    duplicate_count: int = 1
    status: str = "indexed"
    error: str | None = None


@dataclass(frozen=True, slots=True)
class ManifestPaths:
    """Paths written by :func:`write_visual_manifest`."""

    manifest: Path
    summary: Path
    duplicates: Path


@dataclass(slots=True)
class VisualEvidenceReport:
    """Complete result of a recursive visual scan."""

    source_root: Path
    records: list[VisualEvidenceRecord]
    directory_errors: list[dict[str, str]]

    @property
    def complete(self) -> bool:
        return not self.directory_errors and all(record.status == "indexed" for record in self.records)

    def duplicate_groups(self) -> list[dict[str, object]]:
        grouped: dict[str, list[VisualEvidenceRecord]] = defaultdict(list)
        for record in self.records:
            if record.sha256:
                grouped[record.sha256].append(record)
        duplicates: list[dict[str, object]] = []
        for digest, members in sorted(grouped.items()):
            if len(members) < 2:
                continue
            duplicates.append(
                {
                    "duplicate_group": f"sha256:{digest}",
                    "sha256": digest,
                    "count": len(members),
                    "paths": sorted(member.relative_path for member in members),
                }
            )
        return duplicates

    def summary(self) -> dict[str, object]:
        indexed = [record for record in self.records if record.status == "indexed"]
        failed = [record for record in self.records if record.status != "indexed"]
        unique_hashes = {record.sha256 for record in indexed if record.sha256}
        visual_records = [record for record in indexed if record.content_class == "visual"]
        unique_visual_hashes = {record.sha256 for record in visual_records if record.sha256}
        visual_hash_counts = Counter(record.sha256 for record in visual_records if record.sha256)
        visual_duplicate_counts = [count for count in visual_hash_counts.values() if count > 1]
        duplicate_groups = self.duplicate_groups()
        duplicate_files = sum(int(group["count"]) - 1 for group in duplicate_groups)
        return {
            "schema_version": SCHEMA_VERSION,
            "source_root": str(self.source_root.resolve()),
            "completeness_status": "complete" if self.complete else "incomplete",
            "discovered_visuals": len(self.records),
            "indexed_visuals": len(indexed),
            "actual_visuals": sum(
                1 for record in indexed if record.content_class == "visual"
            ),
            "metadata_sidecars": sum(
                1 for record in indexed if record.content_class == "mac_metadata_sidecar"
            ),
            "unverified_visuals": sum(
                1 for record in indexed if record.content_class == "visual_unverified"
            ),
            "extension_mismatches": sum(
                1 for record in indexed if record.extension_matches_content is False
            ),
            "failed_visuals": len(failed),
            "directory_error_count": len(self.directory_errors),
            "unique_content": len(unique_hashes),
            "unique_visual_content": len(unique_visual_hashes),
            "exact_visual_duplicate_groups": len(visual_duplicate_counts),
            "exact_visual_duplicate_files": sum(count - 1 for count in visual_duplicate_counts),
            "exact_duplicate_groups": len(duplicate_groups),
            "exact_duplicate_files": duplicate_files,
            "total_bytes": sum(record.size_bytes or 0 for record in indexed),
            "dimensions_known": sum(
                1 for record in indexed if record.width is not None and record.height is not None
            ),
            "by_extension": dict(sorted(Counter(record.extension for record in self.records).items())),
            "by_origin_class": dict(
                sorted(Counter(record.origin_class for record in self.records).items())
            ),
            "by_content_class": dict(
                sorted(Counter(record.content_class for record in self.records).items())
            ),
            "failed_paths": [record.relative_path for record in failed],
            "directory_errors": list(self.directory_errors),
        }


def _utc_timestamp(seconds: float) -> str:
    return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()


def _sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _numeric_dimension(value: str | None) -> int | None:
    if not value:
        return None
    match = re.match(r"\s*([0-9]+(?:\.[0-9]+)?)", value)
    if not match:
        return None
    number = float(match.group(1))
    return int(round(number)) if number >= 0 else None


def _svg_dimensions(path: Path) -> tuple[int | None, int | None, int | None, str]:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        header = handle.read(262_144)
    svg_tag = re.search(r"<svg\b([^>]*)>", header, flags=re.IGNORECASE | re.DOTALL)
    if not svg_tag:
        return None, None, None, "svg-header"
    attrs = svg_tag.group(1)
    width_match = re.search(r"\bwidth\s*=\s*['\"]([^'\"]+)", attrs, flags=re.IGNORECASE)
    height_match = re.search(r"\bheight\s*=\s*['\"]([^'\"]+)", attrs, flags=re.IGNORECASE)
    width = _numeric_dimension(width_match.group(1) if width_match else None)
    height = _numeric_dimension(height_match.group(1) if height_match else None)
    if width is None or height is None:
        viewbox = re.search(
            r"\bviewBox\s*=\s*['\"]\s*[-+0-9.eE]+[\s,]+[-+0-9.eE]+[\s,]+"
            r"([-+0-9.eE]+)[\s,]+([-+0-9.eE]+)",
            attrs,
            flags=re.IGNORECASE,
        )
        if viewbox:
            width = width if width is not None else _numeric_dimension(viewbox.group(1))
            height = height if height is not None else _numeric_dimension(viewbox.group(2))
    return width, height, 1, "svg-header"


def _jpeg_dimensions(path: Path) -> tuple[int | None, int | None]:
    start_of_frame = {
        0xC0,
        0xC1,
        0xC2,
        0xC3,
        0xC5,
        0xC6,
        0xC7,
        0xC9,
        0xCA,
        0xCB,
        0xCD,
        0xCE,
        0xCF,
    }
    with path.open("rb") as handle:
        if handle.read(2) != b"\xff\xd8":
            return None, None
        while True:
            prefix = handle.read(1)
            if not prefix:
                return None, None
            if prefix != b"\xff":
                continue
            marker = handle.read(1)
            while marker == b"\xff":
                marker = handle.read(1)
            if not marker:
                return None, None
            marker_value = marker[0]
            if marker_value in {0xD8, 0x01}:
                continue
            if marker_value in {0xD9, 0xDA}:
                return None, None
            raw_length = handle.read(2)
            if len(raw_length) != 2:
                return None, None
            segment_length = struct.unpack(">H", raw_length)[0]
            if segment_length < 2:
                return None, None
            if marker_value in start_of_frame:
                payload = handle.read(5)
                if len(payload) != 5:
                    return None, None
                height, width = struct.unpack(">HH", payload[1:5])
                return int(width), int(height)
            handle.seek(segment_length - 2, os.SEEK_CUR)


def _webp_dimensions(header: bytes) -> tuple[int | None, int | None]:
    if len(header) < 30 or header[:4] != b"RIFF" or header[8:12] != b"WEBP":
        return None, None
    chunk = header[12:16]
    if chunk == b"VP8X":
        width = 1 + int.from_bytes(header[24:27], "little")
        height = 1 + int.from_bytes(header[27:30], "little")
        return width, height
    if chunk == b"VP8 " and header[23:26] == b"\x9d\x01\x2a":
        width = int.from_bytes(header[26:28], "little") & 0x3FFF
        height = int.from_bytes(header[28:30], "little") & 0x3FFF
        return width, height
    if chunk == b"VP8L" and header[20:21] == b"\x2f" and len(header) >= 25:
        b0, b1, b2, b3 = header[21:25]
        width = 1 + b0 + ((b1 & 0x3F) << 8)
        height = 1 + (b1 >> 6) + (b2 << 2) + ((b3 & 0x0F) << 10)
        return width, height
    return None, None


def _icns_dimensions(path: Path) -> tuple[int | None, int | None, int | None]:
    sizes = {
        b"icp4": 16,
        b"icp5": 32,
        b"icp6": 64,
        b"ic07": 128,
        b"ic08": 256,
        b"ic09": 512,
        b"ic10": 1024,
        b"ic11": 32,
        b"ic12": 64,
        b"ic13": 256,
        b"ic14": 512,
    }
    payload = path.read_bytes()
    if len(payload) < 8 or payload[:4] != b"icns":
        return None, None, None
    position = 8
    discovered: list[int] = []
    chunks = 0
    while position + 8 <= len(payload):
        chunk_type = payload[position : position + 4]
        chunk_length = int.from_bytes(payload[position + 4 : position + 8], "big")
        if chunk_length < 8 or position + chunk_length > len(payload):
            break
        chunks += 1
        if chunk_type in sizes:
            discovered.append(sizes[chunk_type])
        position += chunk_length
    dimension = max(discovered) if discovered else None
    return dimension, dimension, chunks or None


def detect_visual_format(path: Path) -> str | None:
    """Detect a visual container from bytes rather than trusting its suffix."""

    with path.open("rb") as handle:
        header = handle.read(4096)
    if header[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if header[:2] == b"\xff\xd8":
        return "jpeg"
    if header[:6] in {b"GIF87a", b"GIF89a"}:
        return "gif"
    if header[:2] == b"BM":
        return "bmp"
    if header[:4] == b"\x00\x00\x01\x00":
        return "ico"
    if header[:4] == b"icns":
        return "icns"
    if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "webp"
    if header[:4] in {b"II*\x00", b"MM\x00*"}:
        return "tiff"
    text_header = header.decode("utf-8", errors="ignore").lstrip("\ufeff\x00\t\r\n ")
    if re.search(r"<(?:[A-Za-z_][\w.-]*:)?svg\b", text_header, flags=re.IGNORECASE):
        return "svg"
    return None


def read_visual_dimensions(
    path: Path,
    *,
    detected_format: str | None = None,
) -> tuple[int | None, int | None, int | None, str | None]:
    """Read dimensions without decoding pixel payloads or requiring Pillow."""

    visual_format = detected_format or detect_visual_format(path)
    if visual_format == "svg":
        return _svg_dimensions(path)
    if visual_format == "jpeg":
        width, height = _jpeg_dimensions(path)
        return width, height, 1, "jpeg-header"
    with path.open("rb") as handle:
        header = handle.read(64)
    if visual_format == "png" and len(header) >= 24:
        width, height = struct.unpack(">II", header[16:24])
        return int(width), int(height), 1, "png-header"
    if visual_format == "gif" and len(header) >= 10:
        width, height = struct.unpack("<HH", header[6:10])
        return int(width), int(height), None, "gif-header"
    if visual_format == "bmp" and len(header) >= 26:
        width, height = struct.unpack("<ii", header[18:26])
        return abs(int(width)), abs(int(height)), 1, "bmp-header"
    if visual_format == "webp":
        width, height = _webp_dimensions(header)
        return width, height, None, "webp-header"
    if visual_format == "ico" and len(header) >= 8:
        width = int(header[6]) or 256
        height = int(header[7]) or 256
        count = int.from_bytes(header[4:6], "little")
        return width, height, count or None, "ico-header"
    if visual_format == "icns":
        width, height, count = _icns_dimensions(path)
        return width, height, count, "icns-chunks"
    return None, None, None, "header-unsupported"


def _mime_type(path: Path) -> str:
    overrides = {
        ".icns": "image/icns",
        ".ico": "image/x-icon",
        ".svg": "image/svg+xml",
        ".webp": "image/webp",
    }
    return overrides.get(path.suffix.lower()) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def classify_visual_origin(relative_path: str) -> str:
    """Classify source location without excluding it from the ledger."""

    normalized = relative_path.replace("\\", "/")
    lowered = normalized.lower()
    parts = tuple(part for part in lowered.split("/") if part)
    if parts and parts[-1].startswith("._"):
        return "mac_metadata"
    mirror_prefix = "2026-07-16/f-ram/fram_v22_starter/fram_v22_starter/"
    if lowered.startswith(mirror_prefix):
        return "archive_mirror"
    if any(part in {".git", ".venv", ".spotlight-v100", ".fseventsd", "__pycache__"} for part in parts):
        return "runtime_support"
    if parts and parts[0] in {"artifacts", "storage"}:
        return "generated_artifact"
    if parts and (parts[0].startswith("2026") or parts[0] in {"abc", "images", "the truth"}):
        return "imported_evidence"
    return "canonical_source"


def _iter_visual_paths(
    root: Path,
    extensions: frozenset[str],
    directory_errors: list[dict[str, str]],
) -> Iterator[Path]:
    def on_error(error: OSError) -> None:
        directory_errors.append(
            {
                "path": str(getattr(error, "filename", "") or ""),
                "error": f"{type(error).__name__}: {error}",
            }
        )

    for directory, dirnames, filenames in os.walk(root, topdown=True, onerror=on_error, followlinks=False):
        dirnames.sort(key=str.casefold)
        filenames.sort(key=str.casefold)
        base = Path(directory)
        for filename in filenames:
            path = base / filename
            if path.suffix.lower() in extensions:
                yield path


def _record_for_path(path: Path, root: Path) -> VisualEvidenceRecord:
    relative_path = path.relative_to(root).as_posix()
    extension = path.suffix.lower()
    origin_class = classify_visual_origin(relative_path)
    sidecar = path.name.startswith("._")
    try:
        stat = path.stat()
        digest = _sha256(path)
    except (OSError, ValueError) as exc:
        return VisualEvidenceRecord(
            relative_path=relative_path,
            extension=extension,
            mime_type=_mime_type(path),
            detected_format=None,
            extension_matches_content=None,
            origin_class=origin_class,
            content_class="mac_metadata_sidecar" if sidecar else "visual_unverified",
            size_bytes=None,
            modified_utc=None,
            sha256=None,
            evidence_id=None,
            width=None,
            height=None,
            frame_count=None,
            metadata_method=None,
            status="error",
            error=f"{type(exc).__name__}: {exc}",
        )
    width: int | None = None
    height: int | None = None
    frame_count: int | None = None
    metadata_method: str | None = None
    metadata_error: str | None = None
    detected_format: str | None = None
    try:
        detected_format = detect_visual_format(path)
        width, height, frame_count, metadata_method = read_visual_dimensions(
            path, detected_format=detected_format
        )
    except (OSError, ValueError, struct.error) as exc:
        metadata_error = f"{type(exc).__name__}: {exc}"
    if sidecar:
        content_class = "mac_metadata_sidecar"
    elif detected_format is not None:
        content_class = "visual"
    else:
        content_class = "visual_unverified"
    expected_formats = {
        ".bmp": {"bmp"},
        ".gif": {"gif"},
        ".icns": {"icns"},
        ".ico": {"ico"},
        ".jpeg": {"jpeg"},
        ".jpg": {"jpeg"},
        ".png": {"png"},
        ".svg": {"svg"},
        ".tif": {"tiff"},
        ".tiff": {"tiff"},
        ".webp": {"webp"},
    }
    extension_matches_content = (
        detected_format in expected_formats.get(extension, set()) if detected_format else None
    )
    return VisualEvidenceRecord(
        relative_path=relative_path,
        extension=extension,
        mime_type=_mime_type(path),
        detected_format=detected_format,
        extension_matches_content=extension_matches_content,
        origin_class=origin_class,
        content_class=content_class,
        size_bytes=int(stat.st_size),
        modified_utc=_utc_timestamp(stat.st_mtime),
        sha256=digest,
        evidence_id=f"visual:sha256:{digest}",
        width=width,
        height=height,
        frame_count=frame_count,
        metadata_method=metadata_method,
        metadata_error=metadata_error,
    )


def scan_visual_evidence(
    source_root: Path | str,
    *,
    extensions: Iterable[str] | None = None,
) -> VisualEvidenceReport:
    """Recursively account for every recognized visual under ``source_root``."""

    root = Path(source_root).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"Visual evidence root does not exist or is not a directory: {root}")
    normalized_extensions = frozenset(
        extension.lower() if extension.startswith(".") else f".{extension.lower()}"
        for extension in (extensions or DEFAULT_VISUAL_EXTENSIONS)
    )
    directory_errors: list[dict[str, str]] = []
    records = [
        _record_for_path(path, root)
        for path in _iter_visual_paths(root, normalized_extensions, directory_errors)
    ]
    records.sort(key=lambda record: record.relative_path.casefold())
    by_hash: dict[str, list[VisualEvidenceRecord]] = defaultdict(list)
    for record in records:
        if record.sha256:
            by_hash[record.sha256].append(record)
    for digest, members in by_hash.items():
        if len(members) < 2:
            continue
        group = f"sha256:{digest}"
        for member in members:
            member.duplicate_group = group
            member.duplicate_count = len(members)
    return VisualEvidenceReport(root, records, directory_errors)


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def write_visual_manifest(report: VisualEvidenceReport, output_dir: Path | str) -> ManifestPaths:
    """Write deterministic JSONL, summary, and duplicate ledgers atomically."""

    destination = Path(output_dir)
    manifest_path = destination / "visual_evidence.jsonl"
    summary_path = destination / "visual_evidence_summary.json"
    duplicates_path = destination / "visual_duplicates.json"

    lines = [
        json.dumps(asdict(record), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for record in report.records
    ]
    manifest_text = "\n".join(lines) + ("\n" if lines else "")
    manifest_sha256 = hashlib.sha256(manifest_text.encode("utf-8")).hexdigest()
    summary = report.summary()
    summary.update(
        {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "manifest_sha256": manifest_sha256,
            "manifest_file": manifest_path.name,
            "duplicates_file": duplicates_path.name,
        }
    )
    duplicates = {
        "schema_version": SCHEMA_VERSION,
        "manifest_sha256": manifest_sha256,
        "groups": report.duplicate_groups(),
    }

    _atomic_write(manifest_path, manifest_text)
    _atomic_write(summary_path, json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    _atomic_write(
        duplicates_path,
        json.dumps(duplicates, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return ManifestPaths(manifest_path, summary_path, duplicates_path)


def parse_extensions(values: Sequence[str] | None) -> frozenset[str] | None:
    """Normalize repeated or comma-separated CLI extension values."""

    if not values:
        return None
    parsed: set[str] = set()
    for value in values:
        for item in value.split(","):
            cleaned = item.strip().lower()
            if cleaned:
                parsed.add(cleaned if cleaned.startswith(".") else f".{cleaned}")
    return frozenset(parsed) or None
