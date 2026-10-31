"""PDF chunking utilities with hierarchical segments (spec §14)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Mapping, Optional
import re

try:  # Optional dependency for real PDF parsing
    import pdfplumber
except Exception:  # pragma: no cover - fallback if library missing
    pdfplumber = None  # type: ignore[assignment]

from sklearn.feature_extraction.text import HashingVectorizer

@dataclass(frozen=True)
class PDFSnippet:
    text: str
    page: int
    region: int
    layout_uncertain: bool = False
    column: Optional[str] = None
    section_path: Optional[str] = None

    @property
    def hierarchy(self) -> Mapping[str, str]:
        hierarchy = {
            "cluster": f"doc:{self.page}",
            "segment": f"page:{self.page}:region:{self.region}",
            "chunk": f"chunk:{self.page}-{self.region}",
        }
        if self.section_path:
            hierarchy["section"] = self.section_path
        return hierarchy


_HEADING_RE = re.compile(r"^(#+)\s+(.*)$")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    lowered = text.strip().lower()
    slug = _SLUG_RE.sub("_", lowered).strip("_")
    return slug or "section"


def chunk_pdf(path: Path) -> List[PDFSnippet]:
    """Return page/region snippets with hierarchy metadata.

    If pdfplumber is available, extract real text regions. Otherwise, fall back
    to a line-based stub that chunks every four lines.
    """

    if pdfplumber is not None:
        try:
            return _chunk_pdf_plumber(path)
        except Exception:
            pass
    return _chunk_pdf_fallback(path)


def to_snippet_dicts(snippets: Iterable[PDFSnippet]) -> List[dict]:
    out: List[dict] = []
    for snippet in snippets:
        payload = {
            "kind": "text",
            "text": snippet.text,
            "hierarchy": snippet.hierarchy,
        }
        if snippet.layout_uncertain:
            payload["layout_uncertain"] = True
        if snippet.column:
            payload["column"] = snippet.column
        out.append(payload)
    return out


def _chunk_pdf_plumber(path: Path) -> List[PDFSnippet]:
    snippets: List[PDFSnippet] = []
    vectorizer = HashingVectorizer(
        lowercase=True,
        token_pattern=r"\b\w+\b",
        n_features=512,
        alternate_sign=False,
        norm=None,
    )
    with pdfplumber.open(path) as pdf:
        for page_index, page in enumerate(pdf.pages):
            words = page.extract_words(use_text_flow=True) or []
            if not words:
                text = page.extract_text() or ""
                if text.strip():
                    snippets.append(
                        PDFSnippet(text=text.strip(), page=page_index, region=0, layout_uncertain=True)
                    )
                continue
            bucket_lines: List[str] = []
            current_top: Optional[float] = None
            region_index = 0
            for word in words:
                top = word.get("top", current_top)
                text = word.get("text", "").strip()
                if not text:
                    continue
                if current_top is None or (top is not None and abs(top - current_top) > 8.0):
                    if bucket_lines:
                        snippets.append(
                            PDFSnippet(
                                text=" ".join(bucket_lines),
                                page=page_index,
                                region=region_index,
                                layout_uncertain=True,
                            )
                        )
                        region_index += 1
                        bucket_lines = []
                current_top = top
                bucket_lines.append(text)
            if bucket_lines:
                snippets.append(
                    PDFSnippet(
                        text=" ".join(bucket_lines),
                        page=page_index,
                        region=region_index,
                        layout_uncertain=True,
                    )
                )
    return snippets


def _chunk_pdf_fallback(path: Path) -> List[PDFSnippet]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    raw_lines = [line.rstrip() for line in text.splitlines()]
    lines = [line.strip() for line in raw_lines if line.strip()]
    snippets: List[PDFSnippet] = []
    lines_per_page = 20
    lines_per_region = 4
    has_columns = any(line.startswith(("L|", "R|")) for line in lines)
    unlabeled = False
    items: List[dict] = []
    section_stack: List[str] = []
    column_sections = {"L": [], "R": []}

    for idx, line in enumerate(lines):
        column = None
        text_line = line
        if line.startswith(("L|", "R|")):
            column = line[0]
            text_line = line[2:].strip()
        elif has_columns:
            unlabeled = True
        if not text_line:
            continue

        heading_match = _HEADING_RE.match(text_line)
        if has_columns and column in column_sections:
            stack = column_sections[column]
        else:
            stack = section_stack
        if heading_match:
            level = len(heading_match.group(1))
            slug = _slugify(heading_match.group(2))
            while len(stack) >= level:
                stack.pop()
            stack.append(slug)
        section_path = "/".join(stack) if stack else None

        items.append(
            {
                "index": idx,
                "column": column,
                "text": text_line,
                "section_path": section_path,
            }
        )

    layout_uncertain = (not has_columns) or unlabeled
    ordered: List[dict] = []
    if has_columns and not unlabeled:
        left = [item for item in items if item["column"] == "L"]
        right = [item for item in items if item["column"] == "R"]
        left.sort(key=lambda item: item["index"])
        right.sort(key=lambda item: item["index"])
        ordered = left + right
    else:
        ordered = sorted(items, key=lambda item: item["index"])

    for out_idx, item in enumerate(ordered):
        page = item["index"] // lines_per_page
        region = (item["index"] // lines_per_region) % max(1, lines_per_page // lines_per_region)
        snippets.append(
            PDFSnippet(
                text=item["text"],
                page=page,
                region=region,
                layout_uncertain=layout_uncertain,
                column=item["column"],
                section_path=item["section_path"],
            )
        )
    return snippets
