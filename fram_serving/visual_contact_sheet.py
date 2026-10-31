"""Render review contact sheets from a FRAM visual evidence manifest."""

from __future__ import annotations

import argparse
import html
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Sequence


ORIGIN_PRIORITY = {
    "canonical_source": 0,
    "imported_evidence": 1,
    "archive_mirror": 2,
    "generated_artifact": 3,
    "runtime_support": 4,
    "mac_metadata": 5,
}


def _load_records(manifest_path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with manifest_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"Manifest line {line_number} is not an object")
            records.append(payload)
    return records


def select_visual_representatives(
    records: list[dict[str, Any]],
    *,
    unique_content: bool = True,
) -> list[dict[str, Any]]:
    """Select deterministic picture paths while preserving duplicate mapping."""

    visuals = [
        record
        for record in records
        if record.get("status") == "indexed" and record.get("content_class") == "visual"
    ]
    if not unique_content:
        return [
            {**record, "duplicate_paths": [record.get("relative_path")]}
            for record in sorted(visuals, key=lambda item: str(item.get("relative_path", "")).casefold())
        ]

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in visuals:
        digest = str(record.get("sha256") or record.get("relative_path") or "")
        grouped[digest].append(record)
    representatives: list[dict[str, Any]] = []
    for digest, members in grouped.items():
        members.sort(
            key=lambda item: (
                ORIGIN_PRIORITY.get(str(item.get("origin_class")), 99),
                len(str(item.get("relative_path", ""))),
                str(item.get("relative_path", "")).casefold(),
            )
        )
        representative = dict(members[0])
        representative["sha256"] = digest
        representative["duplicate_paths"] = sorted(
            str(member.get("relative_path")) for member in members
        )
        representatives.append(representative)
    representatives.sort(
        key=lambda item: (
            ORIGIN_PRIORITY.get(str(item.get("origin_class")), 99),
            str(item.get("relative_path", "")).casefold(),
        )
    )
    return representatives


