"""Lightweight sparse key index (spec A9)."""

from __future__ import annotations

from bisect import bisect_left
from collections import defaultdict
import re
from typing import Dict, Iterable, List

from fram_core.claims import ClaimType, extract_claims


_ID_SEP_RE = re.compile(r"[\s\-_]+")
_IBAN_RE = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$")
_ISBN10_RE = re.compile(r"^\d{9}[0-9X]$")
_ISBN13_RE = re.compile(r"^\d{13}$")


def _normalize_identifier(raw: str) -> str:
    return _ID_SEP_RE.sub("", raw.strip().upper())


def _valid_isbn10(value: str) -> bool:
    if not _ISBN10_RE.match(value):
        return False
    total = 0
    for idx, ch in enumerate(value):
        digit = 10 if ch == "X" else ord(ch) - ord("0")
        total += (idx + 1) * digit
    return total % 11 == 0


def _valid_isbn13(value: str) -> bool:
    if not _ISBN13_RE.match(value):
        return False
    total = 0
    for idx, ch in enumerate(value[:12]):
        digit = ord(ch) - ord("0")
        total += digit if idx % 2 == 0 else 3 * digit
    check = (10 - (total % 10)) % 10
    return check == (ord(value[-1]) - ord("0"))


def _valid_iban(value: str) -> bool:
    if not _IBAN_RE.match(value):
        return False
    rearranged = value[4:] + value[:4]
    remainder = 0
    for ch in rearranged:
        if "0" <= ch <= "9":
            remainder = (remainder * 10 + (ord(ch) - ord("0"))) % 97
        else:
            converted = ord(ch) - ord("A") + 10
            remainder = (remainder * 100 + converted) % 97
    return remainder == 1


def _normalize_sparse_key(raw: str) -> tuple[str, bool]:
    normalized = _normalize_identifier(raw)
    if not normalized:
        return "", False
    is_isbn_candidate = "-" in raw and len(normalized) in {10, 13}
    if is_isbn_candidate:
        if len(normalized) == 10 and not _valid_isbn10(normalized):
            return "", False
        if len(normalized) == 13 and not _valid_isbn13(normalized):
            return "", False
    if _IBAN_RE.match(normalized) and not _valid_iban(normalized):
        return "", False
    return normalized, True


class SparseKeyIndex:
    """Tiny in-memory index mapping identifier-like claims to document IDs."""

    def __init__(self, postings_cap: int = 256) -> None:
        self._postings_cap = max(1, int(postings_cap))
        self._key_to_docs: Dict[str, List[str]] = defaultdict(list)

    def add(self, doc_id: str, text: str) -> None:
        for key in self._iter_sparse_keys(text, doc_id=doc_id):
            self._add_doc(key, doc_id)

    def build_from(self, corpus: Dict[str, str]) -> None:
        for doc_id, text in corpus.items():
            self.add(doc_id, text)

    def query(self, text: str) -> List[str]:
        hits: List[str] = []
        seen: set[str] = set()
        for key in self._iter_sparse_keys(text, doc_id="query"):
            for doc_id in self._key_to_docs.get(key, []):
                if doc_id in seen:
                    continue
                seen.add(doc_id)
                hits.append(doc_id)
        return hits

    def keys_for_doc(self, doc_id: str) -> List[str]:
        return sorted(key for key, docs in self._key_to_docs.items() if doc_id in docs)

    def _iter_sparse_keys(self, text: str, doc_id: str) -> Iterable[str]:
        for claim in extract_claims(text, doc_id=doc_id, chunk_id=0):
            if claim.type is ClaimType.Identifier:
                key, ok = _normalize_sparse_key(claim.key)
                if ok and key:
                    yield key
            elif claim.type is ClaimType.NumberOrUnit:
                key = claim.key.strip()
                if key:
                    yield key

    def _add_doc(self, key: str, doc_id: str) -> None:
        docs = self._key_to_docs[key]
        pos = bisect_left(docs, doc_id)
        if pos < len(docs) and docs[pos] == doc_id:
            return
        if len(docs) >= self._postings_cap:
            if docs and doc_id >= docs[-1]:
                return
        docs.insert(pos, doc_id)
        if len(docs) > self._postings_cap:
            docs.pop()
