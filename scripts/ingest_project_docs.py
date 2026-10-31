from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOC_ROOT = PROJECT_ROOT / "docs"
DATA_ROOT = PROJECT_ROOT / "examples" / "data"
PREFIX = "docs_ingest_"


def markdown_to_text(content: str) -> str:
    """Lightweight markdown -> plain text conversion for retrieval."""

    # UTF-8 BOMs are content when files are opened with ``encoding="utf-8"``.
    # Strip only a leading BOM so the first Markdown heading is not silently
    # emitted as plain text and lost from the hierarchy marker stream.
    content = content.removeprefix("\ufeff")
    content = content.replace("\r\n", "\n")
    lines: list[str] = []
    in_code = False
    code_fence_pattern = re.compile(r"^```")
    for raw_line in content.split("\n"):
        line = raw_line.rstrip()
        if code_fence_pattern.match(line.strip()):
            in_code = not in_code
            continue
        if in_code:
            lines.append(line)
            continue
        stripped = line.strip()
        if not stripped:
            lines.append("")
            continue
        if stripped.startswith("#"):
            level = len(raw_line) - len(raw_line.lstrip("#"))
            title = raw_line[level:].strip()
            if title:
                heading_tag = f"[h{level}] {title}"
                lines.append(heading_tag)
            else:
                lines.append("")
            continue
        stripped = re.sub(r"^[*-+]\s+", "- ", stripped)
        stripped = re.sub(r"^>\s?", "", stripped)
        lines.append(stripped)
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def iter_markdown_files(bases: Iterable[Path]) -> list[Path]:
    files: list[Path] = []
    for base in bases:
        files.extend(sorted(base.glob("*.md")))
    return sorted(files)


def target_name(path: Path) -> str:
    stem = re.sub(r"[^a-z0-9]+", "_", path.stem.lower())
    stem = stem.strip("_")
    if not stem:
        stem = "doc"
    return f"{PREFIX}{stem}.txt"


def _is_redirect_placeholder(text: str) -> bool:
    """Detect tiny legacy placeholder docs that redirect to canonical files.

    We skip ingesting these to avoid duplicate shards (e.g., legacy cheat sheet filenames).
    Heuristics: short length and a heading starting with "# This file moved".
    """

    sample = text.strip()
    if not sample:
        return False
    if len(sample) <= 256 and sample.lower().startswith("# this file moved"):
        return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Render project docs into demo corpus text files")
    parser.add_argument("--clean", action="store_true", help="Remove generated files without rewriting them")
    parser.add_argument("--docs", type=Path, nargs="*", default=[DOC_ROOT], help="Doc directories to harvest")
    args = parser.parse_args()

    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    generated = list(DATA_ROOT.glob(f"{PREFIX}*.txt"))
    if args.clean:
        for path in generated:
            path.unlink(missing_ok=True)
        print(f"Removed {len(generated)} generated files")
        return

    for path in generated:
        path.unlink(missing_ok=True)

    doc_files = iter_markdown_files(args.docs)
    if not doc_files:
        print("No markdown files found; nothing written")
        return

    # Optional: try to import the normalizer to clean typographic punctuation.
    try:
        from scripts.normalize_docs_ascii import normalize_text as _normalize_text
    except Exception:
        # Lightweight fallback: only targeted typographic replacements.
        _TYPO_MAP = {
            "\u201C": '"',  # “
            "\u201D": '"',  # ”
            "\u2018": "'",  # ‘
            "\u2019": "'",  # ’
            "\u2014": "-",  # —
            "\u2013": "-",  # –
            "\u2026": "...",  # …
        }

        def _normalize_text(s: str) -> str:
            if not any(c in s for c in _TYPO_MAP):
                return s
            return "".join(_TYPO_MAP.get(c, c) for c in s)

    for doc in doc_files:
        text = doc.read_text(encoding="utf-8")
        # Normalize typographic punctuation before rendering, keeping math as-is.
        text = _normalize_text(text)
        if _is_redirect_placeholder(text):
            print(f"Skipped redirect placeholder: {doc.relative_to(PROJECT_ROOT)}")
            continue
        rendered = markdown_to_text(text)
        target = DATA_ROOT / target_name(doc)
        banner = f"Source: {doc.relative_to(PROJECT_ROOT)}\n\n"
        target.write_text(banner + rendered, encoding="utf-8")
        print(f"Wrote {target.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