def _safe_source_path(source_root: Path, relative_path: str) -> Path:
    root = source_root.resolve()
    candidate = (root / Path(relative_path)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Manifest path escapes source root: {relative_path}") from exc
    return candidate


def _font(size: int):
    from PIL import ImageFont

    candidates = (
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(str(candidate), size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _fit_image(path: Path, size: tuple[int, int], detected_format: str | None):
    from PIL import Image, ImageDraw, ImageOps

    if detected_format == "svg":
        placeholder = Image.new("RGB", size, "#151b2e")
        draw = ImageDraw.Draw(placeholder)
        draw.rectangle((2, 2, size[0] - 3, size[1] - 3), outline="#7593d1", width=2)
        draw.multiline_text(
            (20, 20),
            "SVG VECTOR\nRaster preview unavailable\nSource retained in ledger",
            fill="#dbe7ff",
            font=_font(18),
            spacing=8,
        )
        return placeholder, "svg-placeholder"
    try:
        with Image.open(path) as opened:
            image = ImageOps.exif_transpose(opened)
            if getattr(image, "is_animated", False):
                image.seek(0)
            image = image.convert("RGB")
            image.thumbnail(size, Image.Resampling.LANCZOS)
            canvas = Image.new("RGB", size, "#080b12")
            x = (size[0] - image.width) // 2
            y = (size[1] - image.height) // 2
            canvas.paste(image, (x, y))
            return canvas, "raster"
    except Exception as exc:  # corrupt payloads remain visible as explicit review failures
        placeholder = Image.new("RGB", size, "#2b1018")
        draw = ImageDraw.Draw(placeholder)
        draw.multiline_text(
            (20, 20),
            f"PREVIEW ERROR\n{type(exc).__name__}\nSee observation index",
            fill="#ffd9df",
            font=_font(18),
            spacing=8,
        )
        return placeholder, f"error:{type(exc).__name__}"


def build_contact_sheets(
    *,
    manifest_path: Path,
    source_root: Path,
    output_dir: Path,
    unique_content: bool = True,
    columns: int = 4,
    rows: int = 3,
    tile_width: int = 480,
    tile_height: int = 380,
) -> dict[str, Any]:
    """Render deterministic review sheets and a path-complete observation index."""

    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:  # pragma: no cover - depends on optional environment
        raise RuntimeError("Contact sheets require Pillow; install the FRAM 'visual' extra") from exc

    if columns < 1 or rows < 1:
        raise ValueError("columns and rows must be positive")
    output_dir.mkdir(parents=True, exist_ok=True)
    records = _load_records(manifest_path)
    selected = select_visual_representatives(records, unique_content=unique_content)
    per_sheet = columns * rows
    label_height = 72
    preview_height = tile_height - label_height
    observation_records: list[dict[str, Any]] = []
    sheets: list[str] = []

    for page_start in range(0, len(selected), per_sheet):
        page_number = page_start // per_sheet + 1
        page_records = selected[page_start : page_start + per_sheet]
        sheet = Image.new("RGB", (columns * tile_width, rows * tile_height), "#05070c")
        draw = ImageDraw.Draw(sheet)
        sheet_name = f"visual_contact_sheet_{page_number:03d}.jpg"
        for local_index, record in enumerate(page_records):
            global_index = page_start + local_index + 1
            row, column = divmod(local_index, columns)
            x = column * tile_width
            y = row * tile_height
            relative_path = str(record.get("relative_path") or "")
            source_path = _safe_source_path(source_root, relative_path)
            preview, preview_status = _fit_image(
                source_path,
                (tile_width - 12, preview_height - 12),
                str(record.get("detected_format") or "") or None,
            )
            sheet.paste(preview, (x + 6, y + 6))
            label_y = y + preview_height
            draw.rectangle(
                (x + 4, label_y, x + tile_width - 5, y + tile_height - 5),
                fill="#11182a",
                outline="#344361",
                width=1,
            )
            visual_id = f"VE-{global_index:04d}"
            basename = Path(relative_path).name
            if len(basename) > 48:
                basename = basename[:45] + "..."
            draw.text((x + 12, label_y + 7), f"{visual_id}  {basename}", fill="#f1f5ff", font=_font(17))
            draw.text(
                (x + 12, label_y + 37),
                f"{record.get('width')}x{record.get('height')}  {record.get('origin_class')}  copies:{len(record.get('duplicate_paths') or [])}",
                fill="#aebbd4",
                font=_font(13),
            )
            observation_records.append(
                {
                    "visual_id": visual_id,
                    "sheet": sheet_name,
                    "sheet_position": {"row": row + 1, "column": column + 1},
                    "representative_path": relative_path,
                    "duplicate_paths": list(record.get("duplicate_paths") or []),
                    "sha256": record.get("sha256"),
                    "evidence_id": record.get("evidence_id"),
                    "detected_format": record.get("detected_format"),
                    "width": record.get("width"),
                    "height": record.get("height"),
                    "origin_class": record.get("origin_class"),
                    "preview_status": preview_status,
                }
            )
        sheet.save(output_dir / sheet_name, format="JPEG", quality=92, optimize=True)
        sheets.append(sheet_name)

    index_payload = {
        "schema_version": "fram-visual-observation-1",
        "source_manifest": str(manifest_path.resolve()),
        "source_root": str(source_root.resolve()),
        "mode": "unique_content" if unique_content else "all_paths",
        "selected_visuals": len(selected),
        "sheets": sheets,
        "records": observation_records,
    }
    index_path = output_dir / "visual_contact_sheet_index.json"
    index_path.write_text(
        json.dumps(index_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    html_lines = [
        "<!doctype html><meta charset='utf-8'><title>FRAM Visual Evidence</title>",
        "<style>body{background:#05070c;color:#edf2ff;font:16px system-ui;margin:24px}"
        "img{display:block;max-width:100%;margin:18px 0 36px;border:1px solid #344361}</style>",
        f"<h1>FRAM Visual Evidence</h1><p>{len(selected)} observed visual identities; mapping in "
        "<code>visual_contact_sheet_index.json</code>.</p>",
    ]
    for sheet_name in sheets:
        html_lines.append(f"<h2>{html.escape(sheet_name)}</h2><img src='{html.escape(sheet_name)}'>")
    (output_dir / "index.html").write_text("\n".join(html_lines) + "\n", encoding="utf-8")
    return index_payload


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render FRAM visual evidence contact sheets.")
    parser.add_argument("manifest", type=Path, help="visual_evidence.jsonl path")
    parser.add_argument("source_root", type=Path, help="Source root recorded by the ledger")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--all-paths", action="store_true", help="Render duplicate paths separately")
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument("--rows", type=int, default=3)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = build_contact_sheets(
        manifest_path=args.manifest,
        source_root=args.source_root,
        output_dir=args.output_dir,
        unique_content=not args.all_paths,
        columns=args.columns,
        rows=args.rows,
    )
    print(
        f"Rendered {result['selected_visuals']} visual identities across "
        f"{len(result['sheets'])} contact sheets."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
