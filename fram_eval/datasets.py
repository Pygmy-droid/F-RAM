"""Small, strict dataset contracts for F-RAM evaluation runs (spec section 15)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping


def _string_tuple(value: Any, *, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, Iterable) or isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a string or a sequence of strings")
    return tuple(str(item) for item in value)


def _answer_value(value: Any) -> str | tuple[str, ...] | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, Iterable) and not isinstance(value, Mapping):
        return tuple(str(item) for item in value)
    raise ValueError("expected_answer must be a string or a sequence of strings")


@dataclass(frozen=True)
class EvaluationCase:
    """One query plus the evidence and output expectations used for scoring."""

    case_id: str
    query: str
    relevant_ids: tuple[str, ...] = ()
    task: str = "general"
    domain: str = "default"
    expected_answer: str | tuple[str, ...] | None = None
    expected_citations: tuple[str, ...] = ()
    expected_route: str | None = None
    as_of: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        case_id = str(self.case_id).strip()
        query = str(self.query).strip()
        if not case_id:
            raise ValueError("case_id must not be empty")
        if not query:
            raise ValueError("query must not be empty")
        object.__setattr__(self, "case_id", case_id)
        object.__setattr__(self, "query", query)
        object.__setattr__(
            self,
            "relevant_ids",
            tuple(str(item) for item in self.relevant_ids),
        )
        object.__setattr__(
            self,
            "expected_citations",
            tuple(str(item) for item in self.expected_citations),
        )
        object.__setattr__(self, "metadata", dict(self.metadata))

    @classmethod
    def from_mapping(
        cls,
        payload: Mapping[str, Any],
        *,
        source: Path | None = None,
        line_number: int | None = None,
    ) -> "EvaluationCase":
        """Parse a JSON-style mapping while preserving unknown fields as metadata."""
        query = str(payload.get("query") or "").strip()
        if not query:
            location = f"{source}:{line_number}" if source and line_number else "record"
            raise ValueError(f"{location}: missing non-empty 'query'")

        default_id = (
            f"{source.stem}:{line_number}"
            if source is not None and line_number is not None
            else "case"
        )
        case_id = str(payload.get("case_id") or payload.get("id") or default_id)
        known = {
            "case_id",
            "id",
            "query",
            "relevant_ids",
            "expected_ids",
            "task",
            "domain",
            "expected_answer",
            "answer",
            "expected_citations",
            "citations",
            "expected_route",
            "as_of",
            "metadata",
        }
        metadata = dict(payload.get("metadata") or {})
        metadata.update({key: value for key, value in payload.items() if key not in known})
        return cls(
            case_id=case_id,
            query=query,
            relevant_ids=_string_tuple(
                payload.get("relevant_ids", payload.get("expected_ids")),
                field_name="relevant_ids",
            ),
            task=str(payload.get("task") or "general"),
            domain=str(payload.get("domain") or "default"),
            expected_answer=_answer_value(
                payload.get("expected_answer", payload.get("answer"))
            ),
            expected_citations=_string_tuple(
                payload.get("expected_citations", payload.get("citations")),
                field_name="expected_citations",
            ),
            expected_route=(
                str(payload["expected_route"])
                if payload.get("expected_route") is not None
                else None
            ),
            as_of=str(payload["as_of"]) if payload.get("as_of") is not None else None,
            metadata=metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a stable JSON-serializable representation."""
        return {
            "case_id": self.case_id,
            "query": self.query,
            "relevant_ids": list(self.relevant_ids),
            "task": self.task,
            "domain": self.domain,
            "expected_answer": (
                list(self.expected_answer)
                if isinstance(self.expected_answer, tuple)
                else self.expected_answer
            ),
            "expected_citations": list(self.expected_citations),
            "expected_route": self.expected_route,
            "as_of": self.as_of,
            "metadata": self.metadata,
        }


def iter_jsonl(path: str | Path) -> Iterator[EvaluationCase]:
    """Yield evaluation cases from JSONL with path-and-line validation errors."""
    dataset_path = Path(path)
    with dataset_path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"{dataset_path}:{line_number}: invalid JSON: {exc.msg}"
                ) from exc
            if not isinstance(payload, Mapping):
                raise ValueError(
                    f"{dataset_path}:{line_number}: each JSONL row must be an object"
                )
            yield EvaluationCase.from_mapping(
                payload,
                source=dataset_path,
                line_number=line_number,
            )


def load_jsonl(path: str | Path) -> list[EvaluationCase]:
    """Load a JSONL evaluation dataset into validated cases."""
    return list(iter_jsonl(path))


def write_jsonl(cases: Iterable[EvaluationCase], path: str | Path) -> Path:
    """Write cases as deterministic UTF-8 JSONL and return the output path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for case in cases:
            handle.write(json.dumps(case.to_dict(), sort_keys=True, ensure_ascii=False))
            handle.write("\n")
    return output_path


def synthetic_layout_cases() -> list[EvaluationCase]:
    """Return tiny deterministic PDF/table/code cases for smoke evaluations."""
    return [
        EvaluationCase(
            case_id="synthetic-table-revenue",
            query="Which region reported revenue of 12 million?",
            relevant_ids=("table:revenue:row-south",),
            task="table_qa",
            domain="synthetic_layout",
            expected_answer="South",
            expected_citations=("table:revenue:row-south",),
            metadata={
                "modality": "table",
                "table": [
                    ["Region", "Revenue (million)"],
                    ["North", "9"],
                    ["South", "12"],
                ],
            },
        ),
        EvaluationCase(
            case_id="synthetic-code-normalizer",
            query="Which function normalizes a query before retrieval?",
            relevant_ids=("code:normalize_query",),
            task="code_qa",
            domain="synthetic_layout",
            expected_answer="normalize_query",
            expected_citations=("code:normalize_query",),
            metadata={
                "modality": "code",
                "code": "def normalize_query(text):\n    return ' '.join(text.lower().split())",
            },
        ),
        EvaluationCase(
            case_id="synthetic-pdf-policy",
            query="What fallback is used when local column confidence is low?",
            relevant_ids=("pdf:layout-policy:page-2",),
            task="pdf_qa",
            domain="synthetic_layout",
            expected_answer="text order",
            expected_citations=("pdf:layout-policy:page-2",),
            metadata={
                "modality": "pdf",
                "pages": [
                    {"page": 1, "text": "Layout evaluation overview."},
                    {
                        "page": 2,
                        "text": "When local confidence is low, fall back to text order.",
                    },
                ],
            },
        ),
    ]


__all__ = [
    "EvaluationCase",
    "iter_jsonl",
    "load_jsonl",
    "synthetic_layout_cases",
    "write_jsonl",
]
