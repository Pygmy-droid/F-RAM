"""Typed claim extraction aligning with FRAM v2.2 spec §§11.1-11.2."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Any, Dict, Iterable, List, Sequence, Set, Tuple


class ClaimType(str, Enum):
    Entity = "entity"
    NumberOrUnit = "number_or_unit"
    Identifier = "identifier"
    Date = "date"
    TableFact = "table_fact"
    CodeSymbol = "code_symbol"


@dataclass(frozen=True)
class Claim:
    key: str
    type: ClaimType
    buckets: Tuple[str, ...]
    ctx: Dict[str, Any] | None = field(default=None, compare=False)


_CAP_WORD_RE = re.compile(r"\b[A-Z][a-zA-Z]{2,}\b")
_NUM_UNIT_RE = re.compile(r"\b\d+(?:\.\d+)?\s?(?:[a-zA-Z%°]+)?\b")
_IDENTIFIER_RE = re.compile(r"\b[A-Z0-9]{2,}(?:[-_][A-Z0-9]{2,})+\b")
_DATE_RE = re.compile(r"\b(?:\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})\b")


def _default_buckets(doc_id: str, chunk_id: int, layout_id: str | None) -> Tuple[str, ...]:
    layout_token = layout_id if layout_id is not None else f"{doc_id}:{chunk_id}"
    return (f"doc:{doc_id}", f"layout:{layout_token}")


def extract_claims(
    text: str,
    doc_id: str,
    chunk_id: int,
    layout_id: str | None = None,
) -> List[Claim]:
    """Extract typed claims with doc/layout independence buckets."""

    buckets = _default_buckets(doc_id, chunk_id, layout_id)
    claims: List[Claim] = []
    seen: Set[str] = set()
    content = text or ""

    # Dates (ISO or US-style)
    for m in _DATE_RE.finditer(content):
        key = m.group(0)
        if key not in seen:
            claims.append(Claim(key=key, type=ClaimType.Date, buckets=buckets))
            seen.add(key)

    # Identifiers (IDs, hashes)
    for m in _IDENTIFIER_RE.finditer(content):
        key = m.group(0)
        if key not in seen:
            claims.append(Claim(key=key, type=ClaimType.Identifier, buckets=buckets))
            seen.add(key)

    # Numbers with optional units
    for m in _NUM_UNIT_RE.finditer(content):
        key = m.group(0).strip()
        if key and key not in seen:
            claims.append(Claim(key=key, type=ClaimType.NumberOrUnit, buckets=buckets))
            seen.add(key)

    # Capitalized entities
    for m in _CAP_WORD_RE.finditer(content):
        key = m.group(0)
        if key not in seen:
            claims.append(Claim(key=key, type=ClaimType.Entity, buckets=buckets))
            seen.add(key)

    return claims


def extract_simple(text: str) -> List[Claim]:
    """Compatibility helper for legacy call-sites."""

    return extract_claims(text, doc_id="default", chunk_id=0)


def extract_table_claims(
    rows: Sequence[Sequence[str]],
    headers: Sequence[str],
    buckets: Tuple[str, ...] | None = None,
) -> List[Claim]:
    """Harvest table facts with column-header context (spec §14)."""

    claims: List[Claim] = []
    header_list = list(headers)
    if not header_list:
        return claims

    active_buckets = buckets if buckets is not None else ()

    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            header = header_list[c] if c < len(header_list) else f"col_{c}"
            key = f"{header}={value}"
            ctx = {"row": r, "col": c, "col_header": header}
            claims.append(
                Claim(
                    key=key,
                    type=ClaimType.TableFact,
                    buckets=active_buckets,
                    ctx=ctx,
                )
            )
    return claims
