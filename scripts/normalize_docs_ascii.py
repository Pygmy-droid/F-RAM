from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = PROJECT_ROOT / "docs"
BACKUP_DIR = PROJECT_ROOT / "docs_raw_backup"


# Targeted replacements for typographic punctuation only.
_TYPO_MAP: dict[str, str] = {
    "\u201C": '"',  # left double quotation mark “
    "\u201D": '"',  # right double quotation mark ”
    "\u2018": "'",  # left single quotation mark ‘
    "\u2019": "'",  # right single quotation mark ’
    "\u2014": "-",  # em dash —
    "\u2013": "-",  # en dash –
    "\u2026": "...",  # ellipsis …
}


def _repair_common_mojibake(text: str) -> str:
    """Best-effort fix for CP1252-utf8 mojibake where possible.

    Heuristic: if typical mojibake lead bytes are present (Ã, Â, â),
    attempt latin-1 encode → utf-8 decode roundtrip and keep it only
    if it reduces those markers. This preserves non-ASCII math.
    """

    markers = ("Ã", "Â", "â")
    before = sum(text.count(m) for m in markers)
    if before == 0:
        return text
    try:
        candidate = text.encode("latin-1", errors="ignore").decode("utf-8", errors="replace")
    except Exception:
        return text
    after = sum(candidate.count(m) for m in markers)
    return candidate if after < before else text


def normalize_text(text: str) -> str:
    # First, optionally repair common mojibake patterns.
    text = _repair_common_mojibake(text)
    # Then apply targeted punctuation normalization.
    if not any(ch in text for ch in _TYPO_MAP):  # quick path
        return text
    out_chars: list[str] = []
    for ch in text:
        out_chars.append(_TYPO_MAP.get(ch, ch))
    return "".join(out_chars)


def _iter_doc_files(bases: Iterable[Path]) -> list[Path]:
    files: list[Path] = []
    for base in bases:
        files.extend(sorted(base.rglob("*.md")))
        files.extend(sorted(base.rglob("*.json")))
    return files


def _backup_once(src: Path) -> None:
    rel = src.relative_to(DOCS_DIR)
    dst = BACKUP_DIR / rel
    if dst.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def normalize_docs(docs_dir: Path) -> list[tuple[Path, bool]]:
    changed: list[tuple[Path, bool]] = []
    for path in _iter_doc_files([docs_dir]):
        try:
            original = path.read_text(encoding="utf-8")
        except Exception:
            # Skip unreadable files
            continue
        normalized = normalize_text(original)
        if normalized != original:
            _backup_once(path)
            path.write_text(normalized, encoding="utf-8")
            changed.append((path, True))
        else:
            changed.append((path, False))
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize typographic punctuation in docs to ASCII")
    parser.add_argument("--docs", type=Path, default=DOCS_DIR, help="Docs folder (default: ./docs)")
    args = parser.parse_args()

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    results = normalize_docs(args.docs)
    changed = [str(p) for p, did in results if did]
    print(f"Normalized {len(changed)} files (backed up to {BACKUP_DIR}).")
    for p in changed:
        print(p)


if __name__ == "__main__":
    main()

